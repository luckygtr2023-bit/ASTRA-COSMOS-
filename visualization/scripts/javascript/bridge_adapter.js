// ASTRA Visualization — JavaScript adapter (offline tooling, not runtime)
// Purpose: convert ASTRA Python bridge_state.json → Godot JSON (validation only)
// Not used in Godot rendering loop.
import fs from "fs";
const src = "bridge_state.json";
const dst = "visualization/godot/bridge_state.json";
if(fs.existsSync(src)){
  const data = JSON.parse(fs.readFileSync(src,"utf8"));
  // Sanitize: ensure positions are finite, classification is known
  const allowed = ["REAL_DATA","DERIVED_DATA","SIMULATED_DATA","THEORETICAL","HYPOTHETICAL","SPECULATIVE"];
  for(const obj of data.objects || []){
    if(!allowed.includes(obj.classification)) throw new Error("unknown classification "+obj.classification);
    if(obj.position.some(v=>!isFinite(v))) throw new Error("non-finite position");
  }
  fs.writeFileSync(dst, JSON.stringify(data, null, 2));
  console.log(`[bridge_adapter] wrote ${dst} with ${data.objects.length} objects`);
} else {
  console.log("[bridge_adapter] no bridge_state.json, skipping");
}
