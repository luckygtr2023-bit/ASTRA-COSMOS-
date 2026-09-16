// Node — asset manifest generator (tooling only, zero npm deps)
// Generates visualization/assets/manifest.json for Godot ResourceLoader streaming.
import fs from "fs";
import path from "path";
const root = "visualization/assets";
const manifest = { generated: new Date().toISOString(), assets: [] };
function walk(dir){
  for(const ent of fs.readdirSync(dir, {withFileTypes:true})){
    const p = path.join(dir, ent.name);
    if(ent.isDirectory()) walk(p);
    else {
      const stat = fs.statSync(p);
      manifest.assets.push({ path: p.replace(/\\/g,"/"), size: stat.size, mtime: stat.mtimeMs });
    }
  }
}
if(fs.existsSync(root)) walk(root);
fs.writeFileSync(path.join(root,"manifest.json"), JSON.stringify(manifest, null, 2));
console.log(`[manifest] ${manifest.assets.length} assets`);
