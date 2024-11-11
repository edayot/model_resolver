from beet import Context
from model_resolver.require import ModelResolveNamespace, ItemModelNamespace
from model_resolver.vanilla import Vanilla
from model_resolver.item_model.model import ItemModel
from model_resolver.item_model.item import Item





def beet_default(ctx: Context):
    vanilla = Vanilla(ctx, extend_namespace=([],[ModelResolveNamespace, ItemModelNamespace]))
    
    
    for key, item_model in ctx.assets[ItemModelNamespace].items():
        print(key)
