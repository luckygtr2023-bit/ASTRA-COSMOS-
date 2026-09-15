"""ASTRA COSMOS — Phase 21: adaptive timestep management.

Every step the engine takes is decided by ``AdaptiveTimestepController``
and recorded as an explicit, scientifically justified ``TimestepDecision``
(spec 2.31). The controller NEVER silently clamps:

- ``requested_dt_gyr`` is what the policy computed before intersecting
  with the remaining interval;
- ``clamped_to_remaining`` is True exactly when the interval end (or a
  scheduled event boundary) shortened the step;
- a remaining interval smaller than ``min_dt_gyr`` is taken as-is and
  labelled REMAINDER — the policy floor is never used to inflate it;
- stepping PAST a scheduled event is impossible: event boundaries cap the
  candidate and produce an EVENT_DRIVEN decision landing on the boundary.

Rules (documented order):
    1. candidate = policy.max_dt_gyr                        (CONFIGURED_MAX)
    2. if rate information present (rate_scale > rate_scale_floor):
           candidate = min(candidate, base_dt_gyr / rate_scale),
           floored at min_dt_gyr (floor application is recorded in the
           justification)                                    (RATE_LIMITED)
    3. if a scheduled event boundary lies ahead: candidate =
           min(candidate, boundary - now)                    (EVENT_DRIVEN)
    4. if candidate >= remaining: take remaining, mark
           clamped_to_remaining=True, reason = the binding constraint
           above, else CONFIGURED_MAX
    5. if remaining < min_dt_gyr: take remaining, reason REMAINDER

Non-finite or negative remaining intervals are rejected (never clamped
into validity).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .config import TimestepPolicy
from .errors import EvolutionNumericalError
from .quantity import require_finite_number


class TimestepReason(str, Enum):
    CONFIGURED_MAX = "CONFIGURED_MAX"    # policy ceiling applied
    RATE_LIMITED = "RATE_LIMITED"        # fast physics -> shorter step
    EVENT_DRIVEN = "EVENT_DRIVEN"        # stop exactly on a scheduled event
    REMAINDER = "REMAINDER"              # explicit tail step below policy floor
    NO_INTERVAL = "NO_INTERVAL"          # nothing remains (dt == 0)


@dataclass(frozen=True)
class TimestepDecision:
    dt_gyr: float
    reason: TimestepReason
    justification: str
    model_id: str
    requested_dt_gyr: float = 0.0
    clamped_to_remaining: bool = False

    def to_dict(self):
        return {
            "dt_gyr": self.dt_gyr,
            "reason": self.reason.value,
            "justification": self.justification,
            "model_id": self.model_id,
            "requested_dt_gyr": self.requested_dt_gyr,
            "clamped_to_remaining": self.clamped_to_remaining,
        }

    @classmethod
    def from_dict(cls, d) -> "TimestepDecision":
        return cls(
            dt_gyr=d["dt_gyr"],
            reason=TimestepReason(d["reason"]),
            justification=d["justification"],
            model_id=d["model_id"],
            requested_dt_gyr=d.get("requested_dt_gyr", d["dt_gyr"]),
            clamped_to_remaining=d.get("clamped_to_remaining", False),
        )


class AdaptiveTimestepController:
    """Deterministic timestep selection (see module docstring for rules)."""

    def __init__(self, policy: TimestepPolicy) -> None:
        if not isinstance(policy, TimestepPolicy):
            raise EvolutionNumericalError("AdaptiveTimestepController requires a TimestepPolicy")
        self._policy = policy

    @property
    def policy(self) -> TimestepPolicy:
        return self._policy

    def choose(
        self,
        *,
        now_gyr: float,
        remaining_gyr: float,
        rate_scale: float,
        next_event_time_gyr: Optional[float],
        model_id: str,
    ) -> TimestepDecision:
        now = require_finite_number(now_gyr, "now_gyr")
        remaining = require_finite_number(remaining_gyr, "remaining_gyr")
        if remaining < 0.0:
            raise EvolutionNumericalError("remaining_gyr must be >= 0")
        model_id = str(model_id)
        p = self._policy

        if remaining == 0.0:
            return TimestepDecision(
                dt_gyr=0.0,
                reason=TimestepReason.NO_INTERVAL,
                justification="no interval remains",
                model_id=model_id,
                requested_dt_gyr=0.0,
                clamped_to_remaining=True,
            )

        # Step 1-2: policy ceiling + rate-limited candidate.
        candidate = p.max_dt_gyr
        reason = TimestepReason.CONFIGURED_MAX
        justification = "policy ceiling max_dt_gyr"
        if rate_scale > p.rate_scale_floor:
            scaled = p.base_dt_gyr / rate_scale
            if scaled < p.min_dt_gyr:
                candidate = p.min_dt_gyr
                reason = TimestepReason.RATE_LIMITED
                justification = (
                    f"rate_scale={rate_scale:.6g} drives base_dt/rate below min_dt_gyr; "
                    "policy floor min_dt_gyr applied (recorded, not silent)"
                )
            else:
                # The rate-driven step may never exceed the policy ceiling:
                # decaying rates (rate_scale -> 0) must lengthen steps only
                # UP TO max_dt_gyr, never past it.
                candidate = min(scaled, p.max_dt_gyr)
                reason = TimestepReason.RATE_LIMITED
                if candidate < scaled:
                    justification = (
                        f"rate_scale={rate_scale:.6g}: step = base_dt/rate, "
                        "capped at policy ceiling max_dt_gyr (recorded, not silent)"
                    )
                else:
                    justification = f"rate_scale={rate_scale:.6g}: step = base_dt/rate"

        # Step 3: event boundary cap.
        event_limited = False
        if next_event_time_gyr is not None:
            boundary = require_finite_number(next_event_time_gyr, "next_event_time_gyr")
            if not p.allow_event_driven:
                raise EvolutionNumericalError(
                    "scheduled event supplied but policy.allow_event_driven is False"
                )
            dt_to_event = boundary - now
            if dt_to_event <= 0.0:
                raise EvolutionNumericalError(
                    f"scheduled event at {boundary} is not in the future relative to {now}"
                )
            event_limited = True
            if dt_to_event < candidate:
                candidate = dt_to_event
                reason = TimestepReason.EVENT_DRIVEN
                justification = f"stop exactly on scheduled event boundary at {boundary}"

        # Step 4/5: intersect with the remaining interval, explicitly.
        requested = candidate
        if remaining < p.min_dt_gyr:
            return TimestepDecision(
                dt_gyr=remaining,
                reason=TimestepReason.REMAINDER,
                justification=(
                    f"remaining interval {remaining} below policy min_dt_gyr; taken as-is "
                    "(explicit remainder, not clamped)"
                ),
                model_id=model_id,
                requested_dt_gyr=requested,
                clamped_to_remaining=True,
            )
        if candidate >= remaining:
            if event_limited and requested > remaining:
                reason = TimestepReason.EVENT_DRIVEN
                justification = f"remaining interval ends at scheduled event boundary {now + remaining}"
            elif reason is TimestepReason.CONFIGURED_MAX:
                justification = "policy ceiling covers the remaining interval"
            return TimestepDecision(
                dt_gyr=remaining,
                reason=reason,
                justification=justification + "; covering the remaining interval",
                model_id=model_id,
                requested_dt_gyr=requested,
                clamped_to_remaining=True,
            )
        return TimestepDecision(
            dt_gyr=candidate,
            reason=reason,
            justification=justification,
            model_id=model_id,
            requested_dt_gyr=requested,
            clamped_to_remaining=False,
        )


__all__ = ["TimestepReason", "TimestepDecision", "AdaptiveTimestepController"]
