from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from model_resolver.my_glutinit import glutInit

from PIL import Image

from beet import Context, Texture
from beet.contrib.vanilla import Vanilla


INTERACTIVE = False


class Render():
    '''
    
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


    '''


    def __init__(self, models : dict[dict], ctx : Context, vanilla : Vanilla, size : int = 1024):
        self.models = models
        self.ctx = ctx
        self.vanilla = vanilla
        self.size = size

        self.model_list = list(self.models.keys())
        self.current_model_index = 0
        self.textures_bindings = {}
        self.textures_size = {}
        self.textures = self.load_textures(self.models[self.model_list[self.current_model_index]]['textures'], self.ctx, self.vanilla)

        self.translate = [0, 0, 0]
        self.rotate = [0, 0, 0]
    
    def reload(self):
        self.textures_bindings = {}
        self.textures = self.load_textures(self.models[self.model_list[self.current_model_index]]['textures'], self.ctx, self.vanilla)
        self.generate_textures_bindings()

    def generate_textures_bindings(self):
        self.textures_bindings = {}
        for key, value in self.textures.items():
            tex_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            img_data = value.tobytes("raw", "RGBA")
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, value.width, value.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
            self.textures_bindings[key] = tex_id
            self.textures_size[key] = value.size

    def load_textures(self, textures : dict, ctx : Context, vanilla : Vanilla) -> dict[str, Image.Image]:
        res = {}
        for key in textures.keys():
            value = self.get_real_key(key, textures)
            res[key] = self.load_texture(value, ctx, vanilla)
        return res
    
    def load_texture(self, path : str, ctx : Context, vanilla : Vanilla) -> Image.Image:
        texture = ctx.assets.textures.get(path, None)
        if texture is None:
            path_search = f"minecraft:{path}" if ":" not in path else path
            texture = vanilla.assets.textures.get(path_search, None)
            if texture is None:
                raise FileNotFoundError(f"Texture {path} not found")
        img : Image.Image = texture.image
        img = img.convert("RGBA")
        return img

    


    def get_real_key(self, key : str, textures : dict):
        if textures[key][0] == "#":
            return self.get_real_key(textures[key][1:], textures)
        else:
            return textures[key]



    def render(self):
        glutInit()

        glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_DEPTH)
        glutInitWindowSize(self.size, self.size)
        glutInitWindowPosition(100, 100)
        glutCreateWindow(b"Isometric View")
        if not INTERACTIVE:
            glutHideWindow()
        glutSetOption(GLUT_ACTION_ON_WINDOW_CLOSE, GLUT_ACTION_GLUTMAINLOOP_RETURNS)
        glEnable(GL_DEPTH_TEST)
        glClearColor(0.0, 0.0, 0.0, 0.0)
        glEnable(GL_DEPTH_TEST)

        self.reload()

        glutDisplayFunc(self.display)
        glutReshapeFunc(self.reshape)
        glutIdleFunc(self.display)
        glutKeyboardFunc(self.keyboard)
        
        glutMainLoop()  

    
    def display(self):
        try:
            glClearColor(0.0, 0.0, 0.0, 0.0)
            if not INTERACTIVE:
                img = self.draw_buffer()
                model_name = self.model_list[self.current_model_index].split(":")
                texture_path = f"{model_name[0]}:render/{model_name[1]}"
                self.ctx.assets.textures[texture_path] = Texture(img)

                self.current_model_index += 1
                if self.current_model_index >= len(self.model_list):
                    glutLeaveMainLoop()
                    return
                self.reload()
                self.translate = [0, 0, 0]
                self.rotate = [0, 0, 0]
            else:
                self.draw()

            
            glutSwapBuffers()
        except BaseException as e:
            glutLeaveMainLoop()
            raise e    
    
    def reshape(self, width, height):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)

        zoom = 8

        glOrtho(zoom, -zoom, -zoom, zoom, self.size, -self.size)
        glMatrixMode(GL_MODELVIEW)

    def draw_buffer(self):
        glClearColor(0.0, 0.0, 0.0, 0.0)  # Set clear color to black with alpha 0

        # Create a framebuffer object (FBO) for off-screen rendering
        fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, fbo)

        # Create a renderbuffer for depth testing
        depth_buffer = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, depth_buffer)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT, self.size, self.size)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depth_buffer)

        # Create a texture to render into
        render_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, render_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.size, self.size, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, render_texture, 0)

        # Check framebuffer status
        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            raise RuntimeError("Framebuffer is not complete")

        # Render the scene
        glViewport(0, 0, self.size, self.size)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        model = self.models[self.model_list[self.current_model_index]]
        if "elements" in model:
            for element in model['elements']:
                self.draw_element(element)
        elif "parent" in model and model["parent"] == "builtin/generated":
            glLoadIdentity()
            glRotatef(self.rotate[0], 1, 0, 0)
            glRotatef(self.rotate[1], 0, 1, 0)
            glRotatef(self.rotate[2], 0, 0, 1)
            glEnable(GL_TEXTURE_2D)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            # in this case, it's a 2d sprite
            # textures are always layer0, layer1, layer2, layer3 (if they exist)
            max = 0
            for texture_key in model["textures"]:
                layer = int(texture_key[-1])
                if layer > max:
                    max = layer
            for i in range(max + 1):
                if f"layer{i}" in model["textures"]:
                    texture = self.textures_bindings[f"layer{i}"]
                    glBindTexture(GL_TEXTURE_2D, texture)
                    glBegin(GL_QUADS)
                    scale = 8
                    glTexCoord2f(0, 0); glVertex3f(scale, scale, -i)
                    glTexCoord2f(1, 0); glVertex3f(-scale, scale, -i)
                    glTexCoord2f(1, 1); glVertex3f(-scale, -scale, -i)
                    glTexCoord2f(0, 1); glVertex3f(scale, -scale, -i)
                    glEnd()
            glDisable(GL_TEXTURE_2D)
            glDisable(GL_BLEND)

        # Read the pixel data, including alpha channel
        pixel_data = glReadPixels(0, 0, self.size, self.size, GL_RGBA, GL_UNSIGNED_BYTE)

        # Create an image from pixel data
        img = Image.frombytes("RGBA", (self.size, self.size), pixel_data)
        img = img.transpose(Image.FLIP_TOP_BOTTOM)

        # Release resources
        glDeleteTextures(1, [render_texture])
        glDeleteRenderbuffers(1, [depth_buffer])
        glDeleteFramebuffers(1, [fbo])

        return img


    def draw(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        model = self.models[self.model_list[self.current_model_index]]
        if "elements" in model:
            for element in model['elements']:
                self.draw_element(element)
        elif "parent" in model and model["parent"] == "builtin/generated":
            glLoadIdentity()
            glRotatef(self.rotate[0], 1, 0, 0)
            glRotatef(self.rotate[1], 0, 1, 0)
            glRotatef(self.rotate[2], 0, 0, 1)
            glEnable(GL_TEXTURE_2D)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            # in this case, it's a 2d sprite
            # textures are always layer0, layer1, layer2, layer3 (if they exist)
            max = 0
            for texture_key in model["textures"]:
                layer = int(texture_key[-1])
                if layer > max:
                    max = layer
            for i in range(max + 1):
                if f"layer{i}" in model["textures"]:
                    texture = self.textures_bindings[f"layer{i}"]
                    glBindTexture(GL_TEXTURE_2D, texture)
                    glBegin(GL_QUADS)
                    scale = 8
                    glTexCoord2f(0, 0); glVertex3f(scale, scale, -i)
                    glTexCoord2f(1, 0); glVertex3f(-scale, scale, -i)
                    glTexCoord2f(1, 1); glVertex3f(-scale, -scale, -i)
                    glTexCoord2f(0, 1); glVertex3f(scale, -scale, -i)
                    glEnd()
            glDisable(GL_TEXTURE_2D)
            glDisable(GL_BLEND)
        width, height = glutGet(GLUT_WINDOW_WIDTH), glutGet(GLUT_WINDOW_HEIGHT)
        # read the pixel by pixel, with the alpha channel
        pixel_data = glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE)
        img = Image.frombytes("RGBA", (width, height), pixel_data)
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        return img

        

    def draw_element(self, element : dict):
        glEnable(GL_TEXTURE_2D)
        from_element= element['from']
        to_element = element['to']

        from_element_centered, to_element_centered = self.center_element(from_element, to_element)

        vertices = self.get_vertices(from_element_centered, to_element_centered)

        # transform the vertices
        gui = self.models[self.model_list[self.current_model_index]]['display']['gui']
        scale = gui.get('scale', [1, 1, 1])
        translation = gui.get('translation', [0, 0, 0])
        rotation = gui.get('rotation', [0, 0, 0])

        # reset the matrix
        glLoadIdentity()
        glTranslatef(translation[0]/16, translation[1]/16, translation[2]/16)
        glTranslatef(self.translate[0], self.translate[1], self.translate[2])
        glRotatef(-rotation[0], 1, 0, 0)
        glRotatef(rotation[1] + 180, 0, 1, 0)
        glRotatef(rotation[2], 0, 0, 1)
        glRotatef(self.rotate[0], 1, 0, 0)
        glRotatef(self.rotate[1], 0, 1, 0)
        glRotatef(self.rotate[2], 0, 0, 1)
        glScalef(scale[0], scale[1], scale[2])



        texture_used = [
            element['faces'].get('down', None),
            element['faces'].get('up', None),
            element['faces'].get('north', None),
            element['faces'].get('south', None),
            element['faces'].get('west', None),
            element['faces'].get('east', None)
        ]
        texture_used = [x['texture'][1:] for x in texture_used if x is not None]
        texture_used = list(set(texture_used))
        
        for texture in texture_used:
            glBindTexture(GL_TEXTURE_2D, self.textures_bindings[texture])
            glColor3f(1.0, 1.0, 1.0)
            # get all the faces with the same texture
            for face, data in element['faces'].items():
                if data['texture'][1:] == texture:
                    self.draw_face(face, data, vertices, from_element, to_element)
            
        glDisable(GL_TEXTURE_2D)

    def get_vertices(self, from_element : list, to_element : list):
        x1, y1, z1 = from_element
        x2, y2, z2 = to_element
        return (
            (x1, y1, z1),
            (x2, y1, z1),
            (x2, y2, z1),
            (x1, y2, z1),
            (x1, y2, z2),
            (x2, y2, z2),
            (x2, y1, z2),
            (x1, y1, z2)
        )

    def center_element(self, from_element : list, to_element : list) -> tuple[list, list]:
        # return from_element, to_element
        x1, y1, z1 = from_element
        x2, y2, z2 = to_element
        
        center = (8, 8, 8)

        # compute the new from and to
        from_element = (x1 - center[0], y1 - center[1], z1 - center[2])
        to_element = (x2 - center[0], y2 - center[1], z2 - center[2])
        return from_element, to_element
    

    def draw_face(self, face: str, data: dict, vertices: tuple, from_element: list, to_element: list):
        glBegin(GL_QUADS)

        if 'uv' in data:
            uv = data['uv']
            uv = [x / 16 for x in uv]
            rotation = data.get('rotation', 0)

        else:
            uv = self.get_uv(face, from_element, to_element)
            rotation = 0

        match face:
            case 'down':
                vertices_order = [7, 6, 1, 0]
            case 'up':
                vertices_order = [3, 2, 5, 4]
            case 'south':
                vertices_order = [4, 5, 6, 7]
            case 'north':
                vertices_order = [2, 3, 0, 1]
            case 'east':
                vertices_order = [5, 2, 1, 6]
            case 'west':
                vertices_order = [3, 4, 7, 0]
        
        match rotation:
            case 0:
                pass
            case 90:
                vertices_order = [vertices_order[1], vertices_order[2], vertices_order[3], vertices_order[0]]
            case 180:
                vertices_order = [vertices_order[2], vertices_order[3], vertices_order[0], vertices_order[1]]
            case 270:
                vertices_order = [vertices_order[3], vertices_order[0], vertices_order[1], vertices_order[2]]

        glTexCoord2f(uv[0], uv[1]); glVertex3fv(vertices[vertices_order[0]])
        glTexCoord2f(uv[2], uv[1]); glVertex3fv(vertices[vertices_order[1]])
        glTexCoord2f(uv[2], uv[3]); glVertex3fv(vertices[vertices_order[2]])
        glTexCoord2f(uv[0], uv[3]); glVertex3fv(vertices[vertices_order[3]])
        glEnd()

    def get_uv(self, face : str, from_element : list, to_element : list):

        x1, y1, z1 = from_element
        x2, y2, z2 = to_element

        div = 16

        x1, y1, z1 = x1 / div, y1 / div, z1 / div
        x2, y2, z2 = x2 / div, y2 / div, z2 / div


        match face:
            case 'east':
                return (z1, y1, z2, y2)
            case 'west':
                return (z1, y1, z2, y2)
            case 'up':
                return (x1, z1, x2, z2)
            case 'down':
                return (x1, z1, x2, z2)
            case 'south':
                return (x1, y1, x2, y2)
            case 'north':
                return (x1, y1, x2, y2)

    def keyboard(self, key, x, y):
        # increment the current model index on each click
        if key == b'\x1b':
            glutLeaveMainLoop()
        elif key == b'r':
            self.current_model_index += 1
            self.current_model_index = self.current_model_index % len(self.models)
            self.reload()
            self.translate = [0, 0, 0]
            self.rotate = [0, 0, 0]
        elif key == b'z':
            self.translate[1] += 1
        elif key == b's':
            self.translate[1] -= 1
        elif key == b'q':
            self.translate[0] -= 1
        elif key == b'd':
            self.translate[0] += 1
        # use ijklm to rotate the model
        elif key == b'i':
            self.rotate[0] += 1
        elif key == b'k':
            self.rotate[0] -= 1
        elif key == b'j':
            self.rotate[1] += 1
        elif key == b'l':
            self.rotate[1] -= 1
        elif key == b'u':
            self.rotate[2] += 1
        elif key == b'm':
            self.rotate[2] -= 1

        glutPostRedisplay()

    
    

