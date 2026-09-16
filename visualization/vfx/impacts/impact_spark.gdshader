shader_type particles;
render_mode keep_data;
void start(){ VELOCITY = vec3(randf()*4.0-2.0, randf()*6.0, randf()*4.0-2.0); COLOR = vec4(1.0,0.85,0.5,1.0); }
void process(){ VELOCITY += vec3(0.0, -9.8*DELTA, 0.0); }
