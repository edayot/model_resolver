from PIL import Image
from beet import Context
from beet.contrib.vanilla import Vanilla, Release
from pydantic import BaseModel
from typing import Optional


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
    special_filter: dict = {}
    light: LightOptions = LightOptions()
    save_namespace: Optional[str] = None
