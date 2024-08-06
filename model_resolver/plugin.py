from beet import Context, Model, Texture
from beet.contrib.vanilla import Vanilla, Release
from beet.core.cache import Cache
from beet import NamespaceProxy
from model_resolver.render import Render
from copy import deepcopy
from typing import TypedDict, Mapping
from PIL import Image
from model_resolver.utils import load_textures, ModelResolverOptions
import numpy as np
import hashlib
import logging
from rich import print

logger = logging.getLogger("model_resolver")


def beet_default(ctx: Context):
    opts = ctx.validate("model_resolver", ModelResolverOptions)

    filter = opts.filter
    __special_filter__ = opts.special_filter
    if __special_filter__ is not None and len(__special_filter__) > 0:
        filter = __special_filter__.keys()

    vanilla = ctx.inject(Vanilla)
    if not opts.minecraft_version == "latest":
        vanilla = vanilla.releases[opts.minecraft_version]
    else:
        vanilla = vanilla.releases[vanilla.minecraft_version]
    generated_models = set()
    generated_textures = set()

    for atlas in ctx.assets.atlases:
        resolve_atlas(ctx, vanilla, ctx, atlas, generated_textures)
    if opts.resolve_vanilla_atlas or opts.load_vanilla:
        for atlas in vanilla.assets.atlases:
            resolve_atlas(ctx, vanilla, vanilla, atlas, generated_textures)
    if opts.load_vanilla:
        render_vanilla(ctx, vanilla, generated_models)

    use_cache = opts.use_cache
    cache = ctx.cache["model_resolver"]
    if not "models" in cache.json:
        cache.json["models"] = {}
        cache.json["render_size"] = opts.render_size
        cache.json["minecraft_version"] = opts.minecraft_version
        use_cache = False
    if (
        not cache.json["render_size"] == opts.render_size
        or not cache.json["minecraft_version"] == opts.minecraft_version
    ):
        use_cache = False
        cache.json["render_size"] = opts.render_size
        cache.json["minecraft_version"] = opts.minecraft_version

    logger.info(f"Resolving models...")
    models = {}
    model_set = set(ctx.assets.models.keys())
    if filter is not None and len(filter) > 0:
        model_set = set(ctx.assets.models.match(*filter))
    for model in model_set:
        resolved_model = resolve_model(
            ctx.assets.models[model], vanilla.assets.models, ctx.assets.models
        )
        resolved_model = bake_model(
            resolved_model, ctx, vanilla, model, generated_textures
        )
        if not "textures" in resolved_model.data:
            continue
        if model in cache.json["models"] and use_cache:
            img = handle_cache(cache, model, resolved_model, ctx, vanilla)
            if img is not None:
                # load cached image in ctx
                model_name = model.split(":")
                texture_path = f"{model_name[0]}:render/{model_name[1]}"
                ctx.assets.textures[texture_path] = Texture(img)
                continue

        models[model] = resolved_model.data

    logger.info(f"Handling animations...")
    models = handle_animations(models, ctx, vanilla, generated_textures)

    if len(models) > 0:
        logger.info(f"Rendering models...")
        Render(models, ctx, vanilla, opts).render()

    logger.info(f"Cleaning up...")
    clean_generated(ctx, generated_textures, generated_models)


def handle_cache(cache: Cache, model, resolved_model, ctx, vanilla):
    model_hash = hashlib.sha256(str(resolved_model.data).encode()).hexdigest()
    cached_model_hash = cache.json["models"][model]["model"]
    if model_hash != cached_model_hash:
        return None

    textures = load_textures(resolved_model.data["textures"], ctx, vanilla)
    textures_hash = {}
    for key in resolved_model.data["textures"]:
        textures_hash[key] = hashlib.sha256(textures[key].tobytes()).hexdigest()
    cached_textures_hash = cache.json["models"][model]["textures"]
    if textures_hash != cached_textures_hash:
        return None

    # load cached image
    img_path = cache.get_path(f"{model}.png")
    img = Image.open(img_path)
    return img


def render_vanilla(ctx: Context, vanilla: Release, models: set[str]):
    vanilla_models = vanilla.assets.models

    for model in vanilla_models.match("minecraft:*"):
        if "parent" in vanilla_models[model].data:
            if vanilla_models[model].data["parent"] == "builtin/entity":
                continue
        if model not in ctx.assets.models:
            ctx.assets.models[model] = vanilla_models[model]
            models.add(model)


class Atlas(TypedDict):
    type: str
    textures: list[str]
    palette_key: str
    permutations: dict[str, str]


def clean_generated(
    ctx: Context, generated_textures: set[str], generated_models: set[str]
):
    for texture in generated_textures:
        if texture in ctx.assets.textures:
            del ctx.assets.textures[texture]
    for model in generated_models:
        if model in ctx.assets.models:
            del ctx.assets.models[model]


def resolve_atlas(
    ctx: Context,
    vanilla: Release,
    used_ctx: Context | Release,
    atlas: str,
    generated_textures: set[str],
):
    for source in used_ctx.assets.atlases[atlas].data["sources"]:
        if source["type"] != "paletted_permutations":
            continue
        source: Atlas
        for texture in source["textures"]:
            for variant, color_palette_path in source["permutations"].items():
                new_texture_path = f"{texture}_{variant}"
                new_texture_path = resolve_key(new_texture_path)

                palette_key = resolve_key(source["palette_key"])
                if palette_key in ctx.assets.textures:
                    palette = ctx.assets.textures[palette_key].image
                elif palette_key in vanilla.assets.textures:
                    palette = vanilla.assets.textures[palette_key].image

                color_palette_key = resolve_key(color_palette_path)
                if color_palette_key in ctx.assets.textures:
                    color_palette: Image.Image = ctx.assets.textures[
                        color_palette_key
                    ].image  # color palette
                elif color_palette_key in vanilla.assets.textures:
                    color_palette: Image.Image = vanilla.assets.textures[
                        color_palette_key
                    ].image  # color palette

                grayscale_key = resolve_key(texture)
                if grayscale_key in ctx.assets.textures:
                    grayscale = ctx.assets.textures[grayscale_key].image
                elif grayscale_key in vanilla.assets.textures:
                    grayscale = vanilla.assets.textures[grayscale_key].image

                new_texture = apply_palette(grayscale, palette, color_palette)

                ctx.assets.textures[new_texture_path] = Texture(new_texture)
                generated_textures.add(new_texture_path)


def apply_palette(
    texture: Image.Image, palette: Image.Image, color_palette: Image.Image
) -> Image.Image:
    new_image = Image.new("RGBA", texture.size)
    texture = texture.convert("RGBA")
    palette = palette.convert("RGB")
    color_palette = color_palette.convert("RGB")
    for x in range(texture.width):
        for y in range(texture.height):
            pixel = texture.getpixel((x, y))
            if not isinstance(pixel, tuple):
                raise ValueError("Texture is not RGBA")
            color = pixel[:3]
            alpha = pixel[3]
            # if the color is in palette_key, replace it with the color from color_palette
            found = False
            for i in range(palette.width):
                for j in range(palette.height):
                    if palette.getpixel((i, j)) == color:
                        new_color = color_palette.getpixel((i, j))
                        if not isinstance(new_color, tuple):
                            raise ValueError("Color palette is not RGB")
                        new_image.putpixel((x, y), new_color + (alpha,))
                        found = True
                        break
                if found:
                    break
            if not found:
                new_image.putpixel((x, y), pixel)
    return new_image


def resolve_key(key: str) -> str:
    return f"minecraft:{key}" if ":" not in key else key


def merge_model(child: Model, parent: Model) -> Model:
    merged = parent.data.copy()

    if "textures" in child.data:
        merged["textures"] = merged.get("textures", {})
        merged["textures"].update(child.data["textures"])
    if "elements" in child.data:
        merged["elements"] = child.data["elements"]
    if "display" in child.data:
        merged["display"] = merged.get("display", {})
        for key in child.data["display"].keys():
            merged["display"][key] = child.data["display"][key]
    if "ambientocclusion" in child.data:
        merged["ambientocclusion"] = child.data["ambientocclusion"]
    if "overrides" in child.data:
        merged["overrides"] = child.data["overrides"]
    if "gui_light" in child.data:
        merged["gui_light"] = child.data["gui_light"]

    return Model(merged)


def resolve_model(
    model: Model, vanilla_models: Mapping[str, Model], ctx_models: Mapping[str, Model]
) -> Model:
    # Do something with the model
    if "parent" in model.data:
        resolved_key = resolve_key(model.data["parent"])
        if resolved_key in [
            "minecraft:builtin/generated",
            "minecraft:builtin/entity",
        ]:
            return model
        if resolved_key in vanilla_models:
            parent_model = vanilla_models[resolved_key]
        elif resolved_key in ctx_models:
            parent_model = ctx_models[resolved_key]
        else:
            raise ValueError(f"Parent model {resolved_key} not found")
        parent_model = deepcopy(parent_model)
        parent_model_resolved = resolve_model(parent_model, vanilla_models, ctx_models)

        return merge_model(model, parent_model_resolved)
    else:
        return model


def bake_model(
    model: Model,
    ctx: Context,
    vanilla: Release,
    model_name: str,
    generated_textures: set[str],
):
    if "parent" in model.data:
        if model.data["parent"] in ["builtin/generated"]:
            if "textures" in model.data:
                textures = load_textures(model.data["textures"], ctx, vanilla)
                max = 0
                for key in textures.keys():
                    if not key.startswith("layer"):
                        continue
                    index = int(key[5:])
                    if index > max:
                        max = index
                img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
                for i in range(max + 1):
                    texture = textures.get(f"layer{i}")
                    if texture is None:
                        continue
                    img.paste(texture, (0, 0), texture)
                new_texture = f"debug:{model_name.replace(':', '/')}"
                ctx.assets.textures[new_texture] = Texture(img)
                generated_textures.add(new_texture)
                model.data["textures"] = {"layer": new_texture, "particle": new_texture}
                model.data["elements"] = [
                    {
                        "from": [0, 0, 0],
                        "to": [16, 16, 0],
                        "faces": {"north": {"uv": [0, 0, 16, 16], "texture": "#layer"}},
                    }
                ]
                model.data["display"] = model.data.get("display", {})
                model.data["display"]["gui"] = {"rotation": [180, 0, 180]}
    return model


def is_animated(texture_path: str, ctx: Context, vanilla: Release):
    texture_path = resolve_key(texture_path)
    if texture_path in ctx.assets.textures_mcmeta:
        return True
    if texture_path in vanilla.assets.textures_mcmeta:
        return True
    return False


def get_thing(path, ctx_proxy: NamespaceProxy, vanilla_proxy: NamespaceProxy):
    path = resolve_key(path)
    if path in ctx_proxy:
        return ctx_proxy[path]
    if path in vanilla_proxy:
        return vanilla_proxy[path]
    raise ValueError(f"Texture {path} not found in ctx or vanilla")


def handle_animations(
    models: dict[str, dict],
    ctx: Context,
    vanilla: Release,
    generated_textures: set[str],
):
    for model in set(models.keys()):
        if not "textures" in models[model]:
            continue
        textures = models[model]["textures"]
        if not any(
            [is_animated(textures[key], ctx, vanilla) for key in textures.keys()]
        ):
            continue
        frametimes = []
        animated_cache = {}
        for key, value in textures.items():
            if not is_animated(value, ctx, vanilla):
                continue
            texture = get_thing(value, ctx.assets.textures, vanilla.assets.textures)
            texture_mcmeta = get_thing(
                value, ctx.assets.textures_mcmeta, vanilla.assets.textures_mcmeta
            )
            frametime = texture_mcmeta.data["animation"].get("frametime", 1)

            img = texture.image
            # generate all possible frames for the animation
            width = img.width
            height = img.height
            frames = []
            for i in range(height // width):
                cropped = img.crop((0, i * width, width, (i + 1) * width))
                texture_temp_path = f"debug:{model.replace(':', '/')}/{key}/{i}"
                ctx.assets.textures[texture_temp_path] = Texture(cropped)
                generated_textures.add(texture_temp_path)
                frames.append(texture_temp_path)

            frametimes.append(frametime * len(frames))

            animated_cache[key] = {"frames": frames, "frametime": frametime}
        total_number_of_frames = np.lcm.reduce(frametimes)
        L = []
        for tick in range(total_number_of_frames):
            current_textures = {}
            for key, value in animated_cache.items():
                frametime = value[
                    "frametime"
                ]  # the number of ticks a frame is displayed
                frame_index = (tick // frametime) % len(value["frames"])
                frame = value["frames"][frame_index]
                current_textures[key] = frame
            L.append(current_textures)
        # group L into chunks where current_textures are the same
        # for each chunk, create a new model with the textures

        L_grouped = []
        for i in range(len(L)):
            if i == 0:
                L_grouped.append([L[i], 1])
                continue
            if L[i] == L[i - 1]:
                L_grouped[-1][1] += 1
            else:
                L_grouped.append([L[i], 1])
        for i, (current_textures, count) in enumerate(L_grouped):
            new_model_path = f"{model}/{i}_{count}"
            new_model = deepcopy(models[model])
            new_model["textures"].update(current_textures)
            models[new_model_path] = new_model
        del models[model]

    return models
