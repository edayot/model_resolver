from OpenGL.GL import *  # type: ignore
from OpenGL.GLUT import *  # type: ignore
from OpenGL.GLU import *  # type: ignore
from model_resolver.my_glutinit import glutInit

from PIL import Image
from beet import Context, Texture, Structure
from beet.contrib.vanilla import Vanilla
from nbtlib.contrib.minecraft.structure import StructureFileData
from typing import Any, cast, Generator, Type, Union, TypedDict
from model_resolver.utils import load_textures, ModelResolverOptions, MinecraftModel, ElementModel, RotationModel, FaceModel, DisplayOptionModel

from math import cos, sin, pi, sqrt

from pydantic import BaseModel, Field, ConfigDict
from dataclasses import dataclass
import random
from rich import print



class Task(BaseModel):
    zoom: int = 8
    def run(self, ctx: Context, opts: ModelResolverOptions, models: dict[str, MinecraftModel]):
        pass

    def save_image(self, ctx: Context, opts: ModelResolverOptions, img: Image.Image):
        pass

    def get_needed_models(self, ctx: Context, opts: ModelResolverOptions) -> Generator[str, None, None]:
        return
        yield "minecraft:block/stone"


class RenderError(Exception):
    pass


@dataclass
class Scene:
    ctx: Context
    opts: ModelResolverOptions
    models: dict[str, MinecraftModel]
    tasks: list[Task] = Field(default_factory=list)
    tasks_index: int = 0
    current_zoom: int = 8

    def __repr__(self):
        return f"Scene(tasks_index={self.tasks_index}, current_zoom={self.current_zoom})"

    @property
    def current_task(self):
        return self.tasks[self.tasks_index]


    def render(self):
        glutInit()
        glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_DEPTH) # type: ignore
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

        glutDisplayFunc(self.display)
        glutIdleFunc(self.display)
        glutReshapeFunc(self.reshape)

        glutMainLoop()



    def reshape(self, width: int, height: int):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        zoom = 8
        glOrtho(zoom, -zoom, -zoom, zoom, self.opts.render_size, -self.opts.render_size)
        glMatrixMode(GL_MODELVIEW)

    
    def display(self):
        if self.tasks_index >= len(self.tasks):
            return glutLeaveMainLoop()
        if self.current_task.zoom != self.current_zoom:
            self.current_zoom = self.current_task.zoom
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            glOrtho(self.current_zoom, -self.current_zoom, -self.current_zoom, self.current_zoom, self.opts.render_size, -self.opts.render_size)
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            return

        try:
            glClearColor(0.0, 0.0, 0.0, 0.0)  # Set clear color to black with alpha 0
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_CULL_FACE)
            glCullFace(GL_FRONT)
            glEnable(GL_BLEND)
            glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA)

            glEnable(GL_ALPHA_TEST)
            glAlphaFunc(GL_GREATER, 0)
            glEnable(GL_COLOR_MATERIAL)

            glEnable(GL_NORMALIZE)
            glEnable(GL_LIGHTING)

            # Create a framebuffer object (FBO) for off-screen rendering
            fbo: Any = glGenFramebuffers(1)
            glBindFramebuffer(GL_FRAMEBUFFER, fbo)

            # Create a renderbuffer for depth testing
            depth_buffer: Any = glGenRenderbuffers(1)
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
            render_texture: Any = glGenTextures(1)
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

            self.current_task.run(self.ctx, self.opts, self.models)

            # Create an image from pixel data
            pixel_data: Any = glReadPixels(
                0,
                0,
                self.opts.render_size,
                self.opts.render_size,
                GL_RGBA,
                GL_UNSIGNED_BYTE,
            )
            img = Image.frombytes(
                "RGBA", (self.opts.render_size, self.opts.render_size), pixel_data
            )
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

            # Save the image
            self.current_task.save_image(self.ctx, self.opts, img)

            # Release resources
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            glDeleteTextures([render_texture])
            glDeleteRenderbuffers(1, [depth_buffer])
            glDeleteFramebuffers(1, [fbo])
            glDisable(GL_COLOR_MATERIAL)
            glDisable(GL_NORMALIZE)
            glDisable(GL_DEPTH_TEST)
            glDisable(GL_LIGHTING)
            
        except Exception as e:
            glutLeaveMainLoop()
            raise e
        
        self.tasks_index += 1
        if self.tasks_index >= len(self.tasks):
            glutLeaveMainLoop()
            return
        
        logging.debug(f"Rendering task {self.current_task}... ({self.tasks_index}/{len(self.tasks)})")






class ItemRenderTask(Task):
    model: MinecraftModel
    model_name: str

    textures_binding: dict[str, int] = Field(default_factory=dict)
    offset: tuple[float, float, float] = (0, 0, 0)
    center_offset: tuple[float, float, float] = (0, 0, 0)
    do_rotate_camera: bool = True
    zoom: int = 8
    additional_rotations: list[RotationModel] = Field(default_factory=list)

    model_config  = ConfigDict(protected_namespaces=())

    def __repr__(self):
        return f"ItemRenderTask(model_name={self.model_name})"
    
    def __str__(self):
        return f"ItemRenderTask(model_name={self.model_name})"

    def get_real_key(self, key: str, textures: dict, max_depth: int = 10) -> str:
        if max_depth == 0:
            return "__not_found__"
        if key not in textures:
            return "__not_found__"
        if textures[key][0] == "#":
            return self.get_real_key(textures[key][1:], textures, max_depth - 1)
        else:
            return textures[key]

    def load_textures(self, ctx: Context, opts: ModelResolverOptions) -> dict[str, Image.Image]:
        res = {}
        vanilla = ctx.inject(Vanilla)
        for key in self.model.textures.keys():
            value = self.get_real_key(key, self.model.textures)
            if value == "__not_found__":
                res[key] = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
            else:
                path = f"minecraft:{value}" if ":" not in value else value
                if path in ctx.assets.textures:
                    texture = ctx.assets.textures[path]
                elif path in vanilla.assets.textures:
                    texture = vanilla.assets.textures[path]
                else:
                    raise KeyError(f"Texture {path} not found")
                img: Image.Image = texture.image
                img = img.convert("RGBA")
                res[key] = img
        return res
    
    def generate_textures_bindings(self, ctx: Context, opts: ModelResolverOptions):
        res = {}
        for key, value in self.load_textures(ctx, opts).items():
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
            res[key] = tex_id
        return res

    def save_image(self, ctx: Context, opts: ModelResolverOptions, img: Image.Image):
        if opts.special_filter is None or len(opts.special_filter) == 0:
            if opts.save_namespace is None:
                model_name = self.model_name.split(":")
                texture_path = f"{model_name[0]}:render/{model_name[1]}"
            else:
                model_name = self.model_name
                texture_path = f"{opts.save_namespace}:render/{model_name.replace(':', '/')}"
            ctx.assets.textures[texture_path] = Texture(img)
        else:
            model_name = self.model_name
            path_save = opts.special_filter.get(model_name, None)
            if path_save is not None:
                with open(path_save, "wb") as f:
                    img.save(f, "PNG")

    def rotate_camera(self):
        if not self.do_rotate_camera:
            return
        # transform the vertices
        scale = self.model.display.gui.scale or [1, 1, 1]
        translation = self.model.display.gui.translation or [0, 0, 0]
        rotation = self.model.display.gui.rotation or [0, 0, 0]

        # reset the matrix
        glLoadIdentity()
        glTranslatef(translation[0] / 16, translation[1] / 16, translation[2] / 16)
        glRotatef(-rotation[0], 1, 0, 0)
        glRotatef(rotation[1] + 180, 0, 1, 0)
        glRotatef(rotation[2], 0, 0, 1)
        glScalef(scale[0], scale[1], scale[2])

    def run(self, ctx: Context, opts: ModelResolverOptions, models: dict[str, MinecraftModel]):
        self.rotate_camera()
        textures_bindings = self.generate_textures_bindings(ctx, opts)
        if self.model.gui_light == "side":
            activate_light = GL_LIGHT0
            deactivate_light = GL_LIGHT1
        else:
            activate_light = GL_LIGHT1
            deactivate_light = GL_LIGHT0
        glEnable(activate_light)
        glDisable(deactivate_light)

        for element in self.model.elements:
            # if shade is False, disable lighting
            if not element.shade:
                glDisable(GL_LIGHTING)
                glDisable(GL_LIGHT0)
                glDisable(GL_LIGHT1)
            self.draw_element(element, textures_bindings)
            if not element.shade:
                glEnable(GL_LIGHTING)
                glEnable(activate_light)

        glDisable(GL_LIGHT0)
        glDisable(GL_LIGHT1)

    def draw_element(self, element: ElementModel, textures_bindings: dict[str, int]):
        glEnable(GL_TEXTURE_2D)

        from_element_centered, to_element_centered = self.center_element(
            element.from_, element.to
        )

        vertices = self.get_vertices(
            from_element_centered, to_element_centered, element.rotation
        )
        for rotation in self.additional_rotations:
            vertices = self.rotate_vertices(vertices, rotation)

        texture_used = [
            element.faces.get("down", None),
            element.faces.get("up", None),
            element.faces.get("north", None),
            element.faces.get("south", None),
            element.faces.get("west", None),
            element.faces.get("east", None),
        ]
        texture_used = [x.texture.lstrip("#") for x in texture_used if x is not None]
        texture_used = list(set(texture_used))

        for texture in texture_used:
            if texture not in textures_bindings:
                continue
            glBindTexture(GL_TEXTURE_2D, textures_bindings[texture])
            glColor3f(1.0, 1.0, 1.0)
            # get all the faces with the same texture
            for face, data in element.faces.items():
                if data.texture.lstrip("#") == texture:
                    self.draw_face(face, data, vertices, element.from_, element.to)

        glDisable(GL_TEXTURE_2D)

    def center_element(
        self,
        from_element: tuple[float, float, float],
        to_element: tuple[float, float, float],
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        # return from_element, to_element
        x1, y1, z1 = from_element
        x2, y2, z2 = to_element

        center = (8, 8, 8)
        center = (center[0] + self.center_offset[0], center[1] + self.center_offset[1], center[2] + self.center_offset[2])

        # compute the new from and to
        from_element = (x1 - center[0], y1 - center[1], z1 - center[2])
        to_element = (x2 - center[0], y2 - center[1], z2 - center[2])

        from_element = (from_element[0] + self.offset[0], from_element[1] + self.offset[1], from_element[2] + self.offset[2])
        to_element = (to_element[0] + self.offset[0], to_element[1] + self.offset[1], to_element[2] + self.offset[2])

        return from_element, to_element

    def get_vertices(
        self,
        from_element: tuple[float, float, float],
        to_element: tuple[float, float, float],
        rotation: RotationModel | None,
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
        return self.rotate_vertices(res, rotation)
    
    def rotate_vertices(self, vertices: tuple[list[float], ...], rotation: RotationModel):
        origin = [x - 8 for x in rotation.origin]
        origin = [x - self.center_offset[i] for i, x in enumerate(origin)]
        origin = [x + self.offset[i] for i, x in enumerate(origin)]
        angle = rotation.angle * pi / 180
        for point in vertices:
            x, y, z = point
            x -= origin[0]
            y -= origin[1]
            z -= origin[2]
            if rotation.axis == "x":
                y, z = y * cos(angle) - z * sin(angle), y * sin(angle) + z * cos(angle)
            elif rotation.axis == "y":
                x, z = x * cos(-angle) - z * sin(-angle), x * sin(-angle) + z * cos(
                    -angle
                )
            elif rotation.axis == "z":
                x, y = x * cos(angle) - y * sin(angle), x * sin(angle) + y * cos(angle)
            x += origin[0]
            y += origin[1]
            z += origin[2]
            point[0], point[1], point[2] = x, y, z

        if rotation.rescale:
            factor = sqrt(2)
            for point in vertices:
                if rotation.axis != "x":
                    point[0] = point[0] * factor
                if rotation.axis != "y":
                    point[1] = point[1] * factor
                if rotation.axis != "z":
                    point[2] = point[2] * factor
        return vertices

    
    def draw_face(
        self,
        face: str,
        data: FaceModel,
        vertices: tuple,
        from_element: tuple[float, float, float],
        to_element: tuple[float, float, float],
    ):

        if data.uv:
            uv = [x / 16 for x in data.uv]
        else:
            uv = self.get_uv(face, from_element, to_element)
            uv = [x / 16 for x in uv]


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

        match data.rotation:
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
                raise RenderError(f"Unknown rotation {data.rotation}")

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
            

NestedDictList = Union[dict[str, Any], list[Any]]
def traverse_all(data: NestedDictList, key: str = "model"):
    if isinstance(data, dict):
        if key in data.keys() and isinstance(data[key], str):
            yield data[key]
        for x in data.values():
            if not (isinstance(x, dict) or isinstance(x, list)):
                continue
            yield from traverse_all(x)
    if isinstance(data, list):
        for x in data:
            if not (isinstance(x, dict) or isinstance(x, list)):
                continue
            yield from traverse_all(x, key)


SimpleWhenCondition = dict[str, str]

HardWhenCondition = TypedDict("HardWhenCondition", {
    "OR": list[SimpleWhenCondition],
    "AND": list[SimpleWhenCondition],
}, total=False)

WhenCondition = HardWhenCondition | SimpleWhenCondition


def verify_when(when: WhenCondition, block_state: dict[str, Any]) -> bool:
    if "OR" in when:
        conditions = when["OR"]
        assert isinstance(conditions, list)
        return any([verify_when(x, block_state) for x in conditions])
    if "AND" in when:
        conditions = when["AND"]
        assert isinstance(conditions, list)
        return all([verify_when(x, block_state) for x in conditions])

    for key, value in when.items():
        if not key in block_state:
            return False
        if str(block_state[key]) != str(value):
            return False
    return True


class StructureRenderTask(Task):
    structure: Structure
    structure_name: str
    display_option: DisplayOptionModel = Field(default_factory=lambda: DisplayOptionModel(
        rotation=(30, 225, 0),
        translation=(0, 0, 0),
        scale=(0.625, 0.625, 0.625)
    ))

    zoom: int = 32

    def rotate_camera(self):
        # transform the vertices
        scale = self.display_option.scale or [1, 1, 1]
        translation = self.display_option.translation or [0, 0, 0]
        rotation = self.display_option.rotation or [0, 0, 0]

        

        # reset the matrix
        glLoadIdentity()
        glTranslatef(translation[0] / 16, translation[1] / 16, translation[2] / 16)
        glRotatef(-rotation[0], 1, 0, 0)
        glRotatef(rotation[1] + 180, 0, 1, 0)
        glRotatef(rotation[2], 0, 0, 1)
        glScalef(scale[0], scale[1], scale[2])


    class Config:
        arbitrary_types_allowed = True

    def get_palettes(self):
        if "palette" in self.structure.data:
            yield self.structure.data["palette"]
        if "palettes" in self.structure.data:
            yield from self.structure.data["palettes"]

    def get_needed_models(self, ctx: Context, opts: ModelResolverOptions):
        vanilla = ctx.inject(Vanilla)
        blocks = cast(list[StructureFileData.Block], self.structure.data["blocks"])
        for palette in self.get_palettes():
            for block in blocks:
                block_state = palette[block["state"]]

                if block_state["Name"] in ctx.assets.blockstates:
                    blockstate_json = ctx.assets.blockstates[block_state["Name"]]
                elif block_state["Name"] in vanilla.assets.blockstates:
                    blockstate_json = vanilla.assets.blockstates[block_state["Name"]]
                else:
                    raise KeyError(f"Blockstate {block_state['Name']} not found")
                
                yield from traverse_all(blockstate_json.data)


    def render_variant(self, 
        variant: dict[str, Any] | list[dict[str, Any]],
        pos: tuple[int, int, int],
        center: tuple[int, int, int],
        ctx: Context, opts: ModelResolverOptions, models: dict[str, MinecraftModel]
        ):
        if isinstance(variant, list):
            # choose randomly a variant by the weight property
            variant = random.choices(variant, weights=[x.get("weight", 1) for x in variant])[0]
        model = variant["model"]
        if model == "minecraft:block/air":
            return
        better_pos = [int(pos[i]) for i in range(3)]

        rots = [
            RotationModel(
            origin=(8, 8, 8),
            axis="y",
            angle=-variant.get("y", 0),
            rescale=False
        ),
        ]
        ItemRenderTask(
            model=models[model],
            model_name=model,
            offset=(pos[0]*16, pos[1]*16, pos[2]*16),
            center_offset=center,
            do_rotate_camera=False,
            additional_rotations=rots,
        ).run(ctx, opts, models)
            

    def run(self, ctx: Context, opts: ModelResolverOptions, models: dict[str, MinecraftModel]):
        self.rotate_camera()
        vanilla = ctx.inject(Vanilla)
        blocks = cast(list[StructureFileData.Block], self.structure.data["blocks"])
        if "palette" in self.structure.data:
            palette = cast(list[StructureFileData.BlockState], self.structure.data["palette"])
        if "palettes" in self.structure.data:
            palette = cast(list[list[StructureFileData.BlockState]], self.structure.data["palettes"]).pop()
        min_x, min_y, min_z = [min(x) for x in zip(*[block["pos"] for block in blocks])]
        max_x, max_y, max_z = [max(x) for x in zip(*[block["pos"] for block in blocks])]
        center = ((max_x + min_x) / 2*16, (max_y + min_y) / 2*16, (max_z + min_z) / 2*16)
        for block in blocks:
            block_state = palette[block["state"]]
            pos = block["pos"]
            nbt = block.get("nbt", None)
            
            if block_state["Name"] in ctx.assets.blockstates:
                blockstate_json = ctx.assets.blockstates[block_state["Name"]]
            elif block_state["Name"] in vanilla.assets.blockstates:
                blockstate_json = vanilla.assets.blockstates[block_state["Name"]]
            else:
                raise KeyError(f"Blockstate {block_state['Name']} not found")
            # find the model path in this blockstate
            if "variants" in blockstate_json.data:
                if "" in blockstate_json.data["variants"]:
                    variant = blockstate_json.data["variants"][""]
                else:
                    parsed_dict = {}
                    for key in blockstate_json.data["variants"].keys():
                        parsed_key = {}
                        key_split = key.split(",")
                        for key_split_part in key_split:
                            state, value = key_split_part.split("=")
                            parsed_key[state] = value
                        parsed_dict[key] = parsed_key
                    variant = None
                    for key, parsed_key in parsed_dict.items():
                        if all([parsed_key.get(x, object()) == block_state["Properties"].get(x, object()) for x in parsed_key.keys()]):
                            variant = blockstate_json.data["variants"][key]
                            break
                    if variant is None:
                        raise KeyError(f"Blockstate {block_state['Name']} has no variant for {block_state['Properties']}")
                self.render_variant(variant, pos, center, ctx, opts, models)
            elif "multipart" in blockstate_json.data:
                for part in blockstate_json.data["multipart"]:
                    if not "when" in part:
                        self.render_variant(part["apply"], pos, center, ctx, opts, models)
                    else:
                        when = part["when"]
                        if verify_when(when, block_state["Properties"]):
                            self.render_variant(part["apply"], pos, center, ctx, opts, models)
            else:
                raise KeyError(f"Blockstate {block_state['Name']} has no variants or multipart")
            
                
            

    def save_image(self, ctx: Context, opts: ModelResolverOptions, img: Image.Image):
        if opts.special_filter is None or len(opts.special_filter) == 0:
            if opts.save_namespace is None:
                model_name = self.structure_name.split(":")
                texture_path = f"{model_name[0]}:render/{model_name[1]}"
            else:
                model_name = self.structure_name
                texture_path = f"{opts.save_namespace}:render/{model_name.replace(':', '/')}"
            ctx.assets.textures[texture_path] = Texture(img)
        else:
            model_name = self.structure_name
            path_save = opts.special_filter.get(model_name, None)
            if path_save is not None:
                with open(path_save, "wb") as f:
                    img.save(f, "PNG")
