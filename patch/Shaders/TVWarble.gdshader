shader_type canvas_item;

// Shift color layers around, like in fbaf cutscenes!!!
uniform float movement = 0.0;

uniform float wave_speed = 1.2; //wave loop speed
uniform float wave_freq = 2.0; //wave vertical freq
uniform float wave_width = 0.1; //wave width 

vec2 uv_curve(vec2 uv) {
	uv = (uv - 0.5) * 1.89;
	
	//Adding in below will do curve thing
	uv.x *= 1.0 + pow(abs(uv.y) / 4.0, 2.0);
	uv.y *= 1.0 + pow(abs(uv.x) / 4.0, 2.0);
	
	uv /= 1.0;
	
	vec2 wave_uv_offset;
	wave_uv_offset.x = cos((TIME*wave_speed)+uv.x+uv.y*wave_freq*2.0)*wave_width*0.01;
	float wave_time = sin(TIME/5.0);
	
	uv = (uv / 2.0) + 0.5;
	//uv += wave_uv_offset * wave_time;
	return uv;
}

void fragment() {
	vec2 scale_UV = UV;
	//vec2 wave_uv_offset;
	//wave_uv_offset.x = cos((TIME*wave_speed)+UV.x+UV.y*wave_freq*2.0)*wave_width*0.01;
	//COLOR = vec4(wave_uv_offset,0.0,1.0);
	//COLOR = texture(TEXTURE,scale_UV+wave_uv_offset);
	
	float PI = 3.14159;
	float r = texture(TEXTURE, uv_curve(UV) + vec2(SCREEN_PIXEL_SIZE.x*(sin(TIME * movement * 0.25) - 0.5)), 0.0).r;
	float g = texture(TEXTURE, uv_curve(UV) + vec2(SCREEN_PIXEL_SIZE.x*(sin(TIME * movement*0.1) - 0.3)), 0.0).g;
	float b = texture(TEXTURE, uv_curve(UV) + vec2(SCREEN_PIXEL_SIZE.x*(sin(TIME * movement*0.2) - 0.6)), 0.0).b;
	
	COLOR = vec4(r, g, b, 1.0);
}
