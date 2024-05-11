
from PIL import Image
from beet import Context
from beet.contrib.vanilla import Vanilla





def load_textures(
        textures: dict, ctx: Context, vanilla: Vanilla
    ) -> dict[str, Image.Image]:
        res = {}
        for key in textures.keys():
            value = get_real_key(key, textures)
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

def get_real_key(key: str, textures: dict):
    if textures[key][0] == "#":
        return get_real_key(textures[key][1:], textures)
    else:
        return textures[key]
