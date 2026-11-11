from pathlib import Path
from OpenGL.GL import *  # pyright: ignore[reportWildcardImportFromLibrary]
from OpenGL.GLUT import *  # pyright: ignore[reportWildcardImportFromLibrary]
from OpenGL.GLU import *  # pyright: ignore[reportWildcardImportFromLibrary]

from beet import Context, Texture
from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel
from model_resolver.item_model.item import Item
from model_resolver.item_model.glint import ITEM_GLINT, MODEL_ATLASES, GlintStyle, has_foil
from model_resolver.item_model.transformation import Transformation
from model_resolver.utils import (
    resolve_key,
    log,
)
from model_resolver.pack_getter import PackGetter
from model_resolver.minecraft_model import (
    DisplayOptionModel,
    MinecraftModel,
    extruded_sides,
    ElementModel,
    MultiTextureResolved,
    ResolvableTexture,
    ResolvedTexture,
    RotationModel,
    FaceModel,
    TextureDict,
    TextureSource,
)
from model_resolver.item_model.tint_source import TintSource
from typing import Any, ClassVar, Optional, Generator, Literal
from PIL import Image
from model_resolver.tasks.base import Task, RenderError
from math import pi, cos, sin, sqrt


type TextureBindingsValue = tuple[tuple[tuple[int, TintSource | None], ...], str]


def set_default_blend():
    """BlendFunction.TRANSLUCENT: colors mix by the source alpha, the alpha accumulates.
    Over the transparent clear color this leaves colors multiplied by their alpha, which
    Render.display divides out."""
    glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ONE, GL_ONE_MINUS_SRC_ALPHA)


def rotation_matrix(rotation: RotationModel) -> np.ndarray:
    """CuboidRotation.computeTransform: x, then y, then z, then the rescale."""
    rotation = rotation.to_multi_axis()
    matrix = np.identity(3)
    for angle, axis in zip((rotation.x, rotation.y, rotation.z), ("x", "y", "z")):
        if angle == 0:
            continue
        c, s = cos(angle * pi / 180), sin(angle * pi / 180)
        if axis == "x":
            step = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
        elif axis == "y":
            step = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
        else:
            step = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        matrix = step @ matrix
    if rotation.rescale and not np.allclose(matrix, np.identity(3)):
        matrix = matrix @ np.diag(1 / np.abs(matrix).max(axis=0))
    return matrix


FACE_NORMALS = {
    "down": np.array([0.0, -1.0, 0.0]),
    "up": np.array([0.0, 1.0, 0.0]),
    "north": np.array([0.0, 0.0, -1.0]),
    "south": np.array([0.0, 0.0, 1.0]),
    "west": np.array([-1.0, 0.0, 0.0]),
    "east": np.array([1.0, 0.0, 0.0]),
}


def _rotate(matrix: np.ndarray, axis: str, angle: float) -> np.ndarray:
    c, s = cos(angle), sin(angle)
    step = {
        "x": [[1, 0, 0], [0, c, -s], [0, s, c]],
        "y": [[c, 0, s], [0, 1, 0], [-s, 0, c]],
        "z": [[c, -s, 0], [s, c, 0], [0, 0, 1]],
    }[axis]
    return matrix @ np.array(step)


def nearest_direction(vector: np.ndarray) -> str:
    return max(FACE_NORMALS, key=lambda face: float(FACE_NORMALS[face] @ vector))


def _axis_rotation(axis: str, degrees: float) -> np.ndarray:
    return _rotate(np.identity(3), axis, degrees * pi / 180)


# BlockMath: how the uv frame of each face sits in the world, the south face being the identity
UV_LOCAL_TO_GLOBAL = {
    "south": np.identity(3),
    "east": _axis_rotation("y", 90),
    "west": _axis_rotation("y", -90),
    "north": _axis_rotation("y", 180),
    "up": _axis_rotation("x", -90),
    "down": _axis_rotation("x", 90),
}


def uv_lock_transform(rotation: np.ndarray, face: str) -> np.ndarray:
    """2x2 map of a face's UVs (centered on 0.5) under a block rotation with uvlock, the inverse
    of BlockMath.getFaceTransformation as FaceBakery.bakeVertex applies it."""
    face_action = rotation @ UV_LOCAL_TO_GLOBAL[face]
    new_side = nearest_direction(face_action @ np.array([0.0, 0.0, 1.0]))
    face_transformation = np.linalg.inv(UV_LOCAL_TO_GLOBAL[new_side]) @ face_action
    return np.linalg.inv(face_transformation)[:2, :2]


def _normalized(vector: tuple[float, float, float]) -> np.ndarray:
    v = np.array(vector, dtype=np.float32).astype(float)
    return v / np.linalg.norm(v)


DIFFUSE_LIGHTS = (_normalized((0.2, 1.0, -0.7)), _normalized((-0.2, 1.0, 0.7)))


def _items_3d_pose() -> np.ndarray:
    # Lighting: scaling(1, -1, 1).rotateYXZ(1.0821041, 3.2375858, 0).rotateYXZ(-0.3926991, 2.3561945, 0)
    pose = np.diag([1.0, -1.0, 1.0])
    for y, x in ((1.0821041, 3.2375858), (-0.3926991, 2.3561945)):
        pose = _rotate(_rotate(pose, "y", y), "x", x)
    return pose


def _items_flat_pose() -> np.ndarray:
    # Lighting: rotationY(-0.3926991).rotateX(2.3561945)
    return _rotate(_rotate(np.identity(3), "y", -0.3926991), "x", 2.3561945)


CARDINAL_LIGHTING = {"down": 0.5, "up": 1.0, "north": 0.8, "south": 0.8, "west": 0.6, "east": 0.6}
"""CardinalLighting.DEFAULT, the shading of block faces in the overworld."""

LIGHTS: dict[str, tuple[np.ndarray, np.ndarray]] = {
    "side": (_items_3d_pose() @ DIFFUSE_LIGHTS[0], _items_3d_pose() @ DIFFUSE_LIGHTS[1]),
    "front": (_items_flat_pose() @ DIFFUSE_LIGHTS[0], _items_flat_pose() @ DIFFUSE_LIGHTS[1]),
}
"""Lighting.Entry.ITEMS_3D (gui_light side) and ITEMS_FLAT (front), in GUI pose space."""


@dataclass
class GuiLighting:
    """The light of an item drawn in the GUI, computed per face like light.glsl."""

    lights: tuple[np.ndarray, np.ndarray]
    normal_matrix: np.ndarray
    """From model space to the GUI pose space the lights are in."""

    @classmethod
    def create(
        cls,
        gui_light: str,
        display: "DisplayOptionModel",
        transformation: Optional[Transformation] = None,
    ) -> "GuiLighting":
        # GuiItemAtlas scales the slot by (1, -1, 1), then ItemTransform.apply rotates
        # (rotationXYZ) and scales, then the item model transformation applies
        rx, ry, rz = (angle * pi / 180 for angle in display.rotation)
        pose = _rotate(_rotate(_rotate(np.diag([1.0, -1.0, 1.0]), "x", rx), "y", ry), "z", rz)
        pose = pose @ np.diag(display.scale)
        if transformation is not None:
            pose = pose @ np.array(transformation.get_matrix()).reshape(4, 4).T[:3, :3]
        return cls(LIGHTS.get(gui_light, LIGHTS["side"]), np.linalg.inv(pose).T)

    def brightness(self, normal: np.ndarray) -> float:
        n = self.normal_matrix @ normal
        n = n / np.linalg.norm(n)
        light0, light1 = (max(0.0, float(light @ n)) for light in self.lights)
        return min(1.0, (light0 + light1) * 0.6 + 0.4)


GLINT_TEXTURE = "minecraft:misc/enchanted_glint_item"
GLINT_STRENGTH = 0.75
"""Options.glintStrength, GlintAlpha in the shaders."""
GLINT_UNITS_PER_TICK = 50 * 0.5 * 8
"""TextureTransform.setupGlintTexturing: milliseconds * glintSpeed (0.5 by default) * 8."""
GLINT_LOOP_TICKS = int(np.lcm(110000, 30000) // GLINT_UNITS_PER_TICK)
"""The glint moves along u every 110000 units and along v every 30000: 1650 ticks."""
FRAME_SPRITE = "model_resolver:sprite"
"""Key of `Image.info` naming the sprite an animation frame was cut from."""
type TextureBindings = dict[str, TextureBindingsValue]


def rgba(image: Image.Image) -> Image.Image:
    """The image as RGBA, without the copy convert makes when it already is."""
    return image if image.mode == "RGBA" else image.convert("RGBA")


class GlTextures:
    """The GPU copies of the images drawn by a render, shared by all its tasks.

    One per beet context (`ctx.inject(GlTextures)`): a context runs one pipeline, and a
    process can run several, each with its own OpenGL context.

    Textures named by a path are uploaded once and kept until `clear`. Images made on the fly
    (animation frames, overrides) are freed by `release_transient` once their task is drawn.
    """

    def __init__(self, ctx: Context):
        self.by_path: dict[str, int] = {}
        self.transient: dict[int, tuple[Image.Image, int]] = {}

    @staticmethod
    def upload(image: Image.Image, repeat: bool = False, blur: bool = False) -> int:
        image = rgba(image)
        tex_id: int = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR if blur else GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR if blur else GL_NEAREST)
        if repeat:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA, image.width, image.height, 0,
            GL_RGBA, GL_UNSIGNED_BYTE, image.tobytes("raw", "RGBA"),
        )
        return tex_id

    def from_path(self, key: str, image: Image.Image, repeat: bool = False, blur: bool = False) -> int:
        if key not in self.by_path:
            self.by_path[key] = self.upload(image, repeat, blur)
        return self.by_path[key]

    def from_image(self, image: Image.Image) -> int:
        entry = self.transient.get(id(image))
        if entry is None:
            # the image is kept so its id can't be reused while the texture lives
            entry = self.transient[id(image)] = (image, self.upload(image))
        return entry[1]

    def release_transient(self):
        if self.transient:
            glDeleteTextures([tex_id for _, tex_id in self.transient.values()])
            self.transient.clear()

    def clear(self):
        self.release_transient()
        if self.by_path:
            glDeleteTextures(list(self.by_path.values()))
            self.by_path.clear()


class FrameModel(BaseModel):
    index: int
    time: Optional[int] = None


type FrameState = tuple[int, int, float]
"""The frame index, the frame it blends towards and the blend progress."""


class AnimationModel(BaseModel):
    interpolate: bool = False
    frametime: int = 1
    frames: Optional[list[int | FrameModel]] = None
    width: Optional[int] = None
    height: Optional[int] = None

    def frame_size(self, width: int, height: int) -> tuple[int, int]:
        """AnimationMetadataSection.calculateFrameSize"""
        if self.width is not None:
            return self.width, self.height if self.height is not None else height
        if self.height is not None:
            return width, self.height
        return min(width, height), min(width, height)

    def frame_entries(self, width: int, height: int) -> list[tuple[int, int]]:
        """(frame index, time) of each entry, like SpriteContents.createAnimatedTexture.

        Frames are read row by row from a grid, entries with a bad index or time are dropped.
        """
        frame_width, frame_height = self.frame_size(width, height)
        count = (width // frame_width) * (height // frame_height)
        if self.frames is None:
            return [(i, self.frametime) for i in range(count)]
        entries: list[tuple[int, int]] = []
        for frame in self.frames:
            if isinstance(frame, int):
                index, time = frame, self.frametime
            else:
                index = frame.index
                time = frame.time if frame.time is not None else self.frametime
            if time > 0 and 0 <= index < count:
                entries.append((index, time))
        return entries

    def resolve_ticks(self, width: int, height: int) -> list[FrameState]:
        """The frame shown at each tick of one loop, like SpriteContents.AnimationState.

        Interpolated entries blend towards the next entry by subFrame / time, which the
        game passes to the shader in thousandths. Fewer than two entries is not animated.
        """
        entries = self.frame_entries(width, height)
        if len(entries) <= 1:
            return []
        ticks: list[FrameState] = []
        for i, (index, time) in enumerate(entries):
            next_index = entries[(i + 1) % len(entries)][0]
            for sub_frame in range(time):
                progress = np.float32(sub_frame) / np.float32(time) * np.float32(1000)
                progress = int(progress) / 1000
                if not self.interpolate or next_index == index or progress == 0:
                    ticks.append((index, index, 0.0))
                else:
                    ticks.append((index, next_index, progress))
        return ticks


class TextureMcMetaModel(BaseModel):
    animation: Optional[AnimationModel] = None


class TickGrouped(BaseModel):
    tick: dict[str, FrameState]
    duration: int
    start: int
    """The first tick of the frame, which sets the glint's position."""


@dataclass
class AnimatedTexture:
    ticks: list[FrameState]
    frame_size: tuple[int, int]


@dataclass(kw_only=True)
class GenericModelRenderTask(Task):
    item: Item

    do_rotate_camera: bool = True
    offset: tuple[float, float, float] = (0, 0, 0)
    center_offset: tuple[float, float, float] = (0, 0, 0)
    additional_rotations: list[RotationModel] = field(default_factory=list)
    lighting: Literal["gui", "terrain", "level"] = "gui"
    """How faces are lit: like a GUI item (light.glsl with ITEMS_3D / ITEMS_FLAT), like a block
    in the world (CardinalLighting), or like an entity in the world (light.glsl with LEVEL)."""
    lighting_display: Optional[DisplayOptionModel] = None
    """The display transform the light follows when the camera is not this task's model's."""
    lighting_pose: Optional[np.ndarray] = None
    """Model space to the lights' space (GUI pose space, or the world for level lighting),
    for models placed by hand rather than by rotate_camera."""
    shade_override: bool = False
    """Honour shade_direction_override (and `shade: false`) under the GUI light too: models
    rendered on their own are blocks, the flame of a campfire is lit like a top face."""
    uv_lock: bool = False
    """Keep textures aligned with the world through additional_rotations (blockstate uvlock)."""
    culled_faces: set[str] = field(default_factory=set)
    """World directions in which faces with that cullface are hidden by a neighbour."""
    glint_tick: int = 0
    """The game tick the enchantment glint is drawn at."""
    light: Any = field(default=None, init=False, repr=False)
    glint_texture: Optional[int] = field(default=None, init=False, repr=False)
    glint_style: Optional[GlintStyle] = field(default=None, init=False, repr=False)

    vanilla_display_defaults: ClassVar[bool] = False
    """Items use no transform for a context their models don't define (ItemTransform.NO_TRANSFORM),
    model renders keep a block-like gui default."""

    @property
    def gl_textures(self) -> GlTextures:
        return self.getter._ctx.inject(GlTextures)

    def flush(self):
        super().flush()
        self.item = Item(id="do_not_use")

    def get_display(self, model: MinecraftModel) -> DisplayOptionModel:
        context = self.item.display_context
        if self.vanilla_display_defaults and context not in model.display.model_fields_set:
            return DisplayOptionModel()
        return model.display.get(context)

    def get_textures(self, model: MinecraftModel, images: dict[str, Image.Image]):
        textures = {}
        resolved = {resolve_key(key): image for key, image in images.items()}
        for key, value in model.textures.items():
            if isinstance(value, Image.Image):
                raise RenderError(f"WTF is going on")
            elif isinstance(value, tuple):
                # banner and shield layers
                textures[key] = tuple(
                    (resolved.get(resolve_key(texture), texture) if isinstance(texture, str) else texture, tint)
                    for texture, tint in value
                )
            elif isinstance(value, TextureDict):
                textures[key] = resolved.get(resolve_key(value.sprite), value)
            elif resolve_key(value) in resolved:
                textures[key] = resolved[resolve_key(value)]
            else:
                textures[key] = value
        return textures

    def rotate_camera(
        self,
        model: MinecraftModel,
        transformation: Optional[Transformation] = None,
    ):
        if not self.do_rotate_camera:
            return
        # transform the vertices
        display = self.get_display(model)
        scale = display.scale or [1, 1, 1]
        translation = display.translation or [0, 0, 0]
        rotation = display.rotation or [0, 0, 0]
        if self.item.display_context.endswith("_lefthand"):
            # ItemTransform.apply mirrors the right-hand transform for left hands
            translation = (-translation[0], translation[1], translation[2])
            rotation = (rotation[0], -rotation[1], -rotation[2])

        # reset the matrix
        glLoadIdentity()
        # TODO: Check translation[2] for depth
        glTranslatef(-translation[0], translation[1], -translation[2])
        glRotatef(-rotation[0], 1, 0, 0)
        glRotatef(rotation[1] + 180, 0, 1, 0)
        glRotatef(rotation[2], 0, 0, 1)
        glScalef(scale[0], scale[1], scale[2])
        if transformation is not None:
            # LayerRenderState.applyTransform: after ItemTransform.apply, which ends with
            # translate(-0.5), on geometry in blocks. Here geometry is in pixels around
            # the model center, so translations scale by 16 and the pivot is the corner.
            matrix = list(transformation.get_matrix())
            matrix[12:15] = [x * 16 for x in matrix[12:15]]
            glTranslatef(-8, -8, -8)
            glMultMatrixf(matrix)
            glTranslatef(8, 8, 8)

    def get_real_key(
        self, key: str, textures: dict[str, TextureSource]
    ) -> ResolvableTexture:
        """Follow #references to a texture, like TextureSlots.Resolver; a loop resolves to None."""
        seen: set[str] = set()
        while key in textures and key not in seen:
            seen.add(key)
            value = textures[key]
            if isinstance(value, Image.Image) or isinstance(value, tuple):
                return value
            if isinstance(value, TextureDict):
                value = value.sprite
            if not isinstance(value, str):
                raise RenderError(f"Unknown texture type {type(value)} for key {key}")
            if not value.startswith("#"):
                return value
            key = value[1:]
        return None

    def get_missingno(self) -> Image.Image:
        """Returns a missingno image for debugging purposes."""
        if self.getter.opts.transparent_missingno:
            return Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        path = Path(__file__).parent.parent / "missingno.png"
        if not path.exists():
            raise RenderError(f"Missingno image not found at {path}")
        return Image.open(path).convert("RGBA")

    def load_textures(
        self, model: MinecraftModel, source: Optional[str] = None
    ) -> dict[str, tuple[ResolvedTexture, str]]:
        res: dict[str, tuple[ResolvedTexture, str]] = {}
        used_textures = set()
        textures = dict(model.textures)
        for elem in model.elements:
            for face in elem.faces.values():
                used_textures.add(face.texture.removeprefix("#"))
                if not face.texture.startswith("#"):
                    # a face can name a texture directly
                    textures.setdefault(face.texture, face.texture)
        for key in used_textures - textures.keys():
            # an undefined texture variable is the missing texture, the face is still drawn
            res[key] = (self.get_missingno(), "empty")
            log.warning(f"Texture variable {key} is not defined in {source}")
        for key in textures.keys():
            value = self.get_real_key(key, textures)
            if not key in used_textures:
                continue
            if value is None:
                res[key] = (self.get_missingno(), "empty")
                log.warning(f"Texture {key} not found in {source}")
            elif isinstance(value, Image.Image):
                res[key] = (value, "dynamic")
            elif isinstance(value, tuple):
                # if value is a tuple, it means it's a multi-texture
                layers: list[MultiTextureResolved] = []
                for texture, tint in value:
                    if isinstance(texture, Image.Image):
                        layers.append((rgba(texture), tint))
                        continue
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

                    layers.append((rgba(img), tint))
                # the base layer's sprite, where an entity glint is sampled
                base = value[0][0] if value else None
                res[key] = (tuple(layers), resolve_key(base) if isinstance(base, str) else key)
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
                res[key] = (rgba(img), path)
        return res

    def generate_textures_bindings(
        self, model: MinecraftModel, source: Optional[str] = None
    ):
        res: TextureBindings = {}
        textures = self.load_textures(model, source)
        for key, (value, path) in textures.items():
            if isinstance(value, Image.Image):
                if path == "dynamic":
                    tex_id = self.gl_textures.from_image(value)
                    path = value.info.get(FRAME_SPRITE, path)
                else:
                    tex_id = self.gl_textures.from_path(path, value)
                res[key] = (((tex_id, None),), path)
            elif isinstance(value, tuple):
                res[key] = (tuple((self.gl_textures.from_image(img), tint) for img, tint in value), path)
            else:
                raise RenderError(f"Unknown texture type {type(value)} for key {key}")
        return res

    def render_model(
        self,
        model: MinecraftModel,
        tints: list[TintSource],
        source: Optional[str] = None,
        transformation: Optional[Transformation] = None,
        glint: Optional[GlintStyle] = ITEM_GLINT,
    ):
        """`glint` is how the model draws the enchantment glint when the item has one, None
        for models that never draw it (most special models)."""
        self.rotate_camera(model, transformation)
        if model.generated_layers:
            model = self.extrude_generated(model, source)
        textures_bindings = self.generate_textures_bindings(model, source)
        display = self.lighting_display or self.get_display(model)
        if self.lighting == "level":
            pose = np.identity(3) if self.lighting_pose is None else self.lighting_pose
            self.light = GuiLighting(DIFFUSE_LIGHTS, np.linalg.inv(pose).T)
        elif self.lighting_pose is not None:
            lights = LIGHTS.get(model.gui_light, LIGHTS["side"])
            self.light = GuiLighting(lights, np.linalg.inv(self.lighting_pose).T)
        else:
            self.light = GuiLighting.create(model.gui_light, display, transformation)
        self.glint_texture = self.load_glint() if glint is not None and has_foil(self.item) else None
        self.glint_style = glint
        # `shade` does nothing for items: the GUI light comes from the item shader
        for element in model.elements:
            self.draw_element(element, textures_bindings, tints)

    def load_glint(self) -> Optional[int]:
        texture = self.getter.assets.textures.get(GLINT_TEXTURE)
        if texture is None:
            return None
        mcmeta = self.getter.assets.textures_mcmeta.get(GLINT_TEXTURE)
        blur = bool(mcmeta and mcmeta.data.get("texture", {}).get("blur", False))
        return self.gl_textures.from_path(GLINT_TEXTURE, texture.image, repeat=True, blur=blur)

    def extrude_generated(self, model: MinecraftModel, source: Optional[str] = None) -> MinecraftModel:
        """Add the side faces of a builtin/generated model, they depend on its textures' alpha."""
        textures = self.load_textures(model, source)
        elements = list(model.elements)
        for layer in model.generated_layers:
            image = textures.get(f"layer{layer}", (None, ""))[0]
            if isinstance(image, Image.Image):
                elements.extend(extruded_sides(image, layer))
        return model.model_copy(update={"elements": elements, "generated_layers": []})

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
        linear = rotation_matrix(element.rotation) if element.rotation else np.identity(3)
        for rotation in self.additional_rotations:
            vertices = self.rotate_vertices(vertices, rotation)
            linear = rotation_matrix(rotation) @ linear
        # normals transform with the inverse transpose (rescale stretches the geometry)
        normals = np.linalg.inv(linear).T
        block_rotation = np.identity(3)
        for rotation in self.additional_rotations:
            block_rotation = rotation_matrix(rotation) @ block_rotation

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
            if data.cullface and self.culled_faces:
                if nearest_direction(block_rotation @ FACE_NORMALS[data.cullface]) in self.culled_faces:
                    continue
            self.draw_face(
                face,
                data,
                vertices,
                element.from_,
                element.to,
                tints,
                textures_bindings[textvar],
                self.face_brightness(element, nearest_direction(normals @ FACE_NORMALS[face])),
                uv_lock_transform(block_rotation, face) if self.uv_lock else None,
            )

    def face_brightness(self, element: ElementModel, direction: str) -> float:
        """The shading of a face whose baked quad faces `direction`.

        Like FaceBakery.calculateFacing, the direction is the axis nearest to the face's
        normal after the element and block rotations, and both lightings use that axis.
        """
        # BlockModelLighter.getDirectionalBrightness; `shade: false` before 26.3 is unlit
        override = element.shade_direction_override or (None if element.shade else "up")
        if self.lighting == "terrain":
            return CARDINAL_LIGHTING[override or direction]
        if self.shade_override and override:
            direction = override
        return self.light.brightness(FACE_NORMALS[direction])

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
        """CuboidRotation: rotate around the origin, x then y then z.

        With rescale, each axis is first stretched by 1 / max(|R * axis|), so a face
        rotated by 22.5 degrees still spans the block (1.082) and one by 45 degrees too (sqrt 2).
        """
        origin = np.array(rotation.origin, dtype=float) - 8
        origin -= np.array(self.center_offset, dtype=float)
        origin += np.array(self.offset, dtype=float)
        matrix = rotation_matrix(rotation)
        for point in vertices:
            point[0], point[1], point[2] = (matrix @ (np.array(point, dtype=float) - origin) + origin).tolist()
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
        brightness: float = 1.0,
        uv_transform: Optional[np.ndarray] = None,
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
        vertex_uvs = []
        for uv0, uv1 in texcoords:
            u, v = uv[uv0], uv[uv1]
            if uv_transform is not None:
                u, v = (uv_transform @ np.array([u - 0.5, v - 0.5]) + 0.5).tolist()
            vertex_uvs.append((u, v))
        # glUseProgram(self.program)
        # print(glGetError())
        # self.set_uniforms(self.program)

        glEnable(GL_TEXTURE_2D)

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
            color = (color[0] * brightness, color[1] * brightness, color[2] * brightness)

            # Apply depth offset for layering by modifying polygon offset
            if layer_index > 0:
                glEnable(GL_POLYGON_OFFSET_FILL)
                glPolygonOffset(-layer_index * depht_coef, -layer_index * depht_coef)

            glBegin(GL_QUADS)
            for vertex, (u, v) in zip(rotated_vertices, vertex_uvs):
                glColor3f(*color)
                glTexCoord2f(u, v)
                glVertex3fv(vertex)
            glEnd()

            # Disable polygon offset after use
            if layer_index > 0:
                glDisable(GL_POLYGON_OFFSET_FILL)

        if self.glint_texture is not None:
            self.draw_glint(rotated_vertices, vertex_uvs, bindings[1])

        set_default_blend()

        glDisable(GL_TEXTURE_2D)

    def upload_texture(self, image: Image.Image) -> int:
        return self.gl_textures.from_image(image)

    def draw_quad(
        self,
        tex_id: int,
        vertices: list[tuple[float, float, float]],
        uvs: list[tuple[float, float]],
        color: tuple[float, float, float],
        back_face: bool = False,
    ):
        """A free quad in Minecraft's vertex order (counter-clockwise seen from its front),
        already lit and tinted, in the current matrix (pixels)."""
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        # the mirrored projection makes this pipeline's front faces clockwise
        orders = [[3, 2, 1, 0]] + ([[0, 1, 2, 3]] if back_face else [])
        for order in orders:
            glBegin(GL_QUADS)
            for i in order:
                glColor3f(*color)
                glTexCoord2f(*uvs[i])
                glVertex3fv(vertices[i])
            glEnd()
        glDisable(GL_TEXTURE_2D)

    def glint_sprite_uv(self, sprite: str) -> Optional[tuple[float, float, float, float]]:
        """Where the face's sprite is in the atlas its glint is sampled in, None to use the
        texture's own coordinates."""
        from model_resolver.atlas import MISSING_SPRITE, Atlases

        style = self.glint_style
        if style is None or style.atlas is None:
            return None
        atlases = self.getter._ctx.inject(Atlases)
        if style.atlas == MODEL_ATLASES:
            uv = atlases.model_sprite_uv(self.getter, sprite)
            # an image that isn't a sprite is drawn where the game draws missing ones
            return uv or atlases.layout(self.getter, "minecraft:blocks").uv(MISSING_SPRITE)
        return atlases.layout(self.getter, style.atlas).uv(sprite)

    def draw_glint(self, vertices: list, uvs: list[tuple[float, float]], sprite: str):
        """The enchantment glint at `glint_tick`. Like the GLINT shaders and
        TextureTransform.setupGlintTexturing: the glint texture is sampled at the vertex
        uvs (in the atlas) scaled, turned by 10 degrees and moved with time, and its color
        times the glint strength, squared, is added to the face."""
        assert self.glint_style is not None
        glBindTexture(GL_TEXTURE_2D, self.glint_texture)
        # only where the face itself was drawn
        glDepthFunc(GL_EQUAL)
        # src * src + dst: glColor is the glint strength, the alpha stays
        glBlendFuncSeparate(GL_SRC_COLOR, GL_ONE, GL_ZERO, GL_ONE)
        time = self.glint_tick * GLINT_UNITS_PER_TICK
        offset_u = np.float32(time % 110000) / np.float32(110000)
        offset_v = np.float32(time % 30000) / np.float32(30000)
        rect = self.glint_sprite_uv(sprite)
        scale = self.glint_style.scale
        c, s = cos(0.17453292), sin(0.17453292)
        glBegin(GL_QUADS)
        for vertex, (u, v) in zip(vertices, uvs):
            if rect is not None:
                u, v = rect[0] + (rect[2] - rect[0]) * u, rect[1] + (rect[3] - rect[1]) * v
            u, v = u * scale, v * scale
            glColor3f(GLINT_STRENGTH, GLINT_STRENGTH, GLINT_STRENGTH)
            glTexCoord2f(c * u - s * v - offset_u, s * u + c * v + offset_v)
            glVertex3fv(vertex)
        glEnd()
        glDepthFunc(GL_LEQUAL)

    def get_uv(
        self,
        face: str,
        from_element: tuple[float, float, float],
        to_element: tuple[float, float, float],
    ) -> tuple[float, float, float, float]:
        """FaceBakery.defaultFaceUV: the face's projection of the element, before rotation."""
        x1, y1, z1 = from_element
        x2, y2, z2 = to_element
        match face:
            case "down":
                return (x1, 16 - z2, x2, 16 - z1)
            case "up":
                return (x1, z1, x2, z2)
            case "north":
                return (16 - x2, 16 - y2, 16 - x1, 16 - y1)
            case "south":
                return (x1, 16 - y2, x2, 16 - y1)
            case "west":
                return (z1, 16 - y2, z2, 16 - y1)
            case "east":
                return (16 - z2, 16 - y2, 16 - z1, 16 - y1)
            case _:
                raise RenderError(f"Unknown face {face}")


@dataclass(kw_only=True)
class Animation:
    textures: list[dict[str, TextureSource]]
    getter: PackGetter
    animation_framerate: int

    source: Optional[str] = None
    glint: bool = False
    """An enchantment glint is drawn, which moves on every tick."""

    cache_texture_animated: Any = None

    @property
    def duration_coef(self):
        if self.animation_framerate % 20 != 0 and self.animation_framerate > 0:
            raise TypeError(f"animation_frame must be a positive multiple of 20")
        return self.animation_framerate // 20

    @property
    def is_animated(self) -> bool:
        return self.glint or len(self.get_texture_animated()) > 0

    def texture_paths(self) -> Generator[str, None, None]:
        for textures in self.textures:
            for value in textures.values():
                if isinstance(value, tuple):
                    for layer, _ in value:
                        if isinstance(layer, str):
                            yield layer
                elif isinstance(value, TextureDict):
                    yield value.sprite
                elif isinstance(value, str) and not value.startswith("#"):
                    yield value

    def get_texture_animated(self) -> dict[str, AnimatedTexture]:
        if self.cache_texture_animated is not None:
            return self.cache_texture_animated
        texture_animated: dict[str, AnimatedTexture] = {}
        for texture_path in self.texture_paths():
            if resolve_key(texture_path) in texture_animated:
                continue
            texture = self.texture(texture_path)
            if not texture:
                continue
            mcmeta = self.mcmeta(texture_path)
            if not mcmeta or not mcmeta.animation:
                continue
            image: Image.Image = texture.image
            ticks = mcmeta.animation.resolve_ticks(image.width, image.height)
            if ticks:
                frame_size = mcmeta.animation.frame_size(image.width, image.height)
                texture_animated[resolve_key(texture_path)] = AnimatedTexture(ticks, frame_size)
        self.cache_texture_animated = texture_animated
        return texture_animated

    def get_tick_grouped(
        self,
        texture_animated: dict[str, AnimatedTexture],
    ) -> list[TickGrouped]:
        loops = [len(animated.ticks) for animated in texture_animated.values()]
        if self.glint:
            loops.append(GLINT_LOOP_TICKS)
        total_number_of_tick = int(np.lcm.reduce(loops))
        ticks_grouped: list[TickGrouped] = []
        for i in range(total_number_of_tick):
            tick = {
                texture_path: animated.ticks[i % len(animated.ticks)]
                for texture_path, animated in texture_animated.items()
            }
            # consecutive ticks that show the same images make one longer frame
            if len(ticks_grouped) > 0 and ticks_grouped[-1].tick == tick and not self.glint:
                ticks_grouped[-1].duration += 1
            else:
                ticks_grouped.append(TickGrouped(tick=tick, duration=1, start=i))
        return ticks_grouped

    def get_frames(
        self,
    ) -> Generator[tuple[int, tuple[dict[str, Image.Image], int, int]], None, None]:
        """(index, (images, duration, first tick)) of each frame."""
        if not self.is_animated:
            raise RenderError("Should not be called if is_animated is False")
        texture_animated = self.get_texture_animated()

        ticks_grouped = self.get_tick_grouped(texture_animated)

        for i, tick in enumerate(ticks_grouped):
            images = self.get_images(tick, texture_animated)
            yield i, (images, tick.duration, tick.start)

    @staticmethod
    def crop_frame(image: Image.Image, index: int, frame_size: tuple[int, int]) -> Image.Image:
        width, height = frame_size
        row_size = image.width // width
        x, y = (index % row_size) * width, (index // row_size) * height
        return image.crop((x, y, x + width, y + height))

    def get_images(
        self, tick: TickGrouped, texture_animated: dict[str, AnimatedTexture]
    ) -> dict[str, Image.Image]:
        images = {}
        for texture_path, (index, next_index, progress) in tick.tick.items():
            texture = self.texture(texture_path)
            if not texture:
                raise RenderError(f"Texture {texture_path} not found")
            img: Image.Image = texture.image
            frame_size = texture_animated[texture_path].frame_size
            frame = self.crop_frame(img, index, frame_size)
            if progress > 0:
                next_frame = self.crop_frame(img, next_index, frame_size)
                frame = self.blend_images(frame, next_frame, progress)
            frame.info[FRAME_SPRITE] = resolve_key(texture_path)
            images[texture_path] = frame
        return images

    @staticmethod
    def blend_images(img1: Image.Image, img2: Image.Image, t: float) -> Image.Image:
        # animate_sprite_interpolate.fsh: mix(current, next, progress), stored as 8 bits
        assert img1.size == img2.size
        assert t >= 0 and t <= 1
        a = np.asarray(img1.convert("RGBA"), dtype=np.float32)
        b = np.asarray(img2.convert("RGBA"), dtype=np.float32)
        blended = np.floor(a * np.float32(1 - t) + b * np.float32(t) + 0.5)
        return Image.fromarray(blended.clip(0, 255).astype(np.uint8), "RGBA")

    def texture(self, key: str) -> Optional[Texture]:
        return self.getter.assets.textures.get(resolve_key(key))

    def mcmeta(self, key: str) -> Optional[TextureMcMetaModel]:
        mcmeta = self.getter.assets.textures_mcmeta.get(resolve_key(key))
        if not mcmeta:
            return None
        return TextureMcMetaModel.model_validate(mcmeta.data)
