from OpenGL.GL import *  # pyright: ignore[reportWildcardImportFromLibrary]
from OpenGL.GLUT import *  # pyright: ignore[reportWildcardImportFromLibrary]
from OpenGL.GLU import *  # pyright: ignore[reportWildcardImportFromLibrary]

from dataclasses import dataclass, field
from beet import Blockstate
from model_resolver.block_colors import Biome, block_tints, load_biome
from model_resolver.blocks import FULL_BLOCK, BlockInfo, Box, block_info
from model_resolver.item_model.item import Item
from model_resolver.item_model.special import SpecialModelShulkerBox
from model_resolver.item_model.tint_source import TintSource, TintSourceConstant
from model_resolver.tasks.generic_render import Animation, GenericModelRenderTask, _axis_rotation
from model_resolver.tasks.fluids import FluidState, Position, tesselate_fluid
from model_resolver.item_model.transformation import Transformation
import numpy as np
from model_resolver.utils import log, resolve_key
from model_resolver.minecraft_model import (
    DisplayOptionModel,
    MinecraftModel,
    RotationModel,
    SingleAxisRotationModel,
    TextureSource,
    missing_model,
    resolve_model,
)
from typing import Generator, Literal, Optional, Any, TypedDict, Union
from pydantic import AliasChoices, BaseModel, Field
from functools import cached_property
import random
from model_resolver.tasks.base import Task, RenderError
from model_resolver.tasks.model import AnimatedResultTask, ModelRenderTask
from PIL import Image


class StructureFluids:
    """The structure as a FluidWorld. With `extend`, positions past its sides (not above or
    below) read the nearest block inside it."""

    def __init__(self, task: "StructureRenderTask", extend: bool = False):
        self.task = task
        self.extend = extend

    def state(self, pos: Position) -> Optional[int]:
        x, y, z = pos
        sx, _, sz = self.task.structure.size
        if self.extend:
            x, z = min(max(x, 0), sx - 1), min(max(z, 0), sz - 1)
        return self.task.block_positions.get((x, y, z))

    def palette(self, pos: Position) -> Optional[PaletteModel]:
        state = self.state(pos)
        return None if state is None else self.task.structure.palette[state]

    def fluid(self, pos: Position) -> Optional[FluidState]:
        return self.task.fluid_state(self.palette(pos))

    def info(self, pos: Position) -> Optional[BlockInfo]:
        palleted = self.palette(pos)
        return None if palleted is None else self.task.block_info(palleted)

    def solid(self, pos: Position) -> bool:
        info = self.info(pos)
        return info is not None and info.solid

    def blocks_flow(self, pos: Position) -> bool:
        info = self.info(pos)
        return info is not None and info.blocks_fluid_flow

    def occlusion(self, pos: Position) -> list[Box]:
        info = self.info(pos)
        if info is None:
            return []
        if not info.known:
            # a block of another namespace: occluding when it's a full opaque cube
            state = self.state(pos)
            return FULL_BLOCK if state is not None and self.task.occlusion(state) == "opaque" else []
        return info.occlusion

    def overlay(self, pos: Position) -> bool:
        palleted = self.palette(pos)
        if palleted is None:
            return False
        path = resolve_key(palleted.Name).split(":")[1]
        # HalfTransparentBlock and LeavesBlock
        return path.endswith(("glass", "_leaves", "ice")) or path in ("slime_block", "honey_block")


def _rot(axis: str, degrees: float) -> np.ndarray:
    return _axis_rotation(axis, degrees)


def _affine(linear: np.ndarray = np.identity(3), translation=(0.0, 0.0, 0.0)) -> np.ndarray:
    matrix = np.identity(4)
    matrix[:3, :3] = linear
    matrix[:3, 3] = translation
    return matrix


def camera_matrix(display: DisplayOptionModel) -> np.ndarray:
    """The matrix rotate_camera builds for a display transform (pixels)."""
    tx, ty, tz = display.translation
    rx, ry, rz = display.rotation
    linear = _rot("x", -rx) @ _rot("y", ry + 180) @ _rot("z", rz) @ np.diag(display.scale)
    return _affine(linear, (-tx, ty, -tz))


Y_ROTATION = {"south": 0, "west": 90, "north": 180, "east": 270}
OPPOSITE = {"south": "north", "north": "south", "west": "east", "east": "west"}
DYE_COLORS = (
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
)
SKULLS = {
    "skeleton_skull": "skeleton",
    "wither_skeleton_skull": "wither_skeleton",
    "zombie_head": "zombie",
    "creeper_head": "creeper",
    "dragon_head": "dragon",
    "piglin_head": "piglin",
    "player_head": "player",
}
GOLEM_TEXTURES = {"": "", "exposed_": "_exposed", "weathered_": "_weathered", "oxidized_": "_oxidized"}


def builtin_block(
    name: str, properties: dict[str, str], nbt: dict[str, Any]
) -> Optional[tuple[Optional[str], dict[str, Any], np.ndarray, dict[str, Any]]]:
    """BuiltInBlockModels: (item id, special model, block transformation in blocks, components)."""
    path = name.removeprefix("minecraft:")
    facing = properties.get("facing", "south")
    segment = int(properties.get("rotation", 0)) * 22.5
    for skull, kind in SKULLS.items():
        wall = skull.replace("_skull", "_wall_skull").replace("_head", "_wall_head")
        if path not in (skull, wall):
            continue
        special = {"type": "minecraft:player_head"} if kind == "player" else {"type": "minecraft:head", "kind": kind}
        components = {"minecraft:profile": nbt["profile"]} if "profile" in nbt else {}
        if path == skull:
            # SkullBlockRenderer.createGroundTransformation
            placement = _affine(translation=(0.5, 0, 0.5)) @ _affine(_rot("y", -segment)) @ _affine(np.diag([-1.0, -1.0, 1.0]))
        else:
            step_x, _, step_z = DIRECTIONS[facing]
            placement = _affine(
                _rot("y", -Y_ROTATION[OPPOSITE[facing]]) @ np.diag([-1.0, -1.0, 1.0]),
                (0.5 - step_x * 0.25, 0.25, 0.5 - step_z * 0.25),
            )
        return f"minecraft:{skull}", special, placement, components
    for color in DYE_COLORS:
        if path in (f"{color}_banner", f"{color}_wall_banner"):
            wall = "wall" in path
            angle = Y_ROTATION[facing] if wall else segment
            # BannerRenderer.modelTransformation
            placement = _affine(_rot("y", -angle) @ np.diag([0.6666667, -0.6666667, -0.6666667]), (0.5, 0, 0.5))
            special = {"type": "minecraft:banner", "color": color, "attachment": "wall" if wall else "ground"}
            components = {"minecraft:banner_patterns": nbt["patterns"]} if "patterns" in nbt else {}
            return f"minecraft:{color}_banner", special, placement, components
    if path == "conduit":
        return "minecraft:conduit", {"type": "minecraft:conduit"}, _affine(translation=(0.5, 0.5, 0.5)), {}
    if path == "decorated_pot":
        turn = _affine(_rot("y", 180 - Y_ROTATION[facing]))
        placement = _affine(translation=(0.5, 0.5, 0.5)) @ turn @ _affine(translation=(-0.5, -0.5, -0.5))
        components = {"minecraft:pot_decorations": nbt["sherds"]} if "sherds" in nbt else {}
        return "minecraft:decorated_pot", {"type": "minecraft:decorated_pot"}, placement, components
    if path == "bell":
        return None, {"type": "minecraft:bell"}, np.identity(4), {}
    if path == "enchanting_table":
        placement = _affine(_rot("z", 180) @ _rot("x", 90), (0.5, 0.8125, 0.5))
        return None, {"type": "minecraft:book", "open_angle": 0, "page1": 0, "page2": 0}, placement, {}
    if path == "end_portal":
        placement = _affine(np.diag([1.0, 0.375, 1.0]), (0, 0.375, 0))
        return None, {"type": "minecraft:end_cube", "effect": "portal"}, placement, {}
    if path == "end_gateway":
        return None, {"type": "minecraft:end_cube", "effect": "gateway"}, np.identity(4), {}
    statue = path.removeprefix("waxed_")
    for prefix, suffix in GOLEM_TEXTURES.items():
        if statue == f"{prefix}copper_golem_statue":
            special = {
                "type": "minecraft:copper_golem_statue",
                "pose": properties.get("copper_golem_pose", "standing"),
                "texture": f"minecraft:textures/entity/copper_golem/copper_golem{suffix}.png",
            }
            placement = _affine(_rot("y", -Y_ROTATION[OPPOSITE[facing]]), (0.5, 0, 0.5))
            return None, special, placement, {}
    return None


DIRECTIONS = {
    "down": (0, -1, 0),
    "up": (0, 1, 0),
    "north": (0, 0, -1),
    "south": (0, 0, 1),
    "west": (-1, 0, 0),
    "east": (1, 0, 0),
}


class PaletteModel(BaseModel):
    """A block state in a structure palette: {id, properties} since 26.1 (NbtUtils.readBlockState),
    {Name, Properties} before, which the game still reads."""

    Name: str = Field(validation_alias=AliasChoices("Name", "id"))
    Properties: dict[str, str] = Field(
        default_factory=dict, validation_alias=AliasChoices("Properties", "properties")
    )


class BlockModel(BaseModel):
    state: int
    pos: tuple[int, int, int]
    nbt: Optional[dict[str, Any]] = None


class StructureDataModel(BaseModel):
    DataVersion: int
    size: tuple[int, int, int]
    palette_: Optional[list[PaletteModel]] = Field(alias="palette", default=None)
    palettes: Optional[list[list[PaletteModel]]] = None
    blocks: list[BlockModel]
    entities: Any

    @cached_property
    def palette(self) -> list[PaletteModel]:
        if self.palette_:
            return self.palette_
        if self.palettes:
            return random.choice(self.palettes)
        raise RenderError("No palette found")


class VariantModel(BaseModel):
    model: str | MinecraftModel
    x: int = 0
    y: int = 0
    z: int = 0
    uvlock: bool = False
    weight: int = 1

    @property
    def rotations(self) -> list[RotationModel]:
        # Quadrant.fromXYZAngles: x, then y, then z, each quarter turn is a negative one
        axes: tuple[tuple[Literal["x", "y", "z"], int], ...] = (("x", self.x), ("y", self.y), ("z", self.z))
        rotations: list[RotationModel] = [
            SingleAxisRotationModel(origin=(8, 8, 8), axis=axis, angle=-angle, rescale=False)
            for axis, angle in axes
            if angle % 360 != 0
        ]
        return rotations


Variant = Union[VariantModel, list[VariantModel]]


SimpleWhenCondition = dict[str, str | int | bool]

HardWhenCondition = TypedDict(
    "HardWhenCondition",
    {
        "OR": list[SimpleWhenCondition],
        "AND": list[SimpleWhenCondition],
    },
    total=False,
)

WhenCondition = HardWhenCondition | SimpleWhenCondition


def condition_value(value: str | int | bool) -> str:
    # KeyValueCondition.Terms also reads ints and booleans, as their string form
    return str(value).lower() if isinstance(value, bool) else str(value)


def terms_match(terms: str, value: str) -> bool:
    """`|`-separated terms, any of which must match; a leading `!` negates a term."""
    for term in terms.split("|"):
        if term.startswith("!"):
            if value != term[1:]:
                return True
        elif value == term:
            return True
    return False


def variant_matches(key: str, block_state: dict[str, str]) -> bool:
    """VariantSelector: comma-separated `property=value` pairs, `""` matches every state."""
    for pair in key.split(","):
        name, _, value = pair.partition("=")
        if name and block_state.get(name) != value:
            return False
    return True


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
        if not terms_match(condition_value(value), condition_value(block_state[key])):  # type: ignore
            return False
    return True


class MultiPartModel(BaseModel):
    apply: Variant
    when: Optional[WhenCondition] = None


class BlockState(BaseModel):
    variants: Optional[dict[str, Variant]] = None
    multipart: Optional[list[MultiPartModel]] = None

    def get_models(self):
        if self.variants:
            for variant in self.variants.values():
                if isinstance(variant, list):
                    for v in variant:
                        yield v.model
                else:
                    yield variant.model
        if self.multipart:
            for multipart in self.multipart:
                variant = multipart.apply
                if isinstance(variant, list):
                    for v in variant:
                        yield v.model
                else:
                    yield variant.model

    def select(self, block_state: dict[str, str]) -> Optional[list[Variant]]:
        """What this file draws for a state, None if the file does not cover the state.

        Like BlockStateModelDispatcher.instantiate: the first matching variant wins,
        and a multipart covers every state the variants don't.
        """
        for key, variant in (self.variants or {}).items():
            if variant_matches(key, block_state):
                return [variant]
        if self.multipart is not None:
            return [
                part.apply
                for part in self.multipart
                if not part.when or verify_when(part.when, block_state)
            ]
        return None


@dataclass(kw_only=True)
class StructureRenderTask(GenericModelRenderTask):
    structure_key: str
    display_option: DisplayOptionModel = field(
        default_factory=lambda: DisplayOptionModel(
            rotation=(30, 225, 0), translation=(0, 0, 0), scale=(0.625, 0.625, 0.625)
        )
    )
    zoom: int = 128
    do_rotate_camera: bool = True
    random_seed: int = 143221
    biome: str | dict[str, Any] = "minecraft:plains"
    """The biome every block is in (an id or a worldgen/biome object): grass, foliage and water colors."""

    images_override: Optional[dict[str, Image.Image]] = None
    item: Item = field(default_factory=lambda: Item(id="do_not_use"))

    @cached_property
    def structure(self):
        structure = self.getter.data.structures.get(self.structure_key)
        if structure is None:
            raise RenderError(f"Structure {self.structure_key} not found")
        return StructureDataModel.model_validate(structure.data)

    def rotate_camera(self):
        if not self.do_rotate_camera:
            return
        # transform the vertices
        scale = self.display_option.scale or [1, 1, 1]
        translation = self.display_option.translation or [0, 0, 0]
        rotation = self.display_option.rotation or [0, 0, 0]

        # reset the matrix
        glLoadIdentity()
        glTranslatef(-translation[0], translation[1], -translation[2])
        glRotatef(-rotation[0], 1, 0, 0)
        glRotatef(rotation[1] + 180, 0, 1, 0)
        glRotatef(rotation[2], 0, 0, 1)
        glScalef(scale[0], scale[1], scale[2])

    def run(self):
        random.seed(self.random_seed)
        self.rotate_camera()
        sx, sy, sz = self.structure.size
        center = (sx / 2, sy / 2, sz / 2)
        center = (16 * center[0], 16 * center[1], 16 * center[2])
        for block in self.structure.blocks:
            self.render_block(block, center)
        for entity in self.structure.entities or []:
            if resolve_key(entity.get("nbt", {}).get("id", "")) == "minecraft:item_display":
                self.render_item_display(entity, center)
        # translucent fluids go last, over what is behind them
        for block in self.structure.blocks:
            self.render_fluid(block, center)
        random.seed()

    def render_item_display(self, entity: dict[str, Any], center: tuple[float, float, float]):
        """An item_display entity, like DisplayRenderer: position, billboard orientation
        (fixed: rotationYXZ(-yaw, pitch, 0)), transformation, a half turn around y, then the
        item rendered for its display context."""
        from model_resolver.tasks.item import ItemRenderTask, get_transformations

        nbt = entity["nbt"]
        if "item" not in nbt:
            return
        stack = nbt["item"]
        item = Item(
            id=stack["id"],
            count=stack.get("count", 1),
            components=stack.get("components", {}),
            display_context=nbt.get("item_display", "none"),
            owner=None,
        )
        try:
            item.fill(self.getter._ctx)
        except Exception as e:
            log.warning(f"No default components for {item.id}: {e}")
            item.__resolved__ = True
        render = ItemRenderTask(getter=self.getter, item=item)
        try:
            resolved = list(render.get_parsed_item_model().resolve(self.getter, item))
        except (RenderError, AssertionError) as e:
            log.warning(f"Skipping item_display of {item.id}: {e}")
            return
        yaw, pitch = (nbt.get("Rotation") or [0.0, 0.0])[:2]
        if nbt.get("billboard", "fixed") != "fixed":
            log.warning("Only fixed item_display billboards are supported, drawing it fixed")
        entity_transformation = Transformation.model_validate(
            nbt.get("transformation", {"translation": [0, 0, 0], "left_rotation": [0, 0, 0, 1],
                                        "right_rotation": [0, 0, 0, 1], "scale": [1, 1, 1]})
        )
        position = [16 * x - c for x, c in zip(entity["pos"], center)]
        for model in resolved:
            model_def = model.get_model(self.getter, item).bake()
            transformation, calibration = get_transformations(model)
            display = render.get_display(model_def)
            glPushMatrix()
            glTranslatef(*position)
            # the world pose, also tracked for the light (same steps, linear part only)
            pose = np.identity(3)
            glRotatef(-yaw, 0, 1, 0)
            glRotatef(pitch, 1, 0, 0)
            pose = pose @ _rot("y", -yaw) @ _rot("x", pitch)
            matrix = list(entity_transformation.get_matrix())
            matrix[12:15] = [x * 16 for x in matrix[12:15]]
            glMultMatrixf(matrix)
            pose = pose @ np.array(entity_transformation.get_matrix()).reshape(4, 4).T[:3, :3]
            glRotatef(180, 0, 1, 0)
            pose = pose @ _rot("y", 180)
            # ItemTransform.apply in pixels: translate, rotationXYZ, scale (then translate(-0.5),
            # which is where the centered geometry already is)
            glTranslatef(*display.translation)
            for angle, axis in zip(display.rotation, ((1, 0, 0), (0, 1, 0), (0, 0, 1))):
                glRotatef(angle, *axis)
            glScalef(*display.scale)
            pose = pose @ _rot("x", display.rotation[0]) @ _rot("y", display.rotation[1]) @ _rot("z", display.rotation[2])
            pose = pose @ np.diag(display.scale)
            if transformation is not None:
                local = list(transformation.get_matrix())
                local[12:15] = [x * 16 for x in local[12:15]]
                glTranslatef(-8, -8, -8)
                glMultMatrixf(local)
                glTranslatef(8, 8, 8)
                pose = pose @ np.array(transformation.get_matrix()).reshape(4, 4).T[:3, :3]
            if calibration is not None:
                glMultMatrixf(calibration.get_matrix())
                pose = pose @ np.array(calibration.get_matrix()).reshape(4, 4).T[:3, :3]
            ModelRenderTask(
                getter=self.getter,
                render_size=self.render_size,
                model=model_def,
                item=item,
                dynamic_textures=self.dynamic_textures,
                do_rotate_camera=False,
                tints=model.get_tints(self.getter, item),
                lighting="level",
                lighting_pose=pose,
            ).run()
            glPopMatrix()

    @cached_property
    def block_positions(self) -> dict[tuple[int, int, int], int]:
        return {tuple(block.pos): block.state for block in self.structure.blocks}  # type: ignore

    def neighbour(self, block: BlockModel, direction: str) -> Optional[PaletteModel]:
        dx, dy, dz = DIRECTIONS[direction]
        x, y, z = block.pos
        state = self.block_positions.get((x + dx, y + dy, z + dz))
        return None if state is None else self.structure.palette[state]

    @cached_property
    def _occlusion(self) -> dict[int, Optional[str]]:
        return {}

    def occlusion(self, state: int) -> Optional[str]:
        """"opaque" for full opaque cubes, "self" for full cubes with see-through texels
        (glass culls against glass, HalfTransparentBlock.skipRendering), else None."""
        if state not in self._occlusion:
            self._occlusion[state] = self.compute_occlusion(self.structure.palette[state])
        return self._occlusion[state]

    def compute_occlusion(self, palleted: PaletteModel) -> Optional[str]:
        if resolve_key(palleted.Name).endswith("_leaves") or self.render_special(palleted):
            return None
        try:
            variants = self.get_block_variants(palleted)
        except RenderError:
            return None
        if len(variants) != 1 or isinstance(variants[0], list) or not isinstance(variants[0].model, str):
            return None
        model = self.get_parsed_model(variants[0].model)
        full = [
            element
            for element in model.elements
            if element.from_ == (0, 0, 0) and element.to == (16, 16, 16) and len(element.faces) == 6
            and element.rotation is None
        ]
        if not full:
            return None
        images = [image for image, _ in self.load_textures(model).values() if isinstance(image, Image.Image)]
        opaque = all(image.convert("RGBA").getchannel("A").getextrema()[0] == 255 for image in images)
        return "opaque" if opaque else "self"

    def culled_directions(self, block: BlockModel) -> set[str]:
        """Directions whose neighbour hides the faces that have this cullface (Block.shouldRenderFace)."""
        try:
            name = self.structure.palette[block.state].Name
        except RenderError:
            # a variant drawn on its own, outside of a structure
            return set()
        culled = set()
        for direction in DIRECTIONS:
            neighbour = self.neighbour(block, direction)
            if neighbour is None:
                continue
            kind = self.occlusion(self.block_positions[tuple(  # type: ignore
                a + b for a, b in zip(block.pos, DIRECTIONS[direction])
            )])
            if kind == "opaque" or (kind == "self" and neighbour.Name == name):
                culled.add(direction)
        return culled

    def block_info(self, palleted: PaletteModel) -> BlockInfo:
        key = (palleted.Name, tuple(sorted(palleted.Properties.items())))
        if key not in self._block_infos:
            self._block_infos[key] = block_info(
                self.getter.opts.minecraft_version, palleted.Name, palleted.Properties
            )
        return self._block_infos[key]

    @cached_property
    def _block_infos(self) -> dict[Any, BlockInfo]:
        return {}

    def fluid_of(self, palleted: Optional[PaletteModel]) -> Optional[str]:
        state = self.fluid_state(palleted)
        return None if state is None else state.fluid

    def render_fluid(self, block: BlockModel, center: tuple[float, float, float]):
        """The fluid of a block (water, lava, or waterlogged), like FluidRenderer: sloped and
        flowing towards lower neighbours. Past the structure's sides the world is assumed to
        go on like its edge, so water at the edge doesn't slope down into nothing."""
        pos: Position = tuple(block.pos)  # type: ignore
        quads = tesselate_fluid(StructureFluids(self, extend=True), pos, StructureFluids(self))
        if not quads:
            return
        fluid = self.fluid_of(self.structure.palette[block.state])
        assert fluid is not None
        tint = self.biome_colors.water_color() if fluid == "minecraft:water" else 0xFFFFFF
        red, green, blue = ((tint >> 16) & 0xFF) / 255, ((tint >> 8) & 0xFF) / 255, (tint & 0xFF) / 255
        # where center_element puts a block's model space (pixels, centered on the model)
        shift = np.array(center, dtype=float) + 8 - 16 * np.array(pos, dtype=float)
        for quad in quads:
            image = self.fluid_texture(fluid, quad.texture)
            if image is None:
                continue
            vertices = [tuple(16 * np.array(vertex) - shift) for vertex in quad.vertices]
            color = (red * quad.shade, green * quad.shade, blue * quad.shade)
            self.draw_quad(self.fluid_binding(fluid, quad.texture, image), vertices, quad.uvs, color, quad.back_face)

    def fluid_binding(self, fluid: str, kind: str, image: Image.Image) -> int:
        key = f"{fluid}_{kind}"
        if key not in self._fluid_bindings:
            self._fluid_bindings[key] = self.upload_texture(image)
        return self._fluid_bindings[key]

    @cached_property
    def _fluid_bindings(self) -> dict[str, int]:
        return {}

    def fluid_state(self, palleted: Optional[PaletteModel]) -> Optional[FluidState]:
        """BlockState.getFluidState: water and lava by level, waterlogged blocks, and the blocks
        that always hold water (kelp, seagrass, bubble columns)."""
        if palleted is None:
            return None
        fluid = self.block_info(palleted).fluid
        return None if fluid is None else FluidState(*fluid)

    @cached_property
    def biome_colors(self) -> Biome:
        return load_biome(self.getter, self.biome)

    @cached_property
    def _fluid_textures(self) -> dict[str, Optional[Image.Image]]:
        return {}

    def fluid_texture(self, fluid: str, kind: str) -> Optional[Image.Image]:
        """The still, flowing or overlay texture: the current frame of an animated render,
        else the first frame."""
        key = f"{fluid}_{kind}"
        if key not in self._fluid_textures:
            namespace, path = fluid.split(":")
            texture_key = f"{namespace}:block/{path}_{kind}"
            texture = self.getter.assets.textures.get(texture_key)
            image = None
            if self.images_override and texture_key in self.images_override:
                image = self.images_override[texture_key].convert("RGBA")
            elif texture is not None:
                image = texture.image.convert("RGBA")
                image = image.crop((0, 0, image.width, image.width))
            self._fluid_textures[key] = image
        return self._fluid_textures[key]

    def get_parsed_model(self, key: str) -> MinecraftModel:
        model = self.getter.assets.models.get(key)
        if not model:
            raise RenderError(f"Model {key} not found")
        return MinecraftModel.model_validate(
            resolve_model(model.data, self.getter)
        ).bake()

    def get_block_variants(self, palleted: PaletteModel) -> list[Variant]:
        """The variants drawn for a block state, looked up through every pack.

        Like BlockStateModelLoader.loadBlockStateDefinitionStack, a pack only replaces
        the states its blockstate file covers, the others come from the packs below.
        """
        stack = self.getter.get_stack(Blockstate, palleted.Name)
        if not stack:
            raise RenderError(f"Blockstate {palleted.Name} not found")
        for file in stack:
            variants = BlockState.model_validate(file.data).select(palleted.Properties)
            if variants is not None:
                return variants
        # a state no definition covers shows the missing model
        log.warning(f"No variant of {palleted.Name} for {palleted.Properties}, using the missing model")
        return [VariantModel(model=missing_model())]

    def get_all_textures(self) -> Generator[dict[str, TextureSource], None, None]:
        for state in sorted({block.state for block in self.structure.blocks}):
            for variant in self.get_block_variants(self.structure.palette[state]):
                for option in variant if isinstance(variant, list) else [variant]:
                    if isinstance(option.model, str):
                        yield self.get_parsed_model(option.model).textures
        # the fluids are animated too
        fluids = {self.fluid_of(self.structure.palette[block.state]) for block in self.structure.blocks}
        for fluid in sorted(fluid for fluid in fluids if fluid is not None):
            namespace, path = fluid.split(":")
            yield {kind: f"{namespace}:block/{path}_{kind}" for kind in ("still", "flow")}

    def resolve(self) -> Generator[Task, None, None]:
        animation = Animation(
            textures=list(self.get_all_textures()),
            getter=self.getter,
            animation_framerate=self.animation_framerate,
            source=self.structure_key,
        )
        if not animation.is_animated:
            self.animation_mode = "multi_files"
            yield self
            return

        tasks = []

        frames = list(animation.get_frames())
        animated_path_padding = max(
            self.animated_path_padding, len(str(len(frames) - 1))
        )

        for i, (images, duration) in frames:
            if self.path_save:
                new_path_save = self.path_save / "{i:0{animated_path_padding}}_{duration}.png".format(
                    i = i,
                    duration = duration,
                    animated_path_padding = animated_path_padding
                )
            else:
                new_path_save = None
            if self.path_ctx:
                new_path_ctx = self.path_ctx + "/{i:0{animated_path_padding}}_{duration}".format(
                    i = i,
                    duration = duration,
                    animated_path_padding = animated_path_padding
                )
            else:
                new_path_ctx = None
            if self.animation_mode == "one_file":
                new_path_save = self.path_save
                new_path_ctx = self.path_ctx

            task = StructureRenderTask(
                structure_key=self.structure_key,
                getter=self.getter,
                item=self.item,
                do_rotate_camera=self.do_rotate_camera,
                offset=self.offset,
                center_offset=self.center_offset,
                additional_rotations=self.additional_rotations,
                path_ctx=new_path_ctx,
                path_save=new_path_save,
                animation_mode=self.animation_mode,
                render_size=self.render_size,
                zoom=self.zoom,
                ensure_params=self.ensure_params,
                dynamic_textures=self.dynamic_textures,
                images_override=images,
                animation_duration=duration,
                display_option=self.display_option,
                biome=self.biome,
            )
            yield task
            tasks.append(task)
            if self.animation_mode == "one_file":
                break

        self.tasks = tasks
        if self.animation_mode == "webp":
            yield AnimatedResultTask(
                tasks=tasks,
                path_ctx=self.path_ctx,
                path_save=self.path_save,
                getter=self.getter,
                render_size=self.render_size,
                zoom=self.zoom,
                animation_mode=self.animation_mode,
                animation_framerate=self.animation_framerate,
            )

    def render_special(self, palleted: PaletteModel) -> VariantModel | None:
        if not self.getter.opts.special_rendering:
            return None
        shulker_block_to_textures = {
            "minecraft:shulker_box": "minecraft:shulker",
            "minecraft:white_shulker_box": "minecraft:shulker_white",
            "minecraft:light_gray_shulker_box": "minecraft:shulker_light_gray",
            "minecraft:gray_shulker_box": "minecraft:shulker_gray",
            "minecraft:black_shulker_box": "minecraft:shulker_black",
            "minecraft:brown_shulker_box": "minecraft:shulker_brown",
            "minecraft:red_shulker_box": "minecraft:shulker_red",
            "minecraft:orange_shulker_box": "minecraft:shulker_orange",
            "minecraft:yellow_shulker_box": "minecraft:shulker_yellow",
            "minecraft:lime_shulker_box": "minecraft:shulker_lime",
            "minecraft:green_shulker_box": "minecraft:shulker_green",
            "minecraft:cyan_shulker_box": "minecraft:shulker_cyan",
            "minecraft:light_blue_shulker_box": "minecraft:shulker_light_blue",
            "minecraft:blue_shulker_box": "minecraft:shulker_blue",
            "minecraft:purple_shulker_box": "minecraft:shulker_purple",
            "minecraft:magenta_shulker_box": "minecraft:shulker_magenta",
            "minecraft:pink_shulker_box": "minecraft:shulker_pink",
        }
        if resolve_key(palleted.Name) in shulker_block_to_textures.keys():
            orientation = palleted.Properties.get("facing", "up")
            match orientation:
                case "up":
                    rot = (0, -90, 0)
                case "down":
                    rot = (0, 90, -180)
                case "north":
                    rot = (0, 90, -90)
                case "south":
                    rot = (0, -90, -90)
                case "west":
                    rot = (0, 180, -90)
                case "east":
                    rot = (0, -90, -90)
                case _:
                    raise ValueError(f"Invalid orientation {orientation}")
                
            
            namespace, path = resolve_key(shulker_block_to_textures[resolve_key(palleted.Name)]).split(":")
            texture = f"{namespace}:entity/shulker/{path}"
            model = MinecraftModel.model_validate({
                "credit": "Made with Blockbench",
                "textures": {
                    "0": texture,
                },
                "elements": [
                    {
                        "name": "down_down",
                        "from": [0, 0, 0],
                        "to": [16, 0, 16],
                        "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                        "faces": {
                            "up": {"uv": [8, 7, 12, 11], "texture": "#0"},
                            "down": {"uv": [8, 7, 12, 11], "texture": "#0"},
                        },
                    },
                    {
                        "name": "down_north",
                        "from": [0, 0, 0],
                        "to": [16, 8, 0],
                        "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                        "faces": {
                            "north": {"uv": [8, 11, 12, 13], "texture": "#0"},
                            "south": {"uv": [8, 11, 12, 13], "texture": "#0"},
                        },
                    },
                    {
                        "name": "down_south",
                        "from": [0, 0, 16],
                        "to": [16, 8, 16],
                        "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                        "faces": {
                            "north": {"uv": [0, 11, 4, 13], "texture": "#0"},
                            "south": {"uv": [0, 11, 4, 13], "texture": "#0"},
                        },
                    },
                    {
                        "name": "down_east",
                        "from": [16, 0, 0],
                        "to": [16, 8, 16],
                        "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                        "faces": {
                            "east": {"uv": [4, 11, 8, 13], "texture": "#0"},
                            "west": {"uv": [4, 11, 8, 13], "texture": "#0"},
                        },
                    },
                    {
                        "name": "down_west",
                        "from": [0, 0, 0],
                        "to": [0, 8, 16],
                        "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                        "faces": {
                            "east": {"uv": [12, 11, 16, 13], "texture": "#0"},
                            "west": {"uv": [12, 11, 16, 13], "texture": "#0"},
                        },
                    },
                    {
                        "name": "down_up",
                        "from": [0, 8, 0],
                        "to": [16, 8, 16],
                        "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                        "faces": {
                            "up": {"uv": [4, 7, 8, 11], "texture": "#0"},
                            "down": {"uv": [4, 7, 8, 11], "texture": "#0"},
                        },
                    },
                    {
                        "name": "up_north",
                        "from": [0, 4, 0],
                        "to": [16, 16, 0],
                        "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                        "faces": {
                            "north": {"uv": [8, 4, 12, 7], "texture": "#0"},
                            "south": {"uv": [8, 4, 12, 7], "texture": "#0"},
                        },
                    },
                    {
                        "name": "up_south",
                        "from": [0, 4, 16],
                        "to": [16, 16, 16],
                        "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                        "faces": {
                            "north": {"uv": [0, 4, 4, 7], "texture": "#0"},
                            "south": {"uv": [0, 4, 4, 7], "texture": "#0"},
                        },
                    },
                    {
                        "name": "up_west",
                        "from": [0, 4, 0],
                        "to": [0, 16, 16],
                        "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                        "faces": {
                            "east": {"uv": [12, 4, 16, 7], "texture": "#0"},
                            "west": {"uv": [12, 4, 16, 7], "texture": "#0"},
                        },
                    },
                    {
                        "name": "up_east",
                        "from": [16, 4, 0],
                        "to": [16, 16, 16],
                        "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                        "faces": {
                            "east": {"uv": [4, 4, 8, 7], "texture": "#0"},
                            "west": {"uv": [4, 4, 8, 7], "texture": "#0"},
                        },
                    },
                    {
                        "name": "up_up",
                        "from": [0, 16, 0],
                        "to": [16, 16, 16],
                        "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                        "faces": {
                            "up": {"uv": [4, 0, 8, 4], "rotation": 270, "texture": "#0"},
                            "down": {"uv": [4, 0, 8, 4], "rotation": 270, "texture": "#0"},
                        },
                    },
                    {
                        "name": "up_down",
                        "from": [0, 4, 0],
                        "to": [16, 4, 16],
                        "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                        "faces": {
                            "up": {"uv": [8, 0, 12, 4], "texture": "#0"},
                            "down": {"uv": [8, 0, 12, 4], "texture": "#0"},
                        },
                    },
                ],
            }).bake()

            init_rotation = model.display.gui.rotation
            model.display.gui.rotation = (
                init_rotation[0] + rot[0],
                init_rotation[1] + rot[1],
                init_rotation[2] + rot[2],
            )
            return VariantModel(
                model=model,
            )

    def render_block(self, block: BlockModel, center: tuple[float, float, float]):
        palleted = self.structure.palette[block.state]

        if variant := self.render_special(palleted):
            return self.render_variant(variant, block, center, palleted)
        for variant in self.get_block_variants(palleted):
            self.render_variant(variant, block, center, palleted)
        if self.getter.opts.special_rendering:
            self.render_builtin(block, palleted, center)

    def render_builtin(self, block: BlockModel, palleted: PaletteModel, center: tuple[float, float, float]):
        """The special model BuiltInBlockModels adds to banners, heads, pots, conduits, bells,
        enchanting tables, copper golem statues and end portals, placed by its block transformation."""
        from model_resolver.item_model.model import ItemModelSpecial, VANILLA_SPECIAL_TRANSFORMATIONS

        builtin = builtin_block(resolve_key(palleted.Name), palleted.Properties, block.nbt or {})
        if builtin is None:
            return
        item_id, special, placement, components = builtin
        base = self.special_base(item_id)
        node = ItemModelSpecial.model_validate(
            {"type": "minecraft:special", "base": base or "minecraft:builtin/entity", "model": special}
        )
        item = Item(id=item_id or "minecraft:stone", components=components)
        item.__resolved__ = True
        model = node.get_model(self.getter, item)
        # what the special geometry was calibrated with, see ItemModelSpecial.split_transformation
        default = VANILLA_SPECIAL_TRANSFORMATIONS.get(resolve_key(special["type"]))
        default_matrix = np.identity(4) if default is None else np.array(default, dtype=float).reshape(4, 4).T
        delta = placement @ np.linalg.inv(default_matrix)
        # the gui display tweaks of the special (get_additional_rotations...), relative to its base
        base_display = (
            MinecraftModel.model_validate(resolve_model({"parent": base}, self.getter)).display.gui
            if base
            else model.display.gui
        )
        tweaks = np.linalg.inv(camera_matrix(base_display)) @ camera_matrix(model.display.gui)
        offset = np.array([block.pos[0] * 16, block.pos[1] * 16, block.pos[2] * 16], dtype=float)
        shift = np.array(center, dtype=float) - offset
        delta16 = delta.copy()
        delta16[:3, 3] *= 16
        glPushMatrix()
        glTranslatef(*(-shift))
        glTranslatef(-8, -8, -8)
        glMultMatrixf(delta16.T.flatten())
        glTranslatef(8, 8, 8)
        glMultMatrixf(tweaks.T.flatten())
        pose = delta[:3, :3] @ tweaks[:3, :3]
        if default is not None:
            glMultMatrixf(default)
            pose = pose @ default_matrix[:3, :3]
        glTranslatef(*shift)
        ModelRenderTask(
            getter=self.getter,
            render_size=self.render_size,
            model=model,
            item=item,
            dynamic_textures=self.dynamic_textures,
            do_rotate_camera=False,
            offset=tuple(offset),  # type: ignore
            center_offset=center,
            tints=node.get_tints(self.getter, item),
            # block entities are lit like entities (Lighting.Entry.LEVEL)
            lighting="level",
            lighting_pose=pose,
        ).run()
        glPopMatrix()

    @cached_property
    def _special_bases(self) -> dict[str, Optional[str]]:
        return {}

    def special_base(self, item_id: Optional[str]) -> Optional[str]:
        """The `base` of the special model in the item's definition."""
        if item_id is None:
            return None
        if item_id not in self._special_bases:
            definition = self.getter.assets.item_models.get(item_id)
            bases = [
                data["base"]
                for _, data in traverse_all(definition.data if definition else {}, "base")
            ]
            self._special_bases[item_id] = bases[0] if bases else None
        return self._special_bases[item_id]

    def render_variant(
        self,
        variant: Variant,
        block: BlockModel,
        center: tuple[float, float, float],
        palleted: PaletteModel,
    ):
        if isinstance(variant, list):
            resolved_variant = random.choices(
                variant, weights=[x.weight for x in variant]
            )[0]
        else:
            resolved_variant = variant
        if (
            isinstance(resolved_variant.model, str)
            and resolve_key(resolved_variant.model) == "minecraft:block/air"
        ):
            return

        rots = resolved_variant.rotations
        tints = (
            self.get_tints(resolved_variant.model, palleted)
            if isinstance(resolved_variant.model, str)
            else []
        )

        model = (
            self.get_parsed_model(resolved_variant.model)
            if isinstance(resolved_variant.model, str)
            else resolved_variant.model
        )
        model = model.bake()
        if self.images_override:
            textures = self.get_textures(model, self.images_override)
            model.textures = textures

        task = ModelRenderTask(
            getter=self.getter,
            render_size=self.render_size,
            model=model,
            dynamic_textures=self.dynamic_textures,
            do_rotate_camera=False,
            additional_rotations=rots,
            offset=(block.pos[0] * 16, block.pos[1] * 16, block.pos[2] * 16),
            center_offset=center,
            tints=tints,
            uv_lock=resolved_variant.uvlock,
            lighting="terrain",
            culled_faces=self.culled_directions(block),
        )
        task.run()

    def get_tints(self, model: str, palleted) -> list[TintSource]:
        if not self.getter.opts.colorize_blocks:
            return []

        # BlockColors, with the colors of the structure's biome
        colors = block_tints(self.getter, self.biome_colors, palleted.Name, palleted.Properties)
        if colors is not None:
            return [
                TintSourceConstant(type="minecraft:constant", value=0xFFFFFF if color is None else color)
                for color in colors
            ]

        # blocks BlockColors doesn't know (other namespaces): their item model's tints
        namespace, path = resolve_key(model).split(":")
        path = path.removeprefix("block/")
        item_model_key = f"{namespace}:{path}"
        item_model = self.getter.assets.item_models.get(item_model_key)
        if item_model is not None:
            for _, data in traverse_all(item_model.data):
                if "tints" in data:
                    return TempTintSource.model_validate({"tints": data["tints"]}).tints
        return []


NestedDictList = Union[dict[str, Any], list[Any]]


def traverse_all(data: NestedDictList, key: str = "model"):
    if isinstance(data, dict):
        if key in data.keys() and isinstance(data[key], str):
            yield data[key], data
        for x in data.values():
            if not (isinstance(x, dict) or isinstance(x, list)):
                continue
            yield from traverse_all(x, key)
    if isinstance(data, list):
        for x in data:
            if not (isinstance(x, dict) or isinstance(x, list)):
                continue
            yield from traverse_all(x, key)


class TempTintSource(BaseModel):
    tints: list[TintSource]
