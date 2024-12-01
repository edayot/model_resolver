from beet import Context
from model_resolver import Render


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
    for model in render.vanilla.assets.models:
        namespace, path = model.split(":")
        render.add_model_task(
            model,
            path_ctx=f"{namespace}:render/{path}",
        )
    render.run()
