from beet import Context
from model_resolver.item_model.item import Item
from model_resolver.render import Render
from pathlib import Path
import json





def beet_default(ctx: Context):
    render = Render(ctx)
    current_path = Path(__file__).parent

    apple = Item(id="minecraft:apple")
    iron_boots = Item(id="minecraft:iron_boots", components={
        "minecraft:trim": {
            "material": "minecraft:redstone",
        }
    })
    stone = Item(id="minecraft:stone")
    grass_block = Item(id="minecraft:grass_block")
    with open(current_path / "components.json", "r") as f:
        components = json.load(f)
    super_big_item = Item(id="minecraft:diamond", components=components)

    render.add_item_task(apple, path_ctx="test:apple")
    render.add_item_task(iron_boots, path_ctx="test:iron_boots")
    # render.add_item_task(stone, path_ctx="test:stone")
    # render.add_item_task(grass_block, path_ctx="test:grass_block")
    # render.add_item_task(super_big_item, path_ctx="test:super_big_item")

    render.run()