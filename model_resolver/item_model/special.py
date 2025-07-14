import math
from pydantic import BaseModel, Field
from model_resolver.item_model.tint_source import (
    TintSource,
    to_argb,
    TintSourceConstant,
)
from typing import ClassVar, Optional, Literal, Union, Any
from model_resolver.item_model.item import Item
from model_resolver.minecraft_model import MultiTexture, TextureSource
from model_resolver.utils import PackGetterV2, clamp, resolve_key
from PIL import Image
from uuid import UUID
import json
import base64
from rich import print  # noqa


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
    ]

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        return {}

    def get_scale(self) -> float:
        return 1.0

    def get_additional_rotations(self) -> tuple[float, float, float] | None:
        return None

    def get_tints(self, getter: PackGetterV2, item: Item) -> list[TintSource]:
        return []


class SpecialModelBed(SpecialModelBase):
    type: Literal["minecraft:bed", "bed"]
    texture: str

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        namespace, path = resolve_key(self.texture).split(":")
        model: dict[str, Any] = {
            "textures": {"0": f"{namespace}:entity/bed/{path}"},
            "elements": [
                {
                    "from": [0, 0, 13],
                    "to": [3, 3, 16],
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
                    "from": [0, 3, -16],
                    "to": [16, 9, 0],
                    "faces": {
                        "north": {"uv": [5.5, 5.5, 9.5, 7], "rotation": 180, "texture": "#0"},
                        "east": {"uv": [0, 7, 1.5, 11], "rotation": 270, "texture": "#0"},
                        "west": {"uv": [5.5, 7, 7, 11], "rotation": 90, "texture": "#0"},
                        "up": {"uv": [1.5, 7, 5.5, 11], "rotation": 180, "texture": "#0"},
                        "down": {"uv": [11, 11, 7, 7], "rotation": 180, "texture": "#0"}
                    }
                },
                {
                    "from": [0, 0, -16],
                    "to": [3, 3, -13],
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
                    "from": [13, 0, -16],
                    "to": [16, 3, -13],
                    "faces": {
                        "north": {"uv": [13.25, 0.75, 14, 1.5], "texture": "#0"},
                        "east": {"uv": [12.5, 0.75, 13.25, 1.5], "texture": "#0"},
                        "south": {"uv": [14.75, 0.75, 15.5, 1.5], "texture": "#0"},
                        "west": {"uv": [14, 0.75, 14.75, 1.5], "texture": "#0"},
                        "up": {"uv": [13.25, 0, 14, 0.75], "texture": "#0"},
                        "down": {"uv": [14.75, 0, 14, 0.75], "texture": "#0"}
                    }
                },
                {
                    "from": [0, 3, 0],
                    "to": [16, 9, 16],
                    "faces": {
                        "east": {"uv": [0, 1.5, 1.5, 5.5], "rotation": 270, "texture": "#0"},
                        "south": {"uv": [1.5, 0, 5.5, 1.5], "rotation": 180, "texture": "#0"},
                        "west": {"uv": [5.5, 1.5, 7, 5.5], "rotation": 90, "texture": "#0"},
                        "up": {"uv": [1.5, 1.5, 5.5, 5.5], "rotation": 180, "texture": "#0"},
                        "down": {"uv": [11, 5.5, 7, 1.5], "rotation": 180, "texture": "#0"}
                    }
                },
                {
                    "from": [13, 0, 13],
                    "to": [16, 3, 16],
                    "faces": {
                        "north": {"uv": [14, 2.25, 14.75, 3], "texture": "#0"},
                        "east": {"uv": [13.25, 2.25, 14, 3], "texture": "#0"},
                        "south": {"uv": [12.5, 2.25, 13.25, 3], "texture": "#0"},
                        "west": {"uv": [14.75, 2.25, 15.5, 3], "texture": "#0"},
                        "up": {"uv": [13.25, 1.5, 14, 2.25], "rotation": 270, "texture": "#0"},
                        "down": {"uv": [14, 1.5, 14.75, 2.25], "rotation": 270, "texture": "#0"}
                    }
                }
            ],
        }
        return model


class SpecialModelBaseLayer(SpecialModelBase):
    COLOR_STRING_TO_ARGB: ClassVar[dict[str, int]] ={
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
    base_texture_nopattern: ClassVar[str]
    
    @property
    def entity_type(self) -> str:
        return resolve_key(self.type).split(":")[-1]

    def get_base_color(self, item: Item) -> str | None:
        raise NotImplementedError("This method should be implemented in subclasses")

    def get_color(self, color: str) -> TintSourceConstant:
        if color not in self.COLOR_STRING_TO_ARGB:
            raise ValueError(f"Invalid color {color} for shield")
        argb = self.COLOR_STRING_TO_ARGB[color]
        argb = to_argb(argb)
        return TintSourceConstant(type="constant", value=(argb[1], argb[2], argb[3]))
    

    def get_texture(self, getter: PackGetterV2, item: Item) -> TextureSource:
        if not (base_color := self.get_base_color(item)):
            return self.base_texture_nopattern
        res: list[MultiTexture] = []
        res.append((self.base_texture, None))
        res.append((f"minecraft:entity/{self.entity_type}/base", self.get_color(base_color)))

        for pattern in item.components.get("minecraft:banner_patterns", []):
            pattern_id = resolve_key(pattern["pattern"])
            namespace, path = pattern_id.split(":")
            res.append((f"{namespace}:entity/{self.entity_type}/{path}", self.get_color(pattern["color"])))


        return tuple(res)

class SpecialModelBanner(SpecialModelBaseLayer):
    type: Literal["minecraft:banner", "banner"]
    color: str

    base_texture: ClassVar[str] = "minecraft:entity/banner_base"
    base_texture_nopattern: ClassVar[str] = "minecraft:entity/banner_base"

    def get_base_color(self, item: Item) -> str | None:
        return self.color
    
    def get_scale(self) -> float:
        return 0.75/0.5325
    
    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        texture = self.get_texture(getter, item)
        res = {
            "textures": {
                "0": texture,
            },
            "elements": [
                {
                    "from": [7.5, 1.5, 7.5],
                    "to": [8.5, 22.5, 8.5],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 2, 8]},
                    "faces": {
                        "north": {"uv": [12.5, 0.5, 13, 11], "texture": "#0"},
                        "east": {"uv": [12, 0.5, 12.5, 11], "texture": "#0"},
                        "south": {"uv": [11.5, 0.5, 12, 11], "texture": "#0"},
                        "west": {"uv": [11, 0.5, 11.5, 11], "texture": "#0"},
                        "up": {"uv": [11.5, 0, 12, 0.5], "rotation": 180, "texture": "#0"},
                        "down": {"uv": [12, 0, 12.5, 0.5], "rotation": 180, "texture": "#0"}
                    }
                },
                {
                    "from": [3, 22.5, 7.5],
                    "to": [13, 23.5, 8.5],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 24, 8]},
                    "faces": {
                        "north": {"uv": [6, 11, 11, 11.5], "texture": "#0"},
                        "east": {"uv": [5.5, 11, 6, 11.5], "texture": "#0"},
                        "south": {"uv": [0.5, 11, 5.5, 11.5], "texture": "#0"},
                        "west": {"uv": [0, 11, 0.5, 11.5], "texture": "#0"},
                        "up": {"uv": [0.5, 10.5, 5.5, 11], "texture": "#0"},
                        "down": {"uv": [5.5, 10.5, 10.5, 11], "texture": "#0"}
                    }
                },
                {
                    "from": [3, 3.5, 8.5],
                    "to": [13, 23.5, 9.5],
                    "rotation": {"angle": 0, "axis": "y", "origin": [9, 4, 9]},
                    "faces": {
                        "north": {"uv": [5.5, 0.25, 10.5, 10.25], "texture": "#0"},
                        "east": {"uv": [5.25, 0.25, 5.5, 10.25], "texture": "#0"},
                        "south": {"uv": [0.25, 0.25, 5.25, 10.25], "texture": "#0"},
                        "west": {"uv": [0, 0.25, 0.25, 10.25], "texture": "#0"},
                        "up": {"uv": [0.25, 0, 5.25, 0.25], "texture": "#0"},
                        "down": {"uv": [5.25, 0, 10.25, 0.25], "texture": "#0"}
                    }
                }
            ]
        }
        return res

class SpecialModelShield(SpecialModelBaseLayer):
    type: Literal["minecraft:shield", "shield"]

    base_texture: ClassVar[str] = "minecraft:entity/shield_base"
    base_texture_nopattern: ClassVar[str] = "minecraft:entity/shield_base_nopattern"

    def get_base_color(self, item: Item) -> str | None:
        if not (base_color := item.components.get("minecraft:base_color")):
            return None
        return base_color
        
    
    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        texture = self.get_texture(getter, item)
        res = {
            "textures": {"0": texture},
            "elements": [
                {
                    "from": [-6, -11, 1],
                    "to": [6, 11, 2],
                    "faces": {
                        "north": {"uv": [3.5, 0.25, 6.5, 5.75], "texture": "#0"},
                        "east": {"uv": [3.25, 0.25, 3.5, 5.75], "texture": "#0"},
                        "south": {"uv": [0.25, 0.25, 3.25, 5.75], "texture": "#0"},
                        "west": {"uv": [0, 0.25, 0.25, 5.75], "texture": "#0"},
                        "up": {
                            "uv": [0.25, 0, 3, 0.25],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "down": {
                            "uv": [3.25, 0, 6.25, 0.25],
                            "rotation": 180,
                            "texture": "#0",
                        },
                    },
                },
                {
                    "from": [-1, -3, -5],
                    "to": [1, 3, 1],
                    "faces": {
                        "north": {"uv": [10, 1.5, 10.5, 3], "texture": "#0"},
                        "east": {"uv": [8.5, 1.5, 10, 3], "texture": "#0"},
                        "south": {"uv": [8, 1.5, 8.5, 3], "texture": "#0"},
                        "west": {"uv": [6.5, 1.5, 8, 3], "texture": "#0"},
                        "up": {
                            "uv": [8, 0, 8.5, 1.5],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "down": {
                            "uv": [8.5, 0, 9, 1.5],
                            "rotation": 180,
                            "texture": "#0",
                        },
                    },
                },
            ],
            "gui_light": "front",
        }

        return res


class SpecialModelConduit(SpecialModelBase):
    type: Literal["minecraft:conduit", "conduit"]

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        model: dict[str, Any] = {
            "textures": {
                "0": "entity/conduit/base",
            },
            "elements": [
                {
                    "from": [5, 5, 5],
                    "to": [11, 11, 11],
                    "faces": {
                        "north": {"uv": [12, 12, 9, 6], "texture": "#0"},
                        "east": {"uv": [3, 12, 0, 6], "texture": "#0"},
                        "south": {"uv": [6, 12, 3, 6], "texture": "#0"},
                        "west": {"uv": [9, 12, 6, 6], "texture": "#0"},
                        "up": {"uv": [9, 0, 6, 6], "texture": "#0"},
                        "down": {"uv": [6, 6, 3, 0], "texture": "#0"},
                    },
                }
            ],
        }
        return model


class SpecialModelChest(SpecialModelBase):
    type: Literal["minecraft:chest", "chest"]
    texture: str
    openness: float = 0.0

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        openness = clamp(0.0, self.openness, 1.0)
        angle = openness * 90
        namespace, path = resolve_key(self.texture).split(":")
        model: dict[str, Any] = {
            "elements": [
                {
                    "from": [1, 0, 1],
                    "to": [15, 10, 15],
                    "faces": {
                        "north": {
                            "uv": [3.5, 8.25, 7, 10.75],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "east": {
                            "uv": [0, 8.25, 3.5, 10.75],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "south": {
                            "uv": [10.5, 8.25, 14, 10.75],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "west": {
                            "uv": [7, 8.25, 10.5, 10.75],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "up": {
                            "uv": [7, 4.75, 10.5, 8.25],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "down": {
                            "uv": [3.5, 4.75, 7, 8.25],
                            "rotation": 180,
                            "texture": "#0",
                        },
                    },
                },
                {
                    "from": [1, 9, 1],
                    "to": [15, 14, 15],
                    "rotation": {"angle": -angle, "axis": "x", "origin": [8, 10, 1]},
                    "faces": {
                        "north": {
                            "uv": [3.5, 3.5, 7, 4.75],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "east": {
                            "uv": [0, 3.5, 3.5, 4.75],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "south": {
                            "uv": [10.5, 3.5, 14, 4.75],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "west": {
                            "uv": [7, 3.5, 10.5, 4.75],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "up": {
                            "uv": [7, 0, 10.5, 3.5],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "down": {
                            "uv": [3.5, 0, 7, 3.5],
                            "rotation": 180,
                            "texture": "#0",
                        },
                    },
                },
                {
                    "from": [7, 7, 14],
                    "to": [9, 11, 16],
                    "rotation": {"angle": -angle, "axis": "x", "origin": [8, 10, 1]},
                    "faces": {
                        "north": {
                            "uv": [1, 0.25, 1.5, 1.25],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "east": {
                            "uv": [0.75, 0.25, 1, 1.25],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "south": {
                            "uv": [0.25, 0.25, 0.75, 1.25],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "west": {
                            "uv": [0, 0.25, 0.25, 1.25],
                            "rotation": 180,
                            "texture": "#0",
                        },
                        "up": {"uv": [0.25, 0, 0.75, 0.25], "texture": "#0"},
                        "down": {"uv": [0.75, 0, 1.25, 0.25], "texture": "#0"},
                    },
                },
            ],
            "textures": {"0": f"{namespace}:entity/chest/{path}"},
        }
        return model

    def get_scale(self) -> float:
        return 0.75


class PropertiesModel(BaseModel):
    name: str
    value: str
    signature: Optional[str] = None


class ProfileComponent(BaseModel):
    name: Optional[str] = None
    id: Optional[list[int]] | str = None
    properties: Optional[list[PropertiesModel]] = None


class SpecialModelBaseHead(SpecialModelBase):

    @staticmethod
    def get_model_player(
        getter: PackGetterV2, item: Item, texture: str | Image.Image
    ) -> dict[str, Any]:
        model = {
            "textures": {"1": texture, "particle": texture},
            "elements": [
                {
                    "from": [4, 0, 4],
                    "to": [12, 8, 12],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "north": {"uv": [6, 2, 8, 4], "texture": "#1"},
                        "east": {"uv": [4, 2, 6, 4], "texture": "#1"},
                        "south": {"uv": [2, 2, 4, 4], "texture": "#1"},
                        "west": {"uv": [0, 2, 2, 4], "texture": "#1"},
                        "up": {"uv": [2, 0, 4, 2], "rotation": 180, "texture": "#1"},
                        "down": {"uv": [4, 0, 6, 2], "rotation": 180, "texture": "#1"},
                    },
                },
                {
                    "from": [3.75, -0.25, 3.75],
                    "to": [12.25, 8.25, 12.25],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "north": {"uv": [14, 2, 16, 4], "texture": "#1"},
                        "east": {"uv": [12, 2, 14, 4], "texture": "#1"},
                        "south": {"uv": [10, 2, 12, 4], "texture": "#1"},
                        "west": {"uv": [8, 2, 10, 4], "texture": "#1"},
                        "up": {"uv": [10, 0, 12, 2], "rotation": 180, "texture": "#1"},
                        "down": {
                            "uv": [12, 0, 14, 2],
                            "rotation": 180,
                            "texture": "#1",
                        },
                    },
                },
            ],
        }
        return model


class SpecialModelPlayerHead(SpecialModelBaseHead):
    type: Literal["minecraft:player_head", "player_head"]

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        return self.get_model_player(
            getter, item, self.get_player_texture(getter, item)
        )

    def get_player_texture(self, getter: PackGetterV2, item: Item) -> str | Image.Image:
        DEFAULT_TEXTURE = "minecraft:entity/player/wide/steve"
        if not item.components:
            return DEFAULT_TEXTURE
        if not "minecraft:profile" in item.components:
            return DEFAULT_TEXTURE
        cache = getter._ctx.cache["model_resolver_player_skin"]
        if not isinstance(item.components["minecraft:profile"], str):
            profile = ProfileComponent.model_validate(
                item.components["minecraft:profile"]
            )
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
                    id += unsigned * 2 ** (32 * (3 - i))
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


class SpecialModelHead(SpecialModelBaseHead):
    type: Literal["minecraft:head", "head"]
    kind: Literal[
        "skeleton", "wither_skeleton", "player", "zombie", "creeper", "piglin", "dragon"
    ]
    texture: Optional[str] = None
    animation: float = 0.0

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        match self.kind:
            case "player":
                texture = "minecraft:entity/player/wide/steve"
                return self.get_model_player(getter, item, texture)
            case "zombie":
                return self.get_model_zombie(getter, item)
            case "skeleton":
                texture = self.texture or "minecraft:entity/skeleton/skeleton"
                return self.get_generic_mob_head(getter, item, texture)
            case "wither_skeleton":
                texture = self.texture or "minecraft:entity/skeleton/wither_skeleton"
                return self.get_generic_mob_head(getter, item, texture)
            case "creeper":
                texture = self.texture or "minecraft:entity/creeper/creeper"
                return self.get_generic_mob_head(getter, item, texture)
            case "piglin":
                return self.get_piglin_head(getter, item)
            case "dragon":
                return self.get_dragon_head(getter, item)
            case _:
                raise NotImplementedError(f"Head kind {self.kind} not implemented")

    def get_dragon_head(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        texture = self.texture or "minecraft:entity/enderdragon/dragon"
        model = {
            "textures": {"0": texture, "particle": texture},
            "elements": [
                {
                    "name": "head",
                    "from": [0, -2, 2],
                    "to": [16, 14, 18],
                    "rotation": {"angle": 0, "axis": "y", "origin": [2, -2, 5]},
                    "faces": {
                        "north": {"uv": [10, 2.875, 11, 3.875], "texture": "#0"},
                        "east": {"uv": [9, 2.875, 10, 3.875], "texture": "#0"},
                        "south": {"uv": [8, 2.875, 9, 3.875], "texture": "#0"},
                        "west": {"uv": [7, 2.875, 8, 3.875], "texture": "#0"},
                        "up": {"uv": [8, 1.875, 9, 2.875], "texture": "#0"},
                        "down": {"uv": [9, 1.875, 10, 2.875], "texture": "#0"},
                    },
                },
                {
                    "name": "right ear",
                    "from": [3, 14, 6],
                    "to": [5, 18, 12],
                    "rotation": {"angle": 0, "axis": "y", "origin": [3, 14, 6]},
                    "faces": {
                        "north": {"uv": [0.875, 0.375, 1, 0.625], "texture": "#0"},
                        "east": {"uv": [0.375, 0.375, 0, 0.625], "texture": "#0"},
                        "south": {"uv": [0.375, 0.375, 0.5, 0.625], "texture": "#0"},
                        "west": {"uv": [0.875, 0.375, 0.5, 0.625], "texture": "#0"},
                        "up": {"uv": [0.375, 0, 0.5, 0.375], "texture": "#0"},
                        "down": {"uv": [0.5, 0, 0.625, 0.375], "texture": "#0"},
                    },
                },
                {
                    "name": "left ear",
                    "from": [11, 14, 6],
                    "to": [13, 18, 12],
                    "rotation": {"angle": 0, "axis": "y", "origin": [11, 14, 6]},
                    "faces": {
                        "north": {"uv": [3.875, 0.375, 4, 0.625], "texture": "#0"},
                        "east": {"uv": [3.375, 0.375, 3, 0.625], "texture": "#0"},
                        "south": {"uv": [3.375, 0.375, 3.5, 0.625], "texture": "#0"},
                        "west": {"uv": [3.875, 0.375, 3.5, 0.625], "texture": "#0"},
                        "up": {"uv": [3.375, 0, 3.5, 0.375], "texture": "#0"},
                        "down": {"uv": [3.5, 0, 3.625, 0.375], "texture": "#0"},
                    },
                },
                {
                    "name": "up mouth",
                    "from": [2, 2, 16],
                    "to": [14, 7, 32],
                    "rotation": {"angle": 0, "axis": "y", "origin": [2, 2, 16]},
                    "faces": {
                        "north": {"uv": [13.75, 3.75, 14.5, 4.75], "texture": "#0"},
                        "east": {"uv": [12.75, 3.75, 13.75, 4.0625], "texture": "#0"},
                        "south": {"uv": [12, 3.75, 12.75, 4.0625], "texture": "#0"},
                        "west": {"uv": [11, 3.75, 12, 4.0625], "texture": "#0"},
                        "up": {"uv": [12, 2.75, 12.75, 3.75], "texture": "#0"},
                        "down": {"uv": [12.75, 3.75, 13.5, 2.75], "texture": "#0"},
                    },
                },
                {
                    "name": "down mouth",
                    "from": [2, -2, 16],
                    "to": [14, 2, 32],
                    "rotation": {
                        "angle": self.get_dragon_angle(),
                        "axis": "x",
                        "origin": [8, 2, 16],
                    },
                    "faces": {
                        "north": {"uv": [13.75, 5.0625, 14.5, 5.3125], "texture": "#0"},
                        "east": {"uv": [12.75, 5.0625, 13.75, 5.3125], "texture": "#0"},
                        "south": {"uv": [12, 5.0625, 12.75, 5.3125], "texture": "#0"},
                        "west": {"uv": [11, 5.0625, 12, 5.3125], "texture": "#0"},
                        "up": {"uv": [12, 4.0625, 12.75, 5.0625], "texture": "#0"},
                        "down": {"uv": [12.75, 5.0625, 13.5, 4.0625], "texture": "#0"},
                    },
                },
                {
                    "name": "right nose",
                    "from": [3, 7, 26],
                    "to": [5, 9, 30],
                    "rotation": {"angle": 0, "axis": "y", "origin": [3, 7, 26]},
                    "faces": {
                        "north": {"uv": [7.375, 0.25, 7.625, 0.375], "texture": "#0"},
                        "east": {"uv": [7, 0.25, 7.25, 0.375], "texture": "#0"},
                        "south": {"uv": [7.625, 0.25, 7.75, 0.375], "texture": "#0"},
                        "west": {"uv": [7.375, 0.25, 7.625, 0.375], "texture": "#0"},
                        "up": {"uv": [7.25, 0, 7.375, 0.25], "texture": "#0"},
                        "down": {"uv": [7.375, 0, 7.5, 0.25], "texture": "#0"},
                    },
                },
                {
                    "name": "left nose",
                    "from": [11, 7, 26],
                    "to": [13, 9, 30],
                    "rotation": {"angle": 0, "axis": "y", "origin": [11, 7, 26]},
                    "faces": {
                        "north": {"uv": [7.375, 0.25, 7.625, 0.375], "texture": "#0"},
                        "east": {"uv": [7, 0.25, 7.25, 0.375], "texture": "#0"},
                        "south": {"uv": [7.625, 0.25, 7.75, 0.375], "texture": "#0"},
                        "west": {"uv": [7.375, 0.25, 7.625, 0.375], "texture": "#0"},
                        "up": {"uv": [7.25, 0, 7.375, 0.25], "texture": "#0"},
                        "down": {"uv": [7.375, 0, 7.5, 0.25], "texture": "#0"},
                    },
                },
            ],
        }
        return model

    def get_dragon_angle(self) -> float:
        f = self.animation
        jaw = (math.sin(f * math.pi * 0.2) + 1.0) * 0.2
        # convert to degrees
        jaw = math.degrees(jaw)
        return jaw

    def get_piglin_head(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        texture = self.texture or "minecraft:entity/piglin/piglin"
        left_ear, right_ear = self.get_piglin_angles()
        model = {
            "textures": {"0": texture, "particle": texture},
            "elements": [
                {
                    "name": "head",
                    "from": [3, 0, 4],
                    "to": [13, 8, 12],
                    "faces": {
                        "north": {"uv": [6.5, 2, 9, 4], "texture": "#0"},
                        "east": {"uv": [4.5, 2, 6.5, 4], "texture": "#0"},
                        "south": {"uv": [2, 2, 4.5, 4], "texture": "#0"},
                        "west": {"uv": [0, 2, 2, 4], "texture": "#0"},
                        "up": {"uv": [2, 0, 4.5, 2], "texture": "#0"},
                        "down": {"uv": [4.5, 2, 7, 0], "texture": "#0"},
                    },
                },
                {
                    "name": "center nose",
                    "from": [6, 0, 12],
                    "to": [10, 4, 13],
                    "faces": {
                        "north": {"uv": [9.25, 0.5, 10.25, 1.5], "texture": "#0"},
                        "east": {"uv": [9, 0.5, 9.25, 1.5], "texture": "#0"},
                        "south": {"uv": [8, 0.5, 9, 1.5], "texture": "#0"},
                        "west": {"uv": [7.75, 0.5, 8, 1.5], "texture": "#0"},
                        "up": {"uv": [8, 0.25, 9, 0.5], "texture": "#0"},
                        "down": {"uv": [9, 0.25, 10, 0.5], "texture": "#0"},
                    },
                },
                {
                    "name": "right nose",
                    "from": [5, 0, 12],
                    "to": [6, 2, 13],
                    "faces": {
                        "north": {"uv": [1.25, 0.25, 1.5, 0.75], "texture": "#0"},
                        "east": {"uv": [1, 0.25, 1.25, 0.75], "texture": "#0"},
                        "south": {"uv": [0.75, 0.25, 1, 0.75], "texture": "#0"},
                        "west": {"uv": [0.5, 0.25, 0.75, 0.75], "texture": "#0"},
                        "up": {"uv": [0.75, 0, 1, 0.25], "texture": "#0"},
                        "down": {"uv": [1, 0, 1.25, 0.25], "texture": "#0"},
                    },
                },
                {
                    "name": "left nose",
                    "from": [10, 0, 12],
                    "to": [11, 2, 13],
                    "faces": {
                        "north": {"uv": [1.25, 1.25, 1.5, 1.75], "texture": "#0"},
                        "east": {"uv": [1, 1.25, 1.25, 1.75], "texture": "#0"},
                        "south": {"uv": [0.75, 1.25, 1, 1.75], "texture": "#0"},
                        "west": {"uv": [0.5, 1.25, 0.75, 1.75], "texture": "#0"},
                        "up": {"uv": [0.75, 1, 1, 1.25], "texture": "#0"},
                        "down": {"uv": [1, 1, 1.25, 1.25], "texture": "#0"},
                    },
                },
                {
                    "name": "right ear",
                    "from": [1, 1, 5],
                    "to": [2, 7, 10],
                    "rotation": {
                        "angle": left_ear,
                        "axis": "z",
                        "origin": [1.5, 4, 7.5],
                    },
                    "faces": {
                        "north": {"uv": [12, 2.5, 12.25, 3.75], "texture": "#0"},
                        "east": {"uv": [11, 2.5, 12, 3.75], "texture": "#0"},
                        "south": {"uv": [10.75, 2.5, 11, 3.75], "texture": "#0"},
                        "west": {"uv": [9.75, 2.5, 10.75, 3.75], "texture": "#0"},
                        "up": {"uv": [10.75, 1.5, 11, 2.5], "texture": "#0"},
                        "down": {"uv": [11, 1.5, 11.25, 2.5], "texture": "#0"},
                    },
                },
                {
                    "name": "left ear",
                    "from": [14, 1, 5],
                    "to": [15, 7, 10],
                    "rotation": {
                        "angle": right_ear,
                        "axis": "z",
                        "origin": [14.5, 4, 7.5],
                    },
                    "faces": {
                        "north": {"uv": [15, 2.5, 15.25, 3.75], "texture": "#0"},
                        "east": {"uv": [14, 2.5, 15, 3.75], "texture": "#0"},
                        "south": {"uv": [13.75, 2.5, 14, 3.75], "texture": "#0"},
                        "west": {"uv": [12.75, 2.5, 13.75, 3.75], "texture": "#0"},
                        "up": {"uv": [13.75, 1.5, 14, 2.5], "texture": "#0"},
                        "down": {"uv": [14, 1.5, 14.25, 2.5], "texture": "#0"},
                    },
                },
            ],
        }
        return model

    def get_piglin_angles(self) -> tuple[float, float]:
        f = self.animation
        left_ear = -(math.cos(f * math.pi * 0.2 * 1.2) + 2.5) * 0.2
        right_ear = (math.cos(f * math.pi * 0.2) + 2.5) * 0.2
        # convert to degrees
        left_ear = math.degrees(left_ear)
        right_ear = math.degrees(right_ear)
        return left_ear, right_ear

    def get_model_zombie(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        texture = self.texture or "minecraft:entity/zombie/zombie"
        model = {
            "textures": {"1": texture, "particle": texture},
            "elements": [
                {
                    "from": [4, 0, 4],
                    "to": [12, 8, 12],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "north": {"uv": [6, 2, 8, 4], "texture": "#1"},
                        "east": {"uv": [4, 2, 6, 4], "texture": "#1"},
                        "south": {"uv": [2, 2, 4, 4], "texture": "#1"},
                        "west": {"uv": [0, 2, 2, 4], "texture": "#1"},
                        "up": {"uv": [2, 0, 4, 2], "rotation": 180, "texture": "#1"},
                        "down": {"uv": [4, 0, 6, 2], "rotation": 180, "texture": "#1"},
                    },
                }
            ],
        }
        return model

    def get_generic_mob_head(
        self, getter: PackGetterV2, item: Item, texture: str
    ) -> dict[str, Any]:
        model = {
            "textures": {"0": texture, "particle": texture},
            "elements": [
                {
                    "from": [4, 0, 4],
                    "to": [12, 8, 12],
                    "faces": {
                        "north": {"uv": [6, 4, 8, 8], "texture": "#0"},
                        "east": {"uv": [4, 4, 6, 8], "texture": "#0"},
                        "south": {"uv": [2, 4, 4, 8], "texture": "#0"},
                        "west": {"uv": [0, 4, 2, 8], "texture": "#0"},
                        "up": {"uv": [2, 0, 4, 4], "texture": "#0"},
                        "down": {"uv": [4, 0, 6, 4], "texture": "#0"},
                    },
                }
            ],
        }
        return model

    def get_scale(self) -> float:
        if self.kind == "dragon":
            return 0.75
        return 1


class SpecialModelShulkerBox(SpecialModelBase):
    type: Literal["minecraft:shulker_box", "shulker_box"]
    texture: str
    openness: float = 0.0
    orientation: Literal["down", "east", "north", "south", "up", "west"] = "up"

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        namespace, path = resolve_key(self.texture).split(":")
        texture = f"{namespace}:entity/shulker/{path}"
        x = clamp(0, self.openness * 8, 8)
        rotation = -clamp(0, self.openness * 90 * 3, 90 * 3)
        model: dict[str, Any] = {
            "credit": "Made with Blockbench",
            "textures": {
                "0": texture,
            },
            "elements": [
                {
                    "name": "down_down",
                    "from": [0, 0, 0],
                    "to": [16, 0, 16],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "up": {"uv": [8, 7, 12, 11], "texture": "#0"},
                        "down": {"uv": [8, 7, 12, 11], "texture": "#0"},
                    },
                },
                {
                    "name": "down_north",
                    "from": [0, 0, 0],
                    "to": [16, 8, 0],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "north": {"uv": [8, 11, 12, 13], "texture": "#0"},
                        "south": {"uv": [8, 11, 12, 13], "texture": "#0"},
                    },
                },
                {
                    "name": "down_south",
                    "from": [0, 0, 16],
                    "to": [16, 8, 16],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "north": {"uv": [0, 11, 4, 13], "texture": "#0"},
                        "south": {"uv": [0, 11, 4, 13], "texture": "#0"},
                    },
                },
                {
                    "name": "down_east",
                    "from": [16, 0, 0],
                    "to": [16, 8, 16],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "east": {"uv": [4, 11, 8, 13], "texture": "#0"},
                        "west": {"uv": [4, 11, 8, 13], "texture": "#0"},
                    },
                },
                {
                    "name": "down_west",
                    "from": [0, 0, 0],
                    "to": [0, 8, 16],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "east": {"uv": [12, 11, 16, 13], "texture": "#0"},
                        "west": {"uv": [12, 11, 16, 13], "texture": "#0"},
                    },
                },
                {
                    "name": "down_up",
                    "from": [0, 8, 0],
                    "to": [16, 8, 16],
                    "rotation": {"angle": 0, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "up": {"uv": [4, 7, 8, 11], "texture": "#0"},
                        "down": {"uv": [4, 7, 8, 11], "texture": "#0"},
                    },
                },
                {
                    "name": "up_north",
                    "from": [0, 4 + x, 0],
                    "to": [16, 16 + x, 0],
                    "rotation": {"angle": rotation, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "north": {"uv": [8, 4, 12, 7], "texture": "#0"},
                        "south": {"uv": [8, 4, 12, 7], "texture": "#0"},
                    },
                },
                {
                    "name": "up_south",
                    "from": [0, 4 + x, 16],
                    "to": [16, 16 + x, 16],
                    "rotation": {"angle": rotation, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "north": {"uv": [0, 4, 4, 7], "texture": "#0"},
                        "south": {"uv": [0, 4, 4, 7], "texture": "#0"},
                    },
                },
                {
                    "name": "up_west",
                    "from": [0, 4 + x, 0],
                    "to": [0, 16 + x, 16],
                    "rotation": {"angle": rotation, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "east": {"uv": [12, 4, 16, 7], "texture": "#0"},
                        "west": {"uv": [12, 4, 16, 7], "texture": "#0"},
                    },
                },
                {
                    "name": "up_east",
                    "from": [16, 4 + x, 0],
                    "to": [16, 16 + x, 16],
                    "rotation": {"angle": rotation, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "east": {"uv": [4, 4, 8, 7], "texture": "#0"},
                        "west": {"uv": [4, 4, 8, 7], "texture": "#0"},
                    },
                },
                {
                    "name": "up_up",
                    "from": [0, 16 + x, 0],
                    "to": [16, 16 + x, 16],
                    "rotation": {"angle": rotation, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "up": {"uv": [4, 0, 8, 4], "rotation": 270, "texture": "#0"},
                        "down": {"uv": [4, 0, 8, 4], "rotation": 270, "texture": "#0"},
                    },
                },
                {
                    "name": "up_down",
                    "from": [0, 4 + x, 0],
                    "to": [16, 4 + x, 16],
                    "rotation": {"angle": rotation, "axis": "y", "origin": [8, 8, 8]},
                    "faces": {
                        "up": {"uv": [8, 0, 12, 4], "texture": "#0"},
                        "down": {"uv": [8, 0, 12, 4], "texture": "#0"},
                    },
                },
            ],
        }

        return model

    def get_additional_rotations(self) -> tuple[float, float, float] | None:
        match self.orientation:
            case "up":
                return (0, -90, 0)
            case "down":
                return (0, 90, -180)
            case "north":
                return (0, 90, -90)
            case "south":
                return (0, -90, -90)
            case "west":
                return (0, 180, -90)
            case "east":
                return (0, -90, -90)
            case _:
                raise ValueError(f"Invalid orientation {self.orientation}")





class SpecialModelTrident(SpecialModelBase):
    type: Literal["minecraft:trident", "trident"]


    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        hauteur = -11
        return {
            "textures": {
                "0": "minecraft:entity/trident",
            },
            "elements": [
                {
                    "from": [-0.5, -16+hauteur, -0.5],
                    "to": [0.5, 9+hauteur, 0.5],
                    "faces": {
                        "north": {"uv": [1.5, 3.5, 2, 16], "texture": "#0"},
                        "east": {"uv": [1, 3.5, 1.5, 16], "texture": "#0"},
                        "south": {"uv": [0.5, 3.5, 1, 16], "texture": "#0"},
                        "west": {"uv": [0, 3.5, 0.5, 16], "texture": "#0"},
                        "up": {"uv": [0.5, 3, 1, 3.5], "rotation": 180, "texture": "#0"},
                        "down": {"uv": [1, 3, 1.5, 3.5], "rotation": 180, "texture": "#0"}
                    }
                },
                {
                    "from": [-1.5, 9+hauteur, -0.5],
                    "to": [1.5, 11+hauteur, 0.5],
                    "faces": {
                        "north": {"uv": [4.5, 0.5, 6, 1.5], "texture": "#0"},
                        "east": {"uv": [4, 0.5, 4.5, 1.5], "texture": "#0"},
                        "south": {"uv": [2.5, 0.5, 4, 1.5], "texture": "#0"},
                        "west": {"uv": [2, 0.5, 2.5, 1.5], "texture": "#0"},
                        "up": {"uv": [2.5, 0, 4, 0.5], "rotation": 180, "texture": "#0"},
                        "down": {"uv": [4, 0, 5.5, 0.5], "rotation": 180, "texture": "#0"}
                    }
                },
                {
                    "from": [-0.5, 11+hauteur, -0.5],
                    "to": [0.5, 15+hauteur, 0.5],
                    "faces": {
                        "north": {"uv": [1.5, 0.5, 2, 2.5], "texture": "#0"},
                        "east": {"uv": [1, 0.5, 1.5, 2.5], "texture": "#0"},
                        "south": {"uv": [0.5, 0.5, 1, 2.5], "texture": "#0"},
                        "west": {"uv": [0, 0.5, 0.5, 2.5], "texture": "#0"},
                        "up": {"uv": [0.5, 0, 1, 0.5], "rotation": 180, "texture": "#0"},
                        "down": {"uv": [1, 0, 1.5, 0.5], "rotation": 180, "texture": "#0"}
                    }
                },
                {
                    "from": [-2.5, 10+hauteur, -0.5],
                    "to": [-1.5, 14+hauteur, 0.5],
                    "faces": {
                        "north": {"uv": [3.5, 2, 4, 4], "texture": "#0"},
                        "east": {"uv": [3, 2, 3.5, 4], "texture": "#0"},
                        "south": {"uv": [2.5, 2, 3, 4], "texture": "#0"},
                        "west": {"uv": [2, 2, 2.5, 4], "texture": "#0"},
                        "up": {"uv": [2.5, 1.5, 3, 2], "rotation": 180, "texture": "#0"},
                        "down": {"uv": [3, 1.5, 3.5, 2], "rotation": 180, "texture": "#0"}
                    }
                },
                {
                    "from": [1.5, 10+hauteur, -0.5],
                    "to": [2.5, 14+hauteur, 0.5],
                    "faces": {
                        "north": {"uv": [3.5, 2, 4, 4], "texture": "#0"},
                        "east": {"uv": [2, 2, 2.5, 4], "texture": "#0"},
                        "south": {"uv": [2.5, 2, 3, 4], "texture": "#0"},
                        "west": {"uv": [3, 2, 3.5, 4], "texture": "#0"},
                        "up": {"uv": [2.5, 1.5, 3, 2], "rotation": 180, "texture": "#0"},
                        "down": {"uv": [3, 1.5, 3.5, 2], "rotation": 180, "texture": "#0"}
                    }
                }
            ]
        }


class SpecialModelDecoratedPot(SpecialModelBase):
    type: Literal["minecraft:decorated_pot", "decorated_pot"]

    
    def get_texture(self, pot_decorations: list[str] | None, index: int) -> str:
        if pot_decorations is None or index >= len(pot_decorations):
            return "minecraft:entity/decorated_pot/decorated_pot_side"
        decoration = resolve_key(pot_decorations[index])
        if decoration == "minecraft:brick":
            return "minecraft:entity/decorated_pot/decorated_pot_side"
        namespace, path = decoration.split(":", 1)
        return f"{namespace}:entity/decorated_pot/{path.removesuffix("_sherd")}_pattern"
        

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        pot_decorations = item.components.get("minecraft:pot_decorations", None)

        model: dict[str, Any] = {
        	"textures": {
        		"base": "minecraft:entity/decorated_pot/decorated_pot_base",
        		"north": self.get_texture(pot_decorations, 0),
                "east": self.get_texture(pot_decorations, 2),
                "south": self.get_texture(pot_decorations, 3),
                "west": self.get_texture(pot_decorations, 1),
        	},
        	"elements": [
        		{
        			"from": [4.1, 17.1, 4.1],
        			"to": [11.9, 19.9, 11.9],
        			"faces": {
        				"north": {"uv": [12, 4, 16, 5.5], "texture": "#base"},
        				"east": {"uv": [8, 4, 12, 5.5], "texture": "#base"},
        				"south": {"uv": [4, 4, 8, 5.5], "texture": "#base"},
        				"west": {"uv": [0, 4, 3.5, 5.5], "texture": "#base"},
        				"up": {"uv": [4, 0, 8, 4], "texture": "#base"},
        				"down": {"uv": [8, 4, 12, 0], "texture": "#base"}
        			}
        		},
        		{
        			"from": [4.8, 15.8, 4.8],
        			"to": [11.2, 17.2, 11.2],
        			"faces": {
        				"north": {"uv": [9, 5.5, 12, 6], "texture": "#base"},
        				"east": {"uv": [6, 5.5, 9, 6], "texture": "#base"},
        				"south": {"uv": [3, 5.5, 6, 6], "texture": "#base"},
        				"west": {"uv": [0, 5.5, 3, 6], "texture": "#base"},
        				"up": {"uv": [3, 2.5, 6, 5.5], "texture": "#base"},
        				"down": {"uv": [6, 5.5, 9, 2.5], "texture": "#base"}
        			}
        		},
        		{
        			"from": [1, 0, 1],
        			"to": [15, 16, 15],
        			"faces": {
        				"north": {"uv": [1, 0, 15, 16], "texture": "#north"},
        				"east": {"uv": [1, 0, 15, 16], "texture": "#east"},
        				"south": {"uv": [1, 0, 15, 16], "texture": "#south"},
        				"west": {"uv": [1, 0, 15, 16], "texture": "#west"},
        				"up": {"uv": [7, 13.5, 14, 6.5], "texture": "#base"},
        				"down": {"uv": [0, 6.5, 7, 13.5], "texture": "#base"}
        			}
        		}
        	]
        }
        return model


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

    def get_scale(self) -> float:
        return 0.75

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
        self.used_texture
        return {
            "credit": "Made with Blockbench",
            "textures": {"0": "entity/signs/jungle", "particle": "entity/signs/jungle"},
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

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any]:
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
                        "down": {"uv": [4, 7, 7.5, 6], "texture": "#0"}
                    }
                },
                {
                    "from": [2, 10, 8],
                    "to": [14, 16, 8],
                    "rotation": {"angle": 0, "axis": "y", "origin": [2, 10, 8]},
                    "faces": {
                        "north": {"uv": [6.5, 3, 3.5, 6], "texture": "#0"},
                        "south": {"uv": [3.5, 3, 6.5, 6], "texture": "#0"}
                    }
                }
            ]
        }
        return res


type SpecialModel = Union[
    SpecialModelBed,
    SpecialModelBanner,
    SpecialModelConduit,
    SpecialModelChest,
    SpecialModelPlayerHead,
    SpecialModelHead,
    SpecialModelShulkerBox,
    SpecialModelShield,
    SpecialModelTrident,
    SpecialModelDecoratedPot,
    SpecialModelStandingSign,
    SpecialModelHangingSign,
]
