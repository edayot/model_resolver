from beet import Context
from model_resolver.item_model.item import Item
from model_resolver.render import Render
from pathlib import Path
import json





def beet_default(ctx: Context):
    render = Render(ctx)
    current_path = Path(__file__).parent

    apple = Item(id="minecraft:apple")
    stone = Item(id="minecraft:stone")
    grass_block = Item(id="minecraft:grass_block")
    with open(current_path / "components.json", "r") as f:
        components = json.load(f)
    super_big_item = Item(id="minecraft:diamond", components=components)

    render.add_item_task(apple, save_path_ctx="test:apple")
    render.add_item_task(stone, save_path_ctx="test:stone")
    render.add_item_task(grass_block, save_path_ctx="test:grass_block")
    render.add_item_task(super_big_item, save_path_ctx="test:super_big_item")

    render.run()