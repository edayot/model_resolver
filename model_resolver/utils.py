from PIL import Image
from beet import Context
from beet.contrib.vanilla import Vanilla


def load_textures(
    textures: dict, ctx: Context, vanilla: Vanilla
) -> dict[str, Image.Image]:
    res = {}
    for key in textures.keys():
        value = get_real_key(key, textures)
        if value == "__not_found__":
            res[key] = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        else:
            res[key] = load_texture(value, ctx, vanilla)
    return res


def load_texture(path: str, ctx: Context, vanilla: Vanilla) -> Image.Image:
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
