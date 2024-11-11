from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any, Self
from beet import Context, LATEST_MINECRAFT_VERSION
from model_resolver.utils import ModelResolverOptions
import json


class Item(BaseModel):
    id: str
    count: int = 1
    components: dict[str, Any] = Field(default_factory=dict)

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
            self.components = {
                **components[self.id.removeprefix("minecraft:")],
                **self.components,
            }
        self.__resolved__ = True
        return self
