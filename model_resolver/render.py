from OpenGL.GL import *  # type: ignore
from OpenGL.GLUT import *  # type: ignore
from OpenGL.GLU import *  # type: ignore
from model_resolver.my_glutinit import glutInit

from PIL import Image

from beet import Context, Texture
from beet.contrib.vanilla import Vanilla, Release

from math import cos, sin, pi, sqrt
from typing import Any
import hashlib
from model_resolver.utils import load_textures, ModelResolverOptions
import logging


class RenderError(Exception):
    pass


class Render:
    """

    model = {"model:model":{
        'gui_light': 'side',
        'display': {
            'gui': {'rotation': [30, 225, 0], 'translation': [0, 0, 0], 'scale': [0.625, 0.625, 0.625]},
            'ground': {'rotation': [0, 0, 0], 'translation': [0, 3, 0], 'scale': [0.25, 0.25, 0.25]},
            'fixed': {'rotation': [-90, 0, 0], 'translation': [0, 0, -16], 'scale': [2.001, 2.001, 2.001]},
            'thirdperson_righthand': {'rotation': [75, 45, 0], 'translation': [0, 2.5, 0], 'scale': [0.375, 0.375, 0.375]},
            'firstperson_righthand': {'rotation': [0, 135, 0], 'translation': [0, 0, 0], 'scale': [0.4, 0.4, 0.4]},
            'firstperson_lefthand': {'rotation': [0, 225, 0], 'translation': [0, 0, 0], 'scale': [0.4, 0.4, 0.4]}
        },
        'elements': [
            {
                'from': [0, 0, 0],
                'to': [16, 16, 16],
                'faces': {
                    'down': {'texture': '#down', 'cullface': 'down'},
                    'up': {'texture': '#up', 'cullface': 'up'},
                    'north': {'texture': '#north', 'cullface': 'north'},
                    'south': {'texture': '#south', 'cullface': 'south'},
                    'west': {'texture': '#west', 'cullface': 'west'},
                    'east': {'texture': '#east', 'cullface': 'east'}
                }
            }
        ],
        'textures': {
            'particle': 'simpledrawer:block/drawers_wood_side',
            'down': '#bottom',
            'up': '#top',
            'north': '#front',
            'east': '#side',
            'south': '#side',
            'west': '#side',
            'top': 'simpledrawer:block/drawers_wood_side',
            'bottom': 'simpledrawer:block/drawers_wood_side',
            'side': 'simpledrawer:block/drawers_wood_side',
            'front': 'simpledrawer:block/drawers_wood_front'
        },
        'ambientocclusion': False
    }}


    """

    def __init__(
        self,
        models: dict[str, dict[str, Any]],
        ctx: Context,
        vanilla: Release,
        opts: ModelResolverOptions,
    ):
        self.models = models
        self.ctx = ctx
        self.vanilla = vanilla
        self.opts = opts

        self.model_list = list(self.models.keys())
        self.model_list.sort()
        self.current_model_index = 0
        self.textures_bindings = {}
        self.textures_size = {}
        self.textures = load_textures(
            self.current_model["textures"],
            self.ctx,
            self.vanilla,
        )
        self.reset_camera()
        self.frame_count = 0
        self.logger = logging.getLogger("model_resolver")

    @property
    def current_model_name(self):
        return self.model_list[self.current_model_index]

    @property
    def current_model(self):
        return self.models[self.current_model_name]

    def reset_camera(self):
        self.translate = [0, 0, 0]
        self.rotate = [0, 0, 0]

    def reload(self):
        self.textures_bindings = {}
        self.textures = load_textures(
            self.current_model["textures"],
            self.ctx,
            self.vanilla,
        )
        self.generate_textures_bindings()

    def generate_textures_bindings(self):
        self.textures_bindings = {}
        for key, value in self.textures.items():
            tex_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            img_data = value.tobytes("raw", "RGBA")
            glTexImage2D(
                GL_TEXTURE_2D,
                0,
                GL_RGBA,
                value.width,
                value.height,
                0,
                GL_RGBA,
                GL_UNSIGNED_BYTE,
                img_data,
            )
            self.textures_bindings[key] = tex_id
            self.textures_size[key] = value.size

    def render(self):
        glutInit()

        glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_DEPTH)  # type: ignore
        glutInitWindowSize(self.opts.render_size, self.opts.render_size)
        glutInitWindowPosition(100, 100)
        glutCreateWindow(b"Isometric View")
        glutHideWindow()
        glutSetOption(GLUT_ACTION_ON_WINDOW_CLOSE, GLUT_ACTION_GLUTMAINLOOP_RETURNS)
        glClearColor(0.0, 0.0, 0.0, 0.0)

        # Enable lighting
        glLightfv(GL_LIGHT0, GL_POSITION, self.opts.light.minecraft_light_position)
        glLightfv(GL_LIGHT0, GL_AMBIENT, [self.opts.light.minecraft_ambient_light] * 4)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [self.opts.light.minecraft_light_power] * 4)

        glLightfv(GL_LIGHT1, GL_POSITION, [0.0, 0.0, 10.0, 0.0])
        glLightfv(GL_LIGHT1, GL_DIFFUSE, [1.0] * 4)

        self.reload()

        glutDisplayFunc(self.display)
        glutReshapeFunc(self.reshape)
        glutIdleFunc(self.display)

        glutMainLoop()

    def cache_in_ctx(self, img: Image.Image):
        if not self.opts.use_cache:
            return

        model_hash = hashlib.sha256(
            str(self.current_model).encode()
        ).hexdigest()

        textures_hash = {}
        for key, value in self.textures.items():
            textures_hash[key] = hashlib.sha256(value.tobytes()).hexdigest()

        cache = self.ctx.cache["model_resolver"]

        cache.json["models"][self.current_model_name] = {
            "model": model_hash,
            "textures": textures_hash,
        }
        save_path = cache.get_path(f"{self.current_model_name}.png")
        with open(save_path, "wb") as f:
            img.save(f, "PNG")

    def display(self):
        try:
            glClearColor(0.0, 0.0, 0.0, 0.0)
            img = self.draw_buffer()
            if self.opts.special_filter is None or len(self.opts.special_filter) == 0:
                if self.opts.save_namespace is None:
                    model_name = self.current_model_name.split(":")
                    texture_path = f"{model_name[0]}:render/{model_name[1]}"
                else:
                    model_name = self.current_model_name
                    texture_path = f"{self.opts.save_namespace}:render/{model_name.replace(':', '/')}"
                self.ctx.assets.textures[texture_path] = Texture(img)
            else:
                model_name = self.current_model_name
                path_save = self.opts.special_filter.get(model_name, None)
                if path_save is not None:
                    with open(path_save, "wb") as f:
                        img.save(f, "PNG")

            self.cache_in_ctx(img)
            self.current_model_index += 1
            if self.current_model_index >= len(self.model_list):
                glutLeaveMainLoop()
                return
            self.logger.info(f"Rendering {self.current_model_name}")
            self.reload()
            self.reset_camera()

            # glutSwapBuffers()
        except BaseException as e:
            glutLeaveMainLoop()
            raise e

    def reshape(self, width, height):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)

        zoom = 8

        glOrtho(zoom, -zoom, -zoom, zoom, self.opts.render_size, -self.opts.render_size)
        glMatrixMode(GL_MODELVIEW)

    def draw_buffer(self):

        glClearColor(0.0, 0.0, 0.0, 0.0)  # Set clear color to black with alpha 0
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glCullFace(GL_FRONT)
        # glFrontFace(GL_CCW)
        # enable transparency
        glEnable(GL_BLEND)
        glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA)

        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GREATER, 0)

        # glBlendFunc(GL_ONE, GL_ZERO)

        # add ambient light
        glEnable(GL_COLOR_MATERIAL)

        glEnable(GL_NORMALIZE)
        glEnable(GL_LIGHTING)

        # Create a framebuffer object (FBO) for off-screen rendering
        fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, fbo)

        # Create a renderbuffer for depth testing
        depth_buffer = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, depth_buffer)
        glRenderbufferStorage(
            GL_RENDERBUFFER,
            GL_DEPTH_COMPONENT,
            self.opts.render_size,
            self.opts.render_size,
        )
        glFramebufferRenderbuffer(
            GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depth_buffer
        )

        # Create a texture to render into
        render_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, render_texture)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            self.opts.render_size,
            self.opts.render_size,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            None,
        )
        glFramebufferTexture2D(
            GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, render_texture, 0
        )

        # Check framebuffer status
        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            raise RenderError("Framebuffer is not complete")

        # Render the scene
        glViewport(0, 0, self.opts.render_size, self.opts.render_size)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)  # type: ignore

        model = self.current_model
        gui_light = model.get("gui_light", "side")
        if gui_light == "side":
            activate_light = GL_LIGHT0
            deactivate_light = GL_LIGHT1
        else:
            activate_light = GL_LIGHT1
            deactivate_light = GL_LIGHT0
        glEnable(activate_light)
        glDisable(deactivate_light)
        if "elements" in model:
            for element in model["elements"]:
                shade = element.get("shade", True)
                # if shade is False, disable lighting
                if not shade:
                    glDisable(GL_LIGHTING)
                    glDisable(GL_LIGHT0)
                    glDisable(GL_LIGHT1)
                self.draw_element(element)
                if not shade:
                    glEnable(GL_LIGHTING)
                    glEnable(activate_light)

        glDisable(GL_LIGHT0)
        glDisable(GL_LIGHT1)

        # Read the pixel data, including alpha channel
        pixel_data = glReadPixels(
            0,
            0,
            self.opts.render_size,
            self.opts.render_size,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
        )

        # Create an image from pixel data
        img = Image.frombytes(
            "RGBA", (self.opts.render_size, self.opts.render_size), pixel_data
        )
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        # Release resources
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glDeleteTextures([render_texture])
        glDeleteRenderbuffers(1, [depth_buffer])
        glDeleteFramebuffers(1, [fbo])
        glDisable(GL_COLOR_MATERIAL)
        glDisable(GL_NORMALIZE)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)

        return img

    def draw_element(self, element: dict):
        glEnable(GL_TEXTURE_2D)
        from_element = element["from"]
        to_element = element["to"]
        rotation = element.get("rotation", None)

        from_element_centered, to_element_centered = self.center_element(
            from_element, to_element
        )

        vertices = self.get_vertices(
            from_element_centered, to_element_centered, rotation
        )

        # transform the vertices
        gui = (
            self.current_model
            .get("display", {})
            .get(
                "gui",
                {
                    "rotation": [30, 225, 0],
                    "translation": [0, 0, 0],
                    "scale": [0.625, 0.625, 0.625],
                },
            )
        )
        scale = gui.get("scale", [1, 1, 1])
        translation = gui.get("translation", [0, 0, 0])
        rotation = gui.get("rotation", [0, 0, 0])

        # reset the matrix
        glLoadIdentity()
        glTranslatef(translation[0] / 16, translation[1] / 16, translation[2] / 16)
        glTranslatef(self.translate[0], self.translate[1], self.translate[2])
        glRotatef(-rotation[0], 1, 0, 0)
        glRotatef(rotation[1] + 180, 0, 1, 0)
        glRotatef(rotation[2], 0, 0, 1)
        glRotatef(self.rotate[0], 1, 0, 0)
        glRotatef(self.rotate[1], 0, 1, 0)
        glRotatef(self.rotate[2], 0, 0, 1)
        glScalef(scale[0], scale[1], scale[2])

        texture_used = [
            element["faces"].get("down", None),
            element["faces"].get("up", None),
            element["faces"].get("north", None),
            element["faces"].get("south", None),
            element["faces"].get("west", None),
            element["faces"].get("east", None),
        ]
        texture_used = [x["texture"].lstrip("#") for x in texture_used if x is not None]
        texture_used = list(set(texture_used))

        for texture in texture_used:
            if texture not in self.textures_bindings:
                continue
            glBindTexture(GL_TEXTURE_2D, self.textures_bindings[texture])
            glColor3f(1.0, 1.0, 1.0)
            # get all the faces with the same texture
            for face, data in element["faces"].items():
                if data["texture"].lstrip("#") == texture:
                    self.draw_face(face, data, vertices, from_element, to_element)

        glDisable(GL_TEXTURE_2D)

    def get_vertices(
        self,
        from_element: tuple[float, float, float],
        to_element: tuple[float, float, float],
        rotation: dict | None,
    ) -> tuple:
        x1, y1, z1 = from_element
        x2, y2, z2 = to_element
        res = (
            [x1, y1, z1],
            [x2, y1, z1],
            [x2, y2, z1],
            [x1, y2, z1],
            [x1, y2, z2],
            [x2, y2, z2],
            [x2, y1, z2],
            [x1, y1, z2],
        )
        if rotation is None:
            return res

        origin = rotation["origin"]
        origin = [x - 8 for x in origin]
        axis = rotation["axis"]
        angle = rotation["angle"]
        # rescale scale the axis vertices in
        rescale = rotation.get("rescale", False)

        angle = angle * pi / 180

        for point in res:
            x, y, z = point
            x -= origin[0]
            y -= origin[1]
            z -= origin[2]
            if axis == "x":
                y, z = y * cos(angle) - z * sin(angle), y * sin(angle) + z * cos(angle)
            elif axis == "y":
                x, z = x * cos(-angle) - z * sin(-angle), x * sin(-angle) + z * cos(
                    -angle
                )
            elif axis == "z":
                x, y = x * cos(angle) - y * sin(angle), x * sin(angle) + y * cos(angle)
            x += origin[0]
            y += origin[1]
            z += origin[2]
            point[0], point[1], point[2] = x, y, z

        if rescale:
            factor = sqrt(2)
            for point in res:
                if axis != "x":
                    point[0] = point[0] * factor
                if axis != "y":
                    point[1] = point[1] * factor
                if axis != "z":
                    point[2] = point[2] * factor

        return res

    def center_element(
        self,
        from_element: tuple[float, float, float],
        to_element: tuple[float, float, float],
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        # return from_element, to_element
        x1, y1, z1 = from_element
        x2, y2, z2 = to_element

        center = (8, 8, 8)

        # compute the new from and to
        from_element = (x1 - center[0], y1 - center[1], z1 - center[2])
        to_element = (x2 - center[0], y2 - center[1], z2 - center[2])
        return from_element, to_element

    def draw_face(
        self,
        face: str,
        data: dict,
        vertices: tuple,
        from_element: tuple[float, float, float],
        to_element: tuple[float, float, float],
    ):

        if "uv" in data:
            uv = data["uv"]
            uv = [x / 16 for x in uv]
        else:
            uv = self.get_uv(face, from_element, to_element)
            uv = [x / 16 for x in uv]
        # print([x*16 for x in uv], face)


        match face:
            case "down":
                vertices_order = [7, 6, 1, 0]
            case "up":
                vertices_order = [3, 2, 5, 4]
            case "south":
                vertices_order = [4, 5, 6, 7]
            case "north":
                vertices_order = [2, 3, 0, 1]
            case "east":
                vertices_order = [5, 2, 1, 6]
            case "west":
                vertices_order = [3, 4, 7, 0]
            case _:
                raise RenderError(f"Unknown face {face}")

        rotation = data.get("rotation", 0)
        match rotation:
            case 0:
                pass
            case 90:
                vertices_order = [
                    vertices_order[1],
                    vertices_order[2],
                    vertices_order[3],
                    vertices_order[0],
                ]
            case 180:
                vertices_order = [
                    vertices_order[2],
                    vertices_order[3],
                    vertices_order[0],
                    vertices_order[1],
                ]
            case 270:
                vertices_order = [
                    vertices_order[3],
                    vertices_order[0],
                    vertices_order[1],
                    vertices_order[2],
                ]
            case _:
                raise RenderError(f"Unknown rotation {rotation}")

        rotated_vertices = [vertices[i] for i in vertices_order]
        texcoords = [(0, 1), (2, 1), (2, 3), (0, 3)]
        triangulated_vertices = [
            (rotated_vertices[0], rotated_vertices[1], rotated_vertices[2]),
            (rotated_vertices[0], rotated_vertices[2], rotated_vertices[3]),
        ]
        normals = []
        for v0, v1, v2 in triangulated_vertices:
            u = [v1[i] - v0[i] for i in range(3)]
            v = [v2[i] - v0[i] for i in range(3)]
            normal = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ]
            normals.append(normal)

        # glUseProgram(self.program)
        # print(glGetError())
        # self.set_uniforms(self.program)

        glBegin(GL_QUADS)
        for i, (v0, v1, v2) in enumerate(triangulated_vertices):
            normal = normals[i]
            glNormal3fv(normal)

        for i, (uv0, uv1) in enumerate(texcoords):
            glTexCoord2f(uv[uv0], uv[uv1])
            glVertex3fv(rotated_vertices[i])
        glEnd()
        # glUseProgram(0)

    def get_uv(
        self,
        face: str,
        from_element: tuple[float, float, float],
        to_element: tuple[float, float, float],
    ) -> tuple[float, float, float, float]:

        x1, y1, z1 = from_element
        x2, y2, z2 = to_element

        match face:
            case "east" | "west":
                x_offset = (- (z2 + z1)) % 16
                y_offset = (y2 - y1) % 16
                return (z1+x_offset, y1+y_offset, z2+x_offset, y2+y_offset)
            case "up" | "down":
                x_offset = 0
                y_offset = 0
                return (x1+x_offset, z1+y_offset, x2+x_offset, z2+y_offset)
            case "south" | "north":
                x_offset = (- (x2 + x1)) % 16
                y_offset = (y2 - y1) % 16
                return (x1+x_offset, y1+y_offset, x2+x_offset, y2+y_offset)
            case _:
                raise RenderError(f"Unknown face {face}")

    def keyboard(self, key, x, y):
        # increment the current model index on each click
        if key == b"\x1b":
            glutLeaveMainLoop()
        elif key == b"r":
            self.current_model_index += 1
            self.current_model_index = self.current_model_index % len(self.models)
            self.reload()
            self.reset_camera()
        elif key == b"z":
            self.translate[1] += 1
        elif key == b"s":
            self.translate[1] -= 1
        elif key == b"q":
            self.translate[0] -= 1
        elif key == b"d":
            self.translate[0] += 1
        # use ijklm to rotate the model
        elif key == b"i":
            self.rotate[0] += 1
        elif key == b"k":
            self.rotate[0] -= 1
        elif key == b"j":
            self.rotate[1] += 1
        elif key == b"l":
            self.rotate[1] -= 1
        elif key == b"u":
            self.rotate[2] += 1
        elif key == b"m":
            self.rotate[2] -= 1

        glutPostRedisplay()
