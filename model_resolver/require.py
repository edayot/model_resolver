

from beet import Context, Model, NamespaceFileScope, JsonFile
from typing import ClassVar, Type, Any
from model_resolver.utils import resolve_key
from model_resolver.vanilla import Vanilla
from copy import deepcopy
from pydantic import BaseModel, Field
from typing import Annotated, Literal, Optional

class ModelResolveNamespace(Model):

    def resolve(self, ctx: Context, vanilla: "Vanilla") -> "MinecraftModel":
        internal = self.resolve_internal(ctx, vanilla)
        return MinecraftModel.model_validate(internal, from_attributes=True)

    def resolve_internal(self, ctx: Context, vanilla: "Vanilla") -> dict[str, Any]:
        if not "parent" in self.data:
            return self.data
        parent_key = resolve_key(self.data["parent"])
        if parent_key in [
            "minecraft:builtin/generated",
            "minecraft:builtin/entity",
        ]:
            return self.data
        if parent_key in ctx.assets[ModelResolveNamespace]:
            parent = ctx.assets[ModelResolveNamespace][parent_key]
        elif parent_key in vanilla.assets[ModelResolveNamespace]:
            parent = vanilla.assets[ModelResolveNamespace][parent_key]
        else:
            raise ValueError(f"{parent_key} not in Context or Vanilla")
        resolved_parent = parent.resolve_internal(ctx, vanilla)
        return self.merge_parent(resolved_parent)

        
    def merge_parent(self, parent: dict[str, Any]) -> dict[str, Any]:
        res = deepcopy(parent)
        if "textures" in self.data:
            res.setdefault("textures", {})
            res["textures"].update(self.data["textures"])
        if "elements" in self.data:
            res["elements"] = self.data["elements"]
        if "display" in self.data:
            res.setdefault("display", {})
            for key in self.data["display"].keys():
                res["display"][key] = self.data["display"][key]
        if "ambientocclusion" in self.data:
            res["ambientocclusion"] = self.data["ambientocclusion"]
        if "overrides" in self.data:
            res["overrides"] = self.data["overrides"]
        if "gui_light" in self.data:
            res["gui_light"] = self.data["gui_light"]
        return res

class ItemModelNamespace(JsonFile):
    """Class representing a model."""

    scope: ClassVar[NamespaceFileScope] = ("items",)
    extension: ClassVar[str] = ".json"
         

def beet_default(ctx: Context):
    ctx.assets.extend_namespace.extend([ModelResolveNamespace, ItemModelNamespace])



faces_keys = Literal["north", "south", "east", "west", "up", "down"]

class DisplayOptionModel(BaseModel):
    rotation: tuple[float, float, float] = Field(default_factory=lambda: (0, 0, 0))
    translation: tuple[float, float, float] = Field(default_factory=lambda: (0, 0, 0))
    scale: tuple[float, float, float] = Field(default_factory=lambda: (1, 1, 1))


def _gen(): return DisplayOptionModel()

class DisplayModel(BaseModel):
    thirdperson_righthand: DisplayOptionModel = Field(default_factory=_gen)
    thirdperson_lefthand: DisplayOptionModel = Field(default_factory=_gen)
    firstperson_righthand: DisplayOptionModel = Field(default_factory=_gen)
    firstperson_lefthand: DisplayOptionModel = Field(default_factory=_gen)
    gui: DisplayOptionModel = Field(default_factory=lambda: DisplayOptionModel(
        rotation=(30, 225, 0),
        translation=(0, 0, 0),
        scale=(0.625, 0.625, 0.625)
    ))
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
    from_: tuple[float, float, float] = Field(alias="from", serialization_alias="from")
    to: tuple[float, float, float]
    rotation: Optional[RotationModel] = None
    shade: bool = True
    light_emission: int = 0
    faces: dict[faces_keys, FaceModel]



class MinecraftModel(BaseModel):
    parent: Annotated[Optional[str], "The parent of the model"] = None
    ambientocclusion: Annotated[bool, "Whether the model should use ambient occlusion"] = True
    display: Annotated[DisplayModel, "The display settings for the model in various situations in the game"] = Field(default_factory=lambda: DisplayModel())
    textures: Annotated[dict[str, str], "Resource locations for the textures used in the model, can also be a texture variable"] = Field(default_factory=dict)
    elements: Annotated[list[ElementModel], "The elements that make up the model"] = Field(default_factory=list)
    gui_light: Annotated[Literal["front", "side"], "Control the light position"] = "side"


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
        for i in range(0, max+1):
            if not f"layer{i}" in self.textures:
                continue
            self.elements.append(ElementModel.model_validate({
                "from": [0, 0, -i],
                "to": [16, 16, -i],
                "faces": {
                    "north": {
                        "texture": f"#layer{i}",
                        "uv": [0, 0, 16, 16],
                        "tintindex": i
                    }
                }
            }))
        self.parent = None
        self.display.gui = DisplayOptionModel(rotation=(180, 0, 180)) 
        return self
            