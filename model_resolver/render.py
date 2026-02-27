from OpenGL.GL import *  # pyright: ignore[reportWildcardImportFromLibrary]
from OpenGL.GLUT import *  # pyright: ignore[reportWildcardImportFromLibrary]
from OpenGL.GLU import *  # pyright: ignore[reportWildcardImportFromLibrary]

from dataclasses import dataclass, field
from beet import Context
from model_resolver.utils import LightOptions


@dataclass
class Render:
    ctx: Context


    light: LightOptions = field(default_factory=LightOptions)


    def __enter__(self):
        glutInit()
        glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_DEPTH)  # type: ignore
        glutInitWindowSize(512, 512)
        glutInitWindowPosition(100, 100)
        glutCreateWindow(b"Isometric View")
        glutHideWindow()
        glutSetOption(GLUT_ACTION_ON_WINDOW_CLOSE, GLUT_ACTION_GLUTMAINLOOP_RETURNS)
        glClearColor(0.0, 0.0, 0.0, 0.0)

        # Enable lighting
        glLightfv(GL_LIGHT0, GL_POSITION, self.light.minecraft_light_position)
        glLightfv(GL_LIGHT0, GL_AMBIENT, [self.light.minecraft_ambient_light] * 4)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [self.light.minecraft_light_power] * 4)

        glLightfv(GL_LIGHT1, GL_POSITION, [0.0, 0.0, 10.0, 0.0])
        glLightfv(GL_LIGHT1, GL_DIFFUSE, [1.0] * 4)

        glutDisplayFunc(self.display)
        glutIdleFunc(self.display)
        glutReshapeFunc(self.reshape)

        glutMainLoop()

    def __exit__(self, exc_type, exc, tb):
        pass