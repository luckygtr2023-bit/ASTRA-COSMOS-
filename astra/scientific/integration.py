"""ASTRA Scientific — cross-system integration Protocols (§2.30, §3.14).

Lightweight, runtime_checkable protocols that let the scientific layer
consume existing ASTRA subsystems without duplicating them.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ExistingProvenanceProvider(Protocol):
    def get_provenance(self, object_id: str) -> Any: ...


@runtime_checkable
class UnitProvider(Protocol):
    def unit_of(self, quantity_name: str) -> str: ...
    def dimension_of(self, quantity_name: str) -> str: ...
    def convert(self, value: float, from_unit: str, to_unit: str) -> float: ...


@runtime_checkable
class ObservationProvider(Protocol):
    def observation_timestamp(self, observation_id: str) -> Any: ...
    def is_observed(self, object_id: str) -> bool: ...


@runtime_checkable
class DataIngestionProvider(Protocol):
    def source_of(self, dataset_id: str) -> Any: ...


@runtime_checkable
class EventPublisher(Protocol):
    def publish(self, topic: str, payload: dict) -> None: ...


@runtime_checkable
class PersistenceHook(Protocol):
    def save(self, key: str, payload: dict) -> None: ...
    def load(self, key: str) -> dict | None: ...
