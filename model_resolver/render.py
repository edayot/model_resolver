from OpenGL.GL import *  # type: ignore
from OpenGL.GLUT import *  # type: ignore
from OpenGL.GLU import *  # type: ignore

from beet import Context, Texture, Atlas
from dataclasses import dataclass, field
from model_resolver.item_model.item import Item
from model_resolver.utils import LightOptions, ModelResolverOptions, resolve_key, DEFAULT_RENDER_SIZE
from model_resolver.vanilla import Vanilla
from model_resolver.minecraft_model import (
    ItemModelNamespace,
    MinecraftModel,
    ElementModel,
    RotationModel,
    FaceModel,
    resolve_model,
)
from model_resolver.item_model.model import ItemModel, ItemModelModel
from model_resolver.item_model.tint_source import TintSource
from typing import Optional, Literal, TypedDict, Any, Generator
from pathlib import Path
import logging
from PIL import Image
from math import cos, sin, pi, sqrt
from copy import deepcopy
from pydantic import BaseModel, ConfigDict
import numpy as np
from rich import print


class RenderError(Exception):
    pass


@dataclass(kw_only=True)
class Task:
    ctx: Context
    vanilla: Vanilla
    path_ctx: Optional[str] = None
    path_save: Optional[Path] = None
    render_size: int = DEFAULT_RENDER_SIZE
    zoom: float = 8

    ensure_params: bool = False
    dynamic_textures: dict[str, Image.Image] = field(default_factory=dict)

    def change_params(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(
            self.zoom,
            -self.zoom,
            -self.zoom,
            self.zoom,
            self.render_size,
            -self.render_size,
        )
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def resolve(self) -> Generator["Task", None, None]:
        yield self

    def run(self):
        pass

    def save(self, img: Image.Image):
        if self.path_ctx:
            self.ctx.assets.textures[self.path_ctx] = Texture(img)
        elif self.path_save:
            img.save(self.path_save)


class TickGrouped(TypedDict):
    tick: dict[str, int]
    duration: int


@dataclass(kw_only=True)
class GenericModelRenderTask(Task):
    item: Item

    do_rotate_camera: bool = True
    offset: tuple[float, float, float] = (0, 0, 0)
    center_offset: tuple[float, float, float] = (0, 0, 0)
    additional_rotations: list[RotationModel] = field(default_factory=list)


    def get_texture(self, key: str) -> Texture | None:
        key = resolve_key(key)
        if key in self.ctx.assets.textures:
            return self.ctx.assets.textures[key]
        if key in self.vanilla.assets.textures:
            return self.vanilla.assets.textures[key]
        return None

    def get_texture_mcmeta(self, texture_key: str) -> Optional["TextureMcMetaModel"]:
        key = resolve_key(texture_key)
        if key in self.ctx.assets.textures_mcmeta:
            mcmeta = self.ctx.assets.textures_mcmeta[key]
        elif key in self.vanilla.assets.textures_mcmeta:
            mcmeta = self.vanilla.assets.textures_mcmeta[key]
        else:
            return None
        return TextureMcMetaModel.model_validate(mcmeta.data)

    def get_texture_path_to_frames(self, model: MinecraftModel) -> dict[str, list[int]]:
        texture_path_to_frames = {}
        for texture_path in set([x for x in model.textures.values() if isinstance(x, str)]):
            if isinstance(texture_path, Image.Image):
                continue
            texture = self.get_texture(texture_path)
            if not texture:
                continue
            mcmeta = self.get_texture_mcmeta(texture_path)
            if not mcmeta:
                continue
            if not mcmeta.animation:
                continue
            img: Image.Image = texture.image

            frames = list(mcmeta.animation.resolve_frames(img.height, img.width))
            texture_path_to_frames[texture_path] = frames
        return texture_path_to_frames

    def get_tick_grouped(
        self, texture_path_to_frames: dict[str, list[int]]
    ) -> list[TickGrouped]:
        total_number_of_tick = np.lcm.reduce(
            [len(frames) for frames in texture_path_to_frames.values()]
        )
        ticks = []
        for i in range(total_number_of_tick):
            current_tick = {}
            for texture_path, frames in texture_path_to_frames.items():
                current_tick[texture_path] = frames[i % len(frames)]
            ticks.append(current_tick)

        ticks_grouped = []
        for tick in ticks:
            if len(ticks_grouped) > 0 and ticks_grouped[-1]["tick"] == tick:
                ticks_grouped[-1]["duration"] += 1
            else:
                ticks_grouped.append({"tick": tick, "duration": 1})
        return ticks_grouped

    def rotate_camera(self, model: MinecraftModel):
        if not self.do_rotate_camera:
            return
        # transform the vertices
        scale = model.display.gui.scale or [1, 1, 1]
        translation = model.display.gui.translation or [0, 0, 0]
        rotation = model.display.gui.rotation or [0, 0, 0]

        # reset the matrix
        glLoadIdentity()
        glTranslatef(translation[0] / 16, translation[1] / 16, translation[2] / 16)
        glRotatef(-rotation[0], 1, 0, 0)
        glRotatef(rotation[1] + 180, 0, 1, 0)
        glRotatef(rotation[2], 0, 0, 1)
        glScalef(scale[0], scale[1], scale[2])

    def get_real_key(
        self, key: str, textures: dict[str, str | Image.Image], max_depth: int = 10
    ) -> str | Image.Image:
        if max_depth == 0:
            return "__not_found__"
        if key not in textures:
            return "__not_found__"
        value = textures[key]
        if isinstance(value, Image.Image):
            return textures[key]
        if value[0] == "#":
            return self.get_real_key(value[1:], textures, max_depth - 1)
        else:
            return textures[key]

    def load_textures(
        self, model: MinecraftModel
    ) -> dict[str, tuple[Image.Image, str]]:
        res: dict[str, tuple[Image.Image, str]] = {}
        for key in model.textures.keys():
            value = self.get_real_key(key, model.textures)
            if value == "__not_found__":
                res[key] = (Image.new("RGBA", (16, 16), (0, 0, 0, 0)), "")
            elif isinstance(value, Image.Image):
                res[key] = (value, "dynamic")
            else:
                path = f"minecraft:{value}" if ":" not in value else value
                if path in self.ctx.assets.textures:
                    texture = self.ctx.assets.textures[path]
                elif path in self.vanilla.assets.textures:
                    texture = self.vanilla.assets.textures[path]
                elif path in self.dynamic_textures:
                    texture = Texture(self.dynamic_textures[path])
                else:
                    texture = Texture(Image.new("RGBA", (16, 16), (0, 0, 0, 0)))
                img: Image.Image = texture.image
                img = img.convert("RGBA")
                res[key] = (img, path)
        return res

    def generate_textures_bindings(
        self, model: MinecraftModel
    ) -> dict[str, tuple[int, str]]:
        res: dict[str, tuple[int, str]] = {}
        textures = self.load_textures(model)
        for key, (value, path) in textures.items():
            tex_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            value = value.convert("RGBA")
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
            res[key] = (tex_id, path)
        return res

    def render_model(self, model: MinecraftModel, tints: list[TintSource]):
        self.rotate_camera(model)
        textures_bindings = self.generate_textures_bindings(model)
        if model.gui_light == "side":
            activate_light = GL_LIGHT0
            deactivate_light = GL_LIGHT1
        else:
            activate_light = GL_LIGHT1
            deactivate_light = GL_LIGHT0
        glEnable(activate_light)
        glDisable(deactivate_light)

        for element in model.elements:
            # if shade is False, disable lighting
            if not element.shade:
                glDisable(GL_LIGHTING)
                glDisable(GL_LIGHT0)
                glDisable(GL_LIGHT1)
            self.draw_element(element, textures_bindings, tints)
            if not element.shade:
                glEnable(GL_LIGHTING)
                glEnable(activate_light)

        glDisable(GL_LIGHT0)
        glDisable(GL_LIGHT1)

    def draw_element(
        self,
        element: ElementModel,
        textures_bindings: dict[str, tuple[int, str]],
        tints: list[TintSource],
    ):
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
            glBindTexture(GL_TEXTURE_2D, textures_bindings[texture][0])
            glColor3f(1.0, 1.0, 1.0)
            # get all the faces with the same texture
            for face, data in element.faces.items():
                if data.texture.lstrip("#") == texture:
                    self.draw_face(
                        face, data, vertices, element.from_, element.to, tints, texture
                    )

        glDisable(GL_TEXTURE_2D)

    def center_element(
        self,
        from_element: tuple[float, float, float],
        to_element: tuple[float, float, float],
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        # return from_element, to_element
        x1, y1, z1 = from_element
        x2, y2, z2 = to_element

        center: tuple[float, float, float] = (8, 8, 8)
        center = (
            center[0] + self.center_offset[0],
            center[1] + self.center_offset[1],
            center[2] + self.center_offset[2],
        )

        # compute the new from and to
        from_element = (x1 - center[0], y1 - center[1], z1 - center[2])
        to_element = (x2 - center[0], y2 - center[1], z2 - center[2])

        from_element = (
            from_element[0] + self.offset[0],
            from_element[1] + self.offset[1],
            from_element[2] + self.offset[2],
        )
        to_element = (
            to_element[0] + self.offset[0],
            to_element[1] + self.offset[1],
            to_element[2] + self.offset[2],
        )

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

    def rotate_vertices(
        self, vertices: tuple[list[float], ...], rotation: RotationModel
    ):
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
        face: Literal["down", "up", "north", "south", "east", "west"],
        data: FaceModel,
        vertices: tuple,
        from_element: tuple[float, float, float],
        to_element: tuple[float, float, float],
        tints: list[TintSource],
        texture: Optional[str] = None,
    ):

        if data.uv:
            uv = [x / 16 for x in data.uv]
        else:
            uv = list(self.get_uv(face, from_element, to_element))
            uv = [x / 16 for x in uv]
        assert len(uv) == 4

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

        color = (1.0, 1.0, 1.0)
        if len(tints) > data.tintindex and data.tintindex >= 0 and self.item:
            tint = tints[data.tintindex]
            color = tint.resolve(self.ctx, self.vanilla, item=self.item)
            color = (color[0] / 255, color[1] / 255, color[2] / 255)
        for i, (uv0, uv1) in enumerate(texcoords):
            glColor3f(*color)
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
                x_offset = (-(z2 + z1)) % 16
                y_offset = (y2 - y1) % 16
                return (z1 + x_offset, y1 + y_offset, z2 + x_offset, y2 + y_offset)
            case "up" | "down":
                x_offset = 0
                y_offset = 0
                return (x1 + x_offset, z1 + y_offset, x2 + x_offset, z2 + y_offset)
            case "south" | "north":
                x_offset = (-(x2 + x1)) % 16
                y_offset = (y2 - y1) % 16
                return (x1 + x_offset, y1 + y_offset, x2 + x_offset, y2 + y_offset)
            case _:
                raise RenderError(f"Unknown face {face}")


@dataclass(kw_only=True)
class ItemModelModelRenderTask(GenericModelRenderTask):
    models: list[tuple[MinecraftModel, list[TintSource]]]

    def resolve(self) -> Generator[Task, None, None]:
        yield self

    def run(self):
        for model, tints in self.models:
            self.render_model(model, tints)


@dataclass(kw_only=True)
class ItemRenderTask(GenericModelRenderTask):

    def get_parsed_item_model(self) -> ItemModel:
        assert self.item
        item_model_key = self.item.components["minecraft:item_model"]
        if not item_model_key:
            raise RenderError(f"Item {self.item} does not have a model")
        if item_model_key in self.ctx.assets[ItemModelNamespace]:
            item_model = self.ctx.assets[ItemModelNamespace][item_model_key]
        elif item_model_key in self.vanilla.assets[ItemModelNamespace]:
            item_model = self.vanilla.assets[ItemModelNamespace][item_model_key]
        else:
            raise RenderError(f"Item model {item_model_key} not found")
        return ItemModel.model_validate(item_model.data)

    def run(self):
        parsed_item_model = self.get_parsed_item_model()
        for model in parsed_item_model.resolve(self.ctx, self.vanilla, self.item):
            model_def = model.get_model(self.ctx, self.vanilla, self.item).bake()
            self.render_model(model_def, model.tints)

    def resolve(self) -> Generator[Task, None, None]:
        parsed_item_model = self.get_parsed_item_model()
        item_model_models = list(
            parsed_item_model.resolve(self.ctx, self.vanilla, self.item)
        )
        texture_path_to_frames = {}
        for model in item_model_models:
            model_def = model.get_model(self.ctx, self.vanilla, self.item).bake()
            texture_path_to_frames.update(self.get_texture_path_to_frames(model_def))
        if len(texture_path_to_frames) == 0:
            yield self
            return
        ticks_grouped = self.get_tick_grouped(texture_path_to_frames)

        for i, tick in enumerate(ticks_grouped):
            # get the images for the tick
            images = {}
            for texture_path, index in tick["tick"].items():
                texture = self.get_texture(texture_path)
                if not texture:
                    raise RenderError(f"WTF")
                img: Image.Image = texture.image
                cropped = img.crop(
                    (0, index * img.width, img.width, (index + 1) * img.width)
                )
                images[texture_path] = cropped

            models: list[tuple[MinecraftModel, list[TintSource]]] = []
            for model in item_model_models:
                model_def = model.get_model(self.ctx, self.vanilla, self.item).bake()
                model_def = model_def.model_copy()
                textures = {}
                for key, value in model_def.textures.items():
                    if isinstance(value, Image.Image):
                        raise RenderError(f"WTF is going on")
                    if resolve_key(value) in images:
                        textures[key] = images[value]
                    else:
                        textures[key] = value
                model_def.textures = textures
                models.append((model_def, model.tints))

            if self.path_save:
                new_path_save = self.path_save / f"{i}_{tick['duration']}.png"
            else:
                new_path_save = None
            if self.path_ctx:
                new_path_ctx = self.path_ctx + f"/{i}_{tick['duration']}"
            else:
                new_path_ctx = None
            yield ItemModelModelRenderTask(
                ctx=self.ctx,
                vanilla=self.vanilla,
                models=models,
                item=self.item,
                do_rotate_camera=self.do_rotate_camera,
                offset=self.offset,
                center_offset=self.center_offset,
                additional_rotations=self.additional_rotations,
                path_ctx=new_path_ctx,
                path_save=new_path_save,
                render_size=self.render_size,
                zoom=self.zoom,
                ensure_params=self.ensure_params,
                dynamic_textures=self.dynamic_textures,
            )


@dataclass(kw_only=True)
class ModelRenderTask(GenericModelRenderTask):
    model: MinecraftModel
    tints: list[TintSource] = field(default_factory=list)
    item: Item = field(default_factory=lambda: Item(id="do_not_use"))

    def resolve(self) -> Generator[Task, None, None]:
        yield self

    def run(self):
        self.render_model(self.model, self.tints)


class FrameModel(BaseModel):
    index: int
    time: int


class AnimationModel(BaseModel):
    interpolate: bool = False
    frametime: int = 1
    frames: Optional[list[int | FrameModel]] = None

    def resolve_frames(self, height: int, width: int) -> Generator[int, None, None]:
        if not self.frames:
            for i in range(height // width):
                for _ in range(self.frametime):
                    yield i
            return
        for frame in self.frames:
            if isinstance(frame, int):
                for _ in range(self.frametime):
                    yield frame
            else:
                for _ in range(frame.time):
                    yield frame.index


class TextureMcMetaModel(BaseModel):
    animation: Optional[AnimationModel] = None


@dataclass(kw_only=True)
class ModelPathRenderTask(GenericModelRenderTask):
    model: str
    tints: list[TintSource] = field(default_factory=list)
    item: Item = field(default_factory=lambda: Item(id="do_not_use"))

    def run(self):
        if len(self.tints) > 0:
            assert self.item, "Tints are only available if you provide an item"
        model = self.get_parsed_model()
        self.render_model(model, self.tints)

    def get_parsed_model(self) -> MinecraftModel:
        key = resolve_key(self.model)
        if key in self.ctx.assets.models:
            data = self.ctx.assets.models[key].data
        elif key in self.vanilla.assets.models:
            data = self.vanilla.assets.models[key].data
        else:
            raise RenderError(f"Model {key} not found")
        return MinecraftModel.model_validate(resolve_model(data, self.ctx, self.vanilla)).bake()

    def resolve(self) -> Generator[Task, None, None]:
        model = self.get_parsed_model()
        if not model.textures:
            yield self
            return
        texture_path_to_frames = self.get_texture_path_to_frames(model)
        if len(texture_path_to_frames) == 0:
            yield self
            return

        ticks_grouped = self.get_tick_grouped(texture_path_to_frames)

        for i, tick in enumerate(ticks_grouped):
            # get the images for the tick
            images = {}
            for texture_path, index in tick["tick"].items():
                texture = self.get_texture(texture_path)
                if not texture:
                    raise RenderError(f"WTF")
                img: Image.Image = texture.image
                cropped = img.crop(
                    (0, index * img.width, img.width, (index + 1) * img.width)
                )
                images[texture_path] = cropped
            textures = {}
            for key, value in model.textures.items():
                if isinstance(value, Image.Image):
                    raise RenderError(f"WTF is going on")
                if resolve_key(value) in images:
                    textures[key] = images[value]
                else:
                    textures[key] = value
            new_model = model.model_copy()
            new_model.textures = textures
            if self.path_save:
                new_path_save = self.path_save / f"{i}_{tick['duration']}.png"
            else:
                new_path_save = None
            if self.path_ctx:
                new_path_ctx = self.path_ctx + f"/{i}_{tick['duration']}"
            else:
                new_path_ctx = None
            yield ModelRenderTask(
                ctx=self.ctx,
                vanilla=self.vanilla,
                model=new_model,
                tints=self.tints,
                item=self.item,
                do_rotate_camera=self.do_rotate_camera,
                offset=self.offset,
                center_offset=self.center_offset,
                additional_rotations=self.additional_rotations,
                path_ctx=new_path_ctx,
                path_save=new_path_save,
                render_size=self.render_size,
                zoom=self.zoom,
                ensure_params=self.ensure_params,
                dynamic_textures=self.dynamic_textures,
            )


class AtlasDict(TypedDict):
    type: str
    textures: list[str]
    palette_key: str
    permutations: dict[str, str]


@dataclass
class Render:
    ctx: Context

    tasks: list[Task] = field(default_factory=list)
    tasks_index: int = 0
    light: LightOptions = field(default_factory=LightOptions)
    dynamic_textures: dict[str, Image.Image] = field(default_factory=dict)

    def __post_init__(self):
        opts = self.ctx.validate("model_resolver", ModelResolverOptions)
        self.vanilla = Vanilla(
            self.ctx,
            extend_namespace=([], [ItemModelNamespace]),
            minecraft_version=opts.minecraft_version,
        )

    def __repr__(self):
        return f"<Render of {len(self.tasks)} tasks>"

    @property
    def current_task(self):
        return self.tasks[self.tasks_index]

    def add_item_task(
        self,
        item: Item,
        *,
        path_ctx: Optional[str] = None,
        path_save: Optional[Path] = None,
        render_size: int = DEFAULT_RENDER_SIZE,
    ):
        self.tasks.append(
            ItemRenderTask(
                ctx=self.ctx,
                vanilla=self.vanilla,
                item=item.fill(self.ctx),
                path_ctx=path_ctx,
                path_save=path_save,
                render_size=render_size,
            )
        )

    def add_model_task(
        self,
        model: str,
        *,
        path_ctx: Optional[str] = None,
        path_save: Optional[Path] = None,
        render_size: int = DEFAULT_RENDER_SIZE,
    ):
        self.tasks.append(
            ModelPathRenderTask(
                ctx=self.ctx,
                vanilla=self.vanilla,
                model=model,
                path_ctx=path_ctx,
                path_save=path_save,
                render_size=render_size,
            )
        )

    def resolve_dynamic_textures(self):
        # first, resolve all vanilla altas
        cache = self.ctx.cache.get("model_resolver")
        assert cache
        opts = self.ctx.validate("model_resolver", ModelResolverOptions)
        if "dynamic_textures" in cache.json and opts.use_cache:
            for key, path in cache.json["dynamic_textures"].items():
                self.dynamic_textures[key] = Image.open(path)
            return
        # construct the dynamic textures
        atlases = {
            **{key: value for key, value in self.vanilla.assets.atlases.items()},
            **{key: value for key, value in self.ctx.assets.atlases.items()},
        }
        for key, atlas in atlases.items():
            self.resolve_altas(key, atlas)
        if not opts.use_cache:
            return
        # construct the cache
        cache.json["dynamic_textures"] = {}
        for key, value in self.dynamic_textures.items():
            path = cache.get_path(f"{key}.png")
            with open(path, "wb") as f:
                value.save(f, "PNG")
            cache.json["dynamic_textures"][key] = str(path)

    def apply_palette(
        self, texture: Image.Image, palette: Image.Image, color_palette: Image.Image
    ) -> Image.Image:
        new_image = Image.new("RGBA", texture.size)
        texture = texture.convert("RGBA")
        palette = palette.convert("RGB")
        color_palette = color_palette.convert("RGB")
        for x in range(texture.width):
            for y in range(texture.height):
                pixel = texture.getpixel((x, y))
                if not isinstance(pixel, tuple):
                    raise ValueError("Texture is not RGBA")
                color = pixel[:3]
                alpha = pixel[3]
                # if the color is in palette_key, replace it with the color from color_palette
                found = False
                for i in range(palette.width):
                    for j in range(palette.height):
                        if palette.getpixel((i, j)) == color:
                            new_color = color_palette.getpixel((i, j))
                            if not isinstance(new_color, tuple):
                                raise ValueError("Color palette is not RGB")
                            new_image.putpixel((x, y), new_color + (alpha,))
                            found = True
                            break
                    if found:
                        break
                if not found:
                    new_image.putpixel((x, y), pixel)
        return new_image

    def resolve_altas(self, key: str, atlas: Atlas):
        for source in atlas.data["sources"]:
            if source["type"] != "paletted_permutations":
                continue
            source: AtlasDict
            for texture in source["textures"]:
                for variant, color_palette_path in source["permutations"].items():
                    self.resolve_altas_texture(
                        texture, variant, source, color_palette_path
                    )

    def resolve_altas_texture(
        self, texture: str, variant: str, source: AtlasDict, color_palette_path: str
    ):
        new_texture_path = f"{texture}_{variant}"
        new_texture_path = resolve_key(new_texture_path)

        palette_key = resolve_key(source["palette_key"])
        if palette_key in self.ctx.assets.textures:
            palette = self.ctx.assets.textures[palette_key].image
        elif palette_key in self.vanilla.assets.textures:
            palette = self.vanilla.assets.textures[palette_key].image
        else:
            raise RenderError(f"Palette {palette_key} not found")

        color_palette_key = resolve_key(color_palette_path)
        if color_palette_key in self.ctx.assets.textures:
            color_palette: Image.Image = self.ctx.assets.textures[
                color_palette_key
            ].image
        elif color_palette_key in self.vanilla.assets.textures:
            color_palette: Image.Image = self.vanilla.assets.textures[
                color_palette_key
            ].image
        else:
            raise RenderError(f"Color palette {color_palette_key} not found")

        grayscale_key = resolve_key(texture)
        if grayscale_key in self.ctx.assets.textures:
            grayscale = self.ctx.assets.textures[grayscale_key].image
        elif grayscale_key in self.vanilla.assets.textures:
            grayscale = self.vanilla.assets.textures[grayscale_key].image

        img = self.apply_palette(grayscale, palette, color_palette)

        self.dynamic_textures[new_texture_path] = img

    def run(self):
        self.resolve_dynamic_textures()
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

        new_tasks = []
        for task in self.tasks:
            new_tasks.extend(task.resolve())
        self.tasks = new_tasks

        glutDisplayFunc(self.display)
        glutIdleFunc(self.display)
        glutReshapeFunc(self.reshape)

        glutMainLoop()

    def reshape(self, width: int, height: int):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        zoom = 8
        glOrtho(zoom, -zoom, -zoom, zoom, 512, -512)
        glMatrixMode(GL_MODELVIEW)

    def display(self):
        if self.tasks_index >= len(self.tasks):
            glutLeaveMainLoop()
            return
        try:
            x = self.real_display()
        except:
            glutLeaveMainLoop()
            raise
        self.tasks_index += x
        if self.tasks_index >= len(self.tasks):
            glutLeaveMainLoop()
            return
        logging.debug(
            f"Rendering task {self.current_task}... ({self.tasks_index}/{len(self.tasks)})"
        )

    def real_display(self):
        if not self.current_task.ensure_params:
            self.current_task.ensure_params = True
            self.current_task.change_params()
            return 0

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
        fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, fbo)

        depth_buffer = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, depth_buffer)
        glRenderbufferStorage(
            GL_RENDERBUFFER,
            GL_DEPTH_COMPONENT,
            self.current_task.render_size,
            self.current_task.render_size,
        )
        glFramebufferRenderbuffer(
            GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depth_buffer
        )
        render_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, render_texture)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            self.current_task.render_size,
            self.current_task.render_size,
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
        glViewport(0, 0, self.current_task.render_size, self.current_task.render_size)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)  # type: ignore

        self.current_task.dynamic_textures = self.dynamic_textures
        self.current_task.run()

        pixel_data = glReadPixels(
            0,
            0,
            self.current_task.render_size,
            self.current_task.render_size,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
        )
        img = Image.frombytes(
            "RGBA",
            (self.current_task.render_size, self.current_task.render_size),
            pixel_data,
        )
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        # Save the image
        self.current_task.save(img)

        # Release resources
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glDeleteTextures([render_texture])
        glDeleteRenderbuffers(1, [depth_buffer])
        glDeleteFramebuffers(1, [fbo])
        glDisable(GL_COLOR_MATERIAL)
        glDisable(GL_NORMALIZE)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)

        return 1
