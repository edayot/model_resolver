


from typing import Any, Generator, Literal, Type, Union, Protocol
from git import Optional
from pydantic import AliasChoices, Field, RootModel, BaseModel

from model_resolver.item_model.item import Item
from model_resolver.utils import PackGetterV2, resolve_key

class DataComponentBase(BaseModel):
    def is_valid(self, getter: PackGetterV2, item: Item) -> bool | None: 
        return False
    
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

class AttributeModifier(BaseModel):
    attribute: TaggedID = None
    id: Optional[str] = None
    amount: NumberOrRange = None
    operation: Literal[
        "add_value", 
        "add_multiplied_base", 
        "add_multiplied_total", 
        None
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
        None
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
    test: ItemCondition | None = None

class InventoryLikeDataComponent(DataComponentBase):
    contains: Optional[list[ItemCondition]] = None
    size: NumberOrRange = None
    count: CountItem | None = None

class BundleContentsDataComponent(InventoryLikeDataComponent):
    ...

class ContainerDataComponent(InventoryLikeDataComponent):
    ...

class CustomDataDataComponent(RootModel, DataComponentBase):
    root: dict[str, Any]

    def is_valid(self, getter: PackGetterV2, item: Item):
        none_obj = object()
        custom_data = item.components.get(
            "minecraft:custom_data", 
            item.components.get("custom_data", none_obj)
        )
        if custom_data is none_obj:
            return False
        if not isinstance(custom_data, dict): 
            return False
        for key, val in self.root.items():
            if key not in custom_data:
                return False
            if val != custom_data[key]:
                return False
        return True

class DamageDataComponent(DataComponentBase):
    damage: NumberOrRange = None
    durability: NumberOrRange = None

    def is_valid(self, getter: PackGetterV2, item: Item):
        none_obj = object()
        damage = item.components.get(
            "minecraft:damage", 
            item.components.get("damage", none_obj)
        )
        max_damage = item.components.get(
            "minecraft:max_damage", 
            item.components.get("max_damage", none_obj)
        )
        if damage is none_obj or max_damage is none_obj:
            return False
        durability = max_damage - damage
        return compare_range(self.durability, durability) and compare_range(self.damage, damage)
    

class Enchantment(BaseModel):
    enchantments: TaggedID = None
    levels: NumberOrRange = None

    def iter_enchantments_tags(self, value: str, getter: PackGetterV2) -> Generator[str, None, None]:
        tag = getter.data.enchantment_tags.get(resolve_key(value))
        if tag is None:
            raise ValueError(f"Enchantment tag {tag} not found")
        for enchantment in tag.data["values"]:
            if enchantment.startswith("#"):
                yield from self.iter_enchantments_tags(enchantment[1:], getter)
            else:
                yield enchantment
    def iter_enchantments(self, getter: PackGetterV2) -> Generator[str, None, None]:
        if isinstance(self.enchantments, str):
            if self.enchantments.startswith("#"):
                yield from self.iter_enchantments_tags(self.enchantments[1:], getter)
            else:
                yield self.enchantments
        elif isinstance(self.enchantments, list):
            for value in self.enchantments:
                if value.startswith("#"):
                    yield from self.iter_enchantments_tags(value[1:], getter)
                else:
                    yield value
        elif self.enchantments is None:
            ...
        else:
            raise TypeError(f"Invalid enchantments type {self.enchantments}")

    def is_valid(self, enchantments: dict[str, int], getter: PackGetterV2) -> bool:
        for enchantment in self.iter_enchantments(getter):
            if enchantment not in enchantments:
                continue
            if compare_range(self.levels, enchantments[enchantment]):
                return True
        return False
        
class EnchantmentsLikeDataComponent(RootModel, DataComponentBase):
    root: list[Enchantment] | None = None

    def is_valid_enchantments(self, getter: PackGetterV2, item: Item, enchantments: dict[str, int] | None) -> bool:
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
        none_obj = object()
        enchantments: dict[str, int] = item.components.get(
            "minecraft:enchantments", 
            item.components.get("enchantments", none_obj)
        )
        if enchantments is none_obj:
            return False
        return self.is_valid_enchantments(getter, item, enchantments)
        


class FireworkExplosionDataComponent(DataComponentBase):
    ...

class FireworksDataComponent(DataComponentBase):
    ...

class JukeboxPlayableDataComponent(DataComponentBase):
    ...

class PotionContentsDataComponent(DataComponentBase):
    ...

class StoredEnchantmentsDataComponent(EnchantmentsLikeDataComponent):
    def is_valid(self, getter: PackGetterV2, item: Item) -> bool:
        none_obj = object()
        enchantments: dict[str, int] = item.components.get(
            "minecraft:stored_enchantments", 
            item.components.get("stored_enchantments", none_obj)
        )
        if enchantments is none_obj:
            return False
        return self.is_valid_enchantments(getter, item, enchantments)

class TrimDataComponent(DataComponentBase):
    ...

class WritableBookContentDataComponent(DataComponentBase):
    ...

class WrittenBookContentDataComponent(DataComponentBase):
    ...


class DataComponent(BaseModel):
    attibute_modifiers: Optional[AttributeModifiersDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("attribute_modifiers", "minecraft:attribute_modifiers")
    )
    bundle_contents: Optional[BundleContentsDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("bundle_contents", "minecraft:bundle_contents")
    )
    container: Optional[ContainerDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("container", "minecraft:container")
    )
    custom_data: Optional[CustomDataDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("custom_data", "minecraft:custom_data")
    )
    damage: Optional[DamageDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("damage", "minecraft:damage")
    )
    enchantments: Optional[EnchantmentsDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("enchantments", "minecraft:enchantments")
    )
    firework_explosion: Optional[FireworkExplosionDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("firework_explosion", "minecraft:firework_explosion")
    )
    fireworks: Optional[FireworksDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("fireworks", "minecraft:fireworks")
    )
    jukebox_playable: Optional[JukeboxPlayableDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("jukebox_playable", "minecraft:jukebox_playable")
    )
    potion_contents: Optional[PotionContentsDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("potion_contents", "minecraft:potion_contents")
    )
    stored_enchantments: Optional[StoredEnchantmentsDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("stored_enchantments", "minecraft:stored_enchantments")
    )
    trim: Optional[TrimDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("trim", "minecraft:trim")
    )
    writable_book_content: Optional[WritableBookContentDataComponent] = Field(
        default=None,
        validation_alias=AliasChoices("writable_book_content", "minecraft:writable_book_content")
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
            self.writable_book_content
        ]

        for component in components:
            if component is None:
                continue
            valid.append(component.is_valid(getter, item))
        return all(valid)

