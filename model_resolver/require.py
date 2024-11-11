

from beet import Context, Model, NamespaceFileScope, JsonFile
from typing import ClassVar, Type
from model_resolver.utils import MinecraftModelNullable, MinecraftModel, DisplayModel, resolve_key
from model_resolver.vanilla import Vanilla

class ModelResolveNamespace(Model):

    def resolve(self, ctx: Context, vanilla: "Vanilla") -> MinecraftModel:
        internal = self.resolve_internal(ctx, vanilla)
        if internal.ambientocclusion is None:
            internal.ambientocclusion = True
        if internal.gui_light is None:
            internal.gui_light = "side"
        return MinecraftModel.model_validate(internal, from_attributes=True)

    def resolve_internal(self, ctx: Context, vanilla: "Vanilla") -> MinecraftModelNullable:
        if not "parent" in self.data:
            return MinecraftModelNullable.model_validate(self.data)
        parent_key = resolve_key(self.data["parent"])
        if parent_key in [
            "minecraft:builtin/generated",
            "minecraft:builtin/entity",
        ]:
            return MinecraftModelNullable.model_validate(self.data)
        if parent_key in ctx.assets[ModelResolveNamespace]:
            parent = ctx.assets[ModelResolveNamespace][parent_key]
        elif parent_key in vanilla.assets[ModelResolveNamespace]:
            parent = vanilla.assets[ModelResolveNamespace][parent_key]
        else:
            raise ValueError(f"{parent_key} not in Context or Vanilla")
        resolved_parent = parent.resolve_internal(ctx, vanilla)
        return self.merge_parent(resolved_parent)

        
    def merge_parent(self, parent: "MinecraftModelNullable") -> MinecraftModelNullable:
        child = MinecraftModel.model_validate(self.data)
        return MinecraftModelNullable(
            ambientocclusion=parent.ambientocclusion if parent.ambientocclusion is not None else child.ambientocclusion,
            display=DisplayModel(**{**parent.display.model_dump(), **child.display.model_dump()}),
            textures={**parent.textures, **child.textures},
            elements=child.elements or parent.elements,
            gui_light=parent.gui_light if parent.gui_light is not None else child.gui_light,
            parent=parent.parent,
        )

class ItemModelNamespace(JsonFile):
    """Class representing a model."""

    scope: ClassVar[NamespaceFileScope] = ("items",)
    extension: ClassVar[str] = ".json"
         

def beet_default(ctx: Context):
    ctx.assets.extend_namespace.extend([ModelResolveNamespace, ItemModelNamespace])







