from dataclasses import dataclass
from beet import Context, DataPack, Pack, NamespaceFile, ResourcePack
from pydantic import BaseModel
from typing import TYPE_CHECKING, Any, Self, Type
from collections.abc import MappingView
from beet import Context, LATEST_MINECRAFT_VERSION

from pydantic import BaseModel
import logging

from beet.contrib.vanilla import Vanilla

log = logging.getLogger(__name__)

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


@dataclass
class PackGetterV2[T: Pack]:
    assets: ResourcePack
    data: DataPack
    _ctx: Context
    _vanilla: Vanilla

    @classmethod
    def from_context(cls, ctx: Context) -> Self:
        opts = ctx.validate("model_resolver", ModelResolverOptions)
        vanilla = Vanilla(
            ctx,
            minecraft_version=opts.minecraft_version if opts.minecraft_version != "latest" else LATEST_MINECRAFT_VERSION,
        )
        assets = ResourcePack()
        assets.merge(vanilla.assets)
        assets.merge(ctx.assets)

        data = DataPack()
        data.merge(vanilla.data)
        data.merge(ctx.data)

        return cls(assets=assets, data=data, _ctx=ctx, _vanilla=vanilla)
