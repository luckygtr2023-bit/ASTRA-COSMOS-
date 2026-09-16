namespace astra::meshes { struct Mesh{ int verts; }; Mesh icosphere(int lod){ return {42<<(lod*2)}; } }
