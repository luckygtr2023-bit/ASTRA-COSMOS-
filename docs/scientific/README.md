# ASTRA COSMOS — Canonical Scientific Integrity Layer (Phase 22)

**Layer:** Annotation / Validation / Explanation — never recomputation.  
**Position:** `Data / Models → Existing ASTRA Scientific Engines → **Phase 22 Classification Layer (this package)** → Provenance / Uncertainty / Assumptions / Warnings → Observation / Simulation / UI`

This package is the **single source of truth** for scientific classification, provenance, assumptions, validity, uncertainty, warnings, policy, scenarios, audit, and result envelopes across ASTRA. All other packages must import `Provenance` from here, not declare their own parallel enums.

> Prior layers remain: `astra.celestial.provenance.DataProvenance` (5-value, celestial property blocks) and `astra.evolution.provenance.Provenance` (now a shim `from astra.scientific.classification import Classification as Provenance`). `grep -rn "class Provenance(" astra/` must find **zero** definitions outside `astra/scientific/` (DataProvenance is intentionally named differently and is not flagged).

---

## 1. Classification

Six categories, ordered by epistemic strength (weakest-wins):

```
REAL_DATA (0) < DERIVED_DATA (1) < SIMULATED_DATA (2) < THEORETICAL (3) < HYPOTHETICAL (4) < SPECULATIVE (5)
```

```python
from astra.scientific import Classification, classify_combination

classify_combination((Classification.REAL_DATA, Classification.SIMULATED_DATA))
# → SIMULATED_DATA (weakest)
```

- `ClassificationOrder.strength(c)` → 0..5, `weakest(iter)`, `strongest(iter)`, `ordered()`
- `classify_combination` rejects empty input.
- `Provenance` is an alias (`Classification is Provenance`).

Legacy mapping (`astra.scientific.migration.migrate_legacy`):

| Legacy string | Canonical |
|---|---|
| REAL_DATA, REAL_PHYSICS | REAL_DATA |
| DERIVED_DATA | DERIVED_DATA |
| SIMULATED_DATA | SIMULATED_DATA |
| THEORETICAL_MODEL, THEORETICAL | THEORETICAL |
| SPECULATIVE_MODEL, HYPOTHETICAL | HYPOTHETICAL |
| SPECULATIVE | SPECULATIVE |

The helper also accepts `DataProvenance` and `Classification` members.

---

## 2. Provenance / Derivation Chain

```python
from astra.scientific import ProvenanceNode, DerivationChain, ParameterSource

chain = DerivationChain()
a = ProvenanceNode(node_id="obs-1", classification=Classification.REAL_DATA, source_type="observation")
b = ProvenanceNode(node_id="calc-1", classification=Classification.DERIVED_DATA, source_type="computation", parent_ids=("obs-1",))
chain.add(a); chain.add(b)

chain.ancestors("calc-1")        # → ("obs-1",) deterministically sorted BFS
chain.lineage("calc-1")          # full walk to roots
chain.root_classifications("calc-1")  # classifications of roots
```

Invariants:
- **Append-only** — `add` rejects duplicate `node_id` and unknown `parent_ids`.
- `ProvenanceNode` is frozen; `parent_ids`/`assumptions` are validated, `parameter_sources` maps `str → ParameterSource`.
- `ancestors` BFS is sorted for determinism; `to_dict`/`from_dict` round-trip via `astra.scientific.persistence`.

---

## 3. Assumptions

```python
from astra.scientific import Assumption, AssumptionRegistry
r = AssumptionRegistry()
r.register(Assumption(assumption_id="cosmo-1", statement="Flat ΛCDM", category="cosmological"))
```

- Registry rejects duplicates; `all()` returns deterministic sorted order; no hidden assumptions — every model declares its assumptions explicitly.

---

## 4. Models & Validity

```python
from astra.scientific import ModelDescriptor, ModelRegistry, ValidityDomain, ValidityChecker

reg = ModelRegistry()
reg.register(ModelDescriptor(model_id="astra.evolution.galaxy.v1", name="Galaxy", version="1.0",
                             classification=Classification.SIMULATED_DATA, description="..."))
dom = ValidityDomain(dimensions={"v_kms": (0.0, 300000.0), "z": (0.0, 20.0)})
result = ValidityChecker.check(dom, {"v_kms": 5000.0, "z": 1.0})
# result.is_valid, result.violations, result.closest_boundary, result.warning_code==MODEL_OUTSIDE_VALID_RANGE
# missing dimensions are SKIPPED (never treated as violation), non-finite values are violations
# severity: 1-2 violations → WARNING, 3+ → ERROR
```

- `ModelRegistry.query_by_classification(Classification.SIMULATED_DATA)` etc.

---

## 5. Uncertainty

```python
from astra.scientific import Uncertainty, UncertaintyKind, UNCERTAINTY_UNKNOWN, UncertaintyPropagator

u = Uncertainty(kind=UncertaintyKind.ABSOLUTE, value=0.1)
# UNCERTAINTY_UNKNOWN is singleton sentinel: kind UNKNOWN, value None
UncertaintyPropagator.propagate((u, UNCERTAINTY_UNKNOWN))  # → UNKNOWN (never fabricates)
UncertaintyPropagator.combine_absolute((Uncertainty(...), Uncertainty(...)))  # rss
```

- `Uncertainty` rejects negative, NaN, Inf values; `kind==UNKNOWN` must have `value is None`; `ABSOLUTE`/`RELATIVE` must have finite ≥0.
- Propagation never invents a numeric uncertainty where none exists.

---

## 6. Warnings & Policy

```python
from astra.scientific import ScientificWarning, WarningCode, WarningSeverity, WarningSink, Policy, ScientificConfig
from astra.scientific.policy import enforce

sink = WarningSink()
sink.emit(ScientificWarning(WarningCode.HIGH_UNCERTAINTY, WarningSeverity.WARNING, "σ high"))
cfg = ScientificConfig(policy=Policy.STRICT)
enforce(cfg, sink.all())  # raises ScientificBlockingError if policy says so
# warnings are NEVER dropped — sink still contains them after enforce
```

- `WarningCode`: `MODEL_OUTSIDE_VALID_RANGE`, `HIGH_UNCERTAINTY`, `EXTRAPOLATION_BEYOND_CALIBRATION`, `SPECULATIVE_SCENARIO`, `PROVENANCE_MISMATCH`, `MISSING_PROVENANCE`, `FINITE_NUMERIC_VIOLATION`.
- `WarningSeverity`: `NOTICE < INFO < WARNING < ERROR < BLOCKING`.

Policy matrix (`ScientificConfig.should_reject`):

| Policy | ERROR | BLOCKING | WARN/NOTICE |
|---|---|---|---|
| `STRICT` | ✗ reject | ✗ reject | ✓ allow (kept) |
| `STANDARD` | ✓ allow | ✗ reject | ✓ allow |
| `EXPLORATORY` | ✓ allow | ✓ allow | ✓ allow |
| `SPECULATIVE` | ✓ allow | ✓ allow | ✓ allow |

All allowances still **preserve** warnings in the sink; policy only decides whether to raise.

---

## 7. Scenarios

```python
from astra.scientific import ScenarioIdentity, ScenarioRegistry
reg = ScenarioRegistry()
reg.register(ScenarioIdentity(scenario_id="far-future-wd", description="White dwarf cooling to 1 Gyr",
                              model_config={}, initial_conditions={}, parameter_values={}))
reg.compare("baseline", "far-future-wd")  # never declares a winner, only differences
```

- `ScenarioIdentity` is frozen/immutable; `ScenarioRegistry` rejects silent merges and duplicate ids.

---

## 8. Audit Trail

```python
from astra.scientific import AuditEntry, AuditTrail
trail = AuditTrail()
trail.append(AuditEntry(entry_id="e1", node_id="calc-1", operation="derive", inputs=("obs-1",), outputs=("calc-1",)))
trail.for_node("calc-1")
```

- Append-only, stores **references** (`entry_id`, `node_id`, `inputs`/`outputs` ids), never copies large datasets.

---

## 9. Result Envelope

```python
from astra.scientific import ResultEnvelope, EnvelopeRef
from astra.scientific.provenance import ProvenanceRef

env = ResultEnvelope(envelope_id="r1", value=42.0, classification=Classification.SIMULATED_DATA,
                     provenance=ProvenanceRef("calc-1"), assumption_ids=("cosmo-1",), warnings=())
ref = env.to_ref()  # lightweight EnvelopeRef for hot loops
```

- **Opt-in**: performance-critical kernels use `EnvelopeRef(envelope_id)` only; full `ResultEnvelope` is for boundaries / persistence. Never burdens hot numerical loops.

---

## 10. Integration

```python
from astra.scientific.integration import (
    ExistingProvenanceProvider, UnitProvider, ObservationProvider,
    DataIngestionProvider, EventPublisher, PersistenceHook)
```

- Runtime-checkable `Protocol`s for `astra.core`, `astra.ingestion`, etc. — this layer never re-implements units, observations, or physics.

---

## 11. Persistence

```python
from astra.scientific.persistence import node_to_dict, node_from_dict, envelope_to_dict, envelope_from_dict
d = node_to_dict(node); node2 = node_from_dict(d)  # plain primitives, deterministic
```

---

## 12. Adapters

`astra.scientific.adapters` holds `_Missing*` stubs (`MissingUnits`, `MissingObservation`, `MissingIngestion`, `MissingPhysics`, `MissingNBody`, `MissingUniverse`) that raise `ScientificError` on any attribute access — never a silent no-op.

---

## 13. Errors

```
ScientificError
├── ScientificValidationError
├── ScientificProvenanceError
├── ScientificWarningError
└── ScientificBlockingError
```

---

## 14. Non-Goals

- No physics recomputation, no new units, no new observation sources, no wall-clock in simulation state.
- Hot kernels are not burdened: use `EnvelopeRef` references, not full envelopes, in tight loops.
