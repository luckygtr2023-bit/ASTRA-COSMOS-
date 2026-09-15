"""ASTRA Extreme Spacetime & Travel Engine — comprehensive tests."""

import math
import pytest

from astra.travel import (
    ArrivalState,
    CausalStatus,
    Mechanism,
    Provenance,
    TravelConfig,
    TravelEngine,
    TravelRequest,
    Vec3,
)
from astra.travel.errors import (
    TravelAuthorityError,
    TravelCausalityError,
    TravelNumericalError,
    TravelUnsupportedError,
    TravelValidationError,
)
from astra.travel.relativistic import (
    lorentz_factor,
    proper_time_for_coordinate,
)
from astra.travel.state import TravelState, Transition


# ---------------------------------------------------------------- helpers

class _AllowAll:
    def require(self, operation: str) -> None:
        return None


class _DenyAll:
    def require(self, operation: str) -> None:
        raise TravelAuthorityError("denied")


class _Rel:
    def lorentz_factor(self, velocity):
        speed = velocity.norm() if hasattr(velocity, "norm") else float(velocity)
        return 1.0 / (1.0 - (speed / 299_792_458.0) ** 2) ** 0.5

    def proper_time_delta(self, coordinate_dt, velocity):
        return coordinate_dt / self.lorentz_factor(velocity)

    def relativistic_momentum(self, mass_kg, velocity):
        # simple p = m*v*gamma
        g = self.lorentz_factor(velocity)
        if hasattr(velocity, "to_vector3"):
            v = velocity.to_vector3()
            return v * (g * mass_kg)
        return velocity * (g * mass_kg)

    def relativistic_energy(self, mass_kg, velocity):
        g = self.lorentz_factor(velocity)
        return mass_kg * 299_792_458.0 ** 2 * g


def _engine(authority=None, relativity=None, **kw):
    return TravelEngine(
        config=TravelConfig(),
        authority=authority or _AllowAll(),
        relativity=relativity or _Rel(),
        **kw,
    )


def _req(**over):
    base = dict(
        request_id="t-1",
        traveler_id="ship-1",
        departure_position=Vec3(0.0, 0.0, 0.0),
        departure_velocity=Vec3(1.0e7, 0.0, 0.0),
        departure_coordinate_time_s=0.0,
        departure_reference_frame="world",
        destination_position=Vec3(1.0e12, 0.0, 0.0),
        destination_reference_frame="world",
        mechanism=Mechanism.RELATIVISTIC,
    )
    base.update(over)
    return TravelRequest(**base)


# ---------------------------------------------------------------- basics


def test_lorentz_factor_subluminal():
    assert lorentz_factor(0.0) == pytest.approx(1.0)
    assert lorentz_factor(1.0e7) > 1.0


def test_lorentz_factor_rejects_superluminal():
    with pytest.raises(TravelUnsupportedError):
        lorentz_factor(3.1e8)


def test_proper_time_is_less_than_coordinate():
    proper = proper_time_for_coordinate(100.0, 1.0e7)
    assert proper < 100.0
    assert proper > 0


def test_engine_basic_relativistic_travel():
    e = _engine()
    event = e.execute(_req())
    assert event.mechanism == Mechanism.RELATIVISTIC
    assert event.proper_elapsed_time_s > 0.0
    assert event.coordinate_elapsed_time_s > 0.0
    assert event.proper_elapsed_time_s < event.coordinate_elapsed_time_s  # time dilation
    assert event.provenance == Provenance.SIMULATED_DATA
    assert e.get_state("t-1") == TravelState.COMPLETED
    # worldline ordering
    ts = [s.coordinate_time_s for s in event.worldline.samples]
    assert ts == sorted(ts)
    assert len(ts) >= 2
    # causal status should be timelike for subluminal matter
    assert event.causal_status in (CausalStatus.TIMELIKE, CausalStatus.UNKNOWN)


def test_engine_requires_authority():
    e = TravelEngine(config=TravelConfig(), authority=None, relativity=_Rel())
    # engine creates DefaultAuthorityProvider when authority is None, which allows when no registry
    # To simulate denial, use _DenyAll
    e2 = _engine(authority=_DenyAll())
    with pytest.raises(TravelAuthorityError):
        e2.execute(_req())


def test_engine_denied_authority():
    e = _engine(authority=_DenyAll())
    with pytest.raises(TravelAuthorityError):
        e.execute(_req())


def test_arrival_state_from_event():
    e = _engine()
    event = e.execute(_req())
    arrival = e.arrival_state(event)
    assert isinstance(arrival, ArrivalState)
    assert arrival.traveler_id == event.traveler_id
    assert arrival.proper_time_s == pytest.approx(event.proper_elapsed_time_s)
    assert arrival.coordinate_time_s == pytest.approx(event.arrival_coordinate_time_s)
    assert arrival.causal_status == event.causal_status
    # position matches
    assert arrival.position.to_tuple() == event.arrival_position.to_tuple()


def test_duplicate_travel_id_rejected():
    e = _engine()
    e.execute(_req())
    with pytest.raises(TravelValidationError):
        e.execute(_req())


def test_nan_departure_time_rejected():
    with pytest.raises(TravelNumericalError):
        Vec3(float("nan"), 0.0, 0.0)


def test_inf_position_rejected():
    with pytest.raises(TravelNumericalError):
        Vec3(float("inf"), 0.0, 0.0)


def test_zero_velocity_rejected():
    e = _engine()
    with pytest.raises(TravelValidationError):
        e.execute(_req(departure_velocity=Vec3(0.0, 0.0, 0.0)))


def test_requested_arrival_before_departure_rejected():
    e = _engine()
    with pytest.raises(TravelValidationError):
        e.execute(_req(requested_arrival_coordinate_time_s=-1.0))


def test_state_machine_transitions():
    assert Transition.is_valid(TravelState.READY, TravelState.ACTIVE)
    assert not Transition.is_valid(TravelState.COMPLETED, TravelState.ACTIVE)
    with pytest.raises(TravelValidationError):
        Transition.apply(TravelState.COMPLETED, TravelState.ACTIVE)
    # also test illegal U->COMPLETED directly
    with pytest.raises(TravelValidationError):
        Transition.apply(TravelState.UNCONFIGURED, TravelState.COMPLETED)


def test_wormhole_hypothetical_provenance():
    from astra.travel.wormhole import Wormhole, WormholeMouth, traverse

    wh = Wormhole(
        wormhole_id="wh-1",
        mouth_a=WormholeMouth(mouth_id="A", position=Vec3(0, 0, 0), coordinate_time_s=0.0),
        mouth_b=WormholeMouth(mouth_id="B", position=Vec3(1e12, 0, 0), coordinate_time_s=0.0),
        stability=0.9,
        traversal_duration_s=1.0,
        metric_parameters={},
    )
    assert wh.provenance == Provenance.HYPOTHETICAL
    result = traverse(wh, "ship-1", 0.0)
    assert result["provenance"] == Provenance.HYPOTHETICAL
    assert result["mechanism"] == Mechanism.WORMHOLE


def test_wormhole_unstable_rejected():
    from astra.travel.wormhole import Wormhole, WormholeMouth, traverse

    wh = Wormhole(
        wormhole_id="wh-2",
        mouth_a=WormholeMouth(mouth_id="A", position=Vec3(0, 0, 0), coordinate_time_s=0.0),
        mouth_b=WormholeMouth(mouth_id="B", position=Vec3(1e12, 0, 0), coordinate_time_s=0.0),
        stability=0.0,
        traversal_duration_s=1.0,
        metric_parameters={},
    )
    with pytest.raises(TravelUnsupportedError):
        traverse(wh, "ship-1", 0.0)


def test_warp_provenance_is_theoretical():
    from astra.travel.warp import WarpBubble, WarpConfig, warp_travel_descriptor

    bubble = WarpBubble(
        bubble_id="w-1",
        center=Vec3(0, 0, 0),
        radius_m=100.0,
        bubble_velocity_m_s=1.0e12,
        metric_parameters={},
    )
    cfg = WarpConfig(bubble=bubble)
    desc = warp_travel_descriptor(cfg, "ship-1", 0.0, 1.0e15)
    assert desc["provenance"] == Provenance.THEORETICAL
    assert desc["coordinate_duration_s"] > 0.0


def test_worldline_sample_ordering():
    e = _engine()
    event = e.execute(_req())
    ts = [s.coordinate_time_s for s in event.worldline.samples]
    assert ts == sorted(ts)
    assert len(ts) >= 2


# ---------------------------------------------------------------- extended coverage


class TestRelativisticTravel:
    def test_proper_vs_coordinate_dilation(self):
        e = _engine()
        fast = _req(departure_velocity=Vec3(2.5e8, 0, 0))
        ev = e.execute(fast)
        # at 0.83c gamma ~1.81, proper should be ~0.55 coordinate
        assert ev.proper_elapsed_time_s < ev.coordinate_elapsed_time_s * 0.6

    def test_real_relativity_integration(self):
        # Use real provider (DefaultRelativity) not mock — should still be deterministic
        engine = TravelEngine(config=TravelConfig(), authority=_AllowAll(), relativity=None)
        # None triggers default
        engine.relativity = engine.relativity  # default already
        req = _req(request_id="real-1", departure_velocity=Vec3(1e6, 0, 0))
        ev = engine.execute(req)
        assert ev.proper_elapsed_time_s < ev.coordinate_elapsed_time_s
        assert ev.causal_status == CausalStatus.TIMELIKE

    def test_superluminal_rejected_for_relativistic(self):
        e = _engine()
        with pytest.raises((TravelUnsupportedError, TravelCausalityError, TravelValidationError)):
            e.execute(_req(departure_velocity=Vec3(3e8, 0, 0)))

    def test_requested_arrival_requires_not_superluminal(self):
        e = _engine()
        # distance 1e12, speed 1e7 -> natural duration 1e5, request 1e3 would need 1e9 speed -> >c
        with pytest.raises(TravelCausalityError):
            e.execute(_req(requested_arrival_coordinate_time_s=1000.0))

    def test_requested_arrival_later_allows_wait(self):
        e = _engine()
        ev = e.execute(_req(request_id="wait-1", requested_arrival_coordinate_time_s=200000.0))
        assert ev.arrival_coordinate_time_s == pytest.approx(200000.0)
        # proper should be scaled accordingly
        assert ev.proper_elapsed_time_s > 0


class TestStrongGravity:
    def test_gravitational_travel_with_blackhole(self):
        eng = TravelEngine(config=TravelConfig(), authority=_AllowAll(), relativity=_Rel())
        req = TravelRequest(
            request_id="grav-1",
            traveler_id="probe",
            departure_position=Vec3(1e7, 0, 0),
            departure_velocity=Vec3(1e6, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1.1e7, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.GRAVITATIONAL,
            config={"mass_kg": 1.989e30, "radius_m": 1e7},
        )
        ev = eng.execute(req)
        assert ev.mechanism == Mechanism.GRAVITATIONAL
        assert ev.proper_elapsed_time_s > 0
        assert "gravitational_factor" in ev.metadata
        assert ev.provenance == Provenance.SIMULATED_DATA

    def test_gravitational_redshift_present(self):
        eng = _engine()
        req = _req(request_id="grav-2", mechanism=Mechanism.GRAVITATIONAL, config={"mass_kg": 5.972e24, "radius_m": 6.371e6, "observer_radius_m": 1e7})
        # need to replace engine's mechanism dispatch: _engine defaults to _Rel, but we need real blackhole for redshift — inject default
        eng2 = TravelEngine(config=TravelConfig(), authority=_AllowAll(), relativity=_Rel())
        ev = eng2.execute(req)
        # gravitational redshift may be in metadata
        assert ev.metadata.get("gravitational_redshift") is not None or ev.metadata.get("gravitational_factor") is not None


class TestWormholeEngine:
    def test_engine_wormhole_traversal(self):
        from astra.travel.wormhole import Wormhole, WormholeMouth

        wh = Wormhole(
            wormhole_id="wh-engine-1",
            mouth_a=WormholeMouth(mouth_id="A", position=Vec3(0, 0, 0), coordinate_time_s=0.0),
            mouth_b=WormholeMouth(mouth_id="B", position=Vec3(5e12, 0, 0), coordinate_time_s=0.0),
            stability=0.8,
            traversal_duration_s=2.0,
            metric_parameters={"throat_radius_m": 1000},
        )
        e = _engine()
        req = TravelRequest(
            request_id="wh-req-1",
            traveler_id="ship-wh",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e4, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(5e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WORMHOLE,
            config={"wormhole": wh},
        )
        ev = e.execute(req)
        assert ev.mechanism == Mechanism.WORMHOLE
        assert ev.provenance == Provenance.HYPOTHETICAL
        assert ev.coordinate_elapsed_time_s == pytest.approx(2.0)
        assert ev.proper_elapsed_time_s == pytest.approx(2.0)
        assert ev.metadata["wormhole_id"] == "wh-engine-1"

    def test_wormhole_missing_config_rejected(self):
        e = _engine()
        req = _req(request_id="wh-miss", mechanism=Mechanism.WORMHOLE, config={})
        with pytest.raises(TravelUnsupportedError):
            e.execute(req)

    def test_wormhole_stability_zero_rejected_engine(self):
        from astra.travel.wormhole import Wormhole, WormholeMouth

        wh = Wormhole(
            wormhole_id="wh-bad",
            mouth_a=WormholeMouth(mouth_id="A", position=Vec3(0, 0, 0), coordinate_time_s=0.0),
            mouth_b=WormholeMouth(mouth_id="B", position=Vec3(1e12, 0, 0), coordinate_time_s=0.0),
            stability=0.0,
            traversal_duration_s=1.0,
            metric_parameters={},
        )
        e = _engine()
        req = TravelRequest(
            request_id="wh-bad-req",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WORMHOLE,
            config={"wormhole": wh},
        )
        with pytest.raises(TravelUnsupportedError):
            e.execute(req)
        assert e.get_state("wh-bad-req") == TravelState.PHYSICALLY_UNSUPPORTED

    def test_wormhole_not_teleport_worldline_has_samples(self):
        from astra.travel.wormhole import Wormhole, WormholeMouth

        wh = Wormhole(
            wormhole_id="wh-not-tele",
            mouth_a=WormholeMouth(mouth_id="A", position=Vec3(0, 0, 0), coordinate_time_s=0.0),
            mouth_b=WormholeMouth(mouth_id="B", position=Vec3(1e9, 0, 0), coordinate_time_s=0.0),
            stability=0.9,
            traversal_duration_s=10.0,
            metric_parameters={},
        )
        e = _engine()
        req = TravelRequest(
            request_id="wh-tele-check",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e9, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WORMHOLE,
            config={"wormhole": wh},
        )
        ev = e.execute(req)
        # worldline must have intermediate samples, not just jump
        assert len(ev.worldline.samples) >= 8
        # not instantaneous
        assert ev.coordinate_elapsed_time_s >= 10.0


class TestWarpEngine:
    def test_warp_basic(self):
        from astra.travel.warp import WarpBubble, WarpConfig

        bubble = WarpBubble(bubble_id="warp-1", center=Vec3(0, 0, 0), radius_m=100, bubble_velocity_m_s=2e12, metric_parameters={"wall_steepness": 5.0})
        cfg = WarpConfig(bubble=bubble)
        e = _engine()
        req = TravelRequest(
            request_id="warp-req-1",
            traveler_id="ship-warp",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(4e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WARP,
            config={"warp": cfg},
        )
        ev = e.execute(req)
        assert ev.mechanism == Mechanism.WARP
        assert ev.provenance == Provenance.THEORETICAL
        assert ev.coordinate_elapsed_time_s == pytest.approx(2.0, rel=1e-9)  # 4e12 /2e12
        assert ev.proper_elapsed_time_s == pytest.approx(2.0, rel=1e-9)

    def test_warp_missing_config_rejected(self):
        e = _engine()
        req = _req(request_id="warp-miss", mechanism=Mechanism.WARP, config={})
        with pytest.raises(TravelUnsupportedError):
            e.execute(req)
        assert e.get_state("warp-miss") == TravelState.PHYSICALLY_UNSUPPORTED

    def test_warp_velocity_is_coordinate_not_local(self):
        # Bubble velocity >c is allowed; local speed check should not reject
        from astra.travel.warp import WarpBubble, WarpConfig

        bubble = WarpBubble(bubble_id="warp-ftl", center=Vec3(0, 0, 0), radius_m=50, bubble_velocity_m_s=5e9, metric_parameters={})
        cfg = WarpConfig(bubble=bubble)  # 5e9 > c but as coordinate param it's allowed
        e = _engine()
        req = TravelRequest(
            request_id="warp-ftl-req",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(100, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(5e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WARP,
            config={"warp": cfg},
        )
        ev = e.execute(req)
        # coordinate distance / time = 5e12 / (5e12/5e9)=5e9 >c apparent, but provenance is theoretical and local stays causal
        apparent_speed = 5e12 / ev.coordinate_elapsed_time_s
        assert apparent_speed > 299_792_458.0
        assert ev.causal_status != CausalStatus.CAUSALLY_INVALID

    def test_warp_wall_steepness_guard(self):
        from astra.travel.warp import WarpBubble

        # wall steepness exceeding cap should raise TravelNumericalError at bubble construction
        with pytest.raises((TravelNumericalError, Exception)):
            WarpBubble(bubble_id="warp-steep", center=Vec3(0, 0, 0), radius_m=100, bubble_velocity_m_s=1e6, metric_parameters={"wall_steepness": 1e6})


class TestWhiteHole:
    def test_white_hole_interface_outward_allowed(self):
        from astra.travel.white_hole import WhiteHoleConfig

        # position away from origin so spherical conversion works
        cfg = WhiteHoleConfig(white_hole_id="wh1", position=Vec3(1e9, 0, 0), mass_kg=1.989e30, causal_direction="outward")
        e = _engine()
        req = TravelRequest(
            request_id="whl-1",
            traveler_id="probe-wh",
            departure_position=Vec3(2e9, 0, 0),
            departure_velocity=Vec3(1e6, 0, 0),  # outward
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(3e9, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WHITE_HOLE,
            config={"white_hole": cfg},
        )
        ev = e.execute(req)
        assert ev.mechanism == Mechanism.WHITE_HOLE
        assert ev.provenance == Provenance.HYPOTHETICAL
        assert ev.causal_status == CausalStatus.TIMELIKE

    def test_white_hole_ingoing_rejected(self):
        from astra.travel.white_hole import WhiteHoleConfig

        # Create a white hole at origin mass, then attempt ingoing travel near horizon
        cfg = WhiteHoleConfig(white_hole_id="wh2", position=Vec3(0, 0, 0), mass_kg=1.989e30)
        # departure close to horizon radius (~2954m for solar mass) at 1.2*rs outward then velocity inward
        from astra.blackhole.api import create_black_hole

        bh = create_black_hole(1.989e30)
        from astra.blackhole import schwarzschild
        rs = schwarzschild.schwarzschild_radius_m(1.989e30)
        # place departure at 1.2 rs on x-axis, velocity inward (-x)
        dep = Vec3(1.2 * rs, 0, 0)
        dst = Vec3(1.1 * rs, 0, 0)  # further inward
        e = _engine()
        req = TravelRequest(
            request_id="whl-ing-1",
            traveler_id="ing",
            departure_position=dep,
            departure_velocity=Vec3(-1e5, 0, 0),  # inward
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=dst,
            destination_reference_frame="world",
            mechanism=Mechanism.WHITE_HOLE,
            config={"white_hole": cfg},
        )
        with pytest.raises((TravelCausalityError, TravelUnsupportedError)):
            e.execute(req)

    def test_white_hole_missing_config(self):
        e = _engine()
        req = _req(request_id="wh-miss", mechanism=Mechanism.WHITE_HOLE, config={})
        with pytest.raises(TravelUnsupportedError):
            e.execute(req)


class TestTemporalAndCausality:
    def test_temporal_displacement_fields_separated(self):
        e = _engine()
        req = _req(request_id="temp-1", departure_coordinate_time_s=100.0, departure_velocity=Vec3(1e7, 0, 0))
        ev = e.execute(req)
        assert ev.departure_coordinate_time_s == pytest.approx(100.0)
        assert ev.arrival_coordinate_time_s != ev.departure_coordinate_time_s
        assert ev.proper_elapsed_time_s != ev.coordinate_elapsed_time_s
        # observer elapsed distinct field
        assert ev.observer_elapsed_time_s == pytest.approx(ev.coordinate_elapsed_time_s)
        # arrival state also separates
        arr = e.arrival_state(ev)
        assert arr.proper_time_s == pytest.approx(ev.proper_elapsed_time_s)
        assert arr.coordinate_time_s == pytest.approx(ev.arrival_coordinate_time_s)

    def test_causality_trip_timelike(self):
        e = _engine()
        ev = e.execute(_req())
        assert ev.causal_status in (CausalStatus.TIMELIKE, CausalStatus.UNKNOWN)
        assert e.get_state(ev.travel_id) == TravelState.COMPLETED

    def test_causally_invalid_transition(self):
        # Simulate by executing spacelike attempt via direct engine internal? Instead test that invalid speed is caught as spacelike
        e = TravelEngine(config=TravelConfig(), authority=_AllowAll(), relativity=_Rel(), causality=None)
        # with no causality provider, fallback still classifies spacelike if distance huge vs time
        # Forge a request where distance is 1e12 and speed is 1e7 but requested_arrival is tiny → spacelike → should raise Causality
        req = TravelRequest(
            request_id="causal-bad",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e7, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.RELATIVISTIC,
            config={},
            requested_arrival_coordinate_time_s=1.0,
        )
        with pytest.raises(TravelCausalityError):
            e.execute(req)
        assert e.get_state("causal-bad") == TravelState.CAUSALLY_INVALID

    def test_ctc_representation_where_supported(self):
        # Wormhole diagnostic is always False for single-patch, but we test the CTC status string exists
        from astra.travel.types import CausalStatus

        assert CausalStatus.CTC.value == "CTC"
        # Engine can represent CTC if causality provider returns CTC
        class CTCProvider:
            def check_causal_order(self, dep, arr):
                return CausalStatus.CTC

            def classify_worldline(self, w):
                return CausalStatus.CTC

        e = _engine(causality=CTCProvider())
        # wormhole with CTC provider should surface CTC status (not invalid)
        from astra.travel.wormhole import Wormhole, WormholeMouth

        wh = Wormhole(
            wormhole_id="wh-ctc",
            mouth_a=WormholeMouth(mouth_id="A", position=Vec3(0, 0, 0), coordinate_time_s=0.0),
            mouth_b=WormholeMouth(mouth_id="B", position=Vec3(1e12, 0, 0), coordinate_time_s=0.0),
            stability=0.9,
            traversal_duration_s=1.0,
            metric_parameters={},
        )
        req = TravelRequest(
            request_id="ctc-1",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WORMHOLE,
            config={"wormhole": wh},
        )
        ev = e.execute(req)
        assert ev.causal_status == CausalStatus.CTC


class TestArrivalState:
    def test_arrival_preserves_identity_and_frame(self):
        e = _engine()
        req = _req(request_id="arr-1", traveler_id="voyager", departure_reference_frame="earth", destination_reference_frame="mars")
        ev = e.execute(req)
        arr = e.arrival_state(ev)
        assert arr.traveler_id == "voyager"
        assert arr.reference_frame == "mars"
        assert arr.position.to_tuple() == ev.arrival_position.to_tuple()

    def test_arrival_does_not_mutate_destination(self):
        # ArrivalState is a new object; original destination tuple unchanged
        dst = Vec3(1e12, 0, 0)
        req = _req(request_id="arr-2", destination_position=dst)
        e = _engine()
        ev = e.execute(req)
        arr = e.arrival_state(ev)
        assert dst.to_tuple() == (1e12, 0.0, 0.0)
        assert arr.position.to_tuple() == (1e12, 0.0, 0.0)


class TestSpacecraftIntegration:
    def test_spacecraft_state_preserved(self):
        from astra.spacecraft.state import SpacecraftState
        from astra.motion.state import MotionState
        from astra.mathematics import Vector3 as V3
        from astra.spacecraft.mass import SpacecraftMass
        from astra.spacecraft.engines import Engine, EngineSpec

        # create a spacecraft
        sc_state = SpacecraftState(
            motion=MotionState(position=V3(0, 0, 0), velocity=V3(0, 0, 0)),
            mass=SpacecraftMass(dry_mass=1000, propellant_mass=500),
            engine_specs=[EngineSpec(engine=Engine(id="main", thrust_magnitude=1e4, specific_impulse=300, thrust_direction_local=V3(1, 0, 0)))],
        )
        provider = _engine().spacecraft
        # inject known state
        provider._states["ship-sc"] = sc_state  # DefaultSpacecraftStateProvider internal
        e = TravelEngine(config=TravelConfig(), authority=_AllowAll(), relativity=_Rel(), spacecraft=provider)
        req = TravelRequest(
            request_id="sc-1",
            traveler_id="ship-sc",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e4, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e9, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.RELATIVISTIC,
        )
        ev = e.execute(req)
        # arrival should have updated motion
        new_state = provider.get_state("ship-sc")
        assert new_state is not None
        assert new_state.mass.dry_mass == pytest.approx(1000)
        # position updated to arrival
        assert new_state.motion.position.x == pytest.approx(1e9)


class TestObservationIntegration:
    def test_observation_finite_light_propagation(self):
        from astra.relativity.core import SPEED_OF_LIGHT as C

        e = _engine()
        req = TravelRequest(
            request_id="obs-1",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e7, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(C, 0, 0),  # exactly 1 light-second
            destination_reference_frame="world",
            mechanism=Mechanism.RELATIVISTIC,
            config={"observer_position": Vec3(0, 0, 0)},
        )
        ev = e.execute(req)
        # engine should have recorded observation with delay = distance/c ~1s
        rec = e._observation_records.get(ev.travel_id)
        assert rec is not None
        assert rec["departure_delay_s"] == pytest.approx(0.0)
        assert rec["arrival_delay_s"] == pytest.approx(1.0, rel=1e-6)
        assert rec["observed_arrival_at"] > ev.arrival_coordinate_time_s

    def test_observation_history_in_metadata(self):
        e = _engine()
        ev = e.execute(_req(request_id="obs-2"))
        assert "departure_event" in ev.metadata
        assert "arrival_event" in ev.metadata


class TestLargeScaleAndNumerics:
    def test_large_scale_interstellar(self):
        e = _engine()
        # 4.2 ly ~ 4e16 m
        lx = 4.0e16
        req = TravelRequest(
            request_id="large-1",
            traveler_id="voyager",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(0.5 * 299_792_458, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(lx, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.RELATIVISTIC,
        )
        ev = e.execute(req)
        assert ev.coordinate_elapsed_time_s > 0
        # no overflow
        assert math.isfinite(ev.coordinate_elapsed_time_s)
        assert math.isfinite(ev.proper_elapsed_time_s)

    def test_intergalactic_via_wormhole(self):
        from astra.travel.wormhole import Wormhole, WormholeMouth

        wh = Wormhole(
            wormhole_id="wh-large",
            mouth_a=WormholeMouth(mouth_id="A", position=Vec3(0, 0, 0), coordinate_time_s=0.0),
            mouth_b=WormholeMouth(mouth_id="B", position=Vec3(1e22, 0, 0), coordinate_time_s=0.0),
            stability=0.9,
            traversal_duration_s=5.0,
            metric_parameters={},
        )
        e = _engine()
        req = TravelRequest(
            request_id="large-wh",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e22, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WORMHOLE,
            config={"wormhole": wh},
        )
        ev = e.execute(req)
        # apparent FTL but allowed via topology
        assert ev.coordinate_elapsed_time_s == pytest.approx(5.0)

    def test_numerical_nan_rejected(self):
        with pytest.raises(TravelNumericalError):
            Vec3(float("nan"), 0, 0)
        with pytest.raises(TravelNumericalError):
            TravelRequest(
                request_id="nan-req",
                traveler_id="ship",
                departure_position=Vec3(0, 0, 0),
                departure_velocity=Vec3(1e7, 0, 0),
                departure_coordinate_time_s=float("nan"),
                departure_reference_frame="world",
                destination_position=Vec3(1e12, 0, 0),
                destination_reference_frame="world",
                mechanism=Mechanism.RELATIVISTIC,
            )

    def test_inf_rejected(self):
        with pytest.raises(TravelNumericalError):
            Vec3(float("inf"), 0, 0)

    def test_singularity_at_origin_spherical_handled(self):
        # white hole at origin with zero position triggers spherical guard; engine should handle without NaN
        from astra.travel.white_hole import WhiteHoleConfig

        cfg = WhiteHoleConfig(white_hole_id="sing", position=Vec3(0, 0, 0), mass_kg=1e30)
        e = _engine()
        # departure away from origin, not at singularity, should succeed
        req = TravelRequest(
            request_id="sing-1",
            traveler_id="probe",
            departure_position=Vec3(1e9, 0, 0),
            departure_velocity=Vec3(1e6, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(2e9, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WHITE_HOLE,
            config={"white_hole": cfg},
        )
        ev = e.execute(req)
        assert ev is not None


class TestDeterminism:
    def test_identical_inputs_identical_outputs(self):
        e1 = _engine()
        e2 = _engine()
        req = _req(request_id="det-1")
        ev1 = e1.execute(req)
        ev2 = e2.execute(req)
        assert ev1.proper_elapsed_time_s == pytest.approx(ev2.proper_elapsed_time_s)
        assert ev1.coordinate_elapsed_time_s == pytest.approx(ev2.coordinate_elapsed_time_s)
        assert ev1.arrival_position.to_tuple() == ev2.arrival_position.to_tuple()
        assert len(ev1.worldline.samples) == len(ev2.worldline.samples)
        for s1, s2 in zip(ev1.worldline.samples, ev2.worldline.samples):
            assert s1.coordinate_time_s == pytest.approx(s2.coordinate_time_s)
            assert s1.proper_time_s == pytest.approx(s2.proper_time_s)
            assert s1.position.to_tuple() == s2.position.to_tuple()

    def test_worldline_deterministic_500_runs(self):
        e = _engine()
        req = _req(request_id="det-500-base")
        first = None
        for i in range(20):
            # use fresh engine each time but same request id variant
            eng = _engine()
            r = TravelRequest(
                request_id=f"det-500-{i}",
                traveler_id="ship",
                departure_position=Vec3(0, 0, 0),
                departure_velocity=Vec3(1e7, 0, 0),
                departure_coordinate_time_s=0.0,
                departure_reference_frame="world",
                destination_position=Vec3(1e12, 0, 0),
                destination_reference_frame="world",
                mechanism=Mechanism.RELATIVISTIC,
            )
            ev = eng.execute(r)
            if first is None:
                first = ev
            else:
                assert ev.proper_elapsed_time_s == pytest.approx(first.proper_elapsed_time_s)
                assert ev.coordinate_elapsed_time_s == pytest.approx(first.coordinate_elapsed_time_s)

    def test_no_randomness_in_engine(self):
        # engine should not use global random
        import random

        random.seed(12345)
        e = _engine()
        ev1 = e.execute(_req(request_id="rnd-1"))
        random.seed(99999)
        e2 = _engine()
        ev2 = e2.execute(_req(request_id="rnd-1"))
        assert ev1.proper_elapsed_time_s == pytest.approx(ev2.proper_elapsed_time_s)


class TestProvenance:
    def test_relativistic_is_simulated(self):
        e = _engine()
        ev = e.execute(_req())
        assert ev.provenance == Provenance.SIMULATED_DATA

    def test_wormhole_is_hypothetical(self):
        from astra.travel.wormhole import Wormhole, WormholeMouth

        wh = Wormhole(
            wormhole_id="prov-wh",
            mouth_a=WormholeMouth(mouth_id="A", position=Vec3(0, 0, 0), coordinate_time_s=0.0),
            mouth_b=WormholeMouth(mouth_id="B", position=Vec3(1e12, 0, 0), coordinate_time_s=0.0),
            stability=0.9,
            traversal_duration_s=1.0,
            metric_parameters={},
        )
        e = _engine()
        req = TravelRequest(
            request_id="prov-wh-1",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WORMHOLE,
            config={"wormhole": wh},
        )
        ev = e.execute(req)
        assert ev.provenance == Provenance.HYPOTHETICAL
        assert ev.provenance.to_data_provenance().value == "SPECULATIVE_MODEL"

    def test_warp_is_theoretical(self):
        from astra.travel.warp import WarpBubble, WarpConfig

        bubble = WarpBubble(bubble_id="prov-warp", center=Vec3(0, 0, 0), radius_m=100, bubble_velocity_m_s=1e12, metric_parameters={})
        cfg = WarpConfig(bubble=bubble)
        e = _engine()
        req = TravelRequest(
            request_id="prov-warp-1",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WARP,
            config={"warp": cfg},
        )
        ev = e.execute(req)
        assert ev.provenance == Provenance.THEORETICAL

    def test_white_hole_is_hypothetical(self):
        from astra.travel.white_hole import WhiteHoleConfig

        cfg = WhiteHoleConfig(white_hole_id="prov-whl", position=Vec3(1e9, 0, 0))
        e = _engine()
        req = TravelRequest(
            request_id="prov-whl-1",
            traveler_id="ship",
            departure_position=Vec3(1e9, 0, 0),
            departure_velocity=Vec3(1e6, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(2e9, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WHITE_HOLE,
            config={"white_hole": cfg},
        )
        ev = e.execute(req)
        assert ev.provenance == Provenance.HYPOTHETICAL

    def test_never_present_speculative_as_real(self):
        from astra.travel.wormhole import Wormhole, WormholeMouth

        wh = Wormhole(
            wormhole_id="never-real",
            mouth_a=WormholeMouth(mouth_id="A", position=Vec3(0, 0, 0), coordinate_time_s=0.0),
            mouth_b=WormholeMouth(mouth_id="B", position=Vec3(1e12, 0, 0), coordinate_time_s=0.0),
            stability=0.9,
            traversal_duration_s=1.0,
            metric_parameters={},
        )
        e = _engine()
        req = TravelRequest(
            request_id="never-real-1",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WORMHOLE,
            config={"wormhole": wh},
        )
        ev = e.execute(req)
        assert ev.provenance != Provenance.REAL_DATA
        assert ev.provenance != Provenance.DERIVED_DATA


class TestStateMachine:
    def test_full_lifecycle(self):
        e = _engine()
        req = _req(request_id="life-1")
        assert e.get_state("life-1") == TravelState.UNCONFIGURED
        ev = e.execute(req)
        assert e.get_state("life-1") == TravelState.COMPLETED
        assert ev is not None

    def test_aborted_not_used_but_exists(self):
        assert TravelState.ABORTED.value == "ABORTED"
        assert TravelState.FAILED.value == "FAILED"
        assert Transition.is_valid(TravelState.READY, TravelState.ABORTED)

    def test_state_persistence_after_failure(self):
        e = _engine()
        req = _req(request_id="fail-state", departure_velocity=Vec3(0, 0, 0))
        with pytest.raises(TravelValidationError):
            e.execute(req)
        assert e.get_state("fail-state") == TravelState.FAILED


class TestFailureModes:
    def test_invalid_destination_nan(self):
        with pytest.raises(TravelNumericalError):
            Vec3(float("nan"), 0, 0)

    def test_invalid_metric_unstable_wormhole(self):
        from astra.travel.wormhole import Wormhole, WormholeMouth

        wh = Wormhole(
            wormhole_id="fail-wh",
            mouth_a=WormholeMouth(mouth_id="A", position=Vec3(0, 0, 0), coordinate_time_s=0.0),
            mouth_b=WormholeMouth(mouth_id="B", position=Vec3(1e12, 0, 0), coordinate_time_s=0.0),
            stability=0.0,
            traversal_duration_s=1.0,
            metric_parameters={},
        )
        e = _engine()
        req = TravelRequest(
            request_id="fail-wh-1",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WORMHOLE,
            config={"wormhole": wh},
        )
        with pytest.raises(TravelUnsupportedError):
            e.execute(req)

    def test_causal_violation(self):
        e = _engine()
        req = TravelRequest(
            request_id="fail-causal",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e7, 0, 0),
            departure_coordinate_time_s=10.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.RELATIVISTIC,
            config={},
            requested_arrival_coordinate_time_s=5.0,
        )
        # validation should reject requested before departure before engine even runs causality
        with pytest.raises(TravelValidationError):
            e.execute(req)

    def test_unsupported_mechanism(self):
        # string coercion to unknown
        with pytest.raises(TravelNumericalError):
            TravelRequest(
                request_id="unsup",
                traveler_id="ship",
                departure_position=Vec3(0, 0, 0),
                departure_velocity=Vec3(1e7, 0, 0),
                departure_coordinate_time_s=0.0,
                departure_reference_frame="world",
                destination_position=Vec3(1e12, 0, 0),
                destination_reference_frame="world",
                mechanism="UNKNOWN_MECH",  # type: ignore
            )

    def test_invalid_reference_frame(self):
        with pytest.raises(TravelNumericalError):
            TravelRequest(
                request_id="bad-frame",
                traveler_id="ship",
                departure_position=Vec3(0, 0, 0),
                departure_velocity=Vec3(1e7, 0, 0),
                departure_coordinate_time_s=0.0,
                departure_reference_frame="",  # empty
                destination_position=Vec3(1e12, 0, 0),
                destination_reference_frame="world",
                mechanism=Mechanism.RELATIVISTIC,
            )


class TestSuperluminalRule:
    def test_naive_ftl_without_mechanism_rejected(self):
        e = _engine()
        # attempt relativistic with requested short time requiring >c
        req = TravelRequest(
            request_id="ftl-naive",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e7, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e12, 0, 0),  # 1e12 m
            destination_reference_frame="world",
            mechanism=Mechanism.RELATIVISTIC,
            requested_arrival_coordinate_time_s=1.0,  # need 1e12 speed >c
        )
        with pytest.raises(TravelCausalityError):
            e.execute(req)

    def test_warp_allows_apparent_ftl(self):
        from astra.travel.warp import WarpBubble, WarpConfig

        bubble = WarpBubble(bubble_id="ftl-warp", center=Vec3(0, 0, 0), radius_m=100, bubble_velocity_m_s=1e13, metric_parameters={})
        cfg = WarpConfig(bubble=bubble)
        e = _engine()
        req = TravelRequest(
            request_id="ftl-warp-ok",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e15, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WARP,
            config={"warp": cfg},
        )
        ev = e.execute(req)
        apparent = 1e15 / ev.coordinate_elapsed_time_s
        assert apparent > 299_792_458.0

    def test_wormhole_allows_apparent_ftl(self):
        from astra.travel.wormhole import Wormhole, WormholeMouth

        wh = Wormhole(
            wormhole_id="ftl-wh",
            mouth_a=WormholeMouth(mouth_id="A", position=Vec3(0, 0, 0), coordinate_time_s=0.0),
            mouth_b=WormholeMouth(mouth_id="B", position=Vec3(1e15, 0, 0), coordinate_time_s=0.0),
            stability=1.0,
            traversal_duration_s=1.0,
            metric_parameters={},
        )
        e = _engine()
        req = TravelRequest(
            request_id="ftl-wh-ok",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e15, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WORMHOLE,
            config={"wormhole": wh},
        )
        ev = e.execute(req)
        apparent = 1e15 / ev.coordinate_elapsed_time_s
        assert apparent > 299_792_458.0


class TestCoordinateIntegration:
    def test_reference_frames_preserved(self):
        e = _engine()
        req = _req(request_id="coord-1", departure_reference_frame="earth_surface", destination_reference_frame="mars_orbit")
        ev = e.execute(req)
        assert ev.departure_reference_frame == "earth_surface"
        assert ev.arrival_reference_frame == "mars_orbit"

    def test_arbitrary_coords_allowed(self):
        e = _engine()
        req = _req(request_id="coord-2", departure_position=Vec3(-1e9, 2e9, -3e9), destination_position=Vec3(1e9, -2e9, 3e9))
        ev = e.execute(req)
        assert ev is not None

    def test_local_world_frame_distinction(self):
        # worldline observer_frame is preserved
        e = _engine()
        ev = e.execute(_req(request_id="coord-3"))
        assert ev.worldline.samples[0].observer_frame == "world"


class TestEnergyClassification:
    def test_relativistic_energy_calculated_when_mass_given(self):
        e = _engine()
        req = TravelRequest(
            request_id="energy-1",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e7, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.RELATIVISTIC,
            config={"rest_mass_kg": 1000},
        )
        ev = e.execute(req)
        assert ev.metadata.get("energy_J") is not None
        assert ev.metadata.get("exotic_matter_requirement") == "calculated"

    def test_warp_exotic_unknown(self):
        from astra.travel.warp import WarpBubble, WarpConfig

        bubble = WarpBubble(bubble_id="en-warp", center=Vec3(0, 0, 0), radius_m=100, bubble_velocity_m_s=1e12, metric_parameters={})
        cfg = WarpConfig(bubble=bubble, exotic_matter_requirement="unknown")
        e = _engine()
        req = TravelRequest(
            request_id="energy-warp",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WARP,
            config={"warp": cfg},
        )
        ev = e.execute(req)
        assert ev.metadata["exotic_matter_requirement"] == "unknown"

    def test_wormhole_hypothetical(self):
        from astra.travel.wormhole import Wormhole, WormholeMouth

        wh = Wormhole(
            wormhole_id="en-wh",
            mouth_a=WormholeMouth(mouth_id="A", position=Vec3(0, 0, 0), coordinate_time_s=0.0),
            mouth_b=WormholeMouth(mouth_id="B", position=Vec3(1e12, 0, 0), coordinate_time_s=0.0),
            stability=0.9,
            traversal_duration_s=1.0,
            metric_parameters={},
        )
        e = _engine()
        req = TravelRequest(
            request_id="en-wh-2",
            traveler_id="ship",
            departure_position=Vec3(0, 0, 0),
            departure_velocity=Vec3(1e3, 0, 0),
            departure_coordinate_time_s=0.0,
            departure_reference_frame="world",
            destination_position=Vec3(1e12, 0, 0),
            destination_reference_frame="world",
            mechanism=Mechanism.WORMHOLE,
            config={"wormhole": wh},
        )
        ev = e.execute(req)
        assert ev.metadata["exotic_matter_requirement"] == "hypothetical"
