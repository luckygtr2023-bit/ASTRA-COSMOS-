"""ASTRA Interaction — missing adapters (fail explicitly, never silent)."""

from __future__ import annotations

from .errors import InteractionError


class _Missing:
    def __init__(self, name: str):
        self._name = name
    def __getattr__(self, _):
        raise InteractionError(f"interaction dependency unavailable: {self._name}")

class MissingCore(_Missing):
    def __init__(self): super().__init__("core (Engine/Clock/EventBus)")

class MissingWorld(_Missing):
    def __init__(self): super().__init__("world (Hierarchy/SceneGraph/Spatial)")

class MissingFrames(_Missing):
    def __init__(self): super().__init__("frame registry / origin rebaser")

class MissingSpacecraft(_Missing):
    def __init__(self): super().__init__("spacecraft / motion")

class MissingTemporal(_Missing):
    def __init__(self): super().__init__("temporal / observation")

class MissingTravel(_Missing):
    def __init__(self): super().__init__("travel engine (theoretical/warp/wormhole)")

class MissingScientific(_Missing):
    def __init__(self): super().__init__("scientific classification")
