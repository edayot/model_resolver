from beet import Context
from model_resolver.item_model.item import Item
from model_resolver.render import Render




def beet_default(ctx: Context):
    render = Render(ctx)

    item = Item(
        id="minecraft:player_head",
        components={
            "minecraft:profile": "AirDox_"
        }
    )
    render.add_item_task(item, path_ctx="test:head", render_size=512)


    render.run()