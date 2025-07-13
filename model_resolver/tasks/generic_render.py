from pathlib import Path
from OpenGL.GL import *  # type: ignore
from OpenGL.GLUT import *  # type: ignore
from OpenGL.GLU import *  # type: ignore

from beet import Texture
from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel
from model_resolver.item_model.item import Item
from model_resolver.utils import (
    PackGetterV2,
    resolve_key,
    log,
)
from model_resolver.minecraft_model import (
    MinecraftModel,
    ElementModel,
    MultiTextureResolved,
    ResolvableTexture,
    ResolvedTexture,
    RotationModel,
    FaceModel,
    TextureSource,
)
from model_resolver.item_model.tint_source import TintSource
from typing import Any, Optional, Generator, Literal
from PIL import Image
from model_resolver.tasks.base import Task, RenderError
from math import pi, cos, sin, sqrt
from rich import print  # noqa


type TextureBindingsValue = tuple[tuple[tuple[int, TintSource | None], ...], str]
type TextureBindings = dict[str, TextureBindingsValue]

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


class TickGrouped(BaseModel):
    tick: dict[str, int]
    duration: int
    tick_before: Optional["TickGrouped"] = None
    tick_after: Optional["TickGrouped"] = None


@dataclass(kw_only=True)
class GenericModelRenderTask(Task):
    item: Item

    do_rotate_camera: bool = True
    offset: tuple[float, float, float] = (0, 0, 0)
    center_offset: tuple[float, float, float] = (0, 0, 0)
    additional_rotations: list[RotationModel] = field(default_factory=list)

    def flush(self):
        super().flush()
        self.item = Item(id="do_not_use")

    def get_textures(self, model: MinecraftModel, images: dict[str, Image.Image]):
        textures = {}
        for key, value in model.textures.items():
            if isinstance(value, Image.Image):
                raise RenderError(f"WTF is going on")
            elif isinstance(value, tuple):
                for texture, tint in value:
                    ...
            elif resolve_key(value) in [resolve_key(k) for k in images.keys()]:
                textures[key] = images[value]
            else:
                textures[key] = value
        return textures

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
        self, key: str, textures: dict[str, TextureSource], max_depth: int = 10
    ) -> ResolvableTexture:
        if max_depth == 0:
            return None
        if key not in textures:
            return None
        value = textures[key]
        if isinstance(value, Image.Image):
            return value
        if isinstance(value, tuple):
            return value
        elif isinstance(value, str):
            if value[0] == "#":
                return self.get_real_key(value[1:], textures, max_depth - 1)
            else:
                return value
        else:
            raise RenderError(f"Unknown texture type {type(value)} for key {key}")
    
    def get_missingno(self) -> Image.Image:
        """Returns a missingno image for debugging purposes."""
        if self.getter.opts.transparent_missingno:
            return Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        path = Path(__file__).parent.parent / "missingno.png"
        if not path.exists():
            raise RenderError(f"Missingno image not found at {path}")
        return Image.open(path).convert("RGBA")

    def load_textures(
        self, model: MinecraftModel
    ) -> dict[str, tuple[ResolvedTexture, str]]:
        res: dict[str, tuple[ResolvedTexture, str]] = {}
        for key in model.textures.keys():
            value = self.get_real_key(key, model.textures)
            if value is None:
                res[key] = (self.get_missingno(), "empty")
                log.warning(f"Texture {key} not found in model")
            elif isinstance(value, Image.Image):
                res[key] = (value, "dynamic")
            elif isinstance(value, tuple):
                # if value is a tuple, it means it's a multi-texture
                textures: list[MultiTextureResolved] = []
                for texture, tint in value:
                    path = resolve_key(texture)
                    if path in self.getter.assets.textures:
                        texture = self.getter.assets.textures[path]
                        img: Image.Image = texture.image
                    elif path in self.dynamic_textures:
                        texture = Texture(self.dynamic_textures[path])
                        img = texture.image
                    else:
                        img = self.get_missingno()
                        log.warning(f"Texture {key} not found at {path}")
                        
                    img = img.convert("RGBA")
                    textures.append((img, tint))
                res[key] = (tuple(textures), key)
            else:
                path = resolve_key(value)
                if path in self.getter.assets.textures:
                    texture = self.getter.assets.textures[path]
                    img: Image.Image = texture.image
                elif path in self.dynamic_textures:
                    texture = Texture(self.dynamic_textures[path])
                    img = texture.image
                else:
                    img = self.get_missingno()
                    log.warning(f"Texture {key} not found at {path}")
                img = img.convert("RGBA")
                res[key] = (img, path)
        return res

    def generate_textures_bindings(
        self, model: MinecraftModel
    ):
        res: TextureBindings = {}
        textures = self.load_textures(model)
        for key, (value, path) in textures.items():
            if isinstance(value, Image.Image):
                tex_id: int = glGenTextures(1)
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
                res[key] = (((tex_id, None),), path)
            elif isinstance(value, tuple):
                res_value: list[tuple[int, TintSource | None]] = []
                for img, tint in value:
                    tex_id: int = glGenTextures(1)
                    glBindTexture(GL_TEXTURE_2D, tex_id)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                    img = img.convert("RGBA")
                    img_data = img.tobytes("raw", "RGBA")
                    glTexImage2D(
                        GL_TEXTURE_2D,
                        0,
                        GL_RGBA,
                        img.width,
                        img.height,
                        0,
                        GL_RGBA,
                        GL_UNSIGNED_BYTE,
                        img_data,
                    )
                    res_value.append((tex_id, tint))
                res[key] = (tuple(res_value), path)
            else:
                raise RenderError(f"Unknown texture type {type(value)} for key {key}")
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
        textures_bindings: TextureBindings,
        tints: list[TintSource],
    ):
        

        from_element_centered, to_element_centered = self.center_element(
            element.from_, element.to
        )

        vertices = self.get_vertices(
            from_element_centered, to_element_centered, element.rotation
        )
        for rotation in self.additional_rotations:
            vertices = self.rotate_vertices(vertices, rotation)

        # texture_used = [
        #     element.faces.get("down", None),
        #     element.faces.get("up", None),
        #     element.faces.get("north", None),
        #     element.faces.get("south", None),
        #     element.faces.get("west", None),
        #     element.faces.get("east", None),
        # ]
        # texture_used = [x.texture.lstrip("#") for x in texture_used if x is not None]
        # texture_used = list(set(texture_used))

        # for texture in texture_used:
        #     if texture not in textures_bindings:
        #         continue
        #     glBindTexture(GL_TEXTURE_2D, textures_bindings[texture][0])
        #     glColor3f(1.0, 1.0, 1.0)
        #     # get all the faces with the same texture
        #     for face, data in element.faces.items():
        #         if data.texture.lstrip("#") == texture:
        #             self.draw_face(
        #                 face, data, vertices, element.from_, element.to, tints, texture
        #             )

        for face, data in element.faces.items():
            if (textvar := data.texture.lstrip("#")) not in textures_bindings:
                continue
            self.draw_face(
                face,
                data,
                vertices,
                element.from_,
                element.to,
                tints,
                textures_bindings[textvar],
            )
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

            if rotation.rescale:
                factor = sqrt(2)
                if rotation.axis != "x":
                    x = x * factor
                if rotation.axis != "y":
                    y = y * factor
                if rotation.axis != "z":
                    z = z * factor

            x += origin[0]
            y += origin[1]
            z += origin[2]
            point[0], point[1], point[2] = x, y, z

        return vertices

    def draw_face(
        self,
        face: Literal["down", "up", "north", "south", "east", "west"],
        data: FaceModel,
        vertices: tuple,
        from_element: tuple[float, float, float],
        to_element: tuple[float, float, float],
        tints: list[TintSource],
        bindings: TextureBindingsValue,
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

        glEnable(GL_TEXTURE_2D)
        
        # Save current blend function
        blend_src = glGetIntegerv(GL_BLEND_SRC)
        blend_dst = glGetIntegerv(GL_BLEND_DST)
        
        depht_coef = 0.1

        for layer_index, (tex_id, tint) in enumerate(bindings[0]):
            glBindTexture(GL_TEXTURE_2D, tex_id)
            color = (1.0, 1.0, 1.0)
            real_tint: TintSource | None = tint
            if tint is None and len(tints) > data.tintindex and data.tintindex >= 0:
                real_tint = tints[data.tintindex]
            if real_tint is not None:
                color = real_tint.resolve(self.getter, item=self.item)
                color = (color[0] / 255, color[1] / 255, color[2] / 255)  
            
            # Apply depth offset for layering by modifying polygon offset
            if layer_index > 0:
                glEnable(GL_POLYGON_OFFSET_FILL)
                glPolygonOffset(-layer_index * depht_coef, -layer_index * depht_coef)
                # Change blend function for layered textures
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            glBegin(GL_QUADS)
            for i, (v0, v1, v2) in enumerate(triangulated_vertices):
                normal = normals[i]
                glNormal3fv(normal)
            for i, (uv0, uv1) in enumerate(texcoords):
                glColor3f(*color)
                glTexCoord2f(uv[uv0], uv[uv1])
                glVertex3fv(rotated_vertices[i])
            glEnd()
            
            # Disable polygon offset after use
            if layer_index > 0:
                glDisable(GL_POLYGON_OFFSET_FILL)
        
        # Restore previous blend function
        glBlendFunc(blend_src, blend_dst)
        
        glDisable(GL_TEXTURE_2D)

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
class Animation:
    textures: list[dict[str, str | Image.Image]]
    getter: PackGetterV2
    animation_framerate: int

    cache_texture_animated: Any = None

    @property
    def duration_coef(self):
        if self.animation_framerate % 20 != 0 and self.animation_framerate > 0:
            raise TypeError(f"animation_frame must be a positive multiple of 20")
        return self.animation_framerate // 20

    @property
    def is_animated(self) -> bool:
        texture_animated = self.get_texture_animated()
        if len(texture_animated) == 0:
            return False
        return True

    def get_texture_animated(self) -> dict[str, tuple[list[int], bool]]:
        if self.cache_texture_animated is not None:
            return self.cache_texture_animated
        texture_animated: dict[str, tuple[list[int], bool]] = {}
        for textures in self.textures:
            for texture_path in textures.values():
                if isinstance(texture_path, Image.Image):
                    raise RenderError(f"WTF is going on")
                if resolve_key(texture_path) in texture_animated:
                    continue
                texture = self.texture(texture_path)
                if not texture:
                    continue
                mcmeta = self.mcmeta(texture_path)
                if not mcmeta:
                    continue
                if not mcmeta.animation:
                    continue

                frames = list(
                    mcmeta.animation.resolve_frames(
                        texture.image.height, texture.image.width
                    )
                )
                texture_animated[texture_path] = (frames, mcmeta.animation.interpolate)
        self.cache_texture_animated = texture_animated
        return texture_animated

    def get_tick_grouped(
        self,
        texture_animated: dict[str, tuple[list[int], bool]],
    ) -> list[TickGrouped]:
        total_number_of_tick = np.lcm.reduce(
            [len(frames[0]) for frames in texture_animated.values()]
        )
        ticks = []
        for i in range(total_number_of_tick):
            current_tick = {}
            for texture_path, (frames, interpolated) in texture_animated.items():
                current_tick[texture_path] = frames[i % len(frames)]
            ticks.append(current_tick)

        is_interpolated = any(
            texture_animated[texture_path][1]
            for texture_path in texture_animated.keys()
        )

        ticks_grouped: list[TickGrouped] = []
        for tick in ticks:
            if (
                len(ticks_grouped) > 0
                and ticks_grouped[-1].tick == tick
                and not is_interpolated
            ):
                ticks_grouped[-1].duration += 1
            else:
                ticks_grouped.append(TickGrouped(tick=tick, duration=1))

        for i, tick in enumerate(ticks_grouped):
            tick.tick_before = ticks_grouped[(i - 1) % len(ticks_grouped)]
            tick.tick_after = ticks_grouped[(i + 1) % len(ticks_grouped)]

        return ticks_grouped

    def get_frames(
        self,
    ) -> Generator[tuple[int, tuple[dict[str, Image.Image], int]], None, None]:
        if not self.is_animated:
            raise RenderError("Should not be called if is_animated is False")
        texture_animated = self.get_texture_animated()
        if len(texture_animated) == 0:
            raise RenderError("No animated textures found")

        ticks_grouped = self.get_tick_grouped(texture_animated)

        for i, tick in enumerate(ticks_grouped):
            images = self.get_images(tick, texture_animated)
            yield i, (images, tick.duration)

    def get_images(
        self, tick: TickGrouped, texture_animated: dict[str, tuple[list[int], bool]]
    ) -> dict[str, Image.Image]:
        images = {}
        for texture_path, index in tick.tick.items():
            texture = self.texture(texture_path)
            if not texture:
                raise RenderError(f"WTF")
            img: Image.Image = texture.image
            cropped = img.crop(
                (0, index * img.width, img.width, (index + 1) * img.width)
            )
            if texture_animated[texture_path][1]:
                lenght = 0
                current_index = index
                tick_before = tick.tick_before
                assert tick_before is not None
                for _ in range(999_999):
                    if tick_before.tick[texture_path] != current_index:
                        break
                    tick_before = tick_before.tick_before
                    assert tick_before is not None
                    lenght += 1

                left_lenght = lenght
                tick_after = tick.tick_after
                assert tick_after is not None
                next_index = current_index
                for _ in range(999_999):
                    if tick_after.tick[texture_path] != current_index:
                        next_index = tick_after.tick[texture_path]
                        lenght += 1
                        break
                    tick_after = tick_after.tick_after
                    assert tick_after is not None
                    lenght += 1
                if lenght > 1:
                    next_cropped = img.crop(
                        (
                            0,
                            next_index * img.width,
                            img.width,
                            (next_index + 1) * img.width,
                        )
                    )
                    t = left_lenght / (lenght)
                    cropped = self.blend_images(cropped, next_cropped, t)
            images[texture_path] = cropped
        return images

    @staticmethod
    def blend_images(img1: Image.Image, img2: Image.Image, t: float) -> Image.Image:
        def lerp(a: int, b: int, t: float) -> int:
            return int(a * (1 - t) + b * t)

        assert img1.size == img2.size
        assert t >= 0 and t <= 1
        img1 = img1.convert("RGBA")
        img2 = img2.convert("RGBA")
        result = Image.new("RGBA", img1.size)
        for x in range(img1.width):
            for y in range(img1.height):
                pixel1 = img1.getpixel((x, y))
                pixel2 = img2.getpixel((x, y))
                assert isinstance(pixel1, tuple) and isinstance(pixel2, tuple)
                assert len(pixel1) == 4 and len(pixel2) == 4
                # Blend the pixels using alpha blending
                blended_pixel = (
                    lerp(pixel1[0], pixel2[0], t),
                    lerp(pixel1[1], pixel2[1], t),
                    lerp(pixel1[2], pixel2[2], t),
                    lerp(pixel1[3], pixel2[3], t),
                )
                result.putpixel((x, y), blended_pixel)
        return result

    def texture(self, key: str) -> Optional[Texture]:
        return self.getter.assets.textures.get(resolve_key(key))

    def mcmeta(self, key: str) -> Optional[TextureMcMetaModel]:
        mcmeta = self.getter.assets.textures_mcmeta.get(resolve_key(key))
        if not mcmeta:
            return None
        return TextureMcMetaModel.model_validate(mcmeta.data)
