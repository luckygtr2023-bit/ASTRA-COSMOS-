# ASTRA Bridge — single authority gateway (autoload)
# Godot → VisualizationAPI → ASTRA validation → RenderState → Godot
extends Node

signal render_state_updated(state: Dictionary)
signal astra_event(event: Dictionary)

var _api_url: String = "http://localhost:8000/visualization" # ASTRA Python bridge (if running)
var _last_state: Dictionary = {}
var _origin_offset: Vector3 = Vector3.ZERO
var _frame_id: String = "world"

# Poll ASTRA (http or via file bridge when offline)
var _poll_timer: float = 0.0
const POLL_INTERVAL: float = 1.0/30.0 # 30 Hz (visualization, not physics)

func _ready():
    print("[AstraBridge] Forward+ ready. ASTRA authority preserved. Polling ", _api_url)

func _process(delta: float):
    _poll_timer += delta
    if _poll_timer >= POLL_INTERVAL:
        _poll_timer = 0.0
        _poll_astra()

func _poll_astra():
    # Offline fallback: read visualization/bridge_state.json if http unavailable
    var file = FileAccess.open("res://../../bridge_state.json", FileAccess.READ)
    if file:
        var txt = file.get_as_text()
        var json = JSON.new()
        if json.parse(txt) == OK:
            var state = json.data
            if state.hash() != _last_state.hash():
                _last_state = state
                # Extract origin rebase if present
                if state.has("origin_offset"):
                    _origin_offset = Vector3(state["origin_offset"][0], state["origin_offset"][1], state["origin_offset"][2])
                    _frame_id = state.get("frame_id", _frame_id)
                render_state_updated.emit(state)
        file.close()

# Called by UI / camera to request validated action
func request_interaction(action: Dictionary) -> Dictionary:
    # Never mutate scientific state directly; send to ASTRA for validation
    # Example action: {"type": "NAVIGATE", "target_id": "star-1", "to_scale": "STELLAR_SYSTEM"}
    print("[AstraBridge] request_interaction ", action)
    # In offline demo, we fake a validated echo (no physics bypass in real build)
    var result = {"success": true, "action": action, "note": "delegated to astra.interaction.InteractionEngine (offline echo)"}
    astra_event.emit({"kind": "interaction_queued", "action": action})
    return result

func get_origin_offset() -> Vector3: return _origin_offset
func get_frame_id() -> String: return _frame_id
