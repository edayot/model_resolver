from pydantic import BaseModel, Field
from model_resolver.item_model.tint_source import TintSource
from typing import Optional, Literal, ClassVar, Generator, Union, Any
from beet import Context
from model_resolver.vanilla import Vanilla
from model_resolver.item_model.item import Item
from model_resolver.utils import clamp, resolve_key
from model_resolver.minecraft_model import MinecraftModel, resolve_model
from copy import deepcopy
from PIL import Image
from uuid import UUID
import json
import base64
from rich import print


class ItemModelBase(BaseModel):
    type: Literal[
        "minecraft:model",
        "minecraft:composite",
        "minecraft:condition",
        "minecraft:select",
        "minecraft:range_dispatch",
        "minecraft:bundle/selected_item",
        "minecraft:special",
    ]

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield from []


class ItemModelModel(ItemModelBase):
    type: Literal["minecraft:model"]
    model: str
    tints: list[TintSource] = Field(default_factory=list)

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield self

    def get_model(self, ctx: Context, vanilla: Vanilla, item: Item) -> MinecraftModel:
        key = resolve_key(self.model)
        if key in ctx.assets.models:
            data = ctx.assets.models[key].data
        elif key in vanilla.assets.models:
            data = vanilla.assets.models[key].data
        else:
            raise ValueError(f"Model {key} not found")
        return MinecraftModel.model_validate(resolve_model(data, ctx, vanilla)).bake()
    


class ItemModelComposite(ItemModelBase):
    type: Literal["minecraft:composite"]
    models: list["ItemModelAll"]

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        for model in self.models:
            yield from model.resolve(ctx, vanilla, item)


class ItemModelConditionBase(ItemModelBase):
    type: Literal["minecraft:condition"]
    property: Literal[
        "minecraft:using_item",
        "minecraft:broken",
        "minecraft:damaged",
        "minecraft:has_component",
        "minecraft:fishing_rod/cast",
        "minecraft:bundle/has_selected_item",
        "minecraft:selected",
        "minecraft:carried",
        "minecraft:extended_view",
        "minecraft:custom_model_data",
        "minecraft:keybind_down",
    ]
    on_true: "ItemModelAll"
    on_false: "ItemModelAll"

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        raise NotImplementedError

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
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
    ignore_default: Optional[bool] = False

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        if not item.components:
            return False
        if self.ignore_default:
            return self.component in item.components_from_user
        else:
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


class ItemModelConditionExtendedView(ItemModelConditionBase):
    property: Literal["minecraft:extended_view"]

    def resolve_condition(self, ctx: Context, vanilla: Vanilla, item: Item) -> bool:
        # Not possible to implement
        return False


class ItemModelConditionKeybindDown(ItemModelConditionBase):
    property: Literal["minecraft:keybind_down"]
    keybind: str

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
    ItemModelConditionSelected,
    ItemModelConditionCarried,
    ItemModelConditionExtendedView,
    ItemModelConditionCustomModelData,
    ItemModelConditionKeybindDown,
]


class SelectCase(BaseModel):
    when: str | list[str]
    model: "ItemModelAll"


class ItemModelSelectBase(ItemModelBase):
    type: Literal["minecraft:select"]
    property: Literal[
        "minecraft:main_hand",
        "minecraft:charge_type",
        "minecraft:trim_material",
        "minecraft:block_state",
        "minecraft:display_context",
        "minecraft:local_time",
        "minecraft:holder_type",
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
            if isinstance(case.when, list):
                if value in case.when:
                    return case.model
            elif isinstance(case.when, str):
                if case.when == value:
                    return case.model
        return self.fallback

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
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


class ItemModelSelectLocalTime(ItemModelSelectBase):
    property: Literal["minecraft:local_time"]
    locale: str = ""
    time_zone: Optional[str] = None
    pattern: str

    def resolve_select(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> "ItemModelAll":
        # Not possible to implement
        return self.fallback
    
class ItemModelSelectHolderType(ItemModelSelectBase):
    property: Literal["minecraft:holder_type"]
    
    def resolve_select(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> "ItemModelAll":
        return self.resolve_case("minecraft:player")


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
    ItemModelSelectLocalTime,
]


class RangeDispatchEntry(BaseModel):
    threshold: float
    model: "ItemModelAll"


class ItemModelRangeDispatchBase(ItemModelBase):
    type: Literal["minecraft:range_dispatch"]
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
    entries: list[RangeDispatchEntry] = Field(default_factory=list)
    fallback: Optional["ItemModelAll"] = None

    def resolve_range_dispatch(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> float:
        return 0.0

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        value = self.resolve_range_dispatch(ctx, vanilla, item)
        for entry in self.entries:
            if value >= entry.threshold:
                yield from entry.model.resolve(ctx, vanilla, item)
                return
        if self.fallback:
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
    # wobble: Optional[bool] = True
    # natural_only: Optional[bool] = True

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
        "minecraft:standing_sign",
        "minecraft:hanging_sign",
    ]

    def get_model(self, ctx: Context, vanilla: Vanilla, item: Item) -> dict[str, Any]:
        return {}

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

    def get_model(self, ctx: Context, vanilla: Vanilla, item: Item) -> dict[str, Any]:
        openness = clamp(0.0, self.openness, 1.0)
        angle = openness * 90
        namespace, path = resolve_key(self.texture).split(":")
        model: dict[str, Any] = {
	        "elements": [
                {
                    "from": [1, 0, 1],
                    "to": [15, 10, 15],
                    "faces": {
                        "north": {"uv": [10.5, 8.25, 14, 10.75], "rotation": 180, "texture": "#all"},
                        "east": {"uv": [7, 8.25, 10.5, 10.75], "rotation": 180, "texture": "#all"},
                        "south": {"uv": [3.5, 8.25, 7, 10.75], "rotation": 180, "texture": "#all"},
                        "west": {"uv": [0, 8.25, 3.5, 10.75], "rotation": 180, "texture": "#all"},
                        "up": {"uv": [7, 4.75, 10.5, 8.25], "texture": "#all"},
                        "down": {"uv": [3.5, 4.75, 7, 8.25], "texture": "#all"}
                    }
                },
                {
                    "from": [1, 10, 1],
                    "to": [15, 14, 15],
                    "rotation": {"angle": angle, "axis": "x", "origin": [8, 10, 15]},
                    "faces": {
                        "north": {"uv": [10.5, 3.75, 14, 4.75], "rotation": 180, "texture": "#all"},
                        "east": {"uv": [7, 3.75, 10.5, 4.75], "rotation": 180, "texture": "#all"},
                        "south": {"uv": [3.5, 3.75, 7, 4.75], "rotation": 180, "texture": "#all"},
                        "west": {"uv": [0, 3.75, 3.5, 4.75], "rotation": 180, "texture": "#all"},
                        "up": {"uv": [7, 0, 10.5, 3.5], "texture": "#all"},
                        "down": {"uv": [3.5, 0, 7, 3.5], "texture": "#all"}
                    }
                },
                {
                    "from": [7, 7, 0],
                    "to": [9, 11, 2],
                    "rotation": {"angle": angle, "axis": "x", "origin": [8, 10, 15]},
                    "faces": {
                        "north": {"uv": [0.25, 0.25, 0.75, 1.25], "rotation": 180, "texture": "#all"},
                        "east": {"uv": [0, 0.25, 0.25, 1.25], "rotation": 180, "texture": "#all"},
                        "south": {"uv": [1, 0.25, 1.5, 1.25], "rotation": 180, "texture": "#all"},
                        "west": {"uv": [0.75, 0.25, 1, 1.25], "rotation": 180, "texture": "#all"},
                        "up": {"uv": [0.25, 0, 0.75, 0.25], "rotation": 180, "texture": "#all"},
                        "down": {"uv": [0.75, 0, 1.25, 0.25], "rotation": 180, "texture": "#all"}
                    }
                }
            ],
            "textures": {
                "all": f"{namespace}:entity/chest/{path}"
            }
        }
        return model
        
        

class PropertiesModel(BaseModel):
    name: str
    value: str
    signature: Optional[str] = None

class ProfileComponent(BaseModel):
    name: Optional[str] = None
    id: Optional[list[int]] | str = None
    properties: Optional[list[PropertiesModel]] = None


class SpecialModelHead(SpecialModelBase):
    type: Literal["minecraft:head"]
    kind: Literal[
        "skeleton", "wither_skeleton", "player", "zombie", "creeper", "piglin", "dragon"
    ]
    texture: Optional[str] = None

    def get_model(self, ctx: Context, vanilla: Vanilla, item: Item) -> dict[str, Any]:
        match self.kind:
            case "player":
                return self.get_model_player(ctx, vanilla, item)
            case _:
                raise NotImplementedError(f"Head kind {self.kind} not implemented")

    def get_model_player(self, ctx: Context, vanilla: Vanilla, item: Item) -> dict[str, Any]:
        texture = self.get_player_texture(ctx, vanilla, item)
        model = {
            "textures": {
                "1": texture,
                "particle": texture
            },
            "elements": [
                {
                    "from": [4, 4, 4],
                    "to": [12, 12, 12],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "north": {"uv": [6, 2, 8, 4], "texture": "#1"},
                        "east": {"uv": [4, 2, 6, 4], "texture": "#1"},
                        "south": {"uv": [2, 2, 4, 4], "texture": "#1"},
                        "west": {"uv": [0, 2, 2, 4], "texture": "#1"},
                        "up": {"uv": [2, 0, 4, 2], "rotation": 180, "texture": "#1"},
                        "down": {"uv": [4, 0, 6, 2], "rotation": 180, "texture": "#1"}
                    }
                },
                {
                    "from": [3.75, 3.75, 3.75],
                    "to": [12.25, 12.25, 12.25],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "north": {"uv": [14, 2, 16, 4], "texture": "#1"},
                        "east": {"uv": [12, 2, 14, 4], "texture": "#1"},
                        "south": {"uv": [10, 2, 12, 4], "texture": "#1"},
                        "west": {"uv": [8, 2, 10, 4], "texture": "#1"},
                        "up": {"uv": [10, 0, 12, 2], "rotation": 180, "texture": "#1"},
                        "down": {"uv": [12, 0, 14, 2], "rotation": 180, "texture": "#1"}
                    }
                }
            ]
        }
        return model
    
    def get_player_texture(self, ctx: Context, vanilla: Vanilla, item: Item) -> str | Image.Image:
        DEFAULT_TEXTURE = "minecraft:textures/entity/player/wide/steve"
        if self.texture:
            return self.texture
        if not item.components:
            return DEFAULT_TEXTURE
        if not "minecraft:profile" in item.components:
            return DEFAULT_TEXTURE
        cache = ctx.cache["model_resolver"]
        if not isinstance(item.components["minecraft:profile"], str):
            profile = ProfileComponent.model_validate(item.components["minecraft:profile"])
        else:
            profile = ProfileComponent(name=item.components["minecraft:profile"])
        
        if profile.id or profile.name:
            if profile.name:
                url = "https://api.mojang.com/users/profiles/minecraft/" + profile.name
                path = cache.download(url)
                with open(path, "r") as f:
                    data = json.load(f)
                if not "id" in data:
                    return DEFAULT_TEXTURE
                uuid = UUID(data["id"])
            elif profile.id:
                assert isinstance(profile.id, list)
                id = 0
                for i, signed in enumerate(profile.id):
                    # signed is a 32 bit signed integer
                    unsigned = signed & 0xFFFFFFFF
                    id += unsigned * 2**(32*(3-i))
                uuid = UUID(int=id)
            url = f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid}"
            path = cache.download(url)
            with open(path, "r") as f:
                data = json.load(f)
            profile = ProfileComponent.model_validate(data)
        if not profile.properties:
            return DEFAULT_TEXTURE
        if len(profile.properties) == 0:
            return DEFAULT_TEXTURE
        prop = profile.properties[0]
        value = base64.b64decode(prop.value)
        data = json.loads(value)
        texture_url = data["textures"]["SKIN"]["url"]
        texture_cache = cache.download(texture_url)
        img = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
        with Image.open(texture_cache) as texture:
            img.paste(texture, (0, 0))
        return img


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


wood_types = Literal[
    "oak",
    "spruce",
    "birch",
    "acacia",
    "cherry",
    "jungle",
    "dark_oak",
    "pale_oak",
    "mangrove",
    "bamboo",
    "crimson",
    "warped",
]


class SpecialModelStandingSign(SpecialModelBase):
    type: Literal["minecraft:standing_sign"]
    texture: str
    wood_type: wood_types


class SpecialModelHangingSign(SpecialModelBase):
    type: Literal["minecraft:hanging_sign"]
    texture: str
    wood_type: wood_types


type SpecialModel = Union[
    SpecialModelBed,
    SpecialModelBanner,
    SpecialModelConduit,
    SpecialModelChest,
    SpecialModelHead,
    SpecialModelShulkerBox,
    SpecialModelShield,
    SpecialModelTrident,
    SpecialModelDecoratedPot,
    SpecialModelStandingSign,
    SpecialModelHangingSign,
]


class ItemModelSpecial(ItemModelBase):
    type: Literal["minecraft:special"]
    base: str
    model: SpecialModel

    def get_model(self, ctx: Context, vanilla: Vanilla, item: Item) -> MinecraftModel:
        child = self.model.get_model(ctx, vanilla, item)
        child["parent"] = resolve_key(self.base)
        merged = resolve_model(child, ctx, vanilla)
        return MinecraftModel.model_validate(merged).bake()
    
    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield self
    
    @property
    def tints(self) -> list[TintSource]:
        return []


type ItemModelResolvable = Union[ItemModelModel, ItemModelSpecial]

type ItemModelAll = Union[
    ItemModelModel,
    ItemModelComposite,
    ItemModelCondition,
    ItemModelSelect,
    ItemModelRangeDispatch,
    ItemModelBundleSelectedItem,
    ItemModelSpecial,
]


class ItemModel(BaseModel):
    model: ItemModelAll

    def resolve(
        self, ctx: Context, vanilla: Vanilla, item: Item
    ) -> Generator["ItemModelResolvable", None, None]:
        yield from self.model.resolve(ctx, vanilla, item)
