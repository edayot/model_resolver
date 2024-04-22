import sys
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from PIL import Image

# Cube vertices
vertices = (
    (1, -1, -1),
    (1, 1, -1),
    (-1, 1, -1),
    (-1, -1, -1),
    (1, -1, 1),
    (1, 1, 1),
    (-1, -1, 1),
    (-1, 1, 1)
)

# Cube edges
edges = (
    (0, 1),
    (0, 3),
    (0, 4),
    (2, 1),
    (2, 3),
    (2, 7),
    (6, 3),
    (6, 4),
    (6, 7),
    (5, 1),
    (5, 4),
    (5, 7)
)

# Define textures
textures = []

angleX = 0
angleY = 0

def load_texture(image_path):
    img = Image.open(image_path)
    img_data = img.tobytes("raw", "RGBX", 0, -1)
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width, img.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)

    
    return tex_id

def draw_cube():
    glBegin(GL_QUADS)
    for i, surface in enumerate([(0, 1, 2, 3), (3, 2, 7, 6), (6, 7, 5, 4), (4, 5, 1, 0), (1, 5, 7, 2), (4, 0, 3, 6)]):
        glTexCoord2f(0, 0); glVertex3fv(vertices[surface[0]])
        glTexCoord2f(1, 0); glVertex3fv(vertices[surface[1]])
        glTexCoord2f(1, 1); glVertex3fv(vertices[surface[2]])
        glTexCoord2f(0, 1); glVertex3fv(vertices[surface[3]])
    glEnd()

def display():
    global angleX, angleY

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glTranslatef(0, 0, -3)
    glRotatef(35.264, 1, 0, 0)  # Rotate 45 degrees about X axis
    glRotatef(45, 0, 1, 0)       # Rotate 45 degrees about Y axis
    glRotatef(angleX, 1, 0, 0)
    glRotatef(angleY, 0, 1, 0)

    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, textures[0])
    glColor3f(1.0, 1.0, 1.0)
    draw_cube()
    glDisable(GL_TEXTURE_2D)

    glutSwapBuffers()

def init():
    global textures
    glEnable(GL_DEPTH_TEST)
    glClearColor(0.0, 0.0, 0.0, 1.0)
    textures.append(load_texture("texture.png"))  # Change "texture.png" to your texture file path
    textures.append(load_texture("texture.png"))  # Change "texture.png" to your texture file path
    print(textures)

def reshape(width, height):
    glViewport(0, 0, width, height)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(-2, 2, -2, 2, -10, 10)  # Set up an orthographic projection
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

def keyboard(key, x, y):
    global angleX, angleY
    if key == b'q':
        sys.exit(0)
    elif key == b'a':
        angleY -= 5
    elif key == b'd':
        angleY += 5
    elif key == b'w':
        angleX -= 5
    elif key == b's':
        angleX += 5
    glutPostRedisplay()

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_DEPTH)
    glutInitWindowSize(512, 512)
    glutInitWindowPosition(100, 100)
    glutCreateWindow(b"Isometric View")
    glutSetOption(GLUT_ACTION_ON_WINDOW_CLOSE, GLUT_ACTION_CONTINUE_EXECUTION)
    init()
    glutDisplayFunc(display)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(keyboard)
    glutIdleFunc(display)
    glutMainLoop()

if __name__ == "__main__":
    main()
