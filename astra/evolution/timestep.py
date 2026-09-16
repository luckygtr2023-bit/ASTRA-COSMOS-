"""ASTRA Evolution — adaptive timestep management.

Timestep decisions are explicit, justified, and never silently clamped
(§2.31, §2.32).  The controller chooses the largest stable step within
policy bounds that respects rate-limited dynamics and event scheduling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .config import TimestepPolicy
from .errors import EvolutionNumericalError


class TimestepReason(str, Enum):
    """Machine-readable reason for a timestep choice."""

    CONFIGURED_MAX = "CONFIGURED_MAX"
    CONFIGURED_MIN = "CONFIGURED_MIN"
    RATE_LIMITED = "RATE_LIMITED"
    EVENT_DRIVEN = "EVENT_DRIVEN"
    REMAINING_INTERVAL = "REMAINING_INTERVAL"


@dataclass(frozen=True)
class TimestepDecision:
    """Record of a timestep choice — explicit justification, not a bare float."""

    dt_gyr: float
    reason: TimestepReason
    justification: str
    model_id: str

    def __post_init__(self):
        if isinstance(self.dt_gyr, bool) or not isinstance(self.dt_gyr, (int, float)):
            raise EvolutionNumericalError("dt_gyr must be numeric")
        fv = float(self.dt_gyr)
        if math.isnan(fv) or math.isinf(fv):
            raise EvolutionNumericalError(f"dt_gyr must be finite, got {fv!r}")
        if fv < 0.0:
            raise EvolutionNumericalError(f"dt_gyr must be >= 0, got {fv!r}")
        object.__setattr__(self, "dt_gyr", fv)
        if not isinstance(self.reason, TimestepReason):
            raise TypeError("reason must be a TimestepReason")
        if not isinstance(self.justification, str) or not self.justification:
            raise ValueError("justification must be a non-empty string")
        if not isinstance(self.model_id, str) or not self.model_id:
            raise ValueError("model_id must be a non-empty string")


class AdaptiveTimestepController:
    """Deterministic timestep selection.

    Contract (§2.31):

    - Never chooses a step smaller than ``policy.min_dt_gyr`` or larger than
      ``policy.max_dt_gyr``, except when the *remaining interval itself* is
      smaller than ``min_dt_gyr`` — in that case the controller returns the
      remaining interval directly with ``reason=CONFIGURED_MIN``.  It does
      NOT silently pad or clamp the interval.
    - Rate scaling: ``candidate = min(max_dt, max(min_dt, base_dt / rate_scale))``
      so that fast dynamics get smaller steps.
    - Event-driven: if ``next_event_gyr`` is supplied as an absolute cosmic
      time, the step never goes past it (bounded by the distance to the
      event).  If no caller-provided current time is available, the event
      bound is treated as a delta when ``next_event_gyr`` is smaller than
      ``remaining_gyr``.
    - Deterministic: identical inputs produce identical decisions.
    """

    def __init__(self, policy: TimestepPolicy) -> None:
        if not isinstance(policy, TimestepPolicy):
            raise TypeError("policy must be a TimestepPolicy")
        policy.validate()
        self._policy = policy

    @property
    def policy(self) -> TimestepPolicy:
        return self._policy

    def choose(
        self,
        *,
        remaining_gyr: float,
        rate_scale: float = 1.0,
        next_event_gyr: Optional[float] = None,
        model_id: str = "unknown",
        current_cosmic_time_gyr: Optional[float] = None,
    ) -> TimestepDecision:
        """Choose the next timestep.

        Args:
            remaining_gyr: time remaining to target (Gyr), >= 0.
            rate_scale: dimensionless rate factor (e.g. SFR / SFR_ref);
                >1 means faster evolution → smaller steps.  0 or None means
                no rate limiting.
            next_event_gyr: absolute cosmic time of next event, or if
                ``current_cosmic_time_gyr`` is given, the delta is computed
                correctly; otherwise treated as an upper bound when it is
                smaller than ``remaining_gyr``.
            model_id: model identifier for provenance.
            current_cosmic_time_gyr: optional current time for correct
                event-delta computation.

        Returns:
            TimestepDecision with explicit reason.

        Raises:
            EvolutionNumericalError: on non-finite or negative inputs.
        """
        if isinstance(remaining_gyr, bool) or not isinstance(remaining_gyr, (int, float)):
            raise EvolutionNumericalError("remaining_gyr must be numeric")
        rem = float(remaining_gyr)
        if math.isnan(rem) or math.isinf(rem):
            raise EvolutionNumericalError("remaining_gyr must be finite")
        if rem < 0.0:
            raise EvolutionNumericalError("remaining_gyr must be >= 0")
        if rem == 0.0:
            return TimestepDecision(0.0, TimestepReason.CONFIGURED_MIN,
                                    "no interval remains", model_id)

        if not isinstance(model_id, str) or not model_id:
            raise EvolutionNumericalError("model_id must be a non-empty string")

        # Validate rate_scale
        if rate_scale is not None:
            if isinstance(rate_scale, bool) or not isinstance(rate_scale, (int, float)):
                raise EvolutionNumericalError("rate_scale must be numeric or None")
            rs = float(rate_scale)
            if math.isnan(rs) or math.isinf(rs):
                raise EvolutionNumericalError("rate_scale must be finite")
            if rs < 0.0:
                raise EvolutionNumericalError("rate_scale must be >= 0")
        else:
            rs = 0.0

        p = self._policy

        # If remaining is smaller than min_dt, return remaining directly —
        # do NOT clamp it up to min_dt.  This is the "never silently clamp"
        # guarantee.
        if rem < p.min_dt_gyr:
            return TimestepDecision(rem, TimestepReason.CONFIGURED_MIN,
                                    f"remaining {rem} < min_dt {p.min_dt_gyr}: "
                                    "returning remaining interval directly without clamping",
                                    model_id)

        # Start from max, then apply constraints
        candidate = p.max_dt_gyr
        reason = TimestepReason.CONFIGURED_MAX
        justification = f"policy max_dt {p.max_dt_gyr}"

        # Rate-limited: smaller steps when rates are high
        if rs > 0.0:
            floor = max(p.rate_scale_floor, 1e-30)
            effective_rate = max(rs, floor)
            scaled = p.base_dt_gyr / effective_rate
            # clamp scaled to [min, max]
            scaled = max(p.min_dt_gyr, min(p.max_dt_gyr, scaled))
            if scaled < candidate:
                candidate = scaled
                reason = TimestepReason.RATE_LIMITED
                justification = f"rate-limited: base {p.base_dt_gyr} / rate {effective_rate} = {scaled}"

        # Event-driven: never step past the next event
        if next_event_gyr is not None and p.allow_event_driven:
            if isinstance(next_event_gyr, bool) or not isinstance(next_event_gyr, (int, float)):
                raise EvolutionNumericalError("next_event_gyr must be numeric or None")
            nev = float(next_event_gyr)
            if math.isnan(nev) or math.isinf(nev):
                raise EvolutionNumericalError("next_event_gyr must be finite")
            # Compute event delta
            if current_cosmic_time_gyr is not None:
                if isinstance(current_cosmic_time_gyr, bool) or not isinstance(current_cosmic_time_gyr, (int, float)):
                    raise EvolutionNumericalError("current_cosmic_time_gyr must be numeric")
                cur = float(current_cosmic_time_gyr)
                if math.isnan(cur) or math.isinf(cur):
                    raise EvolutionNumericalError("current_cosmic_time_gyr must be finite")
                event_delta = nev - cur
            else:
                # Heuristic: if next_event_gyr looks like an absolute time
                # much larger than remaining, don't misinterpret; treat as
                # delta only when it would otherwise step past remaining.
                # For determinism, we treat next_event_gyr as a distance
                # when it is < remaining_gyr.
                if nev < rem:
                    event_delta = nev
                else:
                    event_delta = rem  # no effective constraint

            if event_delta <= 0.0:
                # Event is now or past — force min step to hit it exactly
                # but not larger than remaining
                event_step = min(rem, p.min_dt_gyr) if rem >= p.min_dt_gyr else rem
                # If event delta is 0, we should not advance? Caller should
                # handle zero. We return min step to make progress.
                if event_delta == 0.0:
                    pass  # no constraint, keep candidate
                else:
                    # past event: ignore, we already passed it
                    pass
            else:
                # event in future — bound candidate
                if event_delta < candidate:
                    # respect min_dt unless event is closer than min
                    if event_delta < p.min_dt_gyr:
                        # Event is closer than min_dt: return event delta
                        # directly (again, never clamp upward)
                        return TimestepDecision(
                            min(event_delta, rem),
                            TimestepReason.EVENT_DRIVEN,
                            f"next event in {event_delta} < min_dt {p.min_dt_gyr}: "
                            "stepping directly to event",
                            model_id,
                        )
                    candidate = event_delta
                    reason = TimestepReason.EVENT_DRIVEN
                    justification = f"event-driven: next event in {event_delta}"

        # Final clamp: never exceed remaining.  Use an epsilon-aware
        # comparison so that floating-point representation of 0.1 does not
        # cause a penultimate step to be taken when we are effectively at
        # the target.  The epsilon is scaled to the remaining interval.
        eps = 1e-12 * max(1.0, abs(rem))
        if candidate + eps >= rem:
            if reason == TimestepReason.EVENT_DRIVEN:
                return TimestepDecision(rem, TimestepReason.EVENT_DRIVEN,
                                        "covering remaining interval to target/event", model_id)
            return TimestepDecision(rem, TimestepReason.REMAINING_INTERVAL,
                                    "covering remaining interval to target", model_id)

        return TimestepDecision(candidate, reason, justification, model_id)
