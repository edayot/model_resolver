from pydantic import BaseModel
from typing import TYPE_CHECKING

from pydantic import BaseModel

DEFAULT_RENDER_SIZE = 128


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
