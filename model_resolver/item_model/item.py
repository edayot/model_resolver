from pydantic import BaseModel, Field, PrivateAttr
from typing import Any, Optional, Self
from beet import Context
from model_resolver.utils import get_default_components, resolve_key


class Item(BaseModel):
    id: str
    count: int = 1
    components_from_user: dict[str, Any] = Field(
        default_factory=dict, alias="components"
    )
    default_components: dict[str, Any] = Field(default_factory=dict)
    display_context: str = "gui"
    """The ItemDisplayContext it is drawn in: gui, fixed, ground, head, thirdperson_righthand..."""
    owner: Optional[str] = "minecraft:player"
    """Entity type of the living entity holding it, None when there is none (item_display)."""

    __resolved__: bool = False
    _defaults_table: Optional[dict[str, dict[str, Any]]] = PrivateAttr(default=None)

    def fill(self, ctx: Context) -> Self:
        if self.__resolved__:
            return self
        return self.fill_from(get_default_components(ctx))

    def fill_from(self, table: dict[str, dict[str, Any]]) -> Self:
        """Take the default components from a table of every item's defaults."""
        self._defaults_table = table
        real_id = resolve_key(self.id)
        if real_id in table:
            self.default_components = table[real_id]
        self.__resolved__ = True
        return self

    @property
    def patch(self) -> dict[str, Any]:
        """The user components as a DataComponentPatch, namespaced and without no-op entries.

        A removed component (`!id`) maps to REMOVED. Like PatchedDataComponentMap,
        a value equal to the default and a removal of an absent component are dropped.
        """
        defaults = self.defaults
        patch: dict[str, Any] = {}
        for key, value in self.components_from_user.items():
            if key.startswith("!"):
                key = resolve_key(key[1:])
                if key in defaults:
                    patch[key] = REMOVED
                else:
                    patch.pop(key, None)
            else:
                key = resolve_key(key)
                if key in defaults and defaults[key] == value:
                    patch.pop(key, None)
                else:
                    patch[key] = value
        return patch

    @property
    def defaults(self) -> dict[str, Any]:
        return {resolve_key(key): value for key, value in self.default_components.items()}

    @property
    def components(self) -> dict[str, Any]:
        components = self.defaults
        for key, value in self.patch.items():
            if value is REMOVED:
                del components[key]
            else:
                components[key] = value
        return components

    def get(self, component_name: str) -> Any:
        return self.components.get(resolve_key(component_name))

    def has_non_default(self, component_name: str) -> bool:
        """ItemStack.hasNonDefault: the component is set to another value, or removed."""
        return resolve_key(component_name) in self.patch

    @property
    def max_stack_size(self) -> int:
        return self.components.get("minecraft:max_stack_size", 1)

    @property
    def is_damageable(self) -> bool:
        """ItemStack.isDamageableItem"""
        components = self.components
        return (
            "minecraft:max_damage" in components
            and "minecraft:damage" in components
            and "minecraft:unbreakable" not in components
        )

    @property
    def max_damage(self) -> int:
        return self.components.get("minecraft:max_damage", 0)

    @property
    def damage(self) -> int:
        """ItemStack.getDamageValue, clamped to [0, max_damage]"""
        return max(0, min(self.components.get("minecraft:damage", 0), self.max_damage))

    def nested(self, template: Any) -> "Item":
        """An item stack stored in a component (ItemStackTemplate: an id, or {id, count, components}).

        It gets its defaults from the same table as this item.
        """
        if isinstance(template, str):
            template = {"id": template}
        item = Item(
            id=template["id"],
            count=template.get("count", 1),
            components=template.get("components", {}),
        )
        if self._defaults_table is not None:
            return item.fill_from(self._defaults_table)
        item.__resolved__ = True
        return item


class _Removed:
    def __repr__(self) -> str:
        return "REMOVED"


REMOVED: Any = _Removed()
