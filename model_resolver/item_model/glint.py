"""The enchantment glint: which items have one and how each kind of model draws it."""

from dataclasses import dataclass
from typing import Optional

from model_resolver.item_model.item import Item

MODEL_ATLASES = "model"
"""The atlas of item model sprites: items, else blocks (MaterialBaker)."""


@dataclass(frozen=True)
class GlintStyle:
    """How a model draws the enchantment glint: the scale of its TextureTransform and the
    atlas its texture coordinates are in (None for a texture of its own)."""

    scale: float
    atlas: Optional[str] = None


ITEM_GLINT = GlintStyle(8.0, MODEL_ATLASES)
"""TextureTransform.GLINT_TEXTURING, for item models."""
ENTITY_GLINT_SCALE = 0.5
"""The scale of TextureTransform.ENTITY_GLINT_TEXTURING, for special models."""


def has_foil(item: Item) -> bool:
    """ItemStack.hasFoil: enchantment_glint_override, else being enchanted."""
    components = item.components
    override = components.get("minecraft:enchantment_glint_override")
    if override is not None:
        return bool(override)
    enchantments = components.get("minecraft:enchantments") or {}
    if isinstance(enchantments, dict) and isinstance(enchantments.get("levels"), dict):
        enchantments = enchantments["levels"]
    return len(enchantments) > 0
