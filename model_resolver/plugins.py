from beet import Context
from model_resolver import Render
from model_resolver.item_model.item import Item
from model_resolver.utils import get_default_components, resolve_key


def render_all_context(ctx: Context):
    render_all_context_option(ctx, False)


def render_all_context_webp(ctx: Context):
    render_all_context_option(ctx, True)


def render_all_context_option(ctx: Context, animated_as_webp: bool = True):
    render = Render(ctx)
    for model in ctx.assets.models:
        namespace, path = model.split(":")
        render.add_model_task(
            model,
            path_ctx=f"{namespace}:render/{path}",
            animation_mode="webp" if animated_as_webp else "multi_files",
        )
    render.run()


def render_all_vanilla(ctx: Context):
    render_all_vanilla_option(ctx, False)


def render_all_vanilla_webp(ctx: Context):
    render_all_vanilla_option(ctx, True)


def render_all_vanilla_option(ctx: Context, animated_as_webp: bool = True):
    render = Render(ctx)
    for model in render.getter._vanilla.assets.models:
        namespace, path = model.split(":")
        render.add_model_task(
            model,
            path_ctx=f"{namespace}:render/{path}",
            animation_mode="webp" if animated_as_webp else "multi_files",
        )
    render.run()


def render_all_items(ctx: Context):
    render_all_items_option(ctx, False)


def render_all_items_webp(ctx: Context):
    render_all_items_option(ctx, True)


def render_all_items_option(ctx: Context, animated_as_webp: bool = True):
    components = get_default_components(ctx)
    render = Render(ctx)
    for item in components:
        namespace, path = resolve_key(item).split(":")
        render.add_item_task(
            Item(id=f"{namespace}:{path}"),
            path_ctx=f"{namespace}:render/items/{path}",
            animation_mode="webp" if animated_as_webp else "multi_files",
        )
    render.run()
