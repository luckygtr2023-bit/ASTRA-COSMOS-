"""ASTRA Rendering Architecture - authoritative boundary.

ASTRA simulation state is authoritative.
Rendering is a consumer.

    AUTHORITATIVE SIMULATION STATE
                ↓
            RENDER STATE
                ↓
           RENDER CONTEXT
                ↓
             RENDERER
                ↓
           VISUAL OUTPUT

This package is renderer-independent and Blender-independent.
Future layers (Graphics/VFX, Blender Bridge) consume RenderState / RenderContext
without ever mutating simulation truth.
"""

from astra.rendering.exceptions import (
    RenderError,
    RenderStateError,
    CameraError,
    CoordinateConversionError,
    VisibilityError,
    LODError,
    CelestialRenderError,
    PlanetaryRenderError,
    LightingError,
    SpacetimeRenderError,
    TemporalRenderError,
    PerformanceError,
)

from astra.rendering.types import (
    ProjectionType,
    QualityLevel,
    LODLevel,
    VisibilityState,
    TemporalRenderMode,
    DamageVisualState,
    LightType,
    RenderObjectKind,
    Viewport,
    QUALITY_PRESETS,
    LOD_ORDER,
)

from astra.rendering.render_state import (
    MaterialRef,
    RenderObject,
    RenderState,
)

from astra.rendering.render_context import (
    RenderingConstraints,
    RenderContext,
)

from astra.rendering.camera import (
    CameraMode,
    Camera,
    CameraController,
)

from astra.rendering.coordinates import (
    FloatingOriginConfig,
    FloatingOriginRenderer,
    world_to_render,
    render_to_world,
    world_to_camera_relative,
    render_to_camera_relative,
    batch_world_to_render,
    apply_render_origin_to_state,
)

from astra.rendering.culling import (
    Plane,
    Frustum,
    CullingConfig,
    VisibilitySystem,
)

from astra.rendering.lod import (
    LODConfig,
    LODSelector,
)

from astra.rendering.celestial import (
    CelestialRenderDescriptor,
    describe_celestial,
    celestial_to_render_object,
)

from astra.rendering.planetary import (
    TerrainDescriptor,
    AtmosphereDescriptor,
    OceanDescriptor,
    CloudDescriptor,
    PlanetarySurfaceDescriptor,
    PlanetaryRenderDescriptor,
)

from astra.rendering.lighting import (
    LightSource,
    ShadowConfig,
    EclipseParams,
    LightingState,
)

from astra.rendering.spacetime import (
    BlackHoleRenderParams,
    SpacetimeCurvatureVisual,
    WormholeRenderParams,
    WarpRenderParams,
    black_hole_state_to_render_params,
    wormhole_metric_to_render_params,
    warp_metric_to_render_params,
)

from astra.rendering.destruction import (
    FragmentVisual,
    EjectaVisual,
    DebrisVisual,
    DestructionVisualState,
    destruction_result_to_visual,
    apply_destruction_visual_to_object,
)

from astra.rendering.temporal import (
    ObservedRenderRecord,
    compute_lookback,
    observed_state_to_render_record,
    apply_observed_state_to_render_object,
    apply_temporal_mode_to_render_state,
)

from astra.rendering.performance import (
    PerformanceBudget,
    BatchGroup,
    PerformanceManager,
)

from astra.rendering.pipeline import (
    PipelineConfig,
    RenderFrame,
    RenderPipeline,
    scene_graph_adapter,
    celestial_adapter,
)

__all__ = [
    # exceptions
    "RenderError", "RenderStateError", "CameraError", "CoordinateConversionError",
    "VisibilityError", "LODError", "CelestialRenderError", "PlanetaryRenderError",
    "LightingError", "SpacetimeRenderError", "TemporalRenderError", "PerformanceError",
    # types
    "ProjectionType", "QualityLevel", "LODLevel", "VisibilityState", "TemporalRenderMode",
    "DamageVisualState", "LightType", "RenderObjectKind", "Viewport", "QUALITY_PRESETS", "LOD_ORDER",
    # render state
    "MaterialRef", "RenderObject", "RenderState",
    # context
    "RenderingConstraints", "RenderContext",
    # camera
    "CameraMode", "Camera", "CameraController",
    # coordinates
    "FloatingOriginConfig", "FloatingOriginRenderer", "world_to_render", "render_to_world",
    "world_to_camera_relative", "render_to_camera_relative", "batch_world_to_render", "apply_render_origin_to_state",
    # culling
    "Plane", "Frustum", "CullingConfig", "VisibilitySystem",
    # lod
    "LODConfig", "LODSelector",
    # celestial
    "CelestialRenderDescriptor", "describe_celestial", "celestial_to_render_object",
    # planetary
    "TerrainDescriptor", "AtmosphereDescriptor", "OceanDescriptor", "CloudDescriptor",
    "PlanetarySurfaceDescriptor", "PlanetaryRenderDescriptor",
    # lighting
    "LightSource", "ShadowConfig", "EclipseParams", "LightingState",
    # spacetime
    "BlackHoleRenderParams", "SpacetimeCurvatureVisual", "WormholeRenderParams", "WarpRenderParams",
    "black_hole_state_to_render_params", "wormhole_metric_to_render_params", "warp_metric_to_render_params",
    # destruction
    "FragmentVisual", "EjectaVisual", "DebrisVisual", "DestructionVisualState",
    "destruction_result_to_visual", "apply_destruction_visual_to_object",
    # temporal
    "ObservedRenderRecord", "compute_lookback", "observed_state_to_render_record",
    "apply_observed_state_to_render_object", "apply_temporal_mode_to_render_state",
    # performance
    "PerformanceBudget", "BatchGroup", "PerformanceManager",
    # pipeline
    "PipelineConfig", "RenderFrame", "RenderPipeline", "scene_graph_adapter", "celestial_adapter",
]

__version__ = "0.1.0"
