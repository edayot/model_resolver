"""Data component predicates, the `predicate` and `value` of a `minecraft:component` condition.

Mirrors net.minecraft.core.component.predicates: each predicate reads one component and
fails when the item doesn't have it. A `predicate` that is not one of the predicate types
is a component id, and only checks that the component is present (AnyValue).
"""

from dataclasses import dataclass
from typing import Any, ClassVar, Generator, Literal, Optional, Union

import numpy as np
from beet import NamespaceProxy, TagFile
from nbtlib import Byte, ByteArray, Compound, Double, List, String, parse_nbt
from nbtlib.tag import Base as NbtTag
from pydantic import BaseModel, Field, RootModel, model_validator

from model_resolver.item_model.item import Item
from model_resolver.item_model.tint_source import potion_effects
from model_resolver.pack_getter import PackGetter
from model_resolver.utils import log, namespaced, resolve_key


@dataclass
class Context:
    getter: PackGetter
    item: Item
    """The item whose components are tested, nested items are built from it."""


class Bounds(BaseModel):
    """MinMaxBounds: a number for an exact match, or {min, max} where both are optional."""

    min: Optional[float] = None
    max: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def exactly(cls, data: Any) -> Any:
        if isinstance(data, (int, float)):
            return {"min": data, "max": data}
        return data

    def matches(self, value: float) -> bool:
        if self.min is not None and value < self.min:
            return False
        return self.max is None or value <= self.max


ANY = Bounds()


type HolderSet = Union[str, list[Union[str, dict[str, Any]]]]


def iter_tagged_id(
    value: Union[HolderSet, dict[str, Any], None], proxy: NamespaceProxy[Any] | None = None
) -> Generator[str, None, None]:
    """
    A generator that yields all the ids in a holder set: an id, a #tag or a list of ids.
    Tags are resolved with the provided proxy, their entries can be {id, required}.
    """
    if isinstance(value, dict):
        # tag entry {"id": ..., "required": false}
        try:
            yield from iter_tagged_id(value["id"], proxy)
        except ValueError:
            if value.get("required", True):
                raise
    elif isinstance(value, str):
        if value.startswith("#"):
            if proxy is None:
                raise ValueError(f"There is no {value} tag in minecraft")
            tag = proxy.get(resolve_key(value[1:]))
            if tag is None:
                raise ValueError(f"Tag {value} not found")
            if not isinstance(tag, TagFile):
                raise TypeError(f"Invalid tag type {tag}")
            for item in tag.data["values"]:
                yield from iter_tagged_id(item, proxy)
        else:
            yield resolve_key(value)
    elif isinstance(value, list):
        for item in value:
            yield from iter_tagged_id(item, proxy)
    elif value is None:
        ...
    else:
        raise TypeError(f"Invalid tagged id type {value}")


def holder_set_contains(
    holder_set: Optional[HolderSet], value: Any, ctx: Context, registry: str
) -> bool:
    """Whether a registry id is in the holder set. An inline value never is."""
    if not isinstance(value, str):
        return False
    proxy = getattr(ctx.getter.data, f"{registry}_tags", None) if _has_tag(holder_set) else None
    return resolve_key(value) in iter_tagged_id(holder_set, proxy)


def _has_tag(holder_set: Any) -> bool:
    if isinstance(holder_set, str):
        return holder_set.startswith("#")
    return isinstance(holder_set, list) and any(_has_tag(x) for x in holder_set)


class ElementPredicate(BaseModel):
    def test(self, value: Any, ctx: Context) -> bool:
        raise NotImplementedError


class CountEntry[P: ElementPredicate](BaseModel):
    test: P
    count: Bounds


class CollectionPredicate[P: ElementPredicate](BaseModel):
    """CollectionPredicate: `contains` (each predicate matched by some element), `count`, `size`."""

    contains: Optional[list[P]] = None
    count: Optional[list[CountEntry[P]]] = None
    size: Optional[Bounds] = None

    def test(self, values: list[Any], ctx: Context) -> bool:
        if self.contains is not None:
            if not all(any(p.test(v, ctx) for v in values) for p in self.contains):
                return False
        if self.count is not None:
            for entry in self.count:
                if not entry.count.matches(sum(entry.test.test(v, ctx) for v in values)):
                    return False
        return self.size is None or self.size.matches(len(values))


class DataComponentPredicateBase(BaseModel):
    component: ClassVar[str]
    """The component the predicate reads, it fails when the item doesn't have it."""

    def matches(self, ctx: Context) -> bool:
        value = ctx.item.components.get(self.component)
        if value is None:
            return False
        return self.matches_value(value, ctx)

    def matches_value(self, value: Any, ctx: Context) -> bool:
        raise NotImplementedError


class AnyValuePredicate(DataComponentPredicateBase):
    """DataComponentPredicate.AnyValueType: any component id, checks that it is present."""

    id: str

    def matches(self, ctx: Context) -> bool:
        return resolve_key(self.id) in ctx.item.components


class DamagePredicate(DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:damage"
    durability: Bounds = ANY
    damage: Bounds = ANY

    def matches_value(self, value: Any, ctx: Context) -> bool:
        max_damage = ctx.item.components.get("minecraft:max_damage", 0)
        return self.durability.matches(max_damage - value) and self.damage.matches(value)


class EnchantmentPredicate(BaseModel):
    enchantments: Optional[HolderSet] = None
    levels: Bounds = ANY

    def contained_in(self, enchantments: dict[str, int], ctx: Context) -> bool:
        if self.enchantments is not None:
            return any(
                enchantments.get(key, 0) != 0 and self.levels.matches(enchantments[key])
                for key in iter_tagged_id(self.enchantments, self.tags(ctx))
            )
        # no enchantments field: any enchantment with a matching level
        return any(self.levels.matches(level) for level in enchantments.values())

    def tags(self, ctx: Context) -> Optional[NamespaceProxy[Any]]:
        return ctx.getter.data.enchantment_tags if _has_tag(self.enchantments) else None


class EnchantmentsPredicate(RootModel[list[EnchantmentPredicate]], DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:enchantments"
    root: list[EnchantmentPredicate]

    def matches_value(self, value: Any, ctx: Context) -> bool:
        if isinstance(value, dict) and isinstance(value.get("levels"), dict):
            # before 1.21.5: {levels, show_in_tooltip}
            value = value["levels"]
        enchantments = {resolve_key(key): level for key, level in value.items()}
        return all(predicate.contained_in(enchantments, ctx) for predicate in self.root)


class StoredEnchantmentsPredicate(EnchantmentsPredicate):
    component: ClassVar[str] = "minecraft:stored_enchantments"


class MobEffectInstancePredicate(BaseModel):
    amplifier: Bounds = ANY
    duration: Bounds = ANY
    ambient: Optional[bool] = None
    visible: Optional[bool] = None

    def matches(self, effect: dict[str, Any]) -> bool:
        if not self.amplifier.matches(effect.get("amplifier", 0)):
            return False
        if not self.duration.matches(effect.get("duration", 0)):
            return False
        if self.ambient is not None and self.ambient != effect.get("ambient", False):
            return False
        return self.visible is None or self.visible == effect.get("show_particles", True)


class MobEffectsPredicate(RootModel[dict[str, MobEffectInstancePredicate]], ElementPredicate):
    root: dict[str, MobEffectInstancePredicate]

    def test(self, value: Any, ctx: Context) -> bool:
        effects = {resolve_key(key): predicate for key, predicate in self.root.items()}
        predicate = effects.get(resolve_key(value["id"]))
        return predicate is not None and predicate.matches(value)


class PotionContentsPredicate(DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:potion_contents"
    potions: Optional[HolderSet] = None
    effects: Optional[CollectionPredicate[MobEffectsPredicate]] = None

    @model_validator(mode="before")
    @classmethod
    def legacy(cls, data: Any) -> Any:
        # before 26.1 the predicate was the holder set of potions alone
        if isinstance(data, (str, list)):
            return {"potions": data}
        return data

    def matches_value(self, value: Any, ctx: Context) -> bool:
        potion = value if isinstance(value, str) else value.get("potion")
        if self.potions is not None:
            if potion is None or not holder_set_contains(self.potions, potion, ctx, "potion"):
                return False
        if self.effects is not None:
            effects = potion_effects(value, ctx.getter.opts.minecraft_version)
            return self.effects.test(effects, ctx)
        return True


class JukeboxPlayablePredicate(DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:jukebox_playable"
    song: Optional[HolderSet] = None

    @model_validator(mode="before")
    @classmethod
    def legacy(cls, data: Any) -> Any:
        if isinstance(data, (str, list)):
            return {"song": data}
        return data

    def matches_value(self, value: Any, ctx: Context) -> bool:
        if isinstance(value, dict):
            value = value.get("song")
        return self.song is None or holder_set_contains(self.song, value, ctx, "jukebox_song")


class TrimPredicate(DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:trim"
    material: Optional[HolderSet] = None
    pattern: Optional[HolderSet] = None

    def matches_value(self, value: Any, ctx: Context) -> bool:
        if self.material is not None:
            if not holder_set_contains(self.material, value.get("material"), ctx, "trim_material"):
                return False
        if self.pattern is not None:
            if not holder_set_contains(self.pattern, value.get("pattern"), ctx, "trim_pattern"):
                return False
        return True


class VillagerVariantPredicate(RootModel[HolderSet], DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:villager/variant"
    root: HolderSet

    def matches_value(self, value: Any, ctx: Context) -> bool:
        return holder_set_contains(self.root, value, ctx, "villager_type")


class FireworkPredicate(ElementPredicate):
    shape: Optional[str] = None
    has_twinkle: Optional[bool] = None
    has_trail: Optional[bool] = None

    def test(self, value: Any, ctx: Context) -> bool:
        if self.shape is not None and self.shape != value.get("shape"):
            return False
        if self.has_twinkle is not None and self.has_twinkle != value.get("has_twinkle", False):
            return False
        return self.has_trail is None or self.has_trail == value.get("has_trail", False)


class FireworkExplosionPredicate(RootModel[FireworkPredicate], DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:firework_explosion"
    root: FireworkPredicate

    def matches_value(self, value: Any, ctx: Context) -> bool:
        return self.root.test(value, ctx)


class FireworksPredicate(DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:fireworks"
    explosions: Optional[CollectionPredicate[FireworkPredicate]] = None
    flight_duration: Bounds = ANY

    def matches_value(self, value: Any, ctx: Context) -> bool:
        if self.explosions is not None:
            if not self.explosions.test(value.get("explosions", []), ctx):
                return False
        return self.flight_duration.matches(value.get("flight_duration", 0))


def raw_text(value: Any) -> Any:
    # Filterable: a value, or {raw, filtered}
    if isinstance(value, dict) and "raw" in value:
        return value["raw"]
    return value


def text_component(value: Any) -> Any:
    # "text" and {"text": "text"} decode to the same component
    return {"text": value} if isinstance(value, str) else value


class WritablePagePredicate(RootModel[str], ElementPredicate):
    root: str

    def test(self, value: Any, ctx: Context) -> bool:
        return raw_text(value) == self.root


class WritableBookPredicate(DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:writable_book_content"
    pages: Optional[CollectionPredicate[WritablePagePredicate]] = None

    def matches_value(self, value: Any, ctx: Context) -> bool:
        return self.pages is None or self.pages.test(value.get("pages", []), ctx)


class WrittenPagePredicate(RootModel[Any], ElementPredicate):
    root: Any

    def test(self, value: Any, ctx: Context) -> bool:
        return text_component(raw_text(value)) == text_component(self.root)


class WrittenBookPredicate(DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:written_book_content"
    pages: Optional[CollectionPredicate[WrittenPagePredicate]] = None
    author: Optional[str] = None
    title: Optional[str] = None
    generation: Bounds = ANY
    resolved: Optional[bool] = None

    def matches_value(self, value: Any, ctx: Context) -> bool:
        if self.author is not None and self.author != value.get("author"):
            return False
        if self.title is not None and self.title != raw_text(value.get("title")):
            return False
        if not self.generation.matches(value.get("generation", 0)):
            return False
        if self.resolved is not None and self.resolved != value.get("resolved", False):
            return False
        return self.pages is None or self.pages.test(value.get("pages", []), ctx)


class AttributeModifierPredicate(ElementPredicate):
    attribute: Optional[HolderSet] = None
    id: Optional[str] = None
    amount: Bounds = ANY
    operation: Optional[Literal["add_value", "add_multiplied_base", "add_multiplied_total"]] = None
    slot: Optional[str] = None

    def test(self, value: Any, ctx: Context) -> bool:
        if self.attribute is not None:
            if not holder_set_contains(self.attribute, value.get("type"), ctx, "attribute"):
                return False
        if self.id is not None and resolve_key(self.id) != resolve_key(value.get("id", "")):
            return False
        if not self.amount.matches(value.get("amount", 0)):
            return False
        if self.operation is not None and self.operation != value.get("operation"):
            return False
        return self.slot is None or self.slot == value.get("slot", "any")


class AttributeModifiersPredicate(DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:attribute_modifiers"
    modifiers: Optional[CollectionPredicate[AttributeModifierPredicate]] = None

    def matches_value(self, value: Any, ctx: Context) -> bool:
        if isinstance(value, dict):
            # before 1.21.5: {modifiers, show_in_tooltip}
            value = value.get("modifiers", [])
        return self.modifiers is None or self.modifiers.test(value, ctx)


class ItemPredicate(ElementPredicate):
    """ItemPredicate: items, count, exact components and component predicates."""

    items: Optional[HolderSet] = None
    count: Bounds = ANY
    components: Optional[dict[str, Any]] = None
    predicates: Optional[dict[str, Any]] = None

    def test(self, value: Any, ctx: Context) -> bool:
        item: Item = value
        if self.items is not None:
            proxy = ctx.getter.data.item_tags if _has_tag(self.items) else None
            if resolve_key(item.id) not in iter_tagged_id(self.items, proxy):
                return False
        if not self.count.matches(item.count):
            return False
        components = item.components
        for key, expected in (self.components or {}).items():
            # DataComponentExactPredicate: the decoded values are equal
            if namespaced(expected) != namespaced(components.get(resolve_key(key))):
                return False
        nested = Context(ctx.getter, item)
        return all(
            component_predicate(key, predicate).matches(nested)
            for key, predicate in (self.predicates or {}).items()
        )


class ContainerPredicate(DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:container"
    items: Optional[CollectionPredicate[ItemPredicate]] = None

    def contents(self, value: Any, ctx: Context) -> list[Item]:
        # ItemContainerContents.nonEmptyItems, the slots are {slot, item}
        return [ctx.item.nested(slot["item"]) for slot in value]

    def matches_value(self, value: Any, ctx: Context) -> bool:
        return self.items is None or self.items.test(self.contents(value, ctx), ctx)


class BundleContentsPredicate(ContainerPredicate):
    component: ClassVar[str] = "minecraft:bundle_contents"

    def contents(self, value: Any, ctx: Context) -> list[Item]:
        # BundleContents is a plain list of item stacks
        return [ctx.item.nested(stack) for stack in value]


def to_nbt(value: Any) -> Optional[NbtTag]:
    """A component value as NBT: SNBT strings are parsed, JSON values converted like
    Dynamic.convert(NbtOps) does, where every number becomes a double."""
    if isinstance(value, NbtTag):
        return value
    if isinstance(value, bool):
        return Byte(value)
    if isinstance(value, (int, float)):
        return Double(value)
    if isinstance(value, str):
        return String(value)
    if isinstance(value, dict):
        return Compound({key: to_nbt(x) for key, x in value.items()})
    if isinstance(value, list):
        tags = [to_nbt(x) for x in value]
        if tags and all(isinstance(x, Byte) for x in tags):
            # NbtOps collects a list of bytes into a byte array
            return ByteArray(tags)
        return List(tags)
    return None


def compare_nbt(expected: Optional[NbtTag], actual: Optional[NbtTag]) -> bool:
    """NbtUtils.compareNbt(expected, actual, partialListMatches=true)"""
    if expected is None:
        return True
    if actual is None:
        return False
    if isinstance(expected, Compound):
        if not isinstance(actual, Compound) or len(actual) < len(expected):
            return False
        return all(compare_nbt(x, actual.get(key)) for key, x in expected.items())
    if isinstance(expected, List):
        # every expected element matches some actual element, [] only matches []
        if not isinstance(actual, List):
            return False
        if len(expected) == 0:
            return len(actual) == 0
        if len(actual) < len(expected):
            return False
        return all(any(compare_nbt(x, y) for y in actual) for x in expected)
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, np.ndarray):
        return bool(np.array_equal(expected, np.asarray(actual)))
    return expected == actual


class CustomDataPredicate(RootModel[Union[dict[str, Any], str]], DataComponentPredicateBase):
    component: ClassVar[str] = "minecraft:custom_data"
    root: Union[dict[str, Any], str]

    def matches(self, ctx: Context) -> bool:
        # NbtPredicate: an item without custom_data compares as {}
        actual = ctx.item.components.get(self.component, {})
        return self.matches_value(actual, ctx)

    def matches_value(self, value: Any, ctx: Context) -> bool:
        expected = parse_nbt(self.root) if isinstance(self.root, str) else to_nbt(self.root)
        actual = parse_nbt(value) if isinstance(value, str) else to_nbt(value)
        return compare_nbt(expected, actual)


PREDICATES: dict[str, type[DataComponentPredicateBase]] = {
    "minecraft:attribute_modifiers": AttributeModifiersPredicate,
    "minecraft:bundle_contents": BundleContentsPredicate,
    "minecraft:container": ContainerPredicate,
    "minecraft:custom_data": CustomDataPredicate,
    "minecraft:damage": DamagePredicate,
    "minecraft:enchantments": EnchantmentsPredicate,
    "minecraft:firework_explosion": FireworkExplosionPredicate,
    "minecraft:fireworks": FireworksPredicate,
    "minecraft:jukebox_playable": JukeboxPlayablePredicate,
    "minecraft:potion_contents": PotionContentsPredicate,
    "minecraft:stored_enchantments": StoredEnchantmentsPredicate,
    "minecraft:trim": TrimPredicate,
    "minecraft:villager/variant": VillagerVariantPredicate,
    "minecraft:writable_book_content": WritableBookPredicate,
    "minecraft:written_book_content": WrittenBookPredicate,
}
"""DataComponentPredicates in 26.3"""


def component_predicate(predicate: str, value: Any) -> DataComponentPredicateBase:
    """Parse the predicate `value` of the given type, any other id is a component presence check."""
    cls = PREDICATES.get(resolve_key(predicate))
    if cls is None:
        if value not in ({}, None):
            log.warning(f"Component {predicate} has no predicate type, only its presence is checked")
        return AnyValuePredicate(id=predicate)
    return cls.model_validate(value)


class DataComponent(BaseModel):
    """Component predicates by id, all of which must match (DataComponentMatchers.predicates)."""

    predicates: dict[str, Any] = Field(default_factory=dict)

    def is_valid(self, getter: PackGetter, item: Item) -> bool:
        ctx = Context(getter, item)
        return all(
            component_predicate(key, value).matches(ctx) for key, value in self.predicates.items()
        )
