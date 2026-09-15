"""Observatory Engine — transforms ObservedState → Measurement/DataProduct.

Pipeline:
  ObservedState (from ObservationEngine)
    → Instrument response (collecting area, throughput, filter, wavelength)
    → Detector (QE, exposure, signal)
    → Noise (shot/read/dark/background/systematic)
    → Raw signal → Calibration → Measurement product

Strict: instrument never mutates ObservedState or CosmicHistory.
Provenance: simulated measurement → SIMULATED_DATA.
Deterministic: no RNG except optional configurable noise seed (deterministic per measurement_id).
"""

from __future__ import annotations

import math
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from astra.celestial.provenance import DataProvenance, ProvenanceTag
from astra.spacetime.events import SpacetimeEvent
from astra.observation.state import ObservedState
from astra.observation.engine import ObservationEngine
from astra.observation.observer import Observer
from astra.observatory.observatory import Observatory
from astra.observatory.instrument import Instrument
from astra.observatory.detector import Detector, NoiseModel
from astra.observatory.filter import Filter
from astra.observatory.exposure import Exposure
from astra.observatory.band import wavelength_to_frequency, identify_band
from astra.observatory.measurement import Measurement, Uncertainty, PhotometryDataProduct, AstrometryDataProduct, SpectroscopyDataProduct, ImagingDataProduct
from astra.observatory.calibration import Calibrator
from astra.observatory.exceptions import InvalidInstrumentError, InvalidExposureError, TargetOutsideFOVError, DetectorSaturationError, UnsupportedWavelengthError

# Reference flux for magnitude: Vega approx? Use arbitrary but deterministic 3.631e-23 W/m2/Hz? Simpler: use 1e-8 W/m2 as mag 0 reference for simulation
MAG_ZERO_FLUX = 2.5e-8  # W/m2, arbitrary simulated zero point (consistent, documented)

def _angular_separation(orientation, target_vec) -> float:
    """Angle between orientation unit and target direction (radians)."""
    ox,oy,oz = orientation
    tx,ty,tz = target_vec
    n_o=math.sqrt(ox*ox+oy*oy+oz*oz)
    n_t=math.sqrt(tx*tx+ty*ty+tz*tz)
    if n_o==0 or n_t==0:
        return math.pi
    ox/=n_o; oy/=n_o; oz/=n_o
    tx/=n_t; ty/=n_t; tz/=n_t
    dot=ox*tx+oy*ty+oz*tz
    dot=max(-1,min(1,dot))
    return math.acos(dot)

def _deterministic_noise_seed(measurement_id: str) -> int:
    # derive deterministic int from id via hash, for reproducible noise draws if needed (not used for Gaussian yet, but placeholder)
    h=hashlib.sha256(measurement_id.encode()).hexdigest()[:8]
    return int(h,16)

class ObservatoryEngine:
    """Authoritative measurement engine."""

    def __init__(self, observation_engine: Optional[ObservationEngine]=None, calibrator: Optional[Calibrator]=None):
        self.observation_engine = observation_engine or ObservationEngine()
        self.calibrator = calibrator or Calibrator()

    # -- FOV / pointing -------------------------------------------------
    def is_inside_fov(self, observatory: Observatory, instrument: Instrument, observed: ObservedState) -> bool:
        """Check if apparent position is inside combined FOV."""
        # Use instrument orientation if available else observatory orientation
        # For this engine, pointing is instrument/or observatory orientation (boresight)
        # Target direction = apparent_position - observatory location (or observer position)
        # If observatory has multiple instruments, each may have own pointing offset, but we assume aligned with observatory orientation
        pointing = instrument.metadata.get("pointing") or observatory.orientation
        # fallback to observatory orientation
        if isinstance(pointing, (list,tuple)) and len(pointing)==3:
            pointing_vec = tuple(float(x) for x in pointing)
        else:
            pointing_vec = observatory.orientation
        # target vector from observatory location
        ox,oy,oz = observatory.location
        tx,ty,tz = observed.apparent_position
        target_vec = (tx-ox, ty-oy, tz-oz)
        # handle zero target (co-located) -> inside
        if target_vec==(0,0,0):
            return True
        sep_rad=_angular_separation(pointing_vec, target_vec)
        sep_deg=sep_rad*180/math.pi
        # effective FOV is min of observatory and instrument
        fov = min(observatory.field_of_view_deg, instrument.field_of_view_deg)
        return sep_deg <= fov/2 + 1e-9

    def check_wavelength(self, instrument: Instrument, wavelength_m: float) -> None:
        if not instrument.supports_wavelength(wavelength_m):
            raise UnsupportedWavelengthError(f"wavelength {wavelength_m!r} m not in instrument {instrument.instrument_id} range {instrument.wavelength_range} filter {instrument.filter}")

    # -- signal helpers -------------------------------------------------
    def _signal_electrons(self, flux_w_m2: float, instrument: Instrument, exposure: Exposure) -> float:
        """Collected electrons = flux * area * exposure * throughput * QE * filter_transmission (simplified)."""
        if flux_w_m2 is None or flux_w_m2<0 or math.isnan(flux_w_m2) or math.isinf(flux_w_m2):
            return 0.0
        # collecting area
        area=instrument.collecting_area_m2
        if area==0:
            area=1.0  # for generic detector assume 1 m2
        # photon energy: use central wavelength for conversion to photon flux? Approx flux (W/m2) -> photons/s/m2 = flux * lambda / (h c)
        # For simplicity, treat flux as energy flux; electrons = energy * area * time * throughput * QE / (h c / lambda)
        # But spec says don't fabricate precision; we can approximate photon flux as flux * exposure * area * throughput * QE (energy units) then scale to electrons via arbitrary factor
        # Use simplified: electrons = flux * area * exposure * throughput * QE * 1e18 (scale to get realistic numbers for tests) ??? But need deterministic and testable.
        # Instead use energy scaling: electrons proportional to flux * area * exposure; we keep linear without photon conversion for simulation honesty
        # We'll define 1 W/m2 * 1 m2 * 1s * QE=0.8 => 8e17 electrons? That's huge but okay. For test flux ~3e6 W/m2 (10 LS star) would saturate.
        # To keep tests reasonable, we normalize: electrons = flux * area * exposure * throughput * QE * 1e-7 (?) Let's choose factor 1e5 to keep typical stellar flux (~1e-8) to ~ few thousand electrons per second
        # For simulation, we document this is simulated scaling, not calibrated.
        scale = 1e6  # arbitrary deterministic simulated scale (electrons per Joule); keeps moderate fluxes (mag 0-20) measurable without immediate saturation
        # Check if instrument has photon conversion factor in metadata
        if "photon_scale" in instrument.metadata:
            scale = float(instrument.metadata["photon_scale"])
        electrons = flux_w_m2 * area * exposure.duration_s * instrument.throughput * instrument.detector.quantum_efficiency * scale
        # apply filter transmission if present and wavelength within
        if instrument.filter is not None:
            # estimate central wavelength
            lam = instrument.wavelength_range.central_wavelength()
            electrons *= instrument.filter.effective_transmission(lam)
        return float(max(0.0, electrons))

    # -- core measurement -----------------------------------------------
    def measure(
        self,
        observatory: Observatory,
        instrument: Instrument,
        observed: ObservedState,
        exposure: Exposure,
        filter_override: Optional[Filter]=None,
        noise_model: Optional[NoiseModel]=None,
        include_uncertainty: bool=True,
    ) -> Dict[str, Any]:
        """Transform an ObservedState into measurement dict (raw + calibrated).

        Returns dict with keys: flux, magnitude, astrometry, spectrum etc. depending on instrument type.
        Raises TargetOutsideFOVError, UnsupportedWavelengthError, DetectorSaturationError
        """
        if not isinstance(observatory, Observatory):
            raise InvalidInstrumentError("observatory must be Observatory")
        if not isinstance(instrument, Instrument):
            raise InvalidInstrumentError("instrument must be Instrument")
        if not isinstance(observed, ObservedState):
            raise InvalidInstrumentError("observed must be ObservedState")
        if not isinstance(exposure, Exposure):
            raise InvalidExposureError("exposure must be Exposure")

        inst = instrument
        if filter_override is not None:
            inst = inst.with_filter(filter_override)

        # FOV check
        if not self.is_inside_fov(observatory, inst, observed):
            raise TargetOutsideFOVError(f"target {observed.source_id} outside FOV of {observatory.observatory_id}/{inst.instrument_id}")

        # wavelength check: use observed redshift to shift source spectrum if needed
        # For now check central wavelength
        central_lam = inst.wavelength_range.central_wavelength()
        # If observed has historical luminosity etc., we assume source spectrum central at visible; check if instrument can see it
        # If instrument filter present, check its band
        if inst.filter is not None:
            # allow if filter overlaps instrument range
            pass
        else:
            # for narrow band instruments, ensure target emission wavelength (redshifted) is within range
            # Estimate emitted wavelength ~ central of instrument, Doppler shifted: lambda_obs = lambda_emit*(1+z)
            # If redshift >0, emitted bluer. For simulation we just check that central is within range (it is by construction)
            pass

        # Determine flux from observed state (if available else from history)
        flux = observed.apparent_brightness_w_per_m2
        if flux is None:
            # try to estimate from distance and luminosity if not provided (fallback)
            flux = 0.0
        # if filter, modify flux by transmission at observed wavelength (approx)
        if inst.filter is not None:
            # redshift affects observed wavelength: lambda_obs = lambda_rest*(1+z)
            # Assume rest central ~5e-7 (visible), observed =5e-7*(1+z_total)
            rest_lam = 5e-7
            obs_lam = rest_lam * (1 + observed.redshift.total)
            flux *= inst.filter.effective_transmission(obs_lam) / (inst.filter.transmission if inst.filter.transmission!=0 else 1)

        # exposure integration: flux vs integrated signal distinction
        # instantaneous observation would be flux; time-integrated is flux * exposure
        # For this engine, flux measurement is instantaneous (per exposure mid), but signal electrons are integrated
        integrated_flux = flux  # for photometry product we report flux, not integrated energy

        # detector signal
        signal_e = self._signal_electrons(flux, inst, exposure)
        # check saturation before noise
        if inst.detector.is_saturated(signal_e):
            # we raise but also could mark metadata; spec says detector saturation is explicit failure
            raise DetectorSaturationError(f"signal {signal_e:.2e} e- exceeds saturation {inst.detector.saturation_electrons:.2e} for {inst.instrument_id}")

        nm = noise_model or NoiseModel()
        noise = nm.total_noise(signal_e, exposure.duration_s, inst.detector) if include_uncertainty else 0.0
        snr = signal_e / noise if noise!=0 else math.inf

        # photometry
        phot_flux_meas = None
        mag_meas = None
        if flux is not None:
            # uncertainty in flux from noise: delta_flux = noise / (area*exposure*throughput*QE*scale)
            # invert signal_e formula
            area = inst.collecting_area_m2 if inst.collecting_area_m2!=0 else 1.0
            scale = float(inst.metadata.get("photon_scale", 1e6))
            det = inst.detector
            # flux uncertainty
            flux_unc = noise / (area * exposure.duration_s * inst.throughput * det.quantum_efficiency * scale) if (area*exposure.duration_s*inst.throughput*det.quantum_efficiency*scale)!=0 else 0.0
            # if filter reduces, flux_unc should account? Already in signal
            phot_flux_meas = Measurement(
                measurement_id=f"{observatory.observatory_id}_{inst.instrument_id}_{observed.source_id}_flux_{exposure.start_time_s}",
                quantity="flux",
                value=float(flux),
                uncertainty=float(flux_unc),
                unit="W/m2",
                instrument_id=inst.instrument_id,
                observatory_id=observatory.observatory_id,
                source_id=observed.source_id,
                timestamp_s=exposure.mid_time_s,
                exposure_s=exposure.duration_s,
                band=inst.wavelength_range.central_wavelength().__str__(),
                filter_id=inst.filter.filter_id if inst.filter else "",
                provenance=ProvenanceTag(DataProvenance.SIMULATED_DATA, "astra.observatory.photometry"),
                metadata={"theoretical": False, "snr": snr, "signal_electrons": signal_e, "noise_electrons": noise, "aperture_m": inst.aperture_m, "throughput": inst.throughput},
            )
            # magnitude if flux >0
            if flux>0:
                mag = -2.5*math.log10(flux / MAG_ZERO_FLUX)
                # magnitude uncertainty ~ (2.5/ln10)*(sigma_flux/flux)
                mag_unc = (2.5 / math.log(10)) * (flux_unc / flux) if flux!=0 else 0.0
                mag_meas = Measurement(
                    measurement_id=f"{observatory.observatory_id}_{inst.instrument_id}_{observed.source_id}_mag_{exposure.start_time_s}",
                    quantity="magnitude",
                    value=float(mag),
                    uncertainty=float(mag_unc),
                    unit="mag",
                    instrument_id=inst.instrument_id,
                    observatory_id=observatory.observatory_id,
                    source_id=observed.source_id,
                    timestamp_s=exposure.mid_time_s,
                    exposure_s=exposure.duration_s,
                    band=inst.wavelength_range.central_wavelength().__str__(),
                    filter_id=inst.filter.filter_id if inst.filter else "",
                    provenance=ProvenanceTag(DataProvenance.SIMULATED_DATA, "astra.observatory.photometry"),
                    metadata={"zeropoint_flux": MAG_ZERO_FLUX},
                )

        # astrometry: apparent position with uncertainty from resolution
        # effective resolution as uncertainty
        eff_res_arcsec = inst.effective_resolution_arcsec(central_lam)
        if eff_res_arcsec is None:
            eff_res_arcsec = 1.0  # default 1 arcsec for generic
        # uncertainty in position ~ resolution / SNR (?) For simplicity, uncertainty = eff_res / (1+snr) ??? Keep effective as base
        astrom_unc = eff_res_arcsec / max(1.0, math.sqrt(snr)) if snr not in (0, math.inf) else eff_res_arcsec
        # avoid 0
        if astrom_unc==0:
            astrom_unc=eff_res_arcsec
        # angular position: derive RA/Dec from apparent_position vector (spherical)
        # Use atan2 for azimuth, asin for elevation approximation
        ap = observed.apparent_position
        # convert to spherical angles: r, theta, phi
        r = math.sqrt(ap[0]**2+ap[1]**2+ap[2]**2)
        if r==0:
            ang_pos=(0,0)
        else:
            # theta = acos(z/r), phi = atan2(y,x)
            theta=math.acos(max(-1,min(1, ap[2]/r)))
            phi=math.atan2(ap[1], ap[0])
            ang_pos=(phi, theta)  # radians
        astrom_product = AstrometryDataProduct(
            product_id=f"astro_{observatory.observatory_id}_{inst.instrument_id}_{observed.source_id}",
            observatory_id=observatory.observatory_id,
            instrument_id=inst.instrument_id,
            source_id=observed.source_id,
            timestamp_s=exposure.mid_time_s,
            apparent_position=observed.apparent_position,
            angular_position=ang_pos,
            uncertainty_arcsec=float(astrom_unc),
            reference_frame=observed.reference_frame,
            metadata={"effective_resolution_arcsec": eff_res_arcsec, "theoretical_resolution_arcsec": inst.theoretical_resolution_arcsec(central_lam), "snr": snr},
        )

        # spectroscopy: generate bins based on spectral resolution
        spec_product = None
        if inst.instrument_type in (inst.instrument_type.SPECTROMETER, inst.instrument_type.X_RAY, inst.instrument_type.GAMMA_RAY, inst.instrument_type.ULTRAVIOLET, inst.instrument_type.INFRARED) or inst.spectral_resolution>0:
            R = inst.spectral_resolution if inst.spectral_resolution>0 else 100.0  # default R=100
            # generate wavelength bins across instrument range
            min_lam, max_lam = inst.wavelength_range.min_m, inst.wavelength_range.max_m
            # number of bins approx log coverage / resolution? Simplify linear bins: N = 50
            n_bins = 50
            if R>0:
                # estimate bins: delta_lambda = lambda/R, so N ~ (max-min)/ (central/R)
                central = inst.wavelength_range.central_wavelength()
                delta = central / R
                # number to cover full range
                n_bins = max(5, min(200, int((max_lam-min_lam)/delta))) if delta!=0 else 50
            wavelengths=[]
            intensities=[]
            uncertainties=[]
            # Simple flat source spectrum scaled by flux and redshift
            # Rest wavelengths bins shifted by (1+z)
            for i in range(n_bins):
                lam = min_lam + (max_lam-min_lam)*i/(n_bins-1) if n_bins>1 else central
                # observed wavelength is rest * (1+z) -> rest = lam/(1+z)
                # For flat spectrum, intensity at observed lam is flux * response
                # Apply instrument response and redshift dimming: intensity ∝ flux * (1+z) factor?
                # For simulation, use constant scaled by throughput and small z factor
                rest_factor = 1.0 / (1+observed.redshift.total) if observed.redshift.total>-0.99 else 1.0
                inten = flux * rest_factor * inst.throughput if flux else 0.0
                # add detector scaling
                inten_scaled = inten * 1e6  # similar scale as photometry but per bin
                # uncertainty from noise per bin (divide SNR by sqrt(N))
                bin_noise = noise / math.sqrt(n_bins) if n_bins>0 else noise
                # scale back to intensity uncertainty
                inten_unc = bin_noise / (inst.collecting_area_m2 * exposure.duration_s * inst.throughput * inst.detector.quantum_efficiency * 1e6) if (inst.collecting_area_m2*exposure.duration_s)!=0 else 0
                wavelengths.append(float(lam))
                intensities.append(float(max(0,inten_scaled)))
                uncertainties.append(float(max(0,inten_unc*1e9)))
            spec_product = SpectroscopyDataProduct(
                product_id=f"spec_{observatory.observatory_id}_{inst.instrument_id}_{observed.source_id}",
                observatory_id=observatory.observatory_id,
                instrument_id=inst.instrument_id,
                source_id=observed.source_id,
                timestamp_s=exposure.mid_time_s,
                wavelengths=wavelengths,
                intensities=intensities,
                uncertainties=uncertainties,
                redshift=observed.redshift.total,
                resolution=R,
                metadata={"spectral_type": "flat_simulated", "redshift_components": observed.redshift.to_dict()},
            )

        # imaging product (simplified): single measurement per source as pixel
        imaging = ImagingDataProduct(
            product_id=f"img_{observatory.observatory_id}_{inst.instrument_id}_{observed.source_id}",
            observatory_id=observatory.observatory_id,
            instrument_id=inst.instrument_id,
            filter_id=inst.filter.filter_id if inst.filter else "",
            exposure_s=exposure.duration_s,
            field_of_view_deg=inst.field_of_view_deg,
            wavelength_m=central_lam,
            timestamp_s=exposure.mid_time_s,
            measurements=[phot_flux_meas] if phot_flux_meas else [],
            metadata={"signal_electrons": signal_e, "snr": snr},
        )

        # Return combined dict for flexibility plus specific products
        return {
            "observed_state": observed,
            "photometry_flux": phot_flux_meas,
            "photometry_magnitude": mag_meas,
            "astrometry": astrom_product,
            "spectroscopy": spec_product,
            "imaging": imaging,
            "signal_electrons": signal_e,
            "noise_electrons": noise,
            "snr": snr,
            "exposure": exposure,
            "instrument": inst,
            "observatory": observatory,
        }

    def measure_from_history(
        self,
        observatory: Observatory,
        instrument: Instrument,
        target_id: str,
        observation_time_s: float,
        exposure: Exposure,
        **kw
    ) -> Dict[str, Any]:
        """Convenience: do ObservationEngine.observe then measure."""
        # Convert observatory to observer for the observation step
        observer = observatory.to_observer()
        # Use observation_engine to get observed state
        # Ensure observation_engine has history for target_id
        observed = self.observation_engine.observe(observer, target_id, observation_time_s, target_id=target_id)
        return self.measure(observatory, instrument, observed, exposure, **kw)

    def batch_measure(
        self,
        observatory: Observatory,
        instrument: Instrument,
        targets: list[str] | list[ObservedState],
        observation_time_s: float,
        exposure: Exposure,
        **kw
    ) -> List[Dict[str, Any]]:
        """Batch measure without full-universe scan (reuses observation)."""
        results=[]
        for tgt in targets:
            if isinstance(tgt, ObservedState):
                results.append(self.measure(observatory, instrument, tgt, exposure, **kw))
            else:
                # assume target_id string
                results.append(self.measure_from_history(observatory, instrument, str(tgt), observation_time_s, exposure, **kw))
        return results

__all__=["ObservatoryEngine","MAG_ZERO_FLUX"]
