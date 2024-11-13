from PIL import Image
from beet import Context
from pydantic import BaseModel, Field
from typing import Optional

from pydantic import BaseModel, Field
from typing import Annotated, Literal, Optional
from beet import Context


def resolve_key(key: str) -> str:
    return f"minecraft:{key}" if ":" not in key else key

import typing
if typing.TYPE_CHECKING:
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

    load_vanilla: bool = False
    resolve_vanilla_atlas: bool = False
    use_cache: bool = False
    render_size: int = 256
    minecraft_version: str = "latest"
    filter: Optional[list[str]] = []
    special_filter: dict[str, str] = Field(default_factory=dict)
    light: LightOptions = LightOptions()
    save_namespace: Optional[str] = None
    extra_block_entity_models: bool = False
    colorize_blocks: bool = False
    disable_missing_texture_error: bool = False
    experimental_render_structure: bool = False


