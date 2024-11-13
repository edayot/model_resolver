from beet import Context
from model_resolver.item_model.item import Item
from model_resolver.render import Render
from pathlib import Path
import json
import requests





def beet_default(ctx: Context):
    render = Render(ctx)
    current_path = Path(__file__).parent

    r = requests.get('https://raw.githubusercontent.com/misode/mcmeta/refs/heads/registries/item/data.json')
    data = r.json()
    for id in data:
        item = Item(id=id)
        render.add_item_task(item, path_ctx=f"test:{id}")

    render.run()