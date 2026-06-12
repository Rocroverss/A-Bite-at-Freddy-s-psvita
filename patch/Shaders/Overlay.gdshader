shader_type canvas_item;

uniform float satAmt;

vec4 overlay(vec4 base, vec4 blend){
	vec4 limit = step(0.5, base);
	return mix(2.0 * base * blend, 1.0 - 2.0 * (1.0 - base) * (1.0 - blend), limit);
}

void fragment() {
	// Overlay
	vec4 ovr_color = mix(textureLod(SCREEN_TEXTURE, SCREEN_UV, 0.0), overlay(textureLod(SCREEN_TEXTURE, SCREEN_UV, 0.0), COLOR), 1.0);
	//COLOR = mix(textureLod(SCREEN_TEXTURE, SCREEN_UV, 0.0), overlay(textureLod(SCREEN_TEXTURE, SCREEN_UV, 0.0), COLOR), 1.0);
	
	// Saturation
	//vec4 tex_color = texture(SCREEN_TEXTURE, SCREEN_UV) + ovr_color;
	COLOR.rgb = mix(vec3(dot(ovr_color.rgb, vec3(0.299, 0.587, 0.114))), ovr_color.rgb, satAmt);
	COLOR.a = ovr_color.a;
}
