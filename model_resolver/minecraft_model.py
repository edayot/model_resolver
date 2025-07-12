from typing import Any
from model_resolver.item_model.tint_source import TintSource
from model_resolver.utils import PackGetterV2, resolve_key
from copy import deepcopy
from pydantic import BaseModel, Field, ConfigDict, AliasChoices
from typing import Annotated, Literal, Optional
from PIL import Image


faces_keys = Literal["north", "south", "east", "west", "up", "down"]


class DisplayOptionModel(BaseModel):
    rotation: tuple[float, float, float] = Field(default_factory=lambda: (0, 0, 0))
    translation: tuple[float, float, float] = Field(default_factory=lambda: (0, 0, 0))
    scale: tuple[float, float, float] = Field(default_factory=lambda: (1, 1, 1))


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


class RotationModel(BaseModel):
    origin: tuple[float, float, float]
    axis: Literal["x", "y", "z"]
    angle: float
    rescale: bool = False


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
    rotation: Optional[RotationModel] = None
    shade: bool = True
    light_emission: int = 0
    faces: dict[faces_keys, FaceModel]


type MultiTexture = tuple[str, TintSource | None]
type MultiTextureResolved = tuple[Image.Image, TintSource | None]


type ResolvableTexture = None | str | Image.Image | tuple[MultiTexture, ...]
type ResolvedTexture = Image.Image | tuple[MultiTextureResolved, ...] 

type TextureSource = str | Image.Image | tuple[MultiTexture, ...]


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

    def bake(self) -> "MinecraftModel":
        if not self.parent:
            return self
        if not resolve_key(self.parent) == "minecraft:builtin/generated":
            return self
        if not self.textures:
            return self
        max = 0
        for key in self.textures.keys():
            if not key.startswith("layer"):
                continue
            index = int(key.removeprefix("layer"))
            if index > max:
                max = index
        for i in range(0, max + 1):
            if not f"layer{i}" in self.textures:
                continue
            self.elements.append(
                ElementModel.model_validate(
                    {
                        "from": [0, 0, -i],
                        "to": [16, 16, -i],
                        "faces": {
                            "north": {
                                "texture": f"#layer{i}",
                                "uv": [0, 0, 16, 16],
                                "tintindex": i,
                            }
                        },
                    }
                )
            )
        self.parent = None
        self.display.gui = DisplayOptionModel(rotation=(180, 0, 180))
        return self


def resolve_model(
    data: dict[str, Any],
    getter: PackGetterV2,
    delete_parent_elements: bool = False,
) -> dict[str, Any]:
    if not "parent" in data:
        return data
    parent_key = resolve_key(data["parent"])
    if parent_key in [
        "minecraft:builtin/generated",
        "minecraft:builtin/entity",
    ]:
        return data
    if parent_key in getter.assets.models:
        parent = getter.assets.models[parent_key].data
    else:
        raise ValueError(f"{parent_key} not in Context or Vanilla")
    resolved_parent = resolve_model(parent, getter)
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
        for key in child["display"].keys():
            res["display"][key] = child["display"][key]
    if "ambientocclusion" in child:
        res["ambientocclusion"] = child["ambientocclusion"]
    if "overrides" in child:
        res["overrides"] = child["overrides"]
    if "gui_light" in child:
        res["gui_light"] = child["gui_light"]
    return res
