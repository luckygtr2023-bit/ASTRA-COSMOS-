# Camera System — orbital / cinematic / scientific / free / observation / spacecraft / replay
class_name CameraSystem
extends Node3D

enum Mode { ORBITAL, FREE, SPACECRAFT, OBSERVATION, CINEMATIC, REPLAY }

@export var mode: Mode = Mode.ORBITAL
@export var target: Node3D
@export var distance: float = 20.0
@export var smooth: float = 6.0

var _cam: Camera3D
var _yaw: float = 0.0
var _pitch: float = -0.2

func _ready():
    _cam = Camera3D.new()
    _cam.fov = 60.0
    add_child(_cam)
    set_process(true)

func _process(delta: float):
    match mode:
        Mode.ORBITAL:
            _update_orbital(delta)
        Mode.FREE:
            _update_free(delta)
        Mode.CINEMATIC:
            _update_cinematic(delta)

func _update_orbital(delta: float):
    if not target: return
    var target_pos = target.global_position
    var offset = Vector3(sin(_yaw), sin(_pitch), cos(_yaw)) * distance
    var desired = target_pos + offset
    global_position = global_position.lerp(desired, clamp(delta*smooth,0,1))
    look_at(target_pos, Vector3.UP)

func _update_free(delta: float):
    var input = Vector3.ZERO
    if Input.is_action_pressed("free_camera_forward"): input.z -= 1
    if Input.is_action_pressed("orbit_modifier"): _yaw += 0.01

func _update_cinematic(delta: float):
    # Path follows via Tween on parent; placeholder
    pass

func set_mode(m: Mode): mode = m
func set_target(n: Node3D): target = n
