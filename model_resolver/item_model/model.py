from fractions import Fraction
import numpy as np
from functools import cached_property
import math
from pydantic import BaseModel, Field, RootModel, model_validator
from model_resolver.item_model.data_component_predicate import Context, component_predicate
from model_resolver.item_model.tint_source import TintSource
from model_resolver.item_model.special import SpecialModel
from typing import Optional, Literal, ClassVar, Generator, Self, Type, Union, Any
from model_resolver.item_model.item import Item
from model_resolver.item_model.transformation import Transformation
from model_resolver.utils import clamp, namespaced, resolve_key, validate_dispatched
from model_resolver.minecraft_model import MISSING_MODEL_ID, MinecraftModel, missing_model, resolve_model
from model_resolver.pack_getter import PackGetter

ItemModelBaseClass: list[Type["ItemModelBase"]] = []


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
    transformation: Optional[Transformation] = None

    def resolve(
        self, getter: PackGetter, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield from []

    def __init_subclass__(cls, **kwargs):
        # not in the list, not this base class and not any base class
        if (
            cls not in ItemModelBaseClass
            and not cls is ItemModelBase
            and not cls.__name__.endswith("Base")
        ):
            ItemModelBaseClass.append(cls)
        return super().__init_subclass__(**kwargs)
    
    def resolve_with_compose(self, getter: PackGetter, item: Item, parent_transformation: Optional[Transformation]) -> Generator["ItemModelResolvable", None, None]:
        for res in self.resolve(getter, item):
            yield res.with_compose(parent_transformation)
    

    def with_compose(self, parent_transformation: Optional[Transformation]) -> Self:
        # a copy: parsed item models are cached, resolving one must not change it
        if parent_transformation is None:
            return self
        if self.transformation is None:
            return self.model_copy(update={"transformation": parent_transformation})
        return self.model_copy(
            update={"transformation": parent_transformation.compose(self.transformation)}
        )


class ItemModelModel(ItemModelBase):
    type: Literal["minecraft:model", "model"]
    model: str
    tints: list[TintSource] = Field(default_factory=list)

    def resolve(
        self, getter: PackGetter, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield self

    def get_model(self, getter: PackGetter, item: Item) -> MinecraftModel:
        key = resolve_key(self.model)
        if key == MISSING_MODEL_ID:
            return missing_model()
        if key in getter.assets.models:
            data = getter.assets.models[key].data
        else:
            raise ValueError(f"Model {key} not found")
        return MinecraftModel.model_validate(resolve_model(data, getter)).bake()

    def get_tints(self, getter: PackGetter, item: Item) -> list[TintSource]:
        return self.tints


class ItemModelComposite(ItemModelBase):
    type: Literal["minecraft:composite", "composite"]
    models: list["ItemModelRecursive"]

    def resolve(
        self, getter: PackGetter, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        for model in self.models:
            yield from model.resolve_with_compose(getter, item, self.transformation)


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

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        raise NotImplementedError

    def resolve(
        self, getter: PackGetter, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        if self.resolve_condition(getter, item):
            yield from self.on_true.resolve_with_compose(getter, item, self.transformation)
        else:
            yield from self.on_false.resolve_with_compose(getter, item, self.transformation)


class ItemModelConditionUsingItem(ItemModelConditionBase):
    property: Literal["minecraft:using_item", "using_item"]

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionBroken(ItemModelConditionBase):
    property: Literal["minecraft:broken", "broken"]

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        # ItemStack.nextDamageWillBreak
        return item.is_damageable and item.damage >= item.max_damage - 1


class ItemModelConditionComponent(ItemModelConditionBase):
    property: Literal["minecraft:component", "component"]
    predicate: str
    value: Any

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        return component_predicate(self.predicate, self.value).matches(Context(getter, item))


class ItemModelConditionDamaged(ItemModelConditionBase):
    property: Literal["minecraft:damaged", "damaged"]

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        # ItemStack.isDamaged
        return item.is_damageable and item.damage > 0


class ItemModelConditionHasComponent(ItemModelConditionBase):
    property: Literal["minecraft:has_component", "has_component"]
    component: str
    ignore_default: Optional[bool] = False

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        if self.ignore_default:
            return item.has_non_default(self.component)
        return resolve_key(self.component) in item.components


class ItemModelConditionFishingRodCast(ItemModelConditionBase):
    property: Literal["minecraft:fishing_rod/cast", "fishing_rod/cast"]

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionBundleHasSelectedItem(ItemModelConditionBase):
    property: Literal["minecraft:bundle/has_selected_item", "bundle/has_selected_item"]

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionSelected(ItemModelConditionBase):
    property: Literal["minecraft:selected", "selected"]

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionCarried(ItemModelConditionBase):
    property: Literal["minecraft:carried", "carried"]

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionExtendedView(ItemModelConditionBase):
    property: Literal["minecraft:extended_view", "extended_view"]

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionKeybindDown(ItemModelConditionBase):
    property: Literal["minecraft:keybind_down", "keybind_down"]
    keybind: str

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionCustomModelData(ItemModelConditionBase):
    property: Literal["minecraft:custom_model_data", "custom_model_data"]
    index: Optional[int] = 0

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
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

    def resolve_condition(self, getter: PackGetter, item: Item) -> bool:
        # Not possible to implement
        return False


class SelectCase(BaseModel):
    when: Any | list[Any]
    model: "ItemModelRecursive"

    @property
    def values(self) -> list[Any]:
        return self.when if isinstance(self.when, list) else [self.when]


def missing_item_model() -> "ItemModelRecursive":
    # what an absent fallback bakes to (ItemModel.BakingContext.missingItemModel)
    return ItemModelRecursive({"type": "minecraft:model", "model": MISSING_MODEL_ID})


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
    fallback: Optional["ItemModelRecursive"] = None
    possible_values: ClassVar[list[str]] = []

    @classmethod
    def decode(cls, value: Any) -> Any:
        """Read a `when` value, or the item's value, like the property's value codec."""
        return value

    @model_validator(mode="after")
    def validate_cases(self) -> Self:
        # SelectItemModelProperty.Type.validateCases
        if not self.cases:
            raise ValueError("Empty case list")
        seen: list[Any] = []
        duplicates: list[Any] = []
        for case in self.cases:
            for value in case.values:
                value = self.decode(value)
                if value in seen and value not in duplicates:
                    duplicates.append(value)
                seen.append(value)
        if duplicates:
            raise ValueError(f"Duplicate case conditions: {', '.join(map(str, duplicates))}")
        return self

    def get_fallback(self) -> "ItemModelRecursive":
        return self.fallback or missing_item_model()

    def resolve_select(self, getter: PackGetter, item: Item) -> "ItemModelRecursive":
        return self.get_fallback()

    def resolve_case(self, value: Any) -> "ItemModelRecursive":
        if value is None:
            return self.get_fallback()
        value = self.decode(value)
        for case in self.cases:
            if any(self.decode(when) == value for when in case.values):
                return case.model
        return self.get_fallback()

    def resolve(
        self, getter: PackGetter, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield from self.resolve_select(getter, item).resolve_with_compose(getter, item, self.transformation)


class ItemModelSelectMainHand(ItemModelSelectBase):
    property: Literal["minecraft:main_hand", "main_hand"]
    possible_values: ClassVar[list[str]] = ["left", "right"]

    def resolve_select(self, getter: PackGetter, item: Item) -> "ItemModelRecursive":
        # MainHand: the owner's main arm, right by default for a player
        return self.resolve_case("right" if item.owner is not None else None)


class ItemModelSelectChargeType(ItemModelSelectBase):
    property: Literal["minecraft:charge_type", "charge_type"]
    possible_values: ClassVar[list[str]] = ["none", "rocket", "arrow"]

    def resolve_select(self, getter: PackGetter, item: Item) -> "ItemModelRecursive":
        # Charge: a firework rocket among the charged projectiles, any projectile, or none
        projectiles = [
            item.nested(stack)
            for stack in item.components.get("minecraft:charged_projectiles") or []
        ]
        if not projectiles:
            return self.resolve_case("none")
        if any(resolve_key(x.id) == "minecraft:firework_rocket" for x in projectiles):
            return self.resolve_case("rocket")
        return self.resolve_case("arrow")


class ItemModelSelectComponent(ItemModelSelectBase):
    property: Literal["minecraft:component", "component"]
    component: str

    @classmethod
    def decode(cls, value: Any) -> Any:
        # the component codec reads "stone" as minecraft:stone wherever it expects an id
        return namespaced(value)

    def resolve_select(self, getter: PackGetter, item: Item) -> "ItemModelRecursive":
        return self.resolve_case(item.components.get(resolve_key(self.component)))


class ItemModelSelectLocalTime(ItemModelSelectBase):
    property: Literal["minecraft:local_time", "local_time"]
    locale: str = ""
    time_zone: Optional[str] = None
    pattern: str

    def resolve_select(self, getter: PackGetter, item: Item) -> "ItemModelRecursive":
        # Not possible to implement
        return self.get_fallback()


class ItemModelSelectContextEntityType(ItemModelSelectBase):
    property: Literal["minecraft:context_entity_type", "context_entity_type"]

    @classmethod
    def decode(cls, value: Any) -> Any:
        return resolve_key(value) if isinstance(value, str) else value

    def resolve_select(self, getter: PackGetter, item: Item) -> "ItemModelRecursive":
        return self.resolve_case(item.owner)


class ItemModelSelectTrimMaterial(ItemModelSelectBase):
    property: Literal["minecraft:trim_material", "trim_material"]

    @classmethod
    def decode(cls, value: Any) -> Any:
        return resolve_key(value) if isinstance(value, str) else value

    def resolve_select(self, getter: PackGetter, item: Item) -> "ItemModelRecursive":
        trim = item.components.get("minecraft:trim") or {}
        material = trim.get("material")
        # an inline material has no id to select on
        return self.resolve_case(material if isinstance(material, str) else None)


class ItemModelSelectBlockState(ItemModelSelectBase):
    property: Literal["minecraft:block_state", "block_state"]
    block_state_property: str

    def resolve_select(self, getter: PackGetter, item: Item) -> "ItemModelRecursive":
        block_state = item.components.get("minecraft:block_state") or {}
        return self.resolve_case(block_state.get(self.block_state_property))


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

    def resolve_select(self, getter: PackGetter, item: Item) -> "ItemModelRecursive":
        return self.resolve_case(item.display_context)


class ItemModelSelectCustomModelData(ItemModelSelectBase):
    property: Literal["minecraft:custom_model_data", "custom_model_data"]
    index: Optional[int] = 0

    def resolve_select(self, getter: PackGetter, item: Item) -> "ItemModelRecursive":
        strings = (item.components.get("minecraft:custom_model_data") or {}).get("strings", [])
        index = self.index or 0
        return self.resolve_case(strings[index] if 0 <= index < len(strings) else None)


class ItemModelSelectContextDimension(ItemModelSelectBase):
    property: Literal["minecraft:context_dimension", "context_dimension"]

    @classmethod
    def decode(cls, value: Any) -> Any:
        return resolve_key(value) if isinstance(value, str) else value

    def resolve_select(self, getter: PackGetter, item: Item) -> "ItemModelRecursive":
        return self.resolve_case("minecraft:overworld")


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

    def resolve_range_dispatch(self, getter: PackGetter, item: Item) -> float:
        return 0.0

    def resolve(
        self, getter: PackGetter, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        # RangeSelectItemModel: the last entry whose threshold <= value * scale,
        # the fallback when there is none or the value is NaN
        scale = 1.0 if self.scale is None else self.scale
        value = self.resolve_range_dispatch(getter, item) * scale
        selected = self.fallback or missing_item_model()
        if not math.isnan(value):
            for entry in sorted(self.entries, key=lambda x: x.threshold):
                if entry.threshold > value:
                    break
                selected = entry.model
        yield from selected.resolve_with_compose(getter, item, self.transformation)


class ItemModelRangeDispatchCustomModelData(ItemModelRangeDispatchBase):
    property: Literal["minecraft:custom_model_data", "custom_model_data"]
    index: Optional[int] = 0

    def resolve_range_dispatch(self, getter: PackGetter, item: Item) -> float:
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

    def resolve_range_dispatch(self, getter: PackGetter, item: Item) -> float:
        return float(bundle_weight(item))


def bundle_weight(item: Item) -> Fraction:
    """BundleContents.weight: each stack weighs count / max_stack_size,
    a nested bundle its own weight + 1/16 and a beehive with bees 1."""
    weight = Fraction(0)
    for template in item.components.get("minecraft:bundle_contents") or []:
        stack = item.nested(template)
        bees = stack.components.get("minecraft:bees")
        if isinstance(bees, dict):
            bees = bees.get("bees")
        if "minecraft:bundle_contents" in stack.components:
            stack_weight = bundle_weight(stack) + Fraction(1, 16)
        elif bees:
            stack_weight = Fraction(1)
        else:
            stack_weight = Fraction(1, stack.max_stack_size)
        weight += stack_weight * stack.count
    return weight


class ItemModelRangeDispatchDamage(ItemModelRangeDispatchBase):
    property: Literal["minecraft:damage", "damage"]
    normalize: Optional[bool] = True

    def resolve_range_dispatch(self, getter: PackGetter, item: Item) -> float:
        damage, max_damage = item.damage, item.max_damage
        if self.normalize:
            # 0 / 0 is NaN in vanilla, so items without max_damage take the fallback
            return clamp(0.0, damage / max_damage, 1.0) if max_damage else math.nan
        return clamp(0.0, damage, max_damage)


class ItemModelRangeDispatchCount(ItemModelRangeDispatchBase):
    property: Literal["minecraft:count", "count"]
    normalize: Optional[bool] = True

    def resolve_range_dispatch(self, getter: PackGetter, item: Item) -> float:
        count, max_stack_size = item.count, item.max_stack_size
        if self.normalize:
            return clamp(0.0, count / max_stack_size, 1.0)
        return clamp(0.0, count, max_stack_size)


class ItemModelRangeDispatchCooldown(ItemModelRangeDispatchBase):
    property: Literal["minecraft:cooldown", "cooldown"]

    def resolve_range_dispatch(self, getter: PackGetter, item: Item) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchTime(ItemModelRangeDispatchBase):
    property: Literal["minecraft:time", "time"]
    wobble: Optional[bool] = True
    source: Literal["daytime", "moon_phase", "random"]
    # natural_only: Optional[bool] = True

    def resolve_range_dispatch(self, getter: PackGetter, item: Item) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchCompass(ItemModelRangeDispatchBase):
    property: Literal["minecraft:compass", "compass"]
    wobble: Optional[bool] = True
    target: Literal["spawn", "lodestone", "recovery", "none"]

    def resolve_range_dispatch(self, getter: PackGetter, item: Item) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchCrossbowPull(ItemModelRangeDispatchBase):
    property: Literal["minecraft:crossbow/pull", "crossbow/pull"]

    def resolve_range_dispatch(self, getter: PackGetter, item: Item) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchUseDuration(ItemModelRangeDispatchBase):
    property: Literal["minecraft:use_duration", "use_duration"]
    remaining: Optional[bool] = False

    def resolve_range_dispatch(self, getter: PackGetter, item: Item) -> float:
        # Not possible to implement
        return 0.0


class ItemModelRangeDispatchUseCycle(ItemModelRangeDispatchBase):
    property: Literal["minecraft:use_cycle", "use_cycle"]
    period: float = 1.0

    def resolve_range_dispatch(self, getter: PackGetter, item: Item) -> float:
        # Not possible to implement
        return 0.0


class ItemModelBundleSelectedItem(ItemModelBase):
    type: Literal["minecraft:bundle/selected_item", "bundle/selected_item"]


# the transformation vanilla's item definitions give each special model (26.3), column-major.
# Special models built from the entity models themselves (copper golem statue, bell, book)
# are not listed: their transformation applies as is.
_FLIP_YZ = (1.0, 0, 0, 0, 0, -1.0, 0, 0, 0, 0, -1.0, 0)
VANILLA_SPECIAL_TRANSFORMATIONS: dict[str, tuple[float, ...]] = {
    "minecraft:banner": (0.6666667, 0, 0, 0, 0, -0.6666667, 0, 0, 0, 0, -0.6666667, 0, 0.5, 0, 0.5, 1),
    "minecraft:shulker_box": (0.9995, 0, 0, 0, 0, -0.9995, 0, 0, 0, 0, -0.9995, 0, 0.5, 1.4995, 0.5, 1),
    "minecraft:conduit": (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0.5, 0.5, 0.5, 1),
    "minecraft:head": (*_FLIP_YZ, 0.5, 0, 0.5, 1),
    "minecraft:player_head": (*_FLIP_YZ, 0.5, 0, 0.5, 1),
    "minecraft:shield": (*_FLIP_YZ, 0, 0, 0, 1),
}


class ItemModelSpecial(ItemModelBase):
    type: Literal["minecraft:special", "special"]
    base: str
    model: SpecialModel

    def split_transformation(self) -> tuple[Optional[Transformation], Optional[Transformation]]:
        """(transformation, calibration) to draw the special geometry with.

        Vanilla's special renderers draw entity models, which the item definition moves
        into place with a transformation. Our special geometries are block models that
        were calibrated with that vanilla transformation applied the old way (in pixels,
        around the model center): that is the calibration. Whatever the item definition
        adds on top of the vanilla transformation is applied like any other.
        """
        default = VANILLA_SPECIAL_TRANSFORMATIONS.get(resolve_key(self.model.root.get("type", "")))
        if default is None:
            return self.transformation, None
        calibration = Transformation.from_matrix(default)  # type: ignore
        if self.transformation is None:
            # what the item definition asks for is "no transformation": undo vanilla's
            inverse = np.linalg.inv(np.array(default).reshape(4, 4).T)
            return Transformation.from_matrix(tuple(inverse.T.flatten())), calibration  # type: ignore
        actual = np.array(self.transformation.get_matrix()).reshape(4, 4).T
        delta = actual @ np.linalg.inv(np.array(default).reshape(4, 4).T)
        if np.allclose(delta, np.identity(4), atol=1e-6):
            return None, calibration
        return Transformation.from_matrix(tuple(delta.T.flatten())), calibration  # type: ignore

    def get_model(self, getter: PackGetter, item: Item) -> MinecraftModel:
        if not getter.opts.special_rendering:
            return MinecraftModel()
        child = self.model.special_model.get_model(getter, item)
        scale = self.model.special_model.get_scale()
        rotations = self.model.special_model.get_additional_rotations()
        translations = self.model.special_model.get_additional_translations()
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
        init_translation = res.display.gui.translation
        if translations:
            res.display.gui.translation = (
                init_translation[0] + translations[0],
                init_translation[1] + translations[1],
                init_translation[2] + translations[2],
            )
        return res

    def resolve(
        self, getter: PackGetter, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield self

    def get_tints(self, getter: PackGetter, item: Item) -> list[TintSource]:
        return self.model.special_model.get_tints(getter, item)


class ItemModelEmpty(ItemModelBase):
    type: Literal["minecraft:empty", "empty"]

    def get_model(self, getter: PackGetter, item: Item) -> MinecraftModel:
        return MinecraftModel.model_validate({})

    def resolve(
        self, getter: PackGetter, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield from []

    @property
    def tints(self) -> list[TintSource]:
        return []


type ItemModelResolvable = Union[ItemModelModel, ItemModelSpecial]


class ItemModelRecursive(RootModel[Any]):
    root: Any

    @cached_property
    def model(self) -> ItemModelBase:
        return validate_dispatched(self.root, ItemModelBaseClass, "item model")

    def resolve(
        self, getter: PackGetter, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield from self.model.resolve(getter, item)

    def resolve_with_compose(self, getter: PackGetter, item: Item, parent_transformation: Optional[Transformation]) -> Generator["ItemModelResolvable", None, None]:
        yield from self.model.resolve_with_compose(getter, item, parent_transformation)


class ItemModel(BaseModel):
    model: ItemModelRecursive
    hand_animation_on_swap: Optional[bool] = True
    oversized_in_gui: Optional[bool] = False

    def resolve(
        self, getter: PackGetter, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield from self.model.resolve(getter, item)
