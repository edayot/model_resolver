from PIL import Image
from beet import Context
from beet.contrib.vanilla import Vanilla, Release
from pydantic import BaseModel, Field
from typing import Optional

from pydantic import BaseModel, Field
from typing import Annotated, Literal, Optional
from beet import Context

def load_textures(
    textures: dict, ctx: Context, vanilla: Release
) -> dict[str, Image.Image]:
    res = {}
    for key in textures.keys():
        value = get_real_key(key, textures)
        if value == "__not_found__":
            res[key] = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        else:
            res[key] = load_texture(value, ctx, vanilla)
    return res


def load_texture(path: str, ctx: Context, vanilla: Release) -> Image.Image:
    path = f"minecraft:{path}" if ":" not in path else path
    if path in ctx.assets.textures:
        texture = ctx.assets.textures[path]
    elif path in vanilla.assets.textures:
        texture = vanilla.assets.textures[path]
    else:
        raise KeyError(f"Texture {path} not found")
    img: Image.Image = texture.image
    img = img.convert("RGBA")
    return img


def get_real_key(key: str, textures: dict, max_depth: int = 10) -> str:
    if max_depth == 0:
        return "__not_found__"
    if key not in textures:
        return "__not_found__"
    if textures[key][0] == "#":
        return get_real_key(textures[key][1:], textures, max_depth - 1)
    else:
        return textures[key]


class LightOptions(BaseModel):
    """Light options."""

    minecraft_light_power: float = 0.6727302277118515
    minecraft_ambient_light: float = 0.197261163686041
    minecraft_light_position: list[float] = [
        -0.42341569107908505,
        -0.6577205642540358,
        0.4158725999762756,
        0.0,
    ]


class ModelResolverOptions(BaseModel):
    """Model resolver options."""

    load_vanilla: bool = False
    resolve_vanilla_atlas: bool = False
    use_cache: bool = False
    render_size: int = 256
    minecraft_version: str = "latest"
    filter: Optional[list[str]] = []
    special_filter: dict[str, str] = Field(default_factory=dict)
    light: LightOptions = LightOptions()
    save_namespace: Optional[str] = None
    extra_block_entity_models: bool = False
    colorize_blocks: bool = False



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
    from_: tuple[float, float, float] = Field(alias="from")
    to: tuple[float, float, float]
    rotation: Optional[RotationModel] = None
    shade: bool = True
    light_emission: int = 0
    faces: dict[faces_keys, FaceModel]



class MinecraftModel(BaseModel):
    ambientocclusion: Annotated[bool, "Whether the model should use ambient occlusion"] = True
    display: Annotated[DisplayModel, "The display settings for the model in various situations in the game"] = Field(default_factory=lambda: DisplayModel())
    textures: Annotated[dict[str, str], "Resource locations for the textures used in the model, can also be a texture variable"] = Field(default_factory=dict)
    elements: Annotated[list[ElementModel], "The elements that make up the model"] = Field(default_factory=list)
    gui_light: Annotated[Literal["front", "side"], "Control the light position"] = "side"



if __name__ == "__main__":
    obj = {'from': [0, 0, 0], 'to': [16, 2, 16], 'faces': {'up': {'texture': '#inside'}, 'down': {'texture': '#bottom', 'cullface': 'down'}}}
    model = ElementModel.model_validate(obj)