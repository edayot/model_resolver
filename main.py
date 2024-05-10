from beet import Context, Model
from beet.contrib.vanilla import Vanilla
from rich import print
from render import Render
from renderv2 import render_model
from copy import deepcopy
import json


ALREADY_RENDERED = False


def beet_default(ctx: Context):
    global ALREADY_RENDERED
    if ALREADY_RENDERED:
        raise Exception("Already rendered, this is a known issue with PyOpenGL.")
    ALREADY_RENDERED = True
    vanilla_models = ctx.inject(Vanilla).assets.models

    ctx.assets.models["debug:block/test_fence_2"] = vanilla_models["minecraft:item/acacia_fence"]
    ctx.assets.models["debug:block/glass"] = vanilla_models["minecraft:item/glass"]



    # models = {}
    # for model in ctx.assets.models:
    #     resolved_model = resolve_model(ctx.assets.models[model], vanilla_models)
    #     models[model] = resolved_model.data
    
    # Render(models, ctx, ctx.inject(Vanilla)).render()

    for model in ctx.assets.models:
        resolved_model = resolve_model(ctx.assets.models[model], vanilla_models)
        render_model(resolved_model.data, ctx, ctx.inject(Vanilla))
        


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
        parent_model = vanilla_models[resolve_key(model.data["parent"])]
        parent_model = deepcopy(parent_model)
        parent_model_resolved = resolve_model(parent_model, vanilla_models)

        return merge_model(model, parent_model_resolved)
    else:
        return model
