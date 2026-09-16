# Telemetry — rendering diagnostics (fps, draw calls, shader compile time)
extends Node
var _fps_history: Array = []
func _process(delta: float):
    if Engine.get_frames_drawn() % 60 == 0:
        var fps = Engine.get_frames_per_second()
        _fps_history.append(fps)
        if _fps_history.size() > 60: _fps_history.remove_at(0)
        var avg = 0.0
        for v in _fps_history: avg += v
        avg /= _fps_history.size()
        print("[Telemetry] fps=", fps, " avg60=", snapped(avg,0.1), " objects=", get_tree().get_nodes_in_group("astra_objects").size())
