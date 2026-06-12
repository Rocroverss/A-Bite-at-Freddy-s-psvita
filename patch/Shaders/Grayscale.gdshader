shader_type canvas_item;

uniform float amount : hint_range(0.0, 1.0) = 1.0;

void fragment() {
	vec4 pixelColor = texture(TEXTURE, UV);
	//float brightness = (pixelColor.r + pixelColor.g + pixelColor.b) / 3.0;
	float brightness = dot(pixelColor.rgb, vec3(0.299, 0.587, 0.114));
	vec4 grayScale = vec4(brightness, brightness, brightness, pixelColor.a);
	COLOR = mix(pixelColor, grayScale, amount);
}
