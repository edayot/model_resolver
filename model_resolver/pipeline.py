from beet import Context
from model_resolver.require import ModelResolveNamespace, ItemModelNamespace
from model_resolver.vanilla import Vanilla
from model_resolver.item_model.model import ItemModel
from model_resolver.item_model.item import Item





def beet_default(ctx: Context):
    vanilla = Vanilla(ctx, extend_namespace=([],[ModelResolveNamespace, ItemModelNamespace]))
    
    test = {
  "model": {
    "type": "minecraft:condition",
    "on_false": {
      "type": "minecraft:select",
      "cases": [
        {
          "model": {
            "type": "minecraft:model",
            "model": "minecraft:item/crossbow_arrow"
          },
          "when": "arrow"
        },
        {
          "model": {
            "type": "minecraft:model",
            "model": "minecraft:item/crossbow_firework"
          },
          "when": "rocket"
        }
      ],
      "fallback": {
        "type": "minecraft:model",
        "model": "minecraft:item/crossbow"
      },
      "property": "minecraft:charge_type"
    },
    "on_true": {
      "type": "minecraft:range_dispatch",
      "entries": [
        {
          "model": {
            "type": "minecraft:model",
            "model": "minecraft:item/crossbow_pulling_1"
          },
          "threshold": 0.58
        },
        {
          "model": {
            "type": "minecraft:model",
            "model": "minecraft:item/crossbow_pulling_2"
          },
          "threshold": 1.0
        }
      ],
      "fallback": {
        "type": "minecraft:model",
        "model": "minecraft:item/crossbow_pulling_0"
      },
      "property": "minecraft:crossbow/pull"
    },
    "property": "minecraft:using_item"
  }
}
    
    model = ItemModel.model_validate(test)
    models = model.resolve(ctx, vanilla, Item(id="minecraft:crossbow").fill(ctx))
    print(list(models))


