from beet import Context
from model_resolver.item_model.item import Item
from model_resolver.render import Render
from model_resolver.vanilla import Vanilla
from model_resolver.minecraft_model import ItemModelNamespace
from pathlib import Path
import json
import requests





def beet_default(ctx: Context):
    render = Render(ctx)

    for key in render.vanilla.assets[ItemModelNamespace].keys():
        item = Item(id=key)
        path = key.split(":")
        path = f"{path[0]}:render/items/{path[1]}"
        render.add_item_task(item, path_ctx=path)
        
    
    for key in render.vanilla.assets.models.keys():
        path = key.split(":")
        path = f"{path[0]}:render/{path[1]}"
        render.add_model_task(key, path_ctx=path)


    render.run()