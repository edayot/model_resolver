from beet import Context, Model, Texture
from beet.contrib.vanilla import Vanilla
from rich import print
from model_resolver.render import Render
from copy import deepcopy
from typing import TypedDict
from PIL import Image



def beet_default(ctx: Context):
    # resolve dynamic textures
    resove_atlases(ctx)
    vanilla_models = ctx.inject(Vanilla).assets.models
    models = {}
    for model in ctx.assets.models:
        resolved_model = resolve_model(ctx.assets.models[model], vanilla_models)
        if not "textures" in resolved_model.data:
            continue
        models[model] = resolved_model.data
    
    Render(models, ctx, ctx.inject(Vanilla)).render()
        
def render_vanilla(ctx: Context):
    vanilla_models = ctx.inject(Vanilla).assets.models

    models = set()
    for model in vanilla_models.match("minecraft:item/*"):
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



def resove_atlases(ctx: Context):
    vanilla = ctx.inject(Vanilla)
    for atlas in ctx.assets.atlases:
        resolve_atlas(ctx, vanilla, ctx, atlas)
    for atlas in vanilla.assets.atlases:
        resolve_atlas(ctx, vanilla, vanilla, atlas)


def resolve_atlas(ctx: Context, vanilla: Vanilla, used_ctx: Context | Vanilla, atlas: str):
    for source in used_ctx.assets.atlases[atlas].data["sources"]:
        if source["type"] != "paletted_permutations":
            continue
        source : Atlas
        for texture in source["textures"]:
            for variant, color_palette in source["permutations"].items():
                new_texture_path = f"{texture}_{variant}"
                new_texture_path = resolve_key(new_texture_path)

                palette_key = resolve_key(source["palette_key"])
                if palette_key in ctx.assets.textures:
                    palette = ctx.assets.textures[palette_key].image
                elif palette_key in vanilla.assets.textures:
                    palette = vanilla.assets.textures[palette_key].image
                
                color_palette_key = resolve_key(color_palette)
                if color_palette_key in ctx.assets.textures:
                    color_palette = ctx.assets.textures[color_palette_key].image # color palette
                elif color_palette_key in vanilla.assets.textures:
                    color_palette = vanilla.assets.textures[color_palette_key].image # color palette
                
                grayscale_key = resolve_key(texture)
                if grayscale_key in ctx.assets.textures:
                    grayscale = ctx.assets.textures[grayscale_key].image
                elif grayscale_key in vanilla.assets.textures:
                    grayscale = vanilla.assets.textures[grayscale_key].image
                
                new_texture = apply_palette(grayscale, palette, color_palette)

                ctx.assets.textures[new_texture_path] = Texture(new_texture)
                    

def apply_palette(texture: Image.Image, palette: Image.Image, color_palette: Image.Image) -> Image.Image:
    new_image = Image.new("RGBA", texture.size)
    texture = texture.convert("RGBA")
    palette = palette.convert("RGB")
    color_palette = color_palette.convert("RGB")
    for x in range(texture.width):
        for y in range(texture.height):
            pixel = texture.getpixel((x, y))
            color = pixel[:3]
            alpha = pixel[3]
            # if the color is in palette_key, replace it with the color from color_palette
            found = False
            for i in range(palette.width):
                for j in range(palette.height):
                    if palette.getpixel((i, j)) == color:
                        new_color = color_palette.getpixel((i, j))
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
        merged["textures"] = {} if "textures" not in merged else merged["textures"]
        merged["textures"].update(child.data["textures"])
    if "elements" in child.data:
        merged["elements"] = child.data["elements"]
    if "display" in child.data:
        for key in child.data["display"].keys():
            merged["display"][key] = child.data["display"][key]
    if "ambientocclusion" in child.data:
        merged["ambientocclusion"] = child.data["ambientocclusion"]
    if "overrides" in child.data:
        merged["overrides"] = child.data["overrides"]
    if "gui_light" in child.data:
        merged["gui_light"] = child.data["gui_light"]

    return Model(merged)

def resolve_model(model : Model, vanilla_models : dict[str, Model]) -> Model:
    # Do something with the model
    if "parent" in model.data:
        resolved_key = resolve_key(model.data["parent"])
        if resolved_key in [
            "minecraft:builtin/generated",
            "minecraft:builtin/entity",
        ]:
            return model
        parent_model = vanilla_models[resolved_key]
        parent_model = deepcopy(parent_model)
        parent_model_resolved = resolve_model(parent_model, vanilla_models)

        return merge_model(model, parent_model_resolved)
    else:
        return model
