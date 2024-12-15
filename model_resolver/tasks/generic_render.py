from OpenGL.GL import *  # type: ignore
from OpenGL.GLUT import *  # type: ignore
from OpenGL.GLU import *  # type: ignore

from beet import Texture, TextureMcmeta
from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel
from model_resolver.item_model.item import Item
from model_resolver.utils import (
    resolve_key,
)
from model_resolver.minecraft_model import (
    MinecraftModel,
    ElementModel,
    RotationModel,
    FaceModel,
)
from model_resolver.item_model.tint_source import TintSource
from typing import Optional, Generator, TypedDict, Literal
from PIL import Image
from model_resolver.tasks.base import Task, RenderError
from math import pi, cos, sin, sqrt


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
        return (
            self.getter.assets.textures[key]
            if key in self.getter.assets.textures
            else None
        )

    def get_texture_mcmeta(self, texture_key: str) -> Optional["TextureMcMetaModel"]:
        texture_key = resolve_key(texture_key)
        texturemcmeta = self.getter.assets.textures_mcmeta.get(texture_key)
        if not texturemcmeta:
            return None
        return TextureMcMetaModel.model_validate(texturemcmeta.data)

    def get_texture_path_to_frames(self, model: MinecraftModel) -> dict[str, list[int]]:
        texture_path_to_frames = {}
        for texture_path in set(
            [x for x in model.textures.values() if isinstance(x, str)]
        ):
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
        # TODO: Check translation[2] for depth
        glTranslatef(-translation[0], translation[1], -translation[2])
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
                if path in self.getter.assets.textures:
                    texture = self.getter.assets.textures[path]
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
            color = tint.resolve(self.getter, item=self.item)
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
