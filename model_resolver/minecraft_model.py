from typing import Any
from model_resolver.item_model.tint_source import TintSource
from model_resolver.utils import clamp, resolve_key
from model_resolver.pack_getter import PackGetter
from copy import deepcopy
from pydantic import BaseModel, Field, ConfigDict, AliasChoices, field_validator, model_validator
from typing import Annotated, Literal, Optional
from PIL import Image


faces_keys = Literal["north", "south", "east", "west", "up", "down"]


class DisplayOptionModel(BaseModel):
    rotation: tuple[float, float, float] = Field(default_factory=lambda: (0, 0, 0))
    translation: tuple[float, float, float] = Field(default_factory=lambda: (0, 0, 0))
    scale: tuple[float, float, float] = Field(default_factory=lambda: (1, 1, 1))

    @field_validator("translation")
    @classmethod
    def clamp_translation(cls, value: tuple[float, float, float]):
        # ItemTransform.Deserializer: at most 5 blocks
        return tuple(clamp(-80.0, x, 80.0) for x in value)

    @field_validator("scale")
    @classmethod
    def clamp_scale(cls, value: tuple[float, float, float]):
        return tuple(clamp(-4.0, x, 4.0) for x in value)


def with_left_hands(display: dict[str, Any]) -> dict[str, Any]:
    """ItemTransforms.Deserializer: a file without a left-hand entry uses its right-hand one."""
    display = dict(display)
    for view in ("thirdperson", "firstperson"):
        if f"{view}_righthand" in display and f"{view}_lefthand" not in display:
            display[f"{view}_lefthand"] = display[f"{view}_righthand"]
    return display


def _gen():
    return DisplayOptionModel()


class DisplayModel(BaseModel):
    thirdperson_righthand: DisplayOptionModel = Field(default_factory=_gen)
    thirdperson_lefthand: DisplayOptionModel = Field(default_factory=_gen)
    firstperson_righthand: DisplayOptionModel = Field(default_factory=_gen)
    firstperson_lefthand: DisplayOptionModel = Field(default_factory=_gen)
    gui: DisplayOptionModel = Field(
        default_factory=lambda: DisplayOptionModel(
            rotation=(30, 225, 0), translation=(0, 0, 0), scale=(0.625, 0.625, 0.625)
        )
    )
    head: DisplayOptionModel = Field(default_factory=_gen)
    ground: DisplayOptionModel = Field(default_factory=_gen)
    fixed: DisplayOptionModel = Field(default_factory=_gen)
    on_shelf: DisplayOptionModel = Field(default_factory=_gen)

    @model_validator(mode="before")
    @classmethod
    def left_hands(cls, data: Any) -> Any:
        return with_left_hands(data) if isinstance(data, dict) else data

    def get(self, context: str) -> DisplayOptionModel:
        """The transform of an ItemDisplayContext ("none" is the identity)."""
        if context == "none":
            return DisplayOptionModel()
        return getattr(self, context)


class SingleAxisRotationModel(BaseModel):
    origin: tuple[float, float, float]
    axis: Literal["x", "y", "z"]
    angle: float
    rescale: bool = False

    def to_multi_axis(self) -> MultiAxisRotationModel:
        x = self.angle if self.axis == "x" else 0
        y = self.angle if self.axis == "y" else 0
        z = self.angle if self.axis == "z" else 0
        return MultiAxisRotationModel(
            origin=self.origin, x=x, y=y, z=z, rescale=self.rescale
        )

class MultiAxisRotationModel(BaseModel):
    origin: tuple[float, float, float]
    x: float = 0
    y: float = 0
    z: float = 0
    rescale: bool = False

    def to_multi_axis(self) -> MultiAxisRotationModel:
        return self


type RotationModel = SingleAxisRotationModel | MultiAxisRotationModel

class FaceModel(BaseModel):
    uv: Optional[tuple[float, float, float, float]] = None
    texture: Annotated[str, "The texture variable for the face"]
    cullface: Optional[faces_keys | str] = None
    rotation: Literal[0, 90, 180, 270] = 0
    tintindex: int = -1


class ElementModel(BaseModel):
    from_: tuple[float, float, float] = Field(
        validation_alias=AliasChoices("from", "from_")
    )
    to: tuple[float, float, float]
    rotation: Optional[RotationModel] = Field(default=None, union_mode="left_to_right")
    shade: bool = True
    """Before 26.3; `false` is drawn unshaded in the world."""
    shade_direction_override: Optional[faces_keys] = None
    """26.3: the world shading of the element's faces is that of this direction."""
    light_emission: int = 0
    faces: dict[faces_keys, FaceModel]


type MultiTexture = tuple[str, TintSource | None]
type MultiTextureResolved = tuple[Image.Image, TintSource | None]


type ResolvableTexture = None | str | Image.Image | tuple[MultiTexture, ...]
type ResolvedTexture = Image.Image | tuple[MultiTextureResolved, ...]

class TextureDict(BaseModel):
    sprite: str
    force_translucent: bool = False

type TextureSource = str | Image.Image | tuple[MultiTexture, ...] | TextureDict


class MinecraftModel(BaseModel):
    parent: Annotated[Optional[str], "The parent of the model"] = None
    ambientocclusion: Annotated[
        bool, "Whether the model should use ambient occlusion"
    ] = True
    display: Annotated[
        DisplayModel,
        "The display settings for the model in various situations in the game",
    ] = Field(default_factory=lambda: DisplayModel())
    textures: Annotated[
        dict[str, TextureSource],
        "Resource locations for the textures used in the model, can also be a texture variable",
    ] = Field(default_factory=dict)
    elements: Annotated[list[ElementModel], "The elements that make up the model"] = (
        Field(default_factory=list)
    )
    gui_light: Annotated[Literal["front", "side"], "Control the light position"] = (
        "side"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    generated_layers: list[int] = Field(default_factory=list, exclude=True)
    """Texture layers of a builtin/generated model, extruded when drawn (ItemModelGenerator)."""

    def bake(self) -> "MinecraftModel":
        """Build the geometry of builtin/generated, like ItemModelGenerator."""
        if not self.parent:
            return self
        if not resolve_key(self.parent) == "minecraft:builtin/generated":
            return self
        self.parent = None
        if self.elements:
            # the nearest geometry in the parent chain wins
            return self
        for i in range(5):
            # layer0 to layer4, up to the first missing one
            if f"layer{i}" not in self.textures:
                break
            self.generated_layers.append(i)
            texture = f"#layer{i}"
            self.elements.append(
                ElementModel.model_validate(
                    {
                        "from": [0, 0, 7.5],
                        "to": [16, 16, 8.5],
                        "faces": {
                            "south": {"texture": texture, "uv": [0, 0, 16, 16], "tintindex": i},
                            "north": {"texture": texture, "uv": [16, 0, 0, 16], "tintindex": i},
                        },
                    }
                )
            )
        if "gui" not in self.display.model_fields_set:
            # item/generated has no gui transform: NO_TRANSFORM
            self.display.gui = DisplayOptionModel()
        if "gui_light" not in self.model_fields_set:
            self.gui_light = "front"
        return self


def extruded_sides(image: Image.Image, layer: int) -> list[ElementModel]:
    """ItemModelGenerator.bakeSideFaces: a side quad on every edge between an opaque
    pixel and a transparent one (or the border), with UVs shrunk by 0.1 pixel."""
    width, height = image.size
    alpha = image.convert("RGBA").getchannel("A").load()
    assert alpha is not None
    x_scale, y_scale = 16 / width, 16 / height

    def transparent(x: int, y: int) -> bool:
        return not (0 <= x < width and 0 <= y < height) or alpha[x, y] == 0

    sides = []
    texture = f"#layer{layer}"
    for y in range(height):
        for x in range(width):
            if transparent(x, y):
                continue
            top, bottom = 16 - y * y_scale, 16 - (y + 1) * y_scale
            left, right = x * x_scale, (x + 1) * x_scale
            u0, u1 = (x + 0.1) * x_scale, (x + 0.9) * x_scale
            horizontal = (u0, (y + 0.1) * y_scale, u1, (y + 0.9) * y_scale)
            vertical = (u0, (y + 0.9) * y_scale, u1, (y + 0.1) * y_scale)
            # SideDirection: UP, DOWN, LEFT faces EAST and RIGHT faces WEST
            for face, (dx, dy), from_, to, uv in (
                ("up", (0, -1), (left, top, 7.5), (right, top, 8.5), horizontal),
                ("down", (0, 1), (left, bottom, 7.5), (right, bottom, 8.5), horizontal),
                ("east", (-1, 0), (left, bottom, 7.5), (left, top, 8.5), vertical),
                ("west", (1, 0), (right, bottom, 7.5), (right, top, 8.5), vertical),
            ):
                if transparent(x + dx, y + dy):
                    sides.append(
                        ElementModel.model_construct(
                            from_=from_,
                            to=to,
                            rotation=None,
                            shade=True,
                            light_emission=0,
                            faces={face: FaceModel(texture=texture, uv=uv, tintindex=layer)},
                        )
                    )
    return sides


MISSING_MODEL_ID = "minecraft:builtin/missing"


def missing_model() -> MinecraftModel:
    """What Minecraft draws for a model it can't find: a cube textured with missingno, no display transform."""
    face = {"texture": "#missingno", "uv": [0, 0, 16, 16]}
    return MinecraftModel.model_validate(
        {
            "display": {"gui": {"rotation": [0, 0, 0], "translation": [0, 0, 0], "scale": [1, 1, 1]}},
            "elements": [
                {
                    "from": [0, 0, 0],
                    "to": [16, 16, 16],
                    "faces": {name: face for name in ("down", "up", "north", "south", "west", "east")},
                }
            ],
        }
    )


def resolve_model(
    data: dict[str, Any],
    getter: PackGetter,
    delete_parent_elements: bool = False,
    children: tuple[str, ...] = (),
) -> dict[str, Any]:
    if not "parent" in data:
        return data
    parent_key = resolve_key(data["parent"])
    if parent_key in [
        "minecraft:builtin/generated",
        "minecraft:builtin/entity",
    ]:
        return data
    if parent_key in children:
        raise ValueError(f"Model parent cycle: {' -> '.join((*children, parent_key))}")
    if parent_key in getter.assets.models:
        parent = getter.assets.models[parent_key].data
    else:
        raise ValueError(f"{parent_key} not in Context or Vanilla")
    resolved_parent = resolve_model(parent, getter, children=(*children, parent_key))
    return merge_parent(resolved_parent, data, delete_parent_elements)


def merge_parent(
    parent: dict[str, Any],
    child: dict[str, Any],
    delete_parent_elements: bool = False,
) -> dict[str, Any]:
    res = deepcopy(parent)
    if delete_parent_elements:
        res.pop("elements", None)
    if "textures" in child:
        res.setdefault("textures", {})
        res["textures"].update(child["textures"])
    if "elements" in child:
        res["elements"] = child["elements"]
    if "display" in child:
        res.setdefault("display", {})
        for key, value in with_left_hands(child["display"]).items():
            res["display"][key] = value
    if "ambientocclusion" in child:
        res["ambientocclusion"] = child["ambientocclusion"]
    if "overrides" in child:
        res["overrides"] = child["overrides"]
    if "gui_light" in child:
        res["gui_light"] = child["gui_light"]
    return res
