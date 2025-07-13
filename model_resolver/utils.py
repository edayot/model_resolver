from dataclasses import dataclass
import json
import os
import pathlib
import subprocess
from beet import Context, DataPack, Pack, ResourcePack
from pydantic import BaseModel
from typing import TYPE_CHECKING, Any, Literal, Self
from beet import Context, LATEST_MINECRAFT_VERSION
from functools import lru_cache

from pydantic import BaseModel
import logging

from beet.contrib.vanilla import Vanilla

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

    use_cache: bool = False
    minecraft_version: str = "latest"
    special_rendering: bool = False
    colorize_blocks: bool = True
    preferred_minecraft_generated: Literal["misode/mcmeta", "java"] = "misode/mcmeta"
    transparent_missingno: bool = True


@dataclass
class PackGetterV2[T: Pack]:
    assets: ResourcePack
    data: DataPack
    opts: ModelResolverOptions
    _ctx: Context
    _vanilla: Vanilla

    @classmethod
    def from_context(cls, ctx: Context) -> Self:
        opts = ctx.validate("model_resolver", ModelResolverOptions)
        vanilla = Vanilla(
            ctx,
            minecraft_version=(
                opts.minecraft_version
                if opts.minecraft_version != "latest"
                else LATEST_MINECRAFT_VERSION
            ),
        )

        assets = ResourcePack()
        assets.merge(vanilla.assets)
        if opts.special_rendering:
            static_models = pathlib.Path(__file__).parent / "static_models"
            rp = ResourcePack(str(static_models))
            assets.merge(rp)

        assets.merge(ctx.assets)

        data = DataPack()
        data.merge(vanilla.data)
        data.merge(ctx.data)

        return cls(assets=assets, data=data, _ctx=ctx, _vanilla=vanilla, opts=opts)


@lru_cache
def get_default_components(ctx: Context) -> dict[str, Any]:
    getter = PackGetterV2.from_context(ctx)
    version = getter._vanilla.minecraft_version
    opts = ctx.validate("model_resolver", ModelResolverOptions)
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
            release = getter._vanilla.releases[version]
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
            with open(path / "generated" / "reports" / "items.json") as file:
                components = json.load(file)
            return {
                resolve_key(key): value["components"]
                for key, value in components.items()
            }
        case _:
            raise ValueError(f"Unknown preferred_minecraft_generated: {prefered}")
