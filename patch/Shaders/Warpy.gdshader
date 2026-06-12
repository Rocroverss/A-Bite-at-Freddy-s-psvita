shader_type canvas_item;

uniform sampler2D distortTex;
uniform float amt: hint_range(0.0, 1.0) = 0.0;
//uniform float amt = 0.0;
//uniform float rotation = 1.0;

void fragment() {
	//vec2 normalUV = texture(SCREEN_TEXTURE, SCREEN_UV);
	//vec2 distortUV = SCREEN_UV + texture(distortTex, UV * amt).r * 0.05 * amt;
	vec2 distortUV = SCREEN_UV + texture(distortTex, UV * amt).r * 0.02 * amt;
	vec4 screenColor = texture(SCREEN_TEXTURE, distortUV);
	COLOR = screenColor;
	
	// Rotation shader test
	//vec2 rel = distortUV - vec2(0.5, 0.5);
	//float angle = length(rel) * rotation;
	//mat2 rot = mat2(vec2(cos(angle), -sin(angle)), vec2(sin(angle), cos(angle)));
	//rel = rot * rel;
	//distortUV = clamp(rel + vec2(0.5, 0.5), vec2(0.0, 0.0), vec2(1.0, 1.0));
	//COLOR.rgb = textureLod(SCREEN_TEXTURE, distortUV, 0.0).rgb;
}
