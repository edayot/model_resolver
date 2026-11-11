from functools import cached_property
import math
from pydantic import BaseModel, RootModel
from model_resolver.item_model.tint_source import (
    TintSource,
    TintSourceConstant,
)
from typing import ClassVar, Optional, Literal, Type, Any
from model_resolver.item_model.item import Item
from model_resolver.item_model.glint import ENTITY_GLINT_SCALE, GlintStyle
from model_resolver.minecraft_model import MultiTexture, TextureSource
from model_resolver.utils import clamp, resolve_key, validate_dispatched
from model_resolver.pack_getter import PackGetter
from model_resolver.item_model.entity_model import entity_layers, to_elements
from model_resolver.utils import log
from beet import BannerPattern
from PIL import Image
from uuid import UUID
import hashlib
import json
import base64


SpecialModelBaseClass: list[Type["SpecialModelBase"]] = []


class SpecialModelBase(BaseModel):
    type: Literal[
        "minecraft:bed",
        "bed",
        "minecraft:banner",
        "banner",
        "minecraft:conduit",
        "conduit",
        "minecraft:chest",
        "chest",
        "minecraft:head",
        "head",
        "minecraft:shulker_box",
        "shulker_box",
        "minecraft:shield",
        "shield",
        "minecraft:trident",
        "trident",
        "minecraft:decorated_pot",
        "decorated_pot",
        "minecraft:standing_sign",
        "standing_sign",
        "minecraft:hanging_sign",
        "hanging_sign",
        "minecraft:copper_golem_statue",
        "copper_golem_statue",
        "minecraft:bell",
        "bell",
        "minecraft:book",
        "book",
        "minecraft:end_cube",
        "end_cube",
    ]

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        return {}

    def get_additional_translations(self) -> tuple[float, float, float] | None:
        return None

    def get_tints(self, getter: PackGetter, item: Item) -> list[TintSource]:
        return []

    def glint(self) -> Optional[GlintStyle]:
        """Most special renderers ignore hasFoil."""
        return None

    def __init_subclass__(cls, **kwargs):
        # not in the list, not this base class and not any base class
        if (
            cls not in SpecialModelBaseClass
            and not cls is SpecialModelBase
            and not cls.__name__.endswith("Base")
        ):
            SpecialModelBaseClass.append(cls)
        return super().__init_subclass__(**kwargs)


class SpecialModelCopperGolemStatue(SpecialModelBase):
    type: Literal["minecraft:copper_golem_statue", "copper_golem_statue"]
    texture: str
    pose: Literal["sitting", "running", "star", "standing"]

    LAYERS: ClassVar[dict[str, str]] = {
        "standing": "copper_golem",
        "running": "copper_golem_running",
        "sitting": "copper_golem_sitting",
        "star": "copper_golem_star",
    }

    def get_texture_path(self) -> str:
        # the texture is a full path, textures/<path>.png
        namespace, path = resolve_key(self.texture).split(":")
        return f"{namespace}:{path.removeprefix('textures/').removesuffix('.png')}"

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        layer = entity_layers(getter.opts.minecraft_version)[self.LAYERS[self.pose]]
        texture = self.get_texture_path()
        return {
            "textures": {"0": texture, "particle": texture},
            # CopperGolemStatueModel.setupAnim
            "elements": to_elements(layer, poses={"root": {"y": 0.0, "zRot": math.pi}}),
        }


class SpecialModelBed(SpecialModelBase):
    type: Literal["minecraft:bed", "bed"]
    texture: str
    part: Literal["head", "foot"]
    
    def get_additional_translations(self) -> tuple[float, float, float] | None:
        return (0, -4, 0)

    def elements(self) -> list[dict[str, Any]]:
        if self.part == "foot":
            x = 15
            return [
                {
                    "from": [0, 10 + x, 0],
                    "to": [16, 16 + x, 16],
                    "rotation": {"x": -90, "y": 0, "z": 180, "origin": [8, 11 + x, 5]},
                    "faces": {
                        "north": {"uv": [5.5, 5.5, 9.5, 7], "rotation": 180, "texture": "#0"},
                        "east": {"uv": [0, 7, 1.5, 11], "rotation": 270, "texture": "#0"},
                        "west": {"uv": [5.5, 7, 7, 11], "rotation": 90, "texture": "#0"},
                        "up": {"uv": [1.5, 7, 5.5, 11], "rotation": 180, "texture": "#0"},
                        "down": {"uv": [11, 11, 7, 7], "rotation": 180, "texture": "#0"}
                    }
                },
                {
                    "from": [0, 7 + x, 0],
                    "to": [3, 10 + x, 3],
                    "rotation": {"x": -90, "y": 0, "z": 180, "origin": [8, 11 + x, 5]},
                    "faces": {
                        "north": {"uv": [12.5, 3.75, 13.25, 4.5], "texture": "#0"},
                        "east": {"uv": [14.75, 3.75, 15.5, 4.5], "texture": "#0"},
                        "south": {"uv": [14, 3.75, 14.75, 4.5], "texture": "#0"},
                        "west": {"uv": [13.25, 3.75, 14, 4.5], "texture": "#0"},
                        "up": {"uv": [13.25, 3, 14, 3.75], "rotation": 90, "texture": "#0"},
                        "down": {"uv": [14.75, 3, 14, 3.75], "rotation": 90, "texture": "#0"}
                    }
                },
                {
                    "from": [13, 7 + x, 0],
                    "to": [16, 10 + x, 3],
                    "rotation": {"x": -90, "y": 0, "z": 180, "origin": [8, 11 + x, 5]},
                    "faces": {
                        "north": {"uv": [13.25, 0.75, 14, 1.5], "texture": "#0"},
                        "east": {"uv": [12.5, 0.75, 13.25, 1.5], "texture": "#0"},
                        "south": {"uv": [14.75, 0.75, 15.5, 1.5], "texture": "#0"},
                        "west": {"uv": [14, 0.75, 14.75, 1.5], "texture": "#0"},
                        "up": {"uv": [13.25, 0, 14, 0.75], "texture": "#0"},
                        "down": {"uv": [14.75, 0, 14, 0.75], "texture": "#0"}
                    }
                }
            ]
        elif self.part == "head":
             return [
                {
                    "from": [0, 1, 7],
                    "to": [3, 4, 10],
                    "rotation": {"x": -90, "y": 0, "z": 180, "origin": [8, 4.75, 5.25]},
                    "faces": {
                        "north": {"uv": [14.75, 5.25, 15.5, 6], "texture": "#0"},
                        "east": {"uv": [14, 5.25, 14.75, 6], "texture": "#0"},
                        "south": {"uv": [13.25, 5.25, 14, 6], "texture": "#0"},
                        "west": {"uv": [12.5, 5.25, 13.25, 6], "texture": "#0"},
                        "up": {"uv": [13.25, 4.5, 14, 5.25], "rotation": 180, "texture": "#0"},
                        "down": {"uv": [14.75, 4.5, 14, 5.25], "rotation": 180, "texture": "#0"}
                    }
                },
                {
                    "from": [0, 4, -6],
                    "to": [16, 10, 10],
                    "rotation": {"x": -90, "y": 0, "z": 180, "origin": [8, 4.75, 5.25]},
                    "faces": {
                        "east": {"uv": [0, 1.5, 1.5, 5.5], "rotation": 270, "texture": "#0"},
                        "south": {"uv": [1.5, 0, 5.5, 1.5], "rotation": 180, "texture": "#0"},
                        "west": {"uv": [5.5, 1.5, 7, 5.5], "rotation": 90, "texture": "#0"},
                        "up": {"uv": [1.5, 1.5, 5.5, 5.5], "rotation": 180, "texture": "#0"},
                        "down": {"uv": [11, 5.5, 7, 1.5], "rotation": 180, "texture": "#0"}
                    }
                },
                {
                    "from": [13, 1, 7],
                    "to": [16, 4, 10],
                    "rotation": {"x": -90, "y": 0, "z": 180, "origin": [8, 4.75, 5.25]},
                    "faces": {
                        "north": {"uv": [14, 2.25, 14.75, 3], "texture": "#0"},
                        "east": {"uv": [13.25, 2.25, 14, 3], "texture": "#0"},
                        "south": {"uv": [12.5, 2.25, 13.25, 3], "texture": "#0"},
                        "west": {"uv": [14.75, 2.25, 15.5, 3], "texture": "#0"},
                        "up": {"uv": [13.25, 1.5, 14, 2.25], "rotation": 270, "texture": "#0"},
                        "down": {"uv": [14, 1.5, 14.75, 2.25], "rotation": 270, "texture": "#0"}
                    }
                }
            ]
        raise ValueError(f"Invalid bed part {self.part}")

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        namespace, path = resolve_key(self.texture).split(":")
        model: dict[str, Any] = {
            "textures": {"0": f"{namespace}:entity/bed/{path}"},
            "elements": self.elements(),
        }
        return model


def entity_elements(
    getter: PackGetter,
    layer: str,
    texture: str = "#0",
    poses: Optional[dict[str, dict[str, float]]] = None,
    part_textures: Optional[dict[str, str]] = None,
) -> list[dict[str, Any]]:
    """The elements of an entity model layer (LayerDefinitions), in entity model space."""
    return to_elements(entity_layers(getter.opts.minecraft_version)[layer], texture, poses, part_textures)


class SpecialModelLayerBase(SpecialModelBase):
    """Banners and shields: a base sprite, then the pattern layers (BannerRenderer.submitPatterns)."""

    COLOR_STRING_TO_ARGB: ClassVar[dict[str, int]] = {
        "white": 16383998,
        "orange": 16351261,
        "magenta": 13061821,
        "light_blue": 3847130,
        "yellow": 16701501,
        "lime": 8439583,
        "pink": 15961002,
        "gray": 4673362,
        "light_gray": 10329495,
        "cyan": 1481884,
        "purple": 8991416,
        "blue": 3949738,
        "brown": 8606770,
        "green": 6192150,
        "red": 11546150,
        "black": 1908001,
    }

    base_texture: ClassVar[str]
    """The sprite the model is drawn with when it has patterns."""
    pattern_base: ClassVar[str]
    """The first pattern layer, in the base color (Sheets.BANNER_PATTERN_BASE / SHIELD_PATTERN_BASE)."""

    @property
    def entity_type(self) -> str:
        return resolve_key(self.type).split(":")[-1]

    def get_color(self, color: str) -> TintSourceConstant:
        if color not in self.COLOR_STRING_TO_ARGB:
            raise ValueError(f"Invalid color {color} for {self.entity_type}")
        return TintSourceConstant(type="constant", value=self.COLOR_STRING_TO_ARGB[color])

    def get_patterns(self, getter: PackGetter, item: Item, base_color: str) -> tuple[MultiTexture, ...]:
        """The base sprite, then the pattern base in the base color and every pattern."""
        res: list[MultiTexture] = [(self.base_texture, None), (self.pattern_base, self.get_color(base_color))]
        for pattern in item.components.get("minecraft:banner_patterns", [])[:16]:
            namespace, path = self.get_asset_id(getter, pattern["pattern"]).split(":", 1)
            res.append((f"{namespace}:entity/{self.entity_type}/{path}", self.get_color(pattern["color"])))
        return tuple(res)

    @staticmethod
    def get_asset_id(getter: PackGetter, pattern: str | dict[str, Any]) -> str:
        """The asset_id of a banner_pattern, given by id or inline (Sheets.getBannerMaterial)."""
        if isinstance(pattern, dict):
            return resolve_key(pattern["asset_id"])
        pattern = resolve_key(pattern)
        # every vanilla pattern's asset_id is its id, so the vanilla data pack isn't loaded
        for file in getter.get_stack(BannerPattern, pattern, exclude=("_vanilla",)):
            return resolve_key(file.data["asset_id"])
        return pattern


class SpecialModelBanner(SpecialModelLayerBase):
    """BannerRenderer.submitSpecial: the pole and bar, then the flag (still, at phase 0) with
    the patterns."""

    type: Literal["minecraft:banner", "banner"]
    color: str
    attachment: Literal["wall", "ground"] = "ground"

    base_texture: ClassVar[str] = "minecraft:entity/banner/banner_base"
    pattern_base: ClassVar[str] = "minecraft:entity/banner/base"

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        prefix = "" if self.attachment == "ground" else "wall_"
        # BannerFlagModel.setupAnim
        phase = 0.0
        flag_angle = (-0.0125 + 0.01 * math.cos(math.pi * 2 * phase)) * math.pi
        return {
            "textures": {"base": self.base_texture, "flag": self.get_patterns(getter, item, self.color)},
            "elements": entity_elements(getter, f"{prefix}banner", "#base")
            + entity_elements(getter, f"{prefix}banner_flag", "#flag", poses={"flag": {"xRot": flag_angle}}),
        }


class SpecialModelShield(SpecialModelLayerBase):
    """ShieldSpecialRenderer: the patterns, when it has some or a base color, over the shield."""

    type: Literal["minecraft:shield", "shield"]

    base_texture: ClassVar[str] = "minecraft:entity/shield/shield_base"
    base_texture_nopattern: ClassVar[str] = "minecraft:entity/shield/shield_base_nopattern"
    pattern_base: ClassVar[str] = "minecraft:entity/shield/base"

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        base_color = item.components.get("minecraft:base_color")
        if item.components.get("minecraft:banner_patterns") or base_color is not None:
            texture: TextureSource = self.get_patterns(getter, item, base_color or "white")
        else:
            texture = self.base_texture_nopattern
        return {"textures": {"0": texture}, "elements": entity_elements(getter, "shield")}

    def glint(self) -> Optional[GlintStyle]:
        return GlintStyle(ENTITY_GLINT_SCALE, "minecraft:shield_patterns")


class SpecialModelConduit(SpecialModelBase):
    """ConduitSpecialRenderer: the shell."""

    type: Literal["minecraft:conduit", "conduit"]

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        texture = "minecraft:entity/conduit/base"
        return {"textures": {"0": texture, "particle": texture}, "elements": entity_elements(getter, "conduit_shell")}


class SpecialModelChest(SpecialModelBase):
    """ChestSpecialRenderer: the chest model, its lid open by `openness` (ChestModel.setupAnim)."""

    type: Literal["minecraft:chest", "chest"]
    texture: str
    openness: float = 0.0
    chest_type: Literal["single", "left", "right"] = "single"

    LAYERS: ClassVar[dict[str, str]] = {
        "single": "chest",
        "left": "double_chest_left",
        "right": "double_chest_right",
    }

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        namespace, path = resolve_key(self.texture).split(":")
        texture = f"{namespace}:entity/chest/{path}"
        angle = -(clamp(0.0, self.openness, 1.0) * 1.5707964)
        return {
            "textures": {"0": texture, "particle": texture},
            "elements": entity_elements(
                getter, self.LAYERS[self.chest_type], poses={"lid": {"xRot": angle}, "lock": {"xRot": angle}}
            ),
        }


class PropertiesModel(BaseModel):
    name: str
    value: str
    signature: Optional[str] = None


class ProfileComponent(BaseModel):
    name: Optional[str] = None
    id: Optional[list[int]] | str = None
    properties: Optional[list[PropertiesModel]] = None
    texture: Optional[str] = None
    """Skin patch (PlayerSkin.Patch), the texture textures/<path>.png replaces the skin."""

    def uuid(self) -> Optional[UUID]:
        if isinstance(self.id, str):
            return UUID(self.id)
        if self.id is not None:
            # UUIDUtil.uuidFromIntArray, 4 signed 32 bit integers
            value = 0
            for i, signed in enumerate(self.id):
                value += (signed & 0xFFFFFFFF) << (32 * (3 - i))
            return UUID(int=value)
        if self.name is not None:
            return offline_player_uuid(self.name)
        return None


def offline_player_uuid(name: str) -> UUID:
    """UUIDUtil.createOfflinePlayerUUID, Java's UUID.nameUUIDFromBytes."""
    digest = bytearray(hashlib.md5(f"OfflinePlayer:{name}".encode()).digest())
    digest[6] = digest[6] & 0x0F | 0x30
    digest[8] = digest[8] & 0x3F | 0x80
    return UUID(bytes=bytes(digest))


DEFAULT_SKINS = [
    f"minecraft:entity/player/{model}/{name}"
    for model in ("slim", "wide")
    for name in ("alex", "ari", "efe", "kai", "makena", "noor", "steve", "sunny", "zuri")
]


def default_skin(uuid: Optional[UUID]) -> str:
    """DefaultPlayerSkin.get: the skin a profile shows until (or unless) its own skin loads."""
    if uuid is None:
        return DEFAULT_SKINS[6]
    # java.util.UUID.hashCode
    bits = uuid.int
    hilo = (bits >> 64) ^ (bits & 0xFFFFFFFFFFFFFFFF)
    hash_code = ((hilo >> 32) ^ hilo) & 0xFFFFFFFF
    hash_code -= 1 << 32 if hash_code >= 1 << 31 else 0
    return DEFAULT_SKINS[hash_code % len(DEFAULT_SKINS)]


class SpecialModelHeadBase(SpecialModelBase):
    """SkullBlockRenderer.submitSkull: a head model, with SkullModelBase.State's animation."""

    @staticmethod
    def head_model(getter: PackGetter, layer: str, texture: str | Image.Image, animation: float = 0.0) -> dict[str, Any]:
        # setupAnim: the head isn't turned (yRot, xRot 0), the jaw and ears follow the animation
        step = animation * math.pi * 0.2
        poses: dict[str, dict[str, float]] = {"head": {"xRot": 0.0, "yRot": 0.0}}
        if layer == "dragon_skull":
            poses["jaw"] = {"xRot": (math.sin(step) + 1.0) * 0.2}
        elif layer == "piglin_head":
            poses["left_ear"] = {"zRot": -(math.cos(step * 1.2) + 2.5) * 0.2}
            poses["right_ear"] = {"zRot": (math.cos(step) + 2.5) * 0.2}
        return {
            "textures": {"0": texture, "particle": texture},
            "elements": entity_elements(getter, layer, poses=poses),
        }


class SpecialModelPlayerHead(SpecialModelHeadBase):
    type: Literal["minecraft:player_head", "player_head"]

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        # PlayerHeadSpecialRenderer: no animation
        return self.head_model(getter, "humanoid_head", self.get_player_texture(getter, item))

    def get_player_texture(self, getter: PackGetter, item: Item) -> str | Image.Image:
        profile_data = item.components.get("minecraft:profile")
        if profile_data is None:
            return DEFAULT_SKINS[6]
        if isinstance(profile_data, str):
            profile = ProfileComponent(name=profile_data)
        else:
            profile = ProfileComponent.model_validate(profile_data)
        if profile.texture is not None:
            namespace, path = resolve_key(profile.texture).split(":", 1)
            return f"{namespace}:{path}"
        try:
            skin = self.download_skin(getter, profile)
        except Exception as e:
            log.warning(f"Could not load the skin of {profile_data}, using a default skin: {e}")
            skin = None
        return skin if skin is not None else default_skin(profile.uuid())

    def download_skin(self, getter: PackGetter, profile: ProfileComponent) -> Optional[Image.Image]:
        cache = getter._ctx.cache["model_resolver_player_skin"]
        if not profile.properties and (profile.id or profile.name):
            if profile.id:
                uuid = profile.uuid()
            else:
                url = "https://api.mojang.com/users/profiles/minecraft/" + str(profile.name)
                with open(cache.download(url), "r") as f:
                    data = json.load(f)
                if not "id" in data:
                    return None
                uuid = UUID(data["id"])
            url = f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid}"
            with open(cache.download(url), "r") as f:
                data = json.load(f)
            profile = ProfileComponent.model_validate(data)
        textures = [prop for prop in profile.properties or [] if prop.name == "textures"]
        if not textures:
            return None
        data = json.loads(base64.b64decode(textures[0].value))
        if "SKIN" not in data.get("textures", {}):
            return None
        texture_cache = cache.download(data["textures"]["SKIN"]["url"])
        img = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
        with Image.open(texture_cache) as texture:
            img.paste(texture, (0, 0))
        return img


class SpecialModelHead(SpecialModelHeadBase):
    type: Literal["minecraft:head", "head"]
    kind: Literal[
        "skeleton", "wither_skeleton", "player", "zombie", "creeper", "piglin", "dragon"
    ]
    texture: Optional[str] = None
    animation: float = 0.0

    # SkullBlockRenderer.createModel and SKIN_BY_TYPE
    HEADS: ClassVar[dict[str, tuple[str, str]]] = {
        "skeleton": ("mob_head", "minecraft:entity/skeleton/skeleton"),
        "wither_skeleton": ("mob_head", "minecraft:entity/skeleton/wither_skeleton"),
        "zombie": ("humanoid_head", "minecraft:entity/zombie/zombie"),
        "creeper": ("mob_head", "minecraft:entity/creeper/creeper"),
        "piglin": ("piglin_head", "minecraft:entity/piglin/piglin"),
        "dragon": ("dragon_skull", "minecraft:entity/enderdragon/dragon"),
        "player": ("humanoid_head", DEFAULT_SKINS[6]),
    }

    @property
    def texture_override(self) -> Optional[str]:
        # SkullSpecialRenderer: the texture is textures/entity/<path>.png
        if self.texture is None:
            return None
        namespace, path = resolve_key(self.texture).split(":", 1)
        return f"{namespace}:entity/{path}"

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        layer, texture = self.HEADS[self.kind]
        return self.head_model(getter, layer, self.texture_override or texture, self.animation)


class SpecialModelShulkerBox(SpecialModelBase):
    """ShulkerBoxSpecialRenderer: the shell, its lid raised and turned by `openness`
    (ShulkerBoxRenderer.ShulkerBoxModel.setupAnim)."""

    type: Literal["minecraft:shulker_box", "shulker_box"]
    texture: str
    openness: float = 0.0

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        namespace, path = resolve_key(self.texture).split(":")
        texture = f"{namespace}:entity/shulker/{path}"
        lid = {"x": 0.0, "y": 24.0 - self.openness * 0.5 * 16.0, "z": 0.0, "yRot": math.radians(270.0 * self.openness)}
        return {
            "textures": {"0": texture, "particle": texture},
            "elements": entity_elements(getter, "shulker_box", poses={"lid": lid}),
        }


class SpecialModelTrident(SpecialModelBase):
    type: Literal["minecraft:trident", "trident"]

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        texture = "minecraft:entity/trident/trident"
        return {"textures": {"0": texture, "particle": texture}, "elements": entity_elements(getter, "trident")}

    def glint(self) -> Optional[GlintStyle]:
        # RenderTypes.entitySolidGlint on the trident's own texture
        return GlintStyle(ENTITY_GLINT_SCALE)


class SpecialModelDecoratedPot(SpecialModelBase):
    type: Literal["minecraft:decorated_pot", "decorated_pot"]

    # Legacy list order (pre 26.3): [back, left, right, front]
    LEGACY_SIDES: ClassVar[list[str]] = ["back", "left", "right", "front"]

    def get_texture(
        self, pot_decorations: dict[str, Any] | list[str] | None, side: str
    ) -> str:
        decoration: Any = None
        if isinstance(pot_decorations, dict):
            # 26.3+ format: {"back": {"id": ...}, "front": ..., "left": ..., "right": ...}
            decoration = pot_decorations.get(side)
            if isinstance(decoration, dict):
                decoration = decoration.get("id")
        elif isinstance(pot_decorations, list):
            index = self.LEGACY_SIDES.index(side)
            if index < len(pot_decorations):
                decoration = pot_decorations[index]
        if not isinstance(decoration, str):
            return "minecraft:entity/decorated_pot/decorated_pot_side"
        decoration = resolve_key(decoration)
        if decoration == "minecraft:brick":
            return "minecraft:entity/decorated_pot/decorated_pot_side"
        namespace, path = decoration.split(":", 1)
        return f"{namespace}:entity/decorated_pot/{path.removesuffix("_sherd")}_pattern"

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        """DecoratedPotRenderer.submit: the neck, top and bottom with the base sprite, each
        side with its sherd's pattern."""
        pot_decorations = item.components.get("minecraft:pot_decorations", None)
        base = "minecraft:entity/decorated_pot/decorated_pot_base"
        sides = ("back", "left", "right", "front")
        return {
            "textures": {
                "base": base,
                "particle": base,
                **{side: self.get_texture(pot_decorations, side) for side in sides},
            },
            "elements": entity_elements(getter, "decorated_pot_base", "#base")
            + entity_elements(getter, "decorated_pot_sides", part_textures={side: f"#{side}" for side in sides}),
        }


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


class SpecialModelSignBase(SpecialModelBase):
    texture: Optional[str] = None
    wood_type: wood_types

    @property
    def used_texture(self) -> str:
        if self.texture:
            namespace, path = resolve_key(self.texture).split(":", 1)
            return f"{namespace}:entity/signs/{path}"
        if isinstance(self, SpecialModelStandingSign):
            return f"minecraft:entity/signs/{self.wood_type}"
        elif isinstance(self, SpecialModelHangingSign):
            return f"minecraft:entity/signs/hanging/{self.wood_type}"
        raise NotImplementedError()


class SpecialModelStandingSign(SpecialModelSignBase):
    type: Literal["minecraft:standing_sign", "standing_sign"]
    attachment: Literal["ground", "wall"] = "ground"


    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        assert self.attachment == "ground", "Only ground standing signs are supported"
        return {
            "credit": "Made with Blockbench",
            "textures": {"0": self.used_texture},
            "elements": [
                {
                    "from": [7, -6, 7],
                    "to": [9, 8, 9],
                    "rotation": {"angle": 0, "axis": "y", "origin": [0, -8, 7]},
                    "faces": {
                        "north": {"uv": [0.5, 8, 1, 15], "texture": "#0"},
                        "east": {"uv": [0, 8, 0.5, 15], "texture": "#0"},
                        "south": {"uv": [1.5, 8, 2, 15], "texture": "#0"},
                        "west": {"uv": [1, 8, 1.5, 15], "texture": "#0"},
                        "up": {"uv": [1, 8, 0.5, 7], "texture": "#0"},
                        "down": {"uv": [1.5, 7, 1, 8], "texture": "#0"},
                    },
                },
                {
                    "from": [-4, 8, 7],
                    "to": [20, 20, 9],
                    "rotation": {"angle": 0, "axis": "y", "origin": [-4, 6, 7]},
                    "faces": {
                        "north": {"uv": [0.5, 1, 6.5, 7], "texture": "#0"},
                        "east": {"uv": [0, 1, 0.5, 7], "texture": "#0"},
                        "south": {"uv": [7, 1, 13, 7], "texture": "#0"},
                        "west": {"uv": [6.5, 1, 7, 7], "texture": "#0"},
                        "up": {"uv": [6.5, 1, 0.5, 0], "texture": "#0"},
                        "down": {"uv": [12.5, 0, 6.5, 1], "texture": "#0"},
                    },
                },
            ],
        }


class SpecialModelHangingSign(SpecialModelSignBase):
    type: Literal["minecraft:hanging_sign", "hanging_sign"]
    attachment: Literal["wall", "ceiling", "ceiling_middle"] = "ceiling_middle" 

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        assert self.attachment == "ceiling_middle", "Only ceiling_middle hanging signs are supported"
        res = {
            "textures": {
                "0": self.used_texture,
            },
            "elements": [
                {
                    "from": [1, 0, 7],
                    "to": [15, 10, 9],
                    "rotation": {"angle": 0, "axis": "y", "origin": [1, 0, 7]},
                    "faces": {
                        "north": {"uv": [4.5, 7, 8, 12], "texture": "#0"},
                        "east": {"uv": [4, 7.25, 4.5, 12], "texture": "#0"},
                        "south": {"uv": [0.5, 7, 4, 12], "texture": "#0"},
                        "west": {"uv": [0, 7, 0.5, 12], "texture": "#0"},
                        "up": {"uv": [0.5, 6, 4, 7], "texture": "#0"},
                        "down": {"uv": [4, 7, 7.5, 6], "texture": "#0"},
                    },
                },
                {
                    "from": [2, 10, 8],
                    "to": [14, 16, 8],
                    "rotation": {"angle": 0, "axis": "y", "origin": [2, 10, 8]},
                    "faces": {
                        "north": {"uv": [6.5, 3, 3.5, 6], "texture": "#0"},
                        "south": {"uv": [3.5, 3, 6.5, 6], "texture": "#0"},
                    },
                },
            ],
        }
        return res

class SpecialModelBell(SpecialModelBase):
    type: Literal["minecraft:bell", "bell"]

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        texture = "minecraft:entity/bell/bell_body"
        layer = entity_layers(getter.opts.minecraft_version)["bell"]
        return {"textures": {"0": texture, "particle": texture}, "elements": to_elements(layer)}

class SpecialModelBook(SpecialModelBase):
    type: Literal["minecraft:book", "book"]
    open_angle: float
    """Angle (in degrees) between book cover and book centerline (0 means closed, 90 means open flat)."""
    page1: float
    """The positions of two pages inside the book. 0.0 means the page is in the leftmost position, 1.0 means the page in the rightmost position."""
    page2: float
    """The positions of two pages inside the book. 0.0 means the page is in the leftmost position, 1.0 means the page in the rightmost position."""

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        # BookModel.setupAnim with BookSpecialRenderer's state
        openness = math.radians(self.open_angle)
        shift = math.sin(openness)
        poses = {
            "left_lid": {"yRot": math.pi + openness},
            "right_lid": {"yRot": -openness},
            "left_pages": {"yRot": openness, "x": shift},
            "right_pages": {"yRot": -openness, "x": shift},
            "flip_page1": {"yRot": openness - openness * 2 * self.page1, "x": shift},
            "flip_page2": {"yRot": openness - openness * 2 * self.page2, "x": shift},
        }
        texture = "minecraft:entity/enchantment/enchanting_table_book"
        layer = entity_layers(getter.opts.minecraft_version)["book"]
        return {
            "textures": {"0": texture, "particle": texture},
            "elements": to_elements(layer, poses=poses),
        }


class SpecialModelEndCube(SpecialModelBase):
    type: Literal["minecraft:end_cube", "end_cube"]
    effect: Literal["portal", "gateway"]

    def get_model(self, getter: PackGetter, item: Item) -> dict[str, Any]:
        """A still picture of the end portal shader: the starfield on the top face only
        for a portal (at 3/4 of the block), on every face for a gateway."""
        texture = "minecraft:entity/end_portal/end_portal"
        face = {"texture": "#0", "uv": [0, 0, 16, 16]}
        if self.effect == "portal":
            elements = [{"from": [0, 12, 0], "to": [16, 12, 16], "faces": {"up": face}}]
        else:
            faces = ("down", "up", "north", "south", "west", "east")
            elements = [{"from": [0, 0, 0], "to": [16, 16, 16], "faces": {f: face for f in faces}}]
        return {"textures": {"0": texture, "particle": texture}, "elements": elements}


class SpecialModel(RootModel[Any]):
    root: Any

    @cached_property
    def special_model(self) -> SpecialModelBase:
        return validate_dispatched(self.root, SpecialModelBaseClass, "special model")
