from beet import Context
from model_resolver import Item, Render




def beet_default(ctx: Context):
    render = Render(ctx)

    item = Item(
        id="minecraft:player_head",
        components={
            "minecraft:profile": "AirDox_"
        }
    )
    # render.add_item_task(item, path_ctx="test:head", render_size=512)

    # render.add_item_task(Item(id="minecraft:chest"), path_ctx="test:chest", render_size=512)

    # render.add_item_task(Item(id="minecraft:creeper_head"), path_ctx="test:creeper_head", render_size=512)
    # render.add_item_task(Item(id="minecraft:zombie_head"), path_ctx="test:zombie_head", render_size=512)





    render.add_item_task(Item(id="minecraft:diamond", components={
        "minecraft:item_model": "test:skeleton"
    }), path_ctx="test:render/skeleton", render_size=512)
    render.add_item_task(Item(id="minecraft:diamond", components={
        "minecraft:item_model": "test:piglin"
    }), path_ctx="test:render/piglin", render_size=512)
    render.add_item_task(Item(id="minecraft:diamond", components={
        "minecraft:item_model": "test:dragon"
    }), path_ctx="test:render/dragon", render_size=512)
    render.add_item_task(Item(id="minecraft:diamond", components={
        "minecraft:item_model": "test:dragon_scales"
    }), path_ctx="test:render/dragon_scales", render_size=512)
    render.add_item_task(Item(id="minecraft:grass", components={
        "minecraft:item_model": "freerot:diamond"
    }), path_ctx="test:render/model_resolver", render_size=512)
    render.add_item_task(Item(id="minecraft:sculk_sensor", ), 
        path_ctx="test:render/sculk_sensor", render_size=512)
    # render.add_item_task(Item(id="minecraft:diamond", components={
    #     "minecraft:item_model": "test:zombie"
    # }), path_ctx="test:render/zombie", render_size=512)
    # render.add_item_task(Item(id="minecraft:diamond"), path_ctx="test:render/diamond", render_size=512)



    render.run()