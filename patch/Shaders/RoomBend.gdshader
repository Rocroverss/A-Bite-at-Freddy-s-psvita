shader_type canvas_item;

uniform float amountY: hint_range(0.0, 3.0);
uniform float amountX: hint_range(0.0, 3.0);
const vec2 center = vec2(0.5, 0.5);

void fragment() {
	vec2 dist = vec2(length(SCREEN_UV.x - center), length(SCREEN_UV.y - center));
	
	float smoothDir = -1.0 * sign(SCREEN_UV.y - center.x);
	float smoothDir2 = -1.0 * sign(SCREEN_UV.x - center.x);
	
	vec2 uv = vec2(SCREEN_UV.x + dist.x * (((dist.x * 0.2) * (dist.x)) * smoothDir2 * amountX), SCREEN_UV.y + dist.x * (((dist.x * 0.2) * (dist.y)) * smoothDir * amountY));
	
	COLOR = texture(SCREEN_TEXTURE, uv);
}
