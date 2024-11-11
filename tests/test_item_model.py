

from model_resolver.item_model.item import Item
from model_resolver.item_model.model import ItemModel
from pathlib import Path
import json
from beet import run_beet, Context, ProjectConfig, PackConfig, PackLoadOptions
from model_resolver.vanilla import Vanilla
from model_resolver.require import ItemModelNamespace, ModelResolveNamespace



def test_item_model():
    path = Path(__file__).parent / "test_item_model"
    with open(path / "components.json", "r") as f:
        components = json.load(f)
    item = Item(id="minecraft:diamond", components=components)

    with run_beet(
        directory=path,
    ) as ctx: 
        
        last = None
        for item_model in ctx.assets[ItemModelNamespace].values():
            last = ItemModel.model_validate(item_model.data)
        assert last
        vanilla = Vanilla(ctx, extend_namespace=([],[ModelResolveNamespace, ItemModelNamespace]))
        print(list(last.resolve(ctx, vanilla, item)))

    
    
if __name__ == "__main__":
    test_item_model()