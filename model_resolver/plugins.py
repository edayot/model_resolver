import json
from beet import Context, LATEST_MINECRAFT_VERSION
from model_resolver import Render
from model_resolver.item_model.item import Item
from model_resolver.utils import ModelResolverOptions, get_default_components, resolve_key


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
    components = get_default_components(ctx)
    render = Render(ctx)
    for item in components:
        namespace, path = resolve_key(item).split(":")
        render.add_item_task(
            Item(id=f"{namespace}:{path}"), path_ctx=f"{namespace}:render/items/{path}"
        )
    render.run()
