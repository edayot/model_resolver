from functools import cached_property
from pydantic import BaseModel, Field, RootModel
from model_resolver.item_model.data_component_predicate import DataComponent
from model_resolver.item_model.tint_source import TintSource
from model_resolver.item_model.special import SpecialModel
from typing import Optional, Literal, ClassVar, Generator, Union, Any
from model_resolver.item_model.item import Item
from model_resolver.utils import ModelResolverOptions, PackGetterV2, clamp, resolve_key
from model_resolver.minecraft_model import MinecraftModel, resolve_model
from rich import print  # noqa


class ItemModelBase(BaseModel):
    type: Literal[
        "minecraft:model",
        "model",
        "minecraft:composite",
        "composite",
        "minecraft:condition",
        "condition",
        "minecraft:select",
        "select",
        "minecraft:range_dispatch",
        "range_dispatch",
        "minecraft:bundle/selected_item",
        "bundle/selected_item",
        "minecraft:special",
        "special",
        "minecraft:empty",
        "empty",
    ]

    def resolve(
        self, getter: PackGetterV2, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield from []


class ItemModelModel(ItemModelBase):
    type: Literal["minecraft:model", "model"]
    model: str
    tints: list[TintSource] = Field(default_factory=list)

    def resolve(
        self, getter: PackGetterV2, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield self

    def get_model(self, getter: PackGetterV2, item: Item) -> MinecraftModel:
        key = resolve_key(self.model)
        if key in getter.assets.models:
            data = getter.assets.models[key].data
        else:
            raise ValueError(f"Model {key} not found")
        return MinecraftModel.model_validate(resolve_model(data, getter)).bake()

    def get_tints(self, getter: PackGetterV2, item: Item) -> list[TintSource]:
        return self.tints


class ItemModelComposite(ItemModelBase):
    type: Literal["minecraft:composite", "composite"]
    models: list["ItemModelRecursive"]

    def resolve(
        self, getter: PackGetterV2, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        for model in self.models:
            yield from model.resolve(getter, item)


class ItemModelConditionBase(ItemModelBase):
    type: Literal["minecraft:condition", "condition"]
    property: Literal[
        "minecraft:using_item",
        "using_item",
        "minecraft:broken",
        "broken",
        "minecraft:damaged",
        "damaged",
        "minecraft:has_component",
        "has_component",
        "minecraft:fishing_rod/cast",
        "fishing_rod/cast",
        "minecraft:bundle/has_selected_item",
        "bundle/has_selected_item",
        "minecraft:selected",
        "selected",
        "minecraft:carried",
        "carried",
        "minecraft:extended_view",
        "extended_view",
        "minecraft:custom_model_data",
        "custom_model_data",
        "minecraft:keybind_down",
        "keybind_down",
        "minecraft:view_entity",
        "view_entity",
    ]
    on_true: "ItemModelRecursive"
    on_false: "ItemModelRecursive"

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
        raise NotImplementedError

    def resolve(
        self, getter: PackGetterV2, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        if self.resolve_condition(getter, item):
            yield from self.on_true.resolve(getter, item)
        else:
            yield from self.on_false.resolve(getter, item)


class ItemModelConditionUsingItem(ItemModelConditionBase):
    property: Literal["minecraft:using_item", "using_item"]

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionBroken(ItemModelConditionBase):
    property: Literal["minecraft:broken", "broken"]

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
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


class ItemModelConditionComponent(ItemModelConditionBase):
    property: Literal["minecraft:component", "component"]
    predicate: str
    value: Any

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
        data_component = DataComponent.model_validate({self.predicate: self.value})
        return data_component.is_valid(getter, item) or False


class ItemModelConditionDamaged(ItemModelConditionBase):
    property: Literal["minecraft:damaged", "damaged"]

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
        if not item.components:
            return False
        if not "minecraft:damage" in item.components:
            return False
        return item.components["minecraft:damage"] > 0


class ItemModelConditionHasComponent(ItemModelConditionBase):
    property: Literal["minecraft:has_component", "has_component"]
    component: str
    ignore_default: Optional[bool] = False

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
        if not item.components:
            return False
        if self.ignore_default:
            return self.component in item.components_from_user
        else:
            return self.component in item.components


class ItemModelConditionFishingRodCast(ItemModelConditionBase):
    property: Literal["minecraft:fishing_rod/cast", "fishing_rod/cast"]

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionBundleHasSelectedItem(ItemModelConditionBase):
    property: Literal["minecraft:bundle/has_selected_item", "bundle/has_selected_item"]

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionSelected(ItemModelConditionBase):
    property: Literal["minecraft:selected", "selected"]

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionCarried(ItemModelConditionBase):
    property: Literal["minecraft:carried", "carried"]

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionExtendedView(ItemModelConditionBase):
    property: Literal["minecraft:extended_view", "extended_view"]

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionKeybindDown(ItemModelConditionBase):
    property: Literal["minecraft:keybind_down", "keybind_down"]
    keybind: str

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionCustomModelData(ItemModelConditionBase):
    property: Literal["minecraft:custom_model_data", "custom_model_data"]
    index: Optional[int] = 0

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
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


class ItemModelConditionViewEntity(ItemModelConditionBase):
    property: Literal["minecraft:view_entity", "view_entity"]

    def resolve_condition(self, getter: PackGetterV2, item: Item) -> bool:
        # Not possible to implement
        return False


type ItemModelCondition = Union[
    ItemModelConditionUsingItem,
    ItemModelConditionBroken,
    ItemModelConditionComponent,
    ItemModelConditionDamaged,
    ItemModelConditionHasComponent,
    ItemModelConditionFishingRodCast,
    ItemModelConditionBundleHasSelectedItem,
    ItemModelConditionSelected,
    ItemModelConditionCarried,
    ItemModelConditionExtendedView,
    ItemModelConditionCustomModelData,
    ItemModelConditionKeybindDown,
]


class SelectCase(BaseModel):
    when: Any | list[Any]
    model: "ItemModelRecursive"


class ItemModelSelectBase(ItemModelBase):
    type: Literal["minecraft:select", "select"]
    property: Literal[
        "minecraft:main_hand",
        "main_hand",
        "minecraft:charge_type",
        "charge_type",
        "minecraft:component",
        "component",
        "minecraft:trim_material",
        "trim_material",
        "minecraft:block_state",
        "block_state",
        "minecraft:display_context",
        "display_context",
        "minecraft:local_time",
        "local_time",
        "minecraft:context_entity_type",
        "context_entity_type",
        "minecraft:custom_model_data",
        "custom_model_data",
        "minecraft:context_dimension",
        "context_dimension",
    ]
    cases: list[SelectCase] = Field(default_factory=list)
    fallback: "ItemModelRecursive"
    possible_values: ClassVar[list[str]] = []

    def resolve_select(self, getter: PackGetterV2, item: Item) -> "ItemModelRecursive":
        return self.fallback

    def resolve_case(self, value: Any) -> "ItemModelRecursive":
        for case in self.cases:
            if isinstance(case.when, list):
                if value in case.when:
                    return case.model
            else:
                if case.when == value:
                    return case.model
        return self.fallback

    def resolve(
        self, getter: PackGetterV2, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield from self.resolve_select(getter, item).resolve(getter, item)


class ItemModelSelectMainHand(ItemModelSelectBase):
    property: Literal["minecraft:main_hand", "main_hand"]
    possible_values: ClassVar[list[str]] = ["left", "right"]


class ItemModelSelectChargeType(ItemModelSelectBase):
    property: Literal["minecraft:charge_type", "charge_type"]
    possible_values: ClassVar[list[str]] = ["none", "rocket", "arrow"]

    def resolve_select(self, getter: PackGetterV2, item: Item) -> "ItemModelRecursive":
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


class ItemModelSelectComponent(ItemModelSelectBase):
    property: Literal["minecraft:component", "component"]
    component: str

    def resolve_select(self, getter: PackGetterV2, item: Item) -> "ItemModelRecursive":
        component = item.components.get(resolve_key(self.component))
        if component is not None:
            return self.resolve_case(component)
        return self.fallback


class ItemModelSelectLocalTime(ItemModelSelectBase):
    property: Literal["minecraft:local_time", "local_time"]
    locale: str = ""
    time_zone: Optional[str] = None
    pattern: str

    def resolve_select(self, getter: PackGetterV2, item: Item) -> "ItemModelRecursive":
        # Not possible to implement
        return self.fallback


class ItemModelSelectContextEntityType(ItemModelSelectBase):
    property: Literal["minecraft:context_entity_type", "context_entity_type"]

    def resolve_select(self, getter: PackGetterV2, item: Item) -> "ItemModelRecursive":
        return self.resolve_case("minecraft:player")


class ItemModelSelectTrimMaterial(ItemModelSelectBase):
    property: Literal["minecraft:trim_material", "trim_material"]

    def resolve_select(self, getter: PackGetterV2, item: Item) -> "ItemModelRecursive":
        if not item.components:
            return self.fallback
        if not "minecraft:trim" in item.components:
            return self.fallback
        if not "material" in item.components["minecraft:trim"]:
            return self.fallback
        return self.resolve_case(item.components["minecraft:trim"]["material"])


class ItemModelSelectBlockState(ItemModelSelectBase):
    property: Literal["minecraft:block_state", "block_state"]
    block_state_property: str

    def resolve_select(self, getter: PackGetterV2, item: Item) -> "ItemModelRecursive":
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
    property: Literal["minecraft:display_context", "display_context"]
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

    def resolve_select(self, getter: PackGetterV2, item: Item) -> "ItemModelRecursive":
        return self.resolve_case("gui")


class ItemModelSelectCustomModelData(ItemModelSelectBase):
    property: Literal["minecraft:custom_model_data", "custom_model_data"]
    index: Optional[int] = 0

    def resolve_select(self, getter: PackGetterV2, item: Item) -> "ItemModelRecursive":
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


class ItemModelSelectContextDimension(ItemModelSelectBase):
    property: Literal["minecraft:context_dimension", "context_dimension"]

    def resolve_select(self, getter: PackGetterV2, item: Item) -> "ItemModelRecursive":
        return self.resolve_case("minecraft:overworld")


type ItemModelSelect = Union[
    ItemModelSelectMainHand,
    ItemModelSelectChargeType,
    ItemModelSelectComponent,
    ItemModelSelectTrimMaterial,
    ItemModelSelectBlockState,
    ItemModelSelectDisplayContext,
    ItemModelSelectCustomModelData,
    ItemModelSelectLocalTime,
    ItemModelSelectContextEntityType,
    ItemModelSelectContextDimension,
]


class RangeDispatchEntry(BaseModel):
    threshold: float
    model: "ItemModelRecursive"


class ItemModelRangeDispatchBase(ItemModelBase):
    type: Literal["minecraft:range_dispatch", "range_dispatch"]
    property: Literal[
        "minecraft:custom_model_data",
        "custom_model_data",
        "minecraft:bundle/fullness",
        "bundle/fullness",
        "minecraft:damage",
        "damage",
        "minecraft:count",
        "count",
        "minecraft:cooldown",
        "cooldown",
        "minecraft:time",
        "time",
        "minecraft:compass",
        "compass",
        "minecraft:crossbow/pull",
        "crossbow/pull",
        "minecraft:use_duration",
        "use_duration",
        "minecraft:use_cycle",
        "use_cycle",
    ]
    scale: Optional[float] = 1.0
    entries: list[RangeDispatchEntry] = Field(default_factory=list)
    fallback: Optional["ItemModelRecursive"] = None

    def resolve_range_dispatch(self, getter: PackGetterV2, item: Item) -> float:
        return 0.0

    def resolve(
        self, getter: PackGetterV2, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        value = self.resolve_range_dispatch(getter, item)
        for entry in self.entries:
            if value >= entry.threshold:
                yield from entry.model.resolve(getter, item)
                return
        if self.fallback:
            yield from self.fallback.resolve(getter, item)


class ItemModelRangeDispatchCustomModelData(ItemModelRangeDispatchBase):
    property: Literal["minecraft:custom_model_data", "custom_model_data"]
    index: Optional[int] = 0

    def resolve_range_dispatch(self, getter: PackGetterV2, item: Item) -> float:
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
    property: Literal["minecraft:bundle/fullness", "bundle/fullness"]

    def resolve_range_dispatch(self, getter: PackGetterV2, item: Item) -> float:
        # Not implemented for now
        # need to calculate the fullness of the bundle
        return 0.0


class ItemModelRangeDispatchDamage(ItemModelRangeDispatchBase):
    property: Literal["minecraft:damage", "damage"]
    normalize: Optional[bool] = True

    def resolve_range_dispatch(self, getter: PackGetterV2, item: Item) -> float:
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
    property: Literal["minecraft:count", "count"]
    normalize: Optional[bool] = True

    def resolve_range_dispatch(self, getter: PackGetterV2, item: Item) -> float:
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
    property: Literal["minecraft:cooldown", "cooldown"]

    def resolve_range_dispatch(self, getter: PackGetterV2, item: Item) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchTime(ItemModelRangeDispatchBase):
    property: Literal["minecraft:time", "time"]
    wobble: Optional[bool] = True
    source: Literal["daytime", "moon_phase", "random"]
    # natural_only: Optional[bool] = True

    def resolve_range_dispatch(self, getter: PackGetterV2, item: Item) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchCompass(ItemModelRangeDispatchBase):
    property: Literal["minecraft:compass", "compass"]
    wobble: Optional[bool] = True
    target: Literal["spawn", "lodestone", "recovery", "none"]

    def resolve_range_dispatch(self, getter: PackGetterV2, item: Item) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchCrossbowPull(ItemModelRangeDispatchBase):
    property: Literal["minecraft:crossbow/pull", "crossbow/pull"]

    def resolve_range_dispatch(self, getter: PackGetterV2, item: Item) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchUseDuration(ItemModelRangeDispatchBase):
    property: Literal["minecraft:use_duration", "use_duration"]
    remaining: Optional[bool] = False

    def resolve_range_dispatch(self, getter: PackGetterV2, item: Item) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchUseCycle(ItemModelRangeDispatchBase):
    property: Literal["minecraft:use_cycle", "use_cycle"]
    period: float = 1.0

    def resolve_range_dispatch(self, getter: PackGetterV2, item: Item) -> float:
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
    type: Literal["minecraft:bundle/selected_item", "bundle/selected_item"]


class ItemModelSpecial(ItemModelBase):
    type: Literal["minecraft:special", "special"]
    base: str
    model: SpecialModel

    def get_model(self, getter: PackGetterV2, item: Item) -> MinecraftModel:
        opts = getter._ctx.validate("model_resolver", ModelResolverOptions)
        if not opts.special_rendering:
            return MinecraftModel()
        child = self.model.get_model(getter, item)
        scale = self.model.get_scale()
        rotations = self.model.get_additional_rotations()
        child["parent"] = resolve_key(self.base)
        merged = resolve_model(child, getter, delete_parent_elements=True)
        res = MinecraftModel.model_validate(merged).bake()
        init_scale = res.display.gui.scale
        res.display.gui.scale = (
            init_scale[0] * scale,
            init_scale[1] * scale,
            init_scale[2] * scale,
        )

        init_rotation = res.display.gui.rotation
        if rotations:
            res.display.gui.rotation = (
                init_rotation[0] + rotations[0],
                init_rotation[1] + rotations[1],
                init_rotation[2] + rotations[2],
            )
        return res

    def resolve(
        self, getter: PackGetterV2, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield self

    def get_tints(self, getter: PackGetterV2, item: Item) -> list[TintSource]:
        return self.model.get_tints(getter, item)


class ItemModelEmpty(ItemModelBase):
    type: Literal["minecraft:empty", "empty"]

    def get_model(self, getter: PackGetterV2, item: Item) -> MinecraftModel:
        return MinecraftModel.model_validate({})

    def resolve(
        self, getter: PackGetterV2, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield from []

    @property
    def tints(self) -> list[TintSource]:
        return []


type ItemModelResolvable = Union[ItemModelModel, ItemModelSpecial]


class ItemModelAll(RootModel):
    root: Union[
        ItemModelModel,
        ItemModelComposite,
        ItemModelCondition,
        ItemModelSelect,
        ItemModelRangeDispatch,
        ItemModelBundleSelectedItem,
        ItemModelSpecial,
        ItemModelEmpty,
    ]


class ItemModelRecursive(RootModel[Any]):
    root: Any

    @cached_property
    def model(self) -> ItemModelAll:
        return ItemModelAll.model_validate(self.root)

    def resolve(
        self, getter: PackGetterV2, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield from self.model.root.resolve(getter, item)


class ItemModel(BaseModel):
    model: ItemModelRecursive
    hand_animation_on_swap: Optional[bool] = True
    oversized_in_gui: Optional[bool] = False

    def resolve(
        self, getter: PackGetterV2, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield from self.model.resolve(getter, item)
