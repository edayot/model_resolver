from beet import Context
from model_resolver.require import ModelResolveNamespace, ItemModelNamespace
from model_resolver.vanilla import Vanilla






def beet_default(ctx: Context):
    vanilla = Vanilla(ctx, extend_namespace=([],[ModelResolveNamespace, ItemModelNamespace]))
    for model in set(ctx.assets[ModelResolveNamespace].values()):
        model.resolve(ctx, vanilla)
    
