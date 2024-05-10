
import moderngl_window as mglw
from pyrr import Matrix44, Vector3
import moderngl
from beet import Context
from beet.contrib.vanilla import Vanilla
from PIL import Image
from moderngl_window import geometry
from moderngl_window.scene.camera import KeyboardCamera, OrbitCamera, Camera
import numpy as np


MODEL : dict = None
BEET_CONTEXT : Context = None
VANILLA_CONTEXT : Context = None


def render_model(_model, _beet_context, _vanilla_context):
    global MODEL
    global BEET_CONTEXT
    global VANILLA_CONTEXT
    MODEL = _model
    BEET_CONTEXT = _beet_context
    VANILLA_CONTEXT = _vanilla_context
    mglw.run_window_config(RenderModel)


class Beet():
    def __init__(self, model, beet_context, vanilla_context):
        self.model = model
        self.ctx = beet_context
        self.vanilla = vanilla_context


def to_rad(deg):
    return deg*np.pi/180


class RenderModel(mglw.WindowConfig):
    '''
    
    model = {
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
    }


    '''
    title = "Isometric Camera"
    aspect_ratio = 1
    window_size = (1024, 1024)


    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.beet = Beet(MODEL, BEET_CONTEXT, VANILLA_CONTEXT)
        self.load_textures_beet(self.beet.model['textures'], self.beet.ctx, self.beet.vanilla)
        self.prog = self.load_program('/home/erwan/Documents/dev/model_resolver/texture_program.glsl')
        self.prog['texture0'] = 0
        self.prog['texture1'] = 1
        self.prog['texture2'] = 2
        self.prog['texture3'] = 3
        self.prog['texture4'] = 4
        self.prog['texture5'] = 5

        self.face_to_index = {
            'down': 0,
            'up': 1,
            'north': 2,
            'south': 3,
            'west': 4,
            'east': 5
        }

        self.camera = Camera()
        self.camera_enabled = True



    def render(self, time: float, frametime: float):
        self.ctx.enable_only(moderngl.CULL_FACE | moderngl.DEPTH_TEST)

        gui = self.beet.model['display']['gui']
        # gui angle are in degrees
        
        rotation = (
            Matrix44.from_x_rotation(to_rad(-gui['rotation'][0]), dtype='f4')
            * Matrix44.from_y_rotation(to_rad(-gui['rotation'][1]), dtype='f4')
            * Matrix44.from_z_rotation(to_rad(gui['rotation'][2]), dtype='f4')
        ) 
    
        translation = Matrix44.from_translation((0.0, 0.0, 0.0), dtype='f4')
        modelview = translation * rotation

        # orthogonal projection
        zoom = -2
        proj = Matrix44.orthogonal_projection(zoom, -zoom, -zoom, zoom, 512, -512, dtype='f4')

        self.prog['m_proj'].write(proj)
        self.prog['m_model'].write(modelview)
        self.prog['m_camera'].write(self.camera.matrix)

        for element in self.beet.model['elements']:
            self.render_element(element)

    def render_element(self, element):
        from_ = element['from']
        to_ = element['to']
        size = (to_[0] - from_[0], to_[1] - from_[1], to_[2] - from_[2])
        div = 16
        size = (size[0]/div, size[1]/div, size[2]/div)
        center = ((to_[0] + from_[0]) / 2, (to_[1] + from_[1]) / 2, (to_[2] + from_[2]) / 2)
        center = (center[0]/div, center[1]/div, center[2]/div)

        cube = geometry.cube(size=size, center=center, normals=True, uvs=True)
        # bind the textures
        for face in element['faces'].keys():
            texture = self.textures[element['faces'][face]['texture'].lstrip("#")]
            texture.use(self.face_to_index[face])
            cube.render(self.prog)

    def get_real_key(self, key : str, textures : dict):
        if textures[key][0] == "#":
            return self.get_real_key(textures[key][1:], textures)
        else:
            return textures[key]


    def load_textures_beet(self, textures : dict, ctx : Context, vanilla : Vanilla) -> dict[str, moderngl.Texture]:
        self.textures : dict[str, moderngl.Texture] = {}
        for key in textures.keys():
            value = self.get_real_key(key, textures)
            self.textures[key] = self.load_texture_beet(value, ctx, vanilla)
    
    def load_texture_beet(self, path : str, ctx : Context, vanilla : Vanilla) -> moderngl.Texture:
        texture = ctx.assets.textures.get(path, None)
        if texture is None:
            path_search = f"minecraft:{path}" if ":" not in path else path
            texture = vanilla.assets.textures.get(path_search, None)
            if texture is None:
                raise FileNotFoundError(f"Texture {path} not found")
        # no upscale function
        texture.image : Image.Image
        text = self.ctx.texture(texture.image.size, 3, texture.image.tobytes())
        text.filter = (moderngl.NEAREST, moderngl.NEAREST)
        return text

