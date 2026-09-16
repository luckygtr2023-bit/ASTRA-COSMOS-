shader_type particles;
render_mode keep_data;

void start() {
    // Deterministic seed per particle; no random — use RANDOM_SEED
    uint seed = RANDOM_SEED;
    float rx = float(seed % 100u) / 100.0;
    float ry = float((seed / 100u) % 100u) / 100.0;
    float rz = float((seed / 10000u) % 100u) / 100.0;
    VELOCITY = vec3(rx*4.0-2.0, ry*6.0 + 2.0, rz*4.0-2.0);
    COLOR = vec4(1.0, 0.85, 0.5, 1.0);
    ACTIVE = true;
}
void process() {
    VELOCITY += vec3(0.0, -9.8 * DELTA, 0.0);
    COLOR.a *= 1.0 - DELTA * 0.5;
}
