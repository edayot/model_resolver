from dataclasses import dataclass, field
import json
import os
import pathlib
import subprocess
from beet import ContainerProxy, Context, DataPack, Namespace, NamespaceContainer, NamespaceFile, NamespaceProxy, NamespaceProxyDescriptor, Pack, ResourcePack, Texture
from pydantic import BaseModel
from typing import TYPE_CHECKING, Any, Literal, Self, Type, overload
from beet import Context, LATEST_MINECRAFT_VERSION
from functools import cached_property, lru_cache

from pydantic import BaseModel
import logging

from beet.contrib.vanilla import Vanilla, Release

from model_resolver.pack_getter import PackGetter

log = logging.getLogger("model_resolver")

DEFAULT_RENDER_SIZE = 256


def resolve_key(key: str) -> str:
    return f"minecraft:{key}" if ":" not in key else key


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison


def clamp[T: (SupportsRichComparison)](minimum: T, x: T, maximum: T) -> T:
    return max(minimum, min(x, maximum))


class LightOptions(BaseModel):
    """Light options."""

    minecraft_light_power: float = 0.6727302277118515
    minecraft_ambient_light: float = 0.197261163686041
    minecraft_light_position: list[float] = [
        -0.42341569107908505,
        -0.6577205642540358,
        0.4158725999762756,
        0.0,
    ]


class ModelResolverOptions(BaseModel):
    """Model resolver options."""

    use_cache: bool = True
    special_rendering: bool = False
    colorize_blocks: bool = True
    preferred_minecraft_generated: Literal["misode/mcmeta", "java"] = "misode/mcmeta"




@lru_cache
def get_default_components(ctx: Context) -> dict[str, Any]:
    opts = ctx.validate("model_resolver", ModelResolverOptions)
    getter = PackGetter.from_ctx(ctx)
    version = ctx.minecraft_version
    prefered = opts.preferred_minecraft_generated
    # TODO: if java is not found, fallback to misode/mcmeta
    if prefered == "java":
        # test if java is available
        try:
            subprocess.run(
                ["java", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            log.warning("Java not found, falling back to misode/mcmeta")
            prefered = "misode/mcmeta"
    match prefered:
        case "misode/mcmeta":
            url = f"https://raw.githubusercontent.com/misode/mcmeta/refs/tags/{version}-summary/item_components/data.json"
            path = ctx.cache["model_resolver_components"].download(url)
            with open(path) as file:
                components = json.load(file)
            return {resolve_key(key): value for key, value in components.items()}
        case "java":
            release = getter.release
            jar = release.cache.download(
                release.info.data["downloads"]["server"]["url"]
            )
            cache = ctx.cache["model_resolver_components"]
            path = cache.get_path("minecraft_reports")
            if not path.is_dir():
                os.makedirs(path, exist_ok=True)
                subprocess.run(
                    [
                        "java",
                        "-DbundlerMainClass=net.minecraft.data.Main",
                        "-jar",
                        jar,
                        "--reports",
                    ],
                    cwd=path,
                    check=True,
                )
            items_json = path / "generated" / "reports" / "items.json"
            if items_json.exists():
                with open(items_json) as file:
                    components = json.load(file)
                return {
                    resolve_key(key): value["components"]
                    for key, value in components.items()
                }
            # examples/load_vanilla/.beet_cache/model_resolver_components/0x0/generated/reports/minecraft/components/item
            components = {}
            for item in (path / "generated" / "reports" / "minecraft" / "components" / "item").glob("*.json"):
                with open(item) as file:
                    components[resolve_key(item.name.removesuffix(".json"))] = json.load(file)["components"]
            return components
        case _:
            raise ValueError(f"Unknown preferred_minecraft_generated: {prefered}")
