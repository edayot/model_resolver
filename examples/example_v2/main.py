from beet import Context
from model_resolver import Render



def beet_default(ctx: Context):
    render = Render(ctx)

    with render:
        render.add_item_task(
            Item(
                id="minecraft:diamond", components={"minecraft:item_model": "test:piglin"}
            ),
            path_ctx="test:render/piglin",
            render_size=512,
        )