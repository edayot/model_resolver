from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from PIL import Image

from beet import Context
from beet.contrib.vanilla import Vanilla




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


    def __init__(self, models : dict[dict], ctx : Context, vanilla : Vanilla):
        self.models = models
        self.ctx = ctx
        self.vanilla = vanilla

        self.model_list = list(self.models.keys())
        self.current_model_index = 0
        self.reload()
    
    def reload(self):
        self.textures_bindings = {}
        self.textures = self.load_textures(self.models[self.model_list[self.current_model_index]]['textures'], self.ctx, self.vanilla)

    def generate_textures_bindings(self):
        for key, value in self.textures.items():
            tex_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            img_data = value.tobytes("raw", "RGBX", 0, -1)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, value.width, value.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
            self.textures_bindings[key] = tex_id
            print(tex_id)

    def load_textures(self, textures : dict, ctx : Context, vanilla : Vanilla):
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
        img = img.convert("RGB")
        return img

    


    def get_real_key(self, key : str, textures : dict):
        if textures[key][0] == "#":
            return self.get_real_key(textures[key][1:], textures)
        else:
            return textures[key]



    def render(self):
        glutInit()

        glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_DEPTH)
        glutInitWindowSize(512, 512)
        glutInitWindowPosition(100, 100)
        print("Creating window")
        glutCreateWindow(b"Isometric View")
        glutSetOption(GLUT_ACTION_ON_WINDOW_CLOSE, GLUT_ACTION_GLUTMAINLOOP_RETURNS)
        glEnable(GL_DEPTH_TEST)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glEnable(GL_DEPTH_TEST)

        self.generate_textures_bindings()

        glutDisplayFunc(self.display)
        glutReshapeFunc(self.reshape)
        glutIdleFunc(self.display)
        glutKeyboardFunc(self.keyboard)
        glutMainLoop()  

    
    def display(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        # glTranslatef(0, 0, -10)
        glRotatef(30, 1, 0, 0)
        glRotatef(45, 0, 1, 0) 

        self.draw()

        glutSwapBuffers()
    
    def reshape(self, width, height):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()

        zoom = 20

        glOrtho(-zoom, zoom, -zoom, zoom, -512, 512)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def draw(self):
        model = self.models[self.model_list[self.current_model_index]]
        for element in model['elements']:
            self.draw_element(element)
        

    def draw_element(self, element : dict):
        glEnable(GL_TEXTURE_2D)
        from_element = element['from']
        to_element = element['to']

        from_element, to_element = self.center_element(from_element, to_element)

        vertices = self.get_vertices(from_element, to_element)

        texture_used = [
            element['faces'].get('down', None),
            element['faces'].get('up', None),
            element['faces'].get('north', None),
            element['faces'].get('south', None),
            element['faces'].get('west', None),
            element['faces'].get('east', None)
        ]
        texture_used = [x['texture'][1:] for x in texture_used if x is not None]
        
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
        else:
            uv = self.get_uv(face, from_element, to_element)

        match face:
            case 'down':
                glTexCoord2f(uv[0], uv[1]); glVertex3fv(vertices[6])
                glTexCoord2f(uv[2], uv[1]); glVertex3fv(vertices[7])
                glTexCoord2f(uv[2], uv[3]); glVertex3fv(vertices[0])
                glTexCoord2f(uv[0], uv[3]); glVertex3fv(vertices[1])
            case 'up':
                glTexCoord2f(uv[0], uv[1]); glVertex3fv(vertices[2])
                glTexCoord2f(uv[2], uv[1]); glVertex3fv(vertices[3])
                glTexCoord2f(uv[2], uv[3]); glVertex3fv(vertices[4])
                glTexCoord2f(uv[0], uv[3]); glVertex3fv(vertices[5])
            case 'north':
                glTexCoord2f(uv[0], uv[1]); glVertex3fv(vertices[7])
                glTexCoord2f(uv[2], uv[1]); glVertex3fv(vertices[6])
                glTexCoord2f(uv[2], uv[3]); glVertex3fv(vertices[5])
                glTexCoord2f(uv[0], uv[3]); glVertex3fv(vertices[4])
            case 'south':
                glTexCoord2f(uv[0], uv[1]); glVertex3fv(vertices[3])
                glTexCoord2f(uv[2], uv[1]); glVertex3fv(vertices[2])
                glTexCoord2f(uv[2], uv[3]); glVertex3fv(vertices[1])
                glTexCoord2f(uv[0], uv[3]); glVertex3fv(vertices[0])
            case 'west':
                glTexCoord2f(uv[0], uv[1]); glVertex3fv(vertices[6])
                glTexCoord2f(uv[2], uv[1]); glVertex3fv(vertices[1])
                glTexCoord2f(uv[2], uv[3]); glVertex3fv(vertices[2])
                glTexCoord2f(uv[0], uv[3]); glVertex3fv(vertices[5])
            case 'east':
                glTexCoord2f(uv[0], uv[1]); glVertex3fv(vertices[0])
                glTexCoord2f(uv[2], uv[1]); glVertex3fv(vertices[7])
                glTexCoord2f(uv[2], uv[3]); glVertex3fv(vertices[4])
                glTexCoord2f(uv[0], uv[3]); glVertex3fv(vertices[3])
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
        elif key == b'w':
            self.current_model_index += 1
            self.current_model_index = self.current_model_index % len(self.models)
            self.reload()
            self.generate_textures_bindings()
        glutPostRedisplay()

    
    

