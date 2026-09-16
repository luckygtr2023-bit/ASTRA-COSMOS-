# ASTRA Procedural — FastNoiseLite wrapper (GDScript, not C++)
# Generates tilable noise for planet heightmaps at runtime or bake-time.
class_name ProceduralNoise
extends Resource

@export var seed: int = 1337
@export var frequency: float = 0.01
@export var fractal_octaves: int = 5

var _noise: FastNoiseLite

func _init():
    _noise = FastNoiseLite.new()
    _noise.seed = seed
    _noise.frequency = frequency
    _noise.fractal_octaves = fractal_octaves
    _noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH

func get_height(uv: Vector2) -> float:
    return _noise.get_noise_2d(uv.x * 1024.0, uv.y * 1024.0) * 0.5 + 0.5

func bake_to_image(size: int) -> Image:
    var img = Image.create(size, size, false, Image.FORMAT_RF)
    for y in size:
        for x in size:
            var h = get_height(Vector2(float(x)/size, float(y)/size))
            img.set_pixel(x, y, Color(h, h, h))
    return img
