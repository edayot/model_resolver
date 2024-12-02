from dataclasses import dataclass
from beet import Pack, NamespaceFile
from pydantic import BaseModel
from typing import TYPE_CHECKING, Any, Type
from collections.abc import MappingView

from pydantic import BaseModel
import logging

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
class PackGetter[T: Pack]:
    vanilla_pack: T
    ctx_pack: T
    extra_packs: list[T]

    def get[Return: NamespaceFile](self, namespace: Type[Return], key: str) -> Return | None:
        key = resolve_key(key)
        for pack in [self.vanilla_pack, self.ctx_pack, *self.extra_packs]:
            if key in pack[namespace]:
                return pack[namespace][key]
        return None
    
    def __getitem__[Return: NamespaceFile](self, args: tuple[Type[Return], str]) -> Return | None:
        if not isinstance(args, tuple):
            raise TypeError("Must provide a tuple of (namespace, key)")
        if len(args) != 2:
            raise ValueError("Must provide a tuple of (namespace, key)")
        return self.get(namespace=args[0], key=args[1])
    
    




