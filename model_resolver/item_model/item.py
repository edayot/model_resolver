from pydantic import BaseModel, Field
from typing import Any, Self
from beet import Context, LATEST_MINECRAFT_VERSION
from model_resolver.utils import ModelResolverOptions, resolve_key
from model_resolver.vanilla import Vanilla
import json
from copy import deepcopy



class Item(BaseModel):
    id: str
    count: int = 1
    components_from_user: dict[str, Any] = Field(default_factory=dict, alias="components")
    default_components: dict[str, Any] = Field(default_factory=dict)

    __resolved__: bool = False

    def fill(self, ctx: Context) -> Self:
        if self.__resolved__:
            return self
        opts = ctx.validate("model_resolver", ModelResolverOptions)
        version = (
            opts.minecraft_version
            if opts.minecraft_version != "latest"
            else LATEST_MINECRAFT_VERSION
        )
        url = f"https://raw.githubusercontent.com/misode/mcmeta/refs/tags/{version}-summary/item_components/data.json"
        path = ctx.cache["model_resolver"].download(url)
        with open(path) as file:
            components = json.load(file)
        if self.id.removeprefix("minecraft:") in components:
            self.default_components = components[self.id.removeprefix("minecraft:")]
        self.__resolved__ = True
        return self
    
    @property
    def components(self) -> dict[str, Any]:
        return {**self.default_components, **self.components_from_user}
