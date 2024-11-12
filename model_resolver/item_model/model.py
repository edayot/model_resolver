from pydantic import BaseModel, Field
from model_resolver.item_model.tint_source import TintSource
from typing import Optional, Literal, ClassVar, Generator, Union
from beet import Context
from model_resolver.vanilla import Vanilla
from model_resolver.item_model.item import Item
from model_resolver.utils import clamp


class ItemModelBase(BaseModel):
    type: str

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelModel", None, None]:
        yield from []


class ItemModelModel(ItemModelBase):
    type: str = "minecraft:model"
    model: str
    tints: list[TintSource] = Field(default_factory=list)

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelModel", None, None]:
        yield self


class ItemModelComposite(ItemModelBase):
    type: str = "minecraft:composite"
    models: list["ItemModelAll"]

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelModel", None, None]:
        for model in self.models:
            yield from model.resolve(ctx, vanilla, item)


class ItemModelConditionBase(ItemModelBase):
    type: str = "minecraft:condition"
    property: Literal[
        "minecraft:using_item",
        "minecraft:broken",
        "minecraft:damaged",
        "minecraft:has_component",
        "minecraft:fishing_rod/cast",
        "minecraft:bundle/has_selected_item",
        "minecraft:xmas",
        "minecraft:selected",
        "minecraft:carried",
        "minecraft:shift_down",
        "minecraft:custom_model_data",
    ]
    on_true: "ItemModelAll"
    on_false: "ItemModelAll"

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        raise NotImplementedError

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelModel", None, None]:
        if self.resolve_condition(ctx, vanilla, item):
            yield from self.on_true.resolve(ctx, vanilla, item)
        else:
            yield from self.on_false.resolve(ctx, vanilla, item)


class ItemModelConditionUsingItem(ItemModelConditionBase):
    property: Literal["minecraft:using_item"]

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionBroken(ItemModelConditionBase):
    property: Literal["minecraft:broken"]

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        if not item.components:
            return False
        if not "minecraft:damage" in item.components:
            return False
        if not "minecraft:max_damage" in item.components:
            return False
        remaining = (
            item.components["minecraft:max_damage"]
            - item.components["minecraft:damage"]
        )
        return remaining <= 1


class ItemModelConditionDamaged(ItemModelConditionBase):
    property: Literal["minecraft:damaged"]

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        if not item.components:
            return False
        if not "minecraft:damage" in item.components:
            return False
        return item.components["minecraft:damage"] > 0


class ItemModelConditionHasComponent(ItemModelConditionBase):
    property: Literal["minecraft:has_component"]
    component: str

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        if not item.components:
            return False
        return self.component in item.components


class ItemModelConditionFishingRodCast(ItemModelConditionBase):
    property: Literal["minecraft:fishing_rod/cast"]

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionBundleHasSelectedItem(ItemModelConditionBase):
    property: Literal["minecraft:bundle/has_selected_item"]

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionXmas(ItemModelConditionBase):
    property: Literal["minecraft:xmas"]

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        # Possible to implement, but not implemented
        return False


class ItemModelConditionSelected(ItemModelConditionBase):
    property: Literal["minecraft:selected"]

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionCarried(ItemModelConditionBase):
    property: Literal["minecraft:carried"]

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionShiftDown(ItemModelConditionBase):
    property: Literal["minecraft:shift_down"]

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionCustomModelData(ItemModelConditionBase):
    property: Literal["minecraft:custom_model_data"]
    index: Optional[int] = 0

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        if not item.components:
            return False
        if not "minecraft:custom_model_data" in item.components:
            return False
        if not "flags" in item.components["minecraft:custom_model_data"]:
            return False
        index = self.index or 0
        if index >= len(item.components["minecraft:custom_model_data"]["flags"]):
            return False
        return item.components["minecraft:custom_model_data"]["flags"][index]


type ItemModelCondition = Union[
    ItemModelConditionUsingItem,
    ItemModelConditionBroken,
    ItemModelConditionDamaged,
    ItemModelConditionHasComponent,
    ItemModelConditionFishingRodCast,
    ItemModelConditionBundleHasSelectedItem,
    ItemModelConditionXmas,
    ItemModelConditionSelected,
    ItemModelConditionCarried,
    ItemModelConditionShiftDown,
    ItemModelConditionCustomModelData,
]


class SelectCase(BaseModel):
    when: str
    model: "ItemModelAll"


class ItemModelSelectBase(ItemModelBase):
    type: str = "minecraft:select"
    property: Literal[
        "minecraft:main_hand",
        "minecraft:charge_type",
        "minecraft:trim_material",
        "minecraft:block_state",
        "minecraft:display_context",
        "minecraft:custom_model_data",
    ]
    cases: list[SelectCase] = Field(default_factory=list)
    fallback: "ItemModelAll"
    possible_values: ClassVar[list[str]] = []

    def resolve_select(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> "ItemModelAll":
        # Not possible to implement
        return self.fallback

    def resolve_case(self, value: str) -> "ItemModelAll":
        for case in self.cases:
            if case.when == value:
                return case.model
        return self.fallback

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelModel", None, None]:
        yield from self.resolve_select(ctx, vanilla, item).resolve(ctx, vanilla, item)


class ItemModelSelectMainHand(ItemModelSelectBase):
    property: Literal["minecraft:main_hand"]
    possible_values: ClassVar[list[str]] = ["left", "right"]


class ItemModelSelectChargeType(ItemModelSelectBase):
    property: Literal["minecraft:charge_type"]
    possible_values: ClassVar[list[str]] = ["none", "rocket", "arrow"]

    def resolve_select(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> "ItemModelAll":
        if not item.components:
            return self.resolve_case("none")
        if not "minecraft:charge_type" in item.components:
            return self.resolve_case("none")
        items: list[Item] = item.components["minecraft:charge_type"]
        charge_type = "none"
        for item in items:
            if item.id == "minecraft:firework_rocket":
                charge_type = "rocket"
                break
        if charge_type == "none" and len(items) > 0:
            charge_type = "arrow"
        return self.resolve_case(charge_type)


class ItemModelSelectTrimMaterial(ItemModelSelectBase):
    property: Literal["minecraft:trim_material"]

    def resolve_select(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> "ItemModelAll":
        if not item.components:
            return self.fallback
        if not "minecraft:trim" in item.components:
            return self.fallback
        if not "material" in item.components["minecraft:trim"]:
            return self.fallback
        return self.resolve_case(item.components["minecraft:trim"]["material"])


class ItemModelSelectBlockState(ItemModelSelectBase):
    property: Literal["minecraft:block_state"]
    block_state_property: str

    def resolve_select(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> "ItemModelAll":
        if not item.components:
            return self.fallback
        if not "minecraft:block_state" in item.components:
            return self.fallback
        if not self.block_state_property in item.components["minecraft:block_state"]:
            return self.fallback
        return self.resolve_case(
            item.components["minecraft:block_state"][self.block_state_property]
        )


class ItemModelSelectDisplayContext(ItemModelSelectBase):
    property: Literal["minecraft:display_context"]
    possible_values: ClassVar[list[str]] = [
        "none",
        "thirdperson_lefthand",
        "thirdperson_righthand",
        "firstperson_lefthand",
        "firstperson_righthand",
        "gui",
        "head",
        "ground",
        "fixed",
    ]

    def resolve_select(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> "ItemModelAll":
        return self.resolve_case("gui")


class ItemModelSelectCustomModelData(ItemModelSelectBase):
    property: Literal["minecraft:custom_model_data"]
    index: Optional[int] = 0

    def resolve_select(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> "ItemModelAll":
        if not item.components:
            return self.fallback
        if not "minecraft:custom_model_data" in item.components:
            return self.fallback
        if not "strings" in item.components["minecraft:custom_model_data"]:
            return self.fallback
        index = self.index or 0
        if index >= len(item.components["minecraft:custom_model_data"]["strings"]):
            return self.fallback
        return self.resolve_case(
            item.components["minecraft:custom_model_data"]["strings"][index]
        )


type ItemModelSelect = Union[
    ItemModelSelectMainHand,
    ItemModelSelectChargeType,
    ItemModelSelectTrimMaterial,
    ItemModelSelectBlockState,
    ItemModelSelectDisplayContext,
    ItemModelSelectCustomModelData,
]


class RangeDispatchEntry(BaseModel):
    threshold: float
    model: "ItemModelAll"


class ItemModelRangeDispatchBase(ItemModelBase):
    type: str = "minecraft:range_dispatch"
    property: Literal[
        "minecraft:custom_model_data",
        "minecraft:bundle/fullness",
        "minecraft:damage",
        "minecraft:count",
        "minecraft:cooldown",
        "minecraft:time",
        "minecraft:compass",
        "minecraft:crossbow/pull",
        "minecraft:use_duration",
        "minecraft:use_cycle",
    ]
    scale: Optional[float] = 1.0
    entries: list[RangeDispatchEntry]
    fallback: "ItemModelAll"

    def resolve_range_dispatch(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> float:
        return 0.0

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelModel", None, None]:
        value = self.resolve_range_dispatch(ctx, vanilla, item)
        for entry in self.entries:
            if value >= entry.threshold:
                yield from entry.model.resolve(ctx, vanilla, item)
                return
        yield from self.fallback.resolve(ctx, vanilla, item)


class ItemModelRangeDispatchCustomModelData(ItemModelRangeDispatchBase):
    property: Literal["minecraft:custom_model_data"]
    index: Optional[int] = 0

    def resolve_range_dispatch(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> float:
        if not item.components:
            return 0.0
        if not "minecraft:custom_model_data" in item.components:
            return 0.0
        if not "floats" in item.components["minecraft:custom_model_data"]:
            return 0.0
        index = self.index or 0
        if index >= len(item.components["minecraft:custom_model_data"]["floats"]):
            return 0.0
        return item.components["minecraft:custom_model_data"]["floats"][index]


class ItemModelRangeDispatchBundleFullness(ItemModelRangeDispatchBase):
    property: Literal["minecraft:bundle/fullness"]

    def resolve_range_dispatch(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> float:
        # Not implemented for now
        # need to calculate the fullness of the bundle
        return 0.0


class ItemModelRangeDispatchDamage(ItemModelRangeDispatchBase):
    property: Literal["minecraft:damage"]
    normalize: Optional[bool] = True

    def resolve_range_dispatch(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> float:
        if not item.components:
            return 0.0
        if not "minecraft:damage" in item.components:
            return 0.0
        if not "minecraft:max_damage" in item.components:
            return 0.0
        damage = item.components["minecraft:damage"]
        max_damage = item.components["minecraft:max_damage"]
        if self.normalize:
            return damage / max_damage
        return clamp(0.0, damage, max_damage)


class ItemModelRangeDispatchCount(ItemModelRangeDispatchBase):
    property: Literal["minecraft:count"]
    normalize: Optional[bool] = True

    def resolve_range_dispatch(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> float:
        if not item.components:
            return 0.0
        if not "minecraft:max_stack_size" in item.components:
            return 0.0
        count = item.count
        max_stack_size = item.components["minecraft:max_stack_size"]
        if self.normalize:
            return count / max_stack_size
        return clamp(0.0, count, max_stack_size)


class ItemModelRangeDispatchCooldown(ItemModelRangeDispatchBase):
    property: Literal["minecraft:cooldown"]

    def resolve_range_dispatch(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchTime(ItemModelRangeDispatchBase):
    property: Literal["minecraft:time"]
    wobble: Optional[bool] = True
    natural_only: Optional[bool] = True

    def resolve_range_dispatch(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchCompass(ItemModelRangeDispatchBase):
    property: Literal["minecraft:compass"]
    wobble: Optional[bool] = True
    target: Literal["spawn", "lodestone", "recovery"]

    def resolve_range_dispatch(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchCrossbowPull(ItemModelRangeDispatchBase):
    property: Literal["minecraft:crossbow/pull"]

    def resolve_range_dispatch(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchUseDuration(ItemModelRangeDispatchBase):
    property: Literal["minecraft:use_duration"]
    remaining: Optional[bool] = False

    def resolve_range_dispatch(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchUseCycle(ItemModelRangeDispatchBase):
    property: Literal["minecraft:use_cycle"]
    period: float = 1.0

    def resolve_range_dispatch(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> float:
        # Not possible to implement
        return 0.0


type ItemModelRangeDispatch = Union[
    ItemModelRangeDispatchCustomModelData,
    ItemModelRangeDispatchBundleFullness,
    ItemModelRangeDispatchDamage,
    ItemModelRangeDispatchCount,
    ItemModelRangeDispatchCooldown,
    ItemModelRangeDispatchTime,
    ItemModelRangeDispatchCompass,
    ItemModelRangeDispatchCrossbowPull,
    ItemModelRangeDispatchUseDuration,
    ItemModelRangeDispatchUseCycle,
]


class ItemModelBundleSelectedItem(ItemModelBase):
    type: Literal["minecraft:bundle/selected_item"]


class SpecialModelBase(BaseModel):
    type: Literal[
        "minecraft:bed",
        "minecraft:banner",
        "minecraft:conduit",
        "minecraft:chest",
        "minecraft:head",
        "minecraft:shulker_box",
        "minecraft:shield",
        "minecraft:trident",
        "minecraft:decorated_pot",
    ]


class SpecialModelBed(SpecialModelBase):
    type: Literal["minecraft:bed"]
    texture: str


class SpecialModelBanner(SpecialModelBase):
    type: Literal["minecraft:banner"]
    color: str


class SpecialModelConduit(SpecialModelBase):
    type: Literal["minecraft:conduit"]


class SpecialModelChest(SpecialModelBase):
    type: Literal["minecraft:chest"]
    texture: str
    openness: float = 0.0


class SpecialModelHead(SpecialModelBase):
    type: Literal["minecraft:head"]
    kind: Literal[
        "skeleton", "wither_skeleton", "player", "zombie", "creeper", "piglin", "dragon"
    ]


class SpecialModelShulkerBox(SpecialModelBase):
    type: Literal["minecraft:shulker_box"]
    name: str
    openness: float = 0.0
    orientation: Literal["down", "east", "north", "south", "up", "west"] = "up"


class SpecialModelShield(SpecialModelBase):
    type: Literal["minecraft:shield"]


class SpecialModelTrident(SpecialModelBase):
    type: Literal["minecraft:trident"]


class SpecialModelDecoratedPot(SpecialModelBase):
    type: Literal["minecraft:decorated_pot"]


type SpecialModel = Union[
    SpecialModelBed,
    SpecialModelBase,
    SpecialModelBanner,
    SpecialModelConduit,
    SpecialModelChest,
    SpecialModelHead,
    SpecialModelShulkerBox,
    SpecialModelShield,
    SpecialModelTrident,
    SpecialModelDecoratedPot,
]


class ItemModelSpecialBase(ItemModelBase):
    type: Literal["minecraft:special"]
    base: str
    model: SpecialModel


type ItemModelAll = Union[
    ItemModelModel,
    ItemModelComposite,
    ItemModelCondition,
    ItemModelSelect,
    ItemModelRangeDispatch,
    ItemModelBundleSelectedItem,
]


class ItemModel(BaseModel):
    model: ItemModelAll

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelModel", None, None]:
        yield from self.model.resolve(ctx, vanilla, item)
