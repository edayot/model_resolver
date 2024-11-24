from math import cos, pi, sin, sqrt
from OpenGL.GL import *  # type: ignore
from OpenGL.GLUT import *  # type: ignore
from OpenGL.GLU import *  # type: ignore

from typing import Iterable, Literal, Optional, Sequence, Union, get_args
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from beet import Context
from model_resolver.item_model.item import Item
from model_resolver.item_model.tint_source import TintSource
from model_resolver.vanilla import Vanilla
from model_resolver.utils import resolve_key, log
from functools import cached_property
from PIL import Image


class DisplayOptionModel(BaseModel):
    _rotation: Optional[tuple[float, float, float]] = Field(
        validation_alias=AliasChoices("rotation", "_rotation"), default=None
    )

    @property
    def rotation(self) -> tuple[float, float, float]:
        if self._rotation is not None:
            return self._rotation
        return (0, 0, 0)

    _translation: Optional[tuple[float, float, float]] = Field(
        validation_alias=AliasChoices("translation", "_translation"), default=None
    )

    @property
    def translation(self) -> tuple[float, float, float]:
        if self._translation is not None:
            return self._translation
        return (0, 0, 0)

    _scale: Optional[tuple[float, float, float]] = Field(
        validation_alias=AliasChoices("scale", "_scale"), default=None
    )

    @property
    def scale(self) -> tuple[float, float, float]:
        if self._scale is not None:
            return self._scale
        return (1, 1, 1)


faces_keys = Literal["north", "south", "east", "west", "up", "down"]
display_options_keys = Literal[
    "thirdperson_righthand",
    "thirdperson_lefthand",
    "firstperson_righthand",
    "firstperson_lefthand",
    "gui",
    "head",
    "ground",
    "fixed",
]


class RotationModel(BaseModel):
    origin: tuple[float, float, float]
    axis: Literal["x", "y", "z"]
    angle: float
    rescale: bool = False


class FaceModel(BaseModel):
    uv: Optional[tuple[float, float, float, float]] = None
    texture: str
    cullface: Optional[faces_keys | str] = None
    rotation: Literal[0, 90, 180, 270] = 0
    tintindex: int = -1

    def get_uv(
        self, 
        face: faces_keys,
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

    def render(
        self,
        face: faces_keys,
        vertices: tuple[list[float], ...],
        from_element: tuple[float, float, float],
        to_element: tuple[float, float, float],
        tints: Sequence[TintSource],
        item: Optional[Item] = None,
        ctx: Optional[Context] = None,
        vanilla: Optional[Vanilla] = None,
    ):
        if self.uv:
            uv = [x/16 for x in self.uv]
        else:
            uv = list(self.get_uv(face, from_element, to_element))
            uv = [x/16 for x in uv]
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

        match self.rotation:
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
                raise RenderError(f"Unknown rotation {self.rotation}")

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

        glBegin(GL_QUADS)
        for i, (v0, v1, v2) in enumerate(triangulated_vertices):
            normal = normals[i]
            glNormal3fv(normal)

        color = (1.0, 1.0, 1.0)
        if len(tints) > self.tintindex and self.tintindex >= 0 and item:
            tint = tints[self.tintindex]
            assert ctx and vanilla and item, "Tinting requires context, vanilla and item"
            color = tint.resolve(ctx, vanilla, item)
            color = (color[0] / 255, color[1] / 255, color[2] / 255)
        for i, (uv0, uv1) in enumerate(texcoords):
            glColor3f(*color)
            glTexCoord2f(uv[uv0], uv[uv1])
            glVertex3fv(rotated_vertices[i])
        glEnd()


class ElementModel(BaseModel):
    from_: tuple[float, float, float] = Field(
        validation_alias=AliasChoices("from", "from_")
    )
    to: tuple[float, float, float]
    rotation: Optional[RotationModel] = None
    shade: bool = True
    light_emission: int = 0
    faces: dict[faces_keys, FaceModel] = Field(default_factory=dict)

    def render(
        self,
        *,
        ctx: Context,
        vanilla: Vanilla,
        item: Optional[Item] = None,
        texture_bindings: dict[str, int],
        center_offset: tuple[float, float, float] = (0, 0, 0),
        offset: tuple[float, float, float] = (0, 0, 0),
        additional_rotations: Iterable[RotationModel] = (),
        tints: Sequence[TintSource] = (),
    ):
        glEnable(GL_TEXTURE_2D)

        from_center, to_center = self.center(center_offset, offset)

        vertices = self.get_vertices(from_center, to_center, center_offset, offset)
        for rotation in additional_rotations:
            vertices = self.rotate_vertices(vertices, rotation, center_offset, offset)

        textures_used = [
            self.faces.get(key)
            for key in get_args(faces_keys)
        ]
        textures_used = [x.texture.lstrip("#") for x in textures_used if x is not None]
        textures_used = list(set(textures_used))

        for texture in textures_used:
            if texture not in texture_bindings.keys():
                continue
            glBindTexture(GL_TEXTURE_2D, texture_bindings[texture])
            glColor3f(1.0, 1.0, 1.0)
            for face_key, face in self.faces.items():
                if face.texture.lstrip("#") != texture:
                    continue
                face.render(face_key, vertices, self.from_, self.to, tints, item, ctx, vanilla)


        glDisable(GL_TEXTURE_2D)

    def center(
        self, 
        center_offset: tuple[float, float, float] = (0, 0, 0),
        offset: tuple[float, float, float] = (0, 0, 0),
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        center: tuple[float, float, float] = (8, 8, 8)
        center = (
            center[0] + center_offset[0],
            center[1] + center_offset[1],
            center[2] + center_offset[2],
        )
        x1, y1, z1 = self.from_
        x2, y2, z2 = self.to
        

        from_center = (
            x1 - center[0],
            y1 - center[1],
            z1 - center[2],
        )
        to_center = (
            x2 - center[0],
            y2 - center[1],
            z2 - center[2],
        )
        from_center = (
            from_center[0] + offset[0],
            from_center[1] + offset[1],
            from_center[2] + offset[2],
        )
        to_center = (
            to_center[0] + offset[0],
            to_center[1] + offset[1],
            to_center[2] + offset[2],
        )
        return from_center, to_center

    def get_vertices(
        self,
        from_center: tuple[float, float, float],
        to_center: tuple[float, float, float],
        center_offset: tuple[float, float, float] = (0, 0, 0),
        offset: tuple[float, float, float] = (0, 0, 0),
    ) -> tuple[list[float], ...]:
        x1, y1, z1 = from_center
        x2, y2, z2 = to_center

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
        if self.rotation is None:
            return res
        return self.rotate_vertices(res, self.rotation, center_offset, offset)

    def rotate_vertices(
        self, 
        vertices: tuple[list[float], ...],
        rotation: RotationModel,
        center_offset: tuple[float, float, float] = (0, 0, 0),
        offset: tuple[float, float, float] = (0, 0, 0),
    ) -> tuple[list[float], ...]:
        assert rotation is not None
        origin = [x - 8 for x in rotation.origin]
        origin = [x - center_offset[i] for i, x in enumerate(origin)]
        origin = [x + offset[i] for i, x in enumerate(origin)]
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


class MinecraftModel(BaseModel):
    """Class representing a minecraft model."""

    ctx: Context
    vanilla: Vanilla
    item: Optional[Item] = None
    _parent: Optional[str] = Field(
        validation_alias=AliasChoices("parent", "_parent"), default=None
    )

    _ambientocclusion: Optional[bool] = Field(
        validation_alias=AliasChoices("ambientocclusion", "_ambientocclusion"),
        default=None,
    )
    _gui_light: Optional[Literal["front", "side"]] = Field(
        validation_alias=AliasChoices("gui_light", "_gui_light"), default=None
    )
    _textures: Optional[dict[str, str | Image.Image]] = Field(
        validation_alias=AliasChoices("textures", "_textures"), default=None
    )
    _display: Optional[
        dict[
            display_options_keys,
            DisplayOptionModel,
        ]
    ] = Field(validation_alias=AliasChoices("display", "_display"), default=None)
    _elements: Optional[list[ElementModel]] = Field(
        validation_alias=AliasChoices("elements", "_elements"), default=None
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @cached_property
    def parent(self) -> Union["MinecraftModel", None]:
        if self._parent is None:
            return None
        parent_key = resolve_key(self._parent)
        if parent_key in [
            "minecraft:builtin/generated",
            "minecraft:builtin/entity",
        ]:
            return None
        if parent_key in self.ctx.assets.models:
            parent_data = self.ctx.assets.models[parent_key].data
        elif parent_key in self.vanilla.assets.models:
            parent_data = self.vanilla.assets.models[parent_key].data
        else:
            raise ValueError(f"Parent model {parent_key} not found.")
        parent_data["ctx"] = self.ctx
        parent_data["vanilla"] = self.vanilla
        return MinecraftModel.model_validate(parent_data)

    @property
    def ambientocclusion(self) -> bool:
        if self._ambientocclusion is not None:
            return self._ambientocclusion
        if self.parent is None:
            return True
        return self.parent.ambientocclusion

    @property
    def gui_light(self) -> Literal["front", "side"]:
        if self._gui_light is not None:
            return self._gui_light
        if self.parent is None:
            return "side"
        return self.parent.gui_light

    @cached_property
    def textures(self) -> dict[str, Image.Image]:
        textures: dict[str, Image.Image | str] = {}
        if self.parent is not None:
            textures.update(self.parent.textures)
        if self._textures is not None:
            textures.update(self._textures)

        res: dict[str, Image.Image] = {}
        for key, value in textures.items():
            if isinstance(value, Image.Image):
                res[key] = value
                continue
            res[key] = self.get_texture(value)
        return res

    def get_texture(self, key: str, max_depth: int = 20) -> Image.Image:
        if max_depth == 0:
            return Image.new("RGBA", (16, 16))
        if not key in self.textures:
            return Image.new("RGBA", (16, 16))
        value = self.textures[key]
        if isinstance(value, Image.Image):
            return value
        if value.startswith("#"):
            return self.get_texture(value[1:], max_depth - 1)
        value = resolve_key(value)
        if value in self.ctx.assets.textures:
            return self.ctx.assets.textures[value].image
        if value in self.vanilla.assets.textures:
            return self.vanilla.assets.textures[value].image
        log.warning(f"Texture {value} not found.")
        return Image.new("RGBA", (16, 16))

    @property
    def display(self) -> dict[
        display_options_keys,
        DisplayOptionModel,
    ]:
        res = {}
        if self.parent is not None:
            res.update(self.parent.display)
        if self._display is not None:
            res.update(self._display)
        return res

    @property
    def elements(self) -> list[ElementModel]:
        if self._elements:
            return self._elements
        if self.parent is not None:
            return self.parent.elements
        return []

    def generate_textures_bindings(self) -> dict[str, int]:
        res: dict[str, int] = {}
        for key, value in self.textures.items():
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
            res[key] = tex_id
        return res

    def rotate_camera(self, mode: display_options_keys | None):
        if mode is None:
            return
        glLoadIdentity()
        display = self.display[mode]
        glTranslatef(
            -display.translation[0], display.translation[1], display.translation[2]
        )
        glRotatef(-display.rotation[0], 1, 0, 0)
        glRotatef(display.rotation[1] + 180, 0, 1, 0)
        glRotatef(display.rotation[2], 0, 0, 1)
        glScalef(display.scale[0], display.scale[1], display.scale[2])

    def render(
        self,
        mode: display_options_keys | None = "gui",
        center_offset: tuple[float, float, float] = (0, 0, 0),
        offset: tuple[float, float, float] = (0, 0, 0),
        tints: Sequence[TintSource] = (),

    ):
        self.rotate_camera(mode)
        texture_bindings = self.generate_textures_bindings()
        if self.gui_light == "front":
            light = GL_LIGHT0
            not_light = GL_LIGHT1
        else:
            light = GL_LIGHT1
            not_light = GL_LIGHT0
        glEnable(GL_LIGHTING)
        glEnable(light)
        glDisable(not_light)
        for element in self.elements:
            element.render(
                ctx=self.ctx,
                vanilla=self.vanilla,
                item=self.item,
                texture_bindings=texture_bindings,
                center_offset=center_offset,
                offset=offset,
                tints=tints,
            )

            glEnable(GL_LIGHTING)
            glEnable(light)
            glDisable(not_light)

        glDisable(light)
        glEnable(not_light)
