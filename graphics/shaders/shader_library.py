"""Built-in shader library for common celestial rendering effects."""

from __future__ import annotations

from typing import Dict, Optional

from .shader_program import ShaderProgram, ShaderSource, ShaderStage
from .uniform import UniformType
from .vertex_format import POSITION_NORMAL_UV, PARTICLE_VERTEX


class ShaderLibrary:
    """Registry of built-in and user-defined shader programs."""

    def __init__(self) -> None:
        self._shaders: Dict[str, ShaderProgram] = {}
        self._register_builtins()

    def get(self, name: str) -> Optional[ShaderProgram]:
        return self._shaders.get(name)

    def register(self, shader: ShaderProgram) -> None:
        self._shaders[shader.name] = shader

    def list_names(self):
        return list(self._shaders.keys())

    def _register_builtins(self) -> None:
        self._shaders["basic_lighting"] = self._create_basic_lighting()
        self._shaders["emissive"] = self._create_emissive()
        self._shaders["atmosphere"] = self._create_atmosphere()
        self._shaders["star_corona"] = self._create_star_corona()
        self._shaders["black_hole_lensing"] = self._create_black_hole_lensing()
        self._shaders["accretion_disk"] = self._create_accretion_disk()
        self._shaders["wormhole"] = self._create_wormhole()
        self._shaders["warp_field"] = self._create_warp_field()
        self._shaders["particle"] = self._create_particle()
        self._shaders["nebula_volumetric"] = self._create_nebula_volumetric()
        self._shaders["debris"] = self._create_debris()
        self._shaders["depth_only"] = self._create_depth_only()

    def _create_basic_lighting(self) -> ShaderProgram:
        p = ShaderProgram("basic_lighting")
        p.set_vertex_source(
            "#version 330 core\n"
            "layout(location=0) in vec3 position;\n"
            "layout(location=1) in vec3 normal;\n"
            "layout(location=2) in vec2 uv;\n"
            "uniform mat4 model;\nuniform mat4 view;\nuniform mat4 projection;\n"
            "out vec3 vNormal;out vec2 vUV;out vec3 vWorldPos;\n"
            "void main(){\n"
            "  vec4 wp=model*vec4(position,1.0);\n"
            "  vWorldPos=wp.xyz;vNormal=mat3(model)*normal;vUV=uv;\n"
            "  gl_Position=projection*view*wp;\n}\n"
        )
        p.set_fragment_source(
            "#version 330 core\n"
            "in vec3 vNormal;in vec2 vUV;in vec3 vWorldPos;\n"
            "uniform vec3 base_color;\nuniform float roughness;\nuniform float metallic;\n"
            "uniform vec3 light_dir;\nuniform vec3 light_color;\n"
            "out vec4 fragColor;\n"
            "void main(){\n"
            "  vec3 n=normalize(vNormal);vec3 l=normalize(light_dir);\n"
            "  float diff=max(dot(n,l),0.0);\n"
            "  vec3 ambient=0.1*base_color;\n"
            "  vec3 diffuse=diff*light_color*base_color;\n"
            "  fragColor=vec4(ambient+diffuse,1.0);\n}\n"
        )
        p.add_uniform("model", UniformType.MAT4)
        p.add_uniform("view", UniformType.MAT4)
        p.add_uniform("projection", UniformType.MAT4)
        p.add_uniform("base_color", UniformType.VEC3, (1.0, 1.0, 1.0))
        p.add_uniform("roughness", UniformType.FLOAT, 0.5)
        p.add_uniform("metallic", UniformType.FLOAT, 0.0)
        p.add_uniform("light_dir", UniformType.VEC3, (1.0, 1.0, 0.0))
        p.add_uniform("light_color", UniformType.VEC3, (1.0, 1.0, 1.0))
        return p

    def _create_emissive(self) -> ShaderProgram:
        p = ShaderProgram("emissive", depth_write=False)
        p.blend_mode = ShaderProgram.BlendMode.ADDITIVE
        p.set_fragment_source(
            "#version 330 core\n"
            "uniform vec3 emissive_color;\nuniform float emissive_intensity;\n"
            "out vec4 fragColor;\n"
            "void main(){fragColor=vec4(emissive_color*emissive_intensity,1.0);}\n"
        )
        p.add_uniform("emissive_color", UniformType.VEC3, (1.0, 1.0, 1.0))
        p.add_uniform("emissive_intensity", UniformType.FLOAT, 1.0)
        return p

    def _create_atmosphere(self) -> ShaderProgram:
        p = ShaderProgram("atmosphere", depth_write=False, two_sided=True)
        p.blend_mode = ShaderProgram.BlendMode.ALPHA
        p.set_fragment_source(
            "#version 330 core\n"
            "uniform vec3 scatter_color;\nuniform float density;\n"
            "uniform float view_height;\nuniform vec3 sun_direction;\n"
            "out vec4 fragColor;\n"
            "void main(){\n"
            "  float angle=dot(normalize(vNormal),sun_direction);\n"
            "  float scatter=pow(max(angle,0.0),2.0)*density;\n"
            "  fragColor=vec4(scatter_color*scatter,scatter*0.8);\n}\n"
        )
        p.add_uniform("scatter_color", UniformType.VEC3, (0.3, 0.5, 0.9))
        p.add_uniform("density", UniformType.FLOAT, 1.0)
        p.add_uniform("view_height", UniformType.FLOAT, 0.0)
        p.add_uniform("sun_direction", UniformType.VEC3, (1.0, 0.0, 0.0))
        return p

    def _create_star_corona(self) -> ShaderProgram:
        p = ShaderProgram("star_corona", depth_write=False)
        p.blend_mode = ShaderProgram.BlendMode.ADDITIVE
        p.set_fragment_source(
            "#version 330 core\n"
            "uniform vec3 star_color;\nuniform float temperature;\n"
            "uniform float luminosity;\nuniform float time;\n"
            "out vec4 fragColor;\n"
            "void main(){\n"
            "  float pulse=1.0+0.05*sin(time*3.0);\n"
            "  fragColor=vec4(star_color*luminosity*pulse,1.0);\n}\n"
        )
        p.add_uniform("star_color", UniformType.VEC3, (1.0, 1.0, 1.0))
        p.add_uniform("temperature", UniformType.FLOAT, 5778.0)
        p.add_uniform("luminosity", UniformType.FLOAT, 1.0)
        p.add_uniform("time", UniformType.FLOAT, 0.0)
        return p

    def _create_black_hole_lensing(self) -> ShaderProgram:
        p = ShaderProgram("black_hole_lensing", depth_test=False, depth_write=False)
        p.blend_mode = ShaderProgram.BlendMode.ADDITIVE
        p.set_fragment_source(
            "#version 330 core\n"
            "uniform float mass;\nuniform float event_horizon_radius;\n"
            "uniform vec3 bh_position;\nuniform float lensing_strength;\n"
            "uniform sampler2D background_texture;\n"
            "out vec4 fragColor;\n"
            "void main(){\n"
            "  fragColor=vec4(0.0,0.0,0.0,1.0);\n}\n"
        )
        p.add_uniform("mass", UniformType.FLOAT, 1e31)
        p.add_uniform("event_horizon_radius", UniformType.FLOAT, 1.0)
        p.add_uniform("bh_position", UniformType.VEC3, (0.0, 0.0, 0.0))
        p.add_uniform("lensing_strength", UniformType.FLOAT, 1.0)
        return p

    def _create_accretion_disk(self) -> ShaderProgram:
        p = ShaderProgram("accretion_disk", depth_write=False, two_sided=True)
        p.blend_mode = ShaderProgram.BlendMode.ADDITIVE
        p.set_fragment_source(
            "#version 330 core\n"
            "uniform float temperature_inner;\nuniform float temperature_outer;\n"
            "uniform float disk_radius;\nuniform float disk_thickness;\n"
            "uniform float time;\n"
            "out vec4 fragColor;\n"
            "void main(){\n"
            "  fragColor=vec4(1.0,0.5,0.1,0.8);\n}\n"
        )
        p.add_uniform("temperature_inner", UniformType.FLOAT, 1000000.0)
        p.add_uniform("temperature_outer", UniformType.FLOAT, 10000.0)
        p.add_uniform("disk_radius", UniformType.FLOAT, 100.0)
        p.add_uniform("disk_thickness", UniformType.FLOAT, 0.1)
        p.add_uniform("time", UniformType.FLOAT, 0.0)
        return p

    def _create_wormhole(self) -> ShaderProgram:
        p = ShaderProgram("wormhole", depth_test=False, depth_write=False)
        p.blend_mode = ShaderProgram.BlendMode.ADDITIVE
        p.set_fragment_source(
            "#version 330 core\n"
            "uniform float throat_radius;\nuniform float distortion_strength;\n"
            "uniform vec3 wormhole_color;\nuniform float time;\n"
            "out vec4 fragColor;\n"
            "void main(){\n"
            "  fragColor=vec4(wormhole_color,0.5);\n}\n"
        )
        p.add_uniform("throat_radius", UniformType.FLOAT, 1.0)
        p.add_uniform("distortion_strength", UniformType.FLOAT, 1.0)
        p.add_uniform("wormhole_color", UniformType.VEC3, (0.2, 0.4, 0.9))
        p.add_uniform("time", UniformType.FLOAT, 0.0)
        return p

    def _create_warp_field(self) -> ShaderProgram:
        p = ShaderProgram("warp_field", depth_write=False)
        p.blend_mode = ShaderProgram.BlendMode.ADDITIVE
        p.set_fragment_source(
            "#version 330 core\n"
            "uniform float field_strength;\nuniform float field_radius;\n"
            "uniform vec3 warp_color;\nuniform float time;\n"
            "out vec4 fragColor;\n"
            "void main(){\n"
            "  fragColor=vec4(warp_color*field_strength,0.3);\n}\n"
        )
        p.add_uniform("field_strength", UniformType.FLOAT, 1.0)
        p.add_uniform("field_radius", UniformType.FLOAT, 5.0)
        p.add_uniform("warp_color", UniformType.VEC3, (0.1, 0.3, 0.8))
        p.add_uniform("time", UniformType.FLOAT, 0.0)
        return p

    def _create_particle(self) -> ShaderProgram:
        p = ShaderProgram("particle", depth_write=False)
        p.blend_mode = ShaderProgram.BlendMode.ADDITIVE
        p.set_vertex_source(
            "#version 330 core\n"
            "layout(location=0) in vec3 position;\n"
            "layout(location=1) in vec3 velocity;\n"
            "layout(location=2) in float size;\n"
            "layout(location=3) in float life;\n"
            "layout(location=4) in vec4 color;\n"
            "uniform mat4 view;uniform mat4 projection;\n"
            "uniform float global_size;\n"
            "out float vLife;out vec4 vColor;\n"
            "void main(){\n"
            "  vLife=life;vColor=color;\n"
            "  gl_Position=projection*view*vec4(position,1.0);\n"
            "  gl_PointSize=size*global_size;\n}\n"
        )
        p.set_fragment_source(
            "#version 330 core\n"
            "in float vLife;in vec4 vColor;\nout vec4 fragColor;\n"
            "void main(){\n"
            "  vec2 c=gl_PointCoord*2.0-1.0;\n"
            "  float r=dot(c,c);\n"
            "  if(r>1.0)discard;\n"
            "  float alpha=vColor.a*vLife*(1.0-r);\n"
            "  fragColor=vec4(vColor.rgb,alpha);\n}\n"
        )
        p.add_uniform("view", UniformType.MAT4)
        p.add_uniform("projection", UniformType.MAT4)
        p.add_uniform("global_size", UniformType.FLOAT, 1.0)
        return p

    def _create_nebula_volumetric(self) -> ShaderProgram:
        p = ShaderProgram("nebula_volumetric", depth_write=False, two_sided=True)
        p.blend_mode = ShaderProgram.BlendMode.ALPHA
        p.set_fragment_source(
            "#version 330 core\n"
            "uniform vec3 nebula_color;\nuniform float density;\n"
            "uniform float noise_scale;\nuniform float time;\n"
            "out vec4 fragColor;\n"
            "void main(){\n"
            "  fragColor=vec4(nebula_color*density,density*0.5);\n}\n"
        )
        p.add_uniform("nebula_color", UniformType.VEC3, (0.3, 0.1, 0.5))
        p.add_uniform("density", UniformType.FLOAT, 0.5)
        p.add_uniform("noise_scale", UniformType.FLOAT, 1.0)
        p.add_uniform("time", UniformType.FLOAT, 0.0)
        return p

    def _create_debris(self) -> ShaderProgram:
        p = ShaderProgram("debris")
        p.set_fragment_source(
            "#version 330 core\n"
            "uniform vec3 base_color;\nuniform float roughness;\n"
            "out vec4 fragColor;\n"
            "void main(){fragColor=vec4(base_color,1.0);}\n"
        )
        p.add_uniform("base_color", UniformType.VEC3, (0.5, 0.45, 0.4))
        p.add_uniform("roughness", UniformType.FLOAT, 0.9)
        return p

    def _create_depth_only(self) -> ShaderProgram:
        p = ShaderProgram("depth_only")
        p.set_vertex_source(
            "#version 330 core\n"
            "layout(location=0) in vec3 position;\n"
            "uniform mat4 model;uniform mat4 view;uniform mat4 projection;\n"
            "void main(){gl_Position=projection*view*model*vec4(position,1.0);}\n"
        )
        p.set_fragment_source(
            "#version 330 core\nout vec4 fragColor;\nvoid main(){fragColor=vec4(1.0);}\n"
        )
        p.add_uniform("model", UniformType.MAT4)
        p.add_uniform("view", UniformType.MAT4)
        p.add_uniform("projection", UniformType.MAT4)
        return p
