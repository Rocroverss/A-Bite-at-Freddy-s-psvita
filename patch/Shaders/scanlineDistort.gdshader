shader_type canvas_item;

uniform float amount: hint_range(0.0, 1.0) = 1.0;
// Good amount is 0.995

void fragment(){
	COLOR = mix(textureLod(SCREEN_TEXTURE, SCREEN_UV * amount, 0.0), COLOR, 0.05);
}