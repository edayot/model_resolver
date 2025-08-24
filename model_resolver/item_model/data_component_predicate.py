from typing import Any, ClassVar, Generator, Literal, Union, Optional
from beet import NamespaceFile, NamespaceProxy, TagFile
from pydantic import AliasChoices, Field, RootModel, BaseModel
from nbtlib import parse_nbt, Compound

from model_resolver.item_model.item import Item
from model_resolver.utils import PackGetterV2, resolve_key
from rich import print  # noqa


class MinMax(BaseModel):
    min: float
    max: float


type NumberOrRange = Union[int, MinMax, None]
type TaggedID = str | list[str] | None


def compare_range(predicate: NumberOrRange, value: Any) -> bool:
    if isinstance(predicate, int):
        return predicate == value
    if isinstance(predicate, MinMax):
        return predicate.min <= value <= predicate.max
    return False


def iter_tagged_id[
    T: NamespaceFile
](value: TaggedID, proxy: NamespaceProxy[T] | None = None) -> Generator[
    str, None, None
]:
    """
    A generator that yields all the ids in a tagged id.
    If # prefixed value is encountered, it will resolve the tag
    according to the provided proxy (optional).
    """
    if isinstance(value, str):
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


class DataComponentBase(BaseModel):

    def is_valid(self, getter: PackGetterV2, item: Item) -> bool | None:
        return False


class AttributeModifier(BaseModel):
    attribute: TaggedID = None
    id: Optional[str] = None
    amount: NumberOrRange = None
    operation: Literal[
        "add_value", "add_multiplied_base", "add_multiplied_total", None
    ] = None
    slot: Literal[
        "mainhand",
        "offhand",
        "head",
        "chest",
        "legs",
        "feet",
        "hand",
        "armor",
        "any",
        "body",
        "saddle",
        None,
    ] = None


class CountAttributeModifier(BaseModel):
    count: NumberOrRange = None
    test: AttributeModifier | None = None


class Modifier(BaseModel):
    contains: Optional[list[AttributeModifier]] = None
    size: NumberOrRange = None
    count: list[CountAttributeModifier] | None = None


class AttributeModifiersDataComponent(DataComponentBase):
    modifiers: Optional[Modifier] = None


class ItemCondition(BaseModel):
    items: TaggedID = None
    count: NumberOrRange = None
    components: dict[str, Any] | None = None
    predicates: Union["DataComponent", None] = None


class CountItem(DataComponentBase):
    count: NumberOrRange = None
    test: ItemCondition


class PredicateCollection(DataComponentBase):
    contains: Optional[list[ItemCondition]] = None
    size: NumberOrRange = None
    count: list[CountItem] | None = None


class InventoryLikeDataComponent(DataComponentBase):
    inventory_component: ClassVar[str]
    items: Optional[PredicateCollection] = None

    def verify_item_condition(
        self, getter: PackGetterV2, item_condition: ItemCondition, container: list[Item]
    ) -> int:
        """
        Checks the number of times an item condition is met in the container.
        """
        res = 0
        for item in container:
            if item_condition.items is not None:
                if resolve_key(item.id) not in iter_tagged_id(
                    item_condition.items, getter.data.item_tags
                ):
                    continue
            if item_condition.count is not None:
                if not compare_range(item_condition.count, item.count):
                    continue
            if item_condition.components is not None:
                if item_condition.components != item.get("components"):
                    continue
            if item_condition.predicates is not None:
                if not item_condition.predicates.is_valid(getter, item):
                    continue
            res += 1
        return res

    def is_valid(self, getter: PackGetterV2, item: Item) -> bool:
        container: list[Item] = [
            Item.model_validate(x["item"]) for x in item.get(self.inventory_component)
        ]
        if self.items is None:
            return False
        if self.items.size is not None:
            if not compare_range(self.items.size, len(container)):
                return False
        if self.items.contains is not None:
            for item_condition in self.items.contains:
                if self.verify_item_condition(getter, item_condition, container) == 0:
                    return False
        if self.items.count is not None:
            for test_count in self.items.count:
                nb_valid = self.verify_item_condition(
                    getter, test_count.test, container
                )
                if not compare_range(test_count.count, nb_valid):
                    return False
        return True


class BundleContentsDataComponent(InventoryLikeDataComponent):
    inventory_component: ClassVar[str] = "bundle_contents"


class ContainerDataComponent(InventoryLikeDataComponent):
    inventory_component: ClassVar[str] = "container"


class CustomDataDataComponent(RootModel, DataComponentBase):
    root: dict[str, Any] | str

    def verify_equal(
        self, predicate: dict[str, Any] | list[dict[str, Any]] | int | str, value: Any
    ) -> bool:
        if isinstance(predicate, dict):
            if not isinstance(value, dict):
                return False
            for key, val in predicate.items():
                if key not in value:
                    return False
                if not self.verify_equal(val, value[key]):
                    return False
            return True
        if isinstance(predicate, list):
            if not isinstance(value, list):
                return False
            for val in predicate:
                if not val in value:
                    return False
            return True
        return predicate == value

    def is_valid(self, getter: PackGetterV2, item: Item):
        custom_data = item.get("custom_data")
        if custom_data is None:
            return False
        if not isinstance(custom_data, dict):
            return False
        if isinstance(self.root, str):
            nbt: Compound = parse_nbt(self.root)
            a = self.verify_equal(nbt, custom_data)
            return a
        return self.verify_equal(self.root, custom_data)


class DamageDataComponent(DataComponentBase):
    damage: NumberOrRange = None
    durability: NumberOrRange = None

    def is_valid(self, getter: PackGetterV2, item: Item):
        damage = item.get("damage")
        max_damage = item.get("max_damage")
        if max_damage is None:
            return False
        if damage is None:
            damage = 0
        durability = max_damage - damage
        return compare_range(self.durability, durability) and compare_range(
            self.damage, damage
        )


class Enchantment(BaseModel):
    enchantments: TaggedID = None
    levels: NumberOrRange = None

    def is_valid(self, enchantments: dict[str, int], getter: PackGetterV2) -> bool:
        enchantments = {resolve_key(key): value for key, value in enchantments.items()}
        for enchantment in iter_tagged_id(
            self.enchantments, getter.data.enchantment_tags
        ):
            if enchantment not in enchantments:
                continue
            if compare_range(self.levels, enchantments[enchantment]):
                return True
        return False


class EnchantmentsLikeDataComponent(RootModel, DataComponentBase):
    root: list[Enchantment] | None = None

    def is_valid_enchantments(
        self, getter: PackGetterV2, item: Item, component_name: str
    ) -> bool:
        enchantments: dict[str, int] | None = item.get(component_name)
        if enchantments is None:
            return False
        if self.root is None or enchantments is None:
            return False
        if len(self.root) > len(enchantments):
            return False
        for predicate_enchantment in self.root:
            if not predicate_enchantment.is_valid(enchantments, getter):
                return False
        return True


class EnchantmentsDataComponent(EnchantmentsLikeDataComponent):
    def is_valid(self, getter: PackGetterV2, item: Item) -> bool:
        return self.is_valid_enchantments(getter, item, "enchantments")


class FireworkExplosionDataComponent(DataComponentBase): ...


class FireworksDataComponent(DataComponentBase): ...


class JukeboxPlayableDataComponent(RootModel, DataComponentBase):
    root: TaggedID = None

    def is_valid(self, getter: PackGetterV2, item: Item) -> bool:
        jukebox_playable = item.get("jukebox_playable")
        if jukebox_playable is None:
            return False
        for sound in iter_tagged_id(self.root):
            if resolve_key(sound) == resolve_key(jukebox_playable):
                return True
        return False


class PotionContentsDataComponent(DataComponentBase):
    root: TaggedID = None

    def is_valid(self, getter: PackGetterV2, item: Item) -> bool:
        potion = item.get("potion_contents")
        if potion is None:
            return False
        potion_type = potion.get("potion")
        if potion_type is None:
            return False
        potion_type = resolve_key(potion_type)
        for predicate_potion_type in iter_tagged_id(self.root):
            if potion_type == predicate_potion_type:
                return True
        return False


class StoredEnchantmentsDataComponent(EnchantmentsLikeDataComponent):
    def is_valid(self, getter: PackGetterV2, item: Item) -> bool:
        return self.is_valid_enchantments(getter, item, "stored_enchantments")


class TrimDataComponent(DataComponentBase):
    material: TaggedID = None
    pattern: TaggedID = None

    def is_valid(self, getter: PackGetterV2, item: Item) -> bool:
        trim = item.get("trim")
        if trim is None:
            return False
        if self.material is not None:
            material = trim.get("material")
            if material is None:
                return False
            material = resolve_key(material)
            if not any(
                material == predicate_material
                for predicate_material in iter_tagged_id(self.material)
            ):
                return False
        if self.pattern is not None:
            pattern = trim.get("pattern")
            if pattern is None:
                return False
            pattern = resolve_key(pattern)
            if not any(
                pattern == predicate_pattern
                for predicate_pattern in iter_tagged_id(self.pattern)
            ):
                return False
        return True


class WritableBookContentDataComponent(DataComponentBase): ...


class WrittenBookContentDataComponent(DataComponentBase): ...


class DataComponent(BaseModel):
    attibute_modifiers: Optional[AttributeModifiersDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices(
            "attribute_modifiers", "minecraft:attribute_modifiers"
        ),
    )
    bundle_contents: Optional[BundleContentsDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("bundle_contents", "minecraft:bundle_contents"),
    )
    container: Optional[ContainerDataComponent] = Field(
        default=None, validation_alias=AliasChoices("container", "minecraft:container")
    )
    custom_data: Optional[CustomDataDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("custom_data", "minecraft:custom_data"),
    )
    damage: Optional[DamageDataComponent] = Field(
        default=None, validation_alias=AliasChoices("damage", "minecraft:damage")
    )
    enchantments: Optional[EnchantmentsDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("enchantments", "minecraft:enchantments"),
    )
    firework_explosion: Optional[FireworkExplosionDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices(
            "firework_explosion", "minecraft:firework_explosion"
        ),
    )
    fireworks: Optional[FireworksDataComponent] = Field(
        default=None, validation_alias=AliasChoices("fireworks", "minecraft:fireworks")
    )
    jukebox_playable: Optional[JukeboxPlayableDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("jukebox_playable", "minecraft:jukebox_playable"),
    )
    potion_contents: Optional[PotionContentsDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("potion_contents", "minecraft:potion_contents"),
    )
    stored_enchantments: Optional[StoredEnchantmentsDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices(
            "stored_enchantments", "minecraft:stored_enchantments"
        ),
    )
    trim: Optional[TrimDataComponent] = Field(
        default=None, validation_alias=AliasChoices("trim", "minecraft:trim")
    )
    writable_book_content: Optional[WritableBookContentDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices(
            "writable_book_content", "minecraft:writable_book_content"
        ),
    )

    def is_valid(self, getter: PackGetterV2, item: Item) -> bool:
        valid = []
        components: list[Optional[DataComponentBase]] = [
            self.attibute_modifiers,
            self.bundle_contents,
            self.container,
            self.custom_data,
            self.damage,
            self.enchantments,
            self.firework_explosion,
            self.fireworks,
            self.jukebox_playable,
            self.potion_contents,
            self.stored_enchantments,
            self.trim,
            self.writable_book_content,
        ]

        for component in components:
            if component is None:
                continue
            valid.append(component.is_valid(getter, item))
        return all(valid)
