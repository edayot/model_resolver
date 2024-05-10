#version 330

#if defined VERTEX_SHADER

in vec3 in_position;
in vec3 in_normal;
in vec2 in_texcoord_0;

uniform mat4 m_model;
uniform mat4 m_camera;
uniform mat4 m_proj;

out vec3 pos;
out vec3 normal;
out vec2 uv;

void main() {
    mat4 m_view = m_camera * m_model;
    vec4 p = m_view * vec4(in_position, 1.0);
    gl_Position =  m_proj * p;
    mat3 m_normal = inverse(transpose(mat3(m_view)));
    normal = m_normal * normalize(in_normal);
    uv = in_texcoord_0;
    pos = p.xyz;
}

#elif defined FRAGMENT_SHADER

out vec4 fragColor;

uniform sampler2D texture0;
uniform sampler2D texture1;
uniform sampler2D texture2;
uniform sampler2D texture3;
uniform sampler2D texture4;
uniform sampler2D texture5;

in vec3 pos;
in vec3 normal;
in vec2 uv;

void main() {
    vec3 absNormal = abs(normal);
    int faceIndex = int(absNormal.x > absNormal.y && absNormal.x > absNormal.z ? normal.x < 0.0 ? 0 : 1 :
                        absNormal.y > absNormal.z ? normal.y < 0.0 ? 2 : 3 : normal.z < 0.0 ? 4 : 5);
    if (faceIndex == 0) {
        fragColor = texture(texture0, uv);
    } else if (faceIndex == 1) {
        fragColor = texture(texture1, uv);
    } else if (faceIndex == 2) {
        fragColor = texture(texture2, uv);
    } else if (faceIndex == 3) {
        fragColor = texture(texture3, uv);
    } else if (faceIndex == 4) {
        fragColor = texture(texture4, uv);
    } else {
        fragColor = texture(texture5, uv);
    }
}
#endif
