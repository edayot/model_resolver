import json
from beet import Context, LATEST_MINECRAFT_VERSION
from model_resolver import Render
from model_resolver.item_model.item import Item
from model_resolver.utils import ModelResolverOptions, resolve_key


def render_all_context(ctx: Context):
    render = Render(ctx)
    for model in ctx.assets.models:
        namespace, path = model.split(":")
        render.add_model_task(
            model,
            path_ctx=f"{namespace}:render/{path}",
        )
    render.run()


def render_all_vanilla(ctx: Context):
    render = Render(ctx)
    for model in render.getter._vanilla.assets.models:
        namespace, path = model.split(":")
        render.add_model_task(
            model,
            path_ctx=f"{namespace}:render/{path}",
        )
    render.run()


def render_all_items(ctx: Context):
    opts = ctx.validate("model_resolver", ModelResolverOptions)
    version = (
        opts.minecraft_version
        if opts.minecraft_version != "latest"
        else LATEST_MINECRAFT_VERSION
    )
    url = f"https://raw.githubusercontent.com/misode/mcmeta/refs/tags/{version}-summary/item_components/data.json"
    path = ctx.cache["model_resolver"].download(url)
    render = Render(ctx)
    with open(path) as file:
        components = json.load(file)
    for item in components:
        namespace, path = resolve_key(item).split(":")
        render.add_item_task(
            Item(id=f"{namespace}:{path}"), path_ctx=f"{namespace}:render/items/{path}"
        )
    render.run()
