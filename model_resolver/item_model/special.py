import math
from turtle import left
from pydantic import BaseModel, Field
from model_resolver.item_model.tint_source import TintSource
from typing import Optional, Literal, ClassVar, Generator, Union, Any
from beet import Context
from beet.contrib.vanilla import Vanilla
from model_resolver.item_model.item import Item
from model_resolver.utils import ModelResolverOptions, PackGetterV2, clamp, resolve_key
from model_resolver.minecraft_model import MinecraftModel, resolve_model
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

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any] | tuple[dict[str, Any], float]:
        return {}


class SpecialModelBed(SpecialModelBase):
    type: Literal["minecraft:bed", "bed"]
    texture: str


class SpecialModelBanner(SpecialModelBase):
    type: Literal["minecraft:banner", "banner"]
    color: str


class SpecialModelConduit(SpecialModelBase):
    type: Literal["minecraft:conduit", "conduit"]


class SpecialModelChest(SpecialModelBase):
    type: Literal["minecraft:chest", "chest"]
    texture: str
    openness: float = 0.0

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any] | tuple[dict[str, Any], float]:
        openness = clamp(0.0, self.openness, 1.0)
        angle = openness * 90
        namespace, path = resolve_key(self.texture).split(":")
        model: dict[str, Any] | tuple[dict[str, Any], float] = {
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


class PropertiesModel(BaseModel):
    name: str
    value: str
    signature: Optional[str] = None


class ProfileComponent(BaseModel):
    name: Optional[str] = None
    id: Optional[list[int]] | str = None
    properties: Optional[list[PropertiesModel]] = None


class SpecialModelHead(SpecialModelBase):
    type: Literal["minecraft:head", "head"]
    kind: Literal[
        "skeleton", "wither_skeleton", "player", "zombie", "creeper", "piglin", "dragon"
    ]
    texture: Optional[str] = None
    animation: float = 0.0

    def get_model(self, getter: PackGetterV2, item: Item) -> dict[str, Any] | tuple[dict[str, Any], float]:
        match self.kind:
            case "player":
                return self.get_model_player(getter, item)
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

    def get_dragon_head(self, getter: PackGetterV2, item: Item) -> dict[str, Any] | tuple[dict[str, Any], float]:
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
                        "down": {"uv": [9, 1.875, 10, 2.875], "texture": "#0"}
                    }
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
                        "down": {"uv": [0.5, 0, 0.625, 0.375], "texture": "#0"}
                    }
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
                        "down": {"uv": [3.5, 0, 3.625, 0.375], "texture": "#0"}
                    }
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
                        "down": {"uv": [12.75, 3.75, 13.5, 2.75], "texture": "#0"}
                    }
                },
                {
                    "name": "down mouth",
                    "from": [2, -2, 16],
                    "to": [14, 2, 32],
                    "rotation": {"angle": self.get_dragon_angle(), "axis": "x", "origin": [8, 2, 16]},
                    "faces": {
                        "north": {"uv": [13.75, 5.0625, 14.5, 5.3125], "texture": "#0"},
                        "east": {"uv": [12.75, 5.0625, 13.75, 5.3125], "texture": "#0"},
                        "south": {"uv": [12, 5.0625, 12.75, 5.3125], "texture": "#0"},
                        "west": {"uv": [11, 5.0625, 12, 5.3125], "texture": "#0"},
                        "up": {"uv": [12, 4.0625, 12.75, 5.0625], "texture": "#0"},
                        "down": {"uv": [12.75, 5.0625, 13.5, 4.0625], "texture": "#0"}
                    }
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
                        "down": {"uv": [7.375, 0, 7.5, 0.25], "texture": "#0"}
                    }
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
                        "down": {"uv": [7.375, 0, 7.5, 0.25], "texture": "#0"}
                    }
                }
            ],
        }
        return model, 0.75
    
    def get_dragon_angle(self) -> float:
        f = self.animation
        jaw = (math.sin(f * math.pi * 0.2) + 1.0) * 0.2
        # convert to degrees
        jaw = math.degrees(jaw)
        return jaw

    def get_piglin_head(self, getter: PackGetterV2, item: Item) -> dict[str, Any] | tuple[dict[str, Any], float]:
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
                    "rotation": {"angle": left_ear, "axis": "z", "origin": [1.5, 4, 7.5]},
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
                    "rotation": {"angle": right_ear, "axis": "z", "origin": [14.5, 4, 7.5]},
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
        

    def get_model_zombie(self, getter: PackGetterV2, item: Item) -> dict[str, Any] | tuple[dict[str, Any], float]:
        texture = self.texture or "minecraft:entity/zombie/zombie"
        model = {
            "textures": {"1": texture, "particle": texture},
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
                        "down": {"uv": [4, 0, 6, 2], "rotation": 180, "texture": "#1"},
                    },
                }
            ],
        }
        return model

    def get_generic_mob_head(
        self, getter: PackGetterV2, item: Item, texture: str
    ) -> dict[str, Any] | tuple[dict[str, Any], float]:
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

    def get_model_player(self, getter: PackGetterV2, item: Item) -> dict[str, Any] | tuple[dict[str, Any], float]:
        texture = self.get_player_texture(getter, item)
        model = {
            "textures": {"1": texture, "particle": texture},
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
                        "down": {"uv": [4, 0, 6, 2], "rotation": 180, "texture": "#1"},
                    },
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

    def get_player_texture(self, getter: PackGetterV2, item: Item) -> str | Image.Image:
        DEFAULT_TEXTURE = "minecraft:entity/player/wide/steve"
        if self.texture:
            return self.texture
        if not item.components:
            return DEFAULT_TEXTURE
        if not "minecraft:profile" in item.components:
            return DEFAULT_TEXTURE
        cache = getter._ctx.cache["model_resolver"]
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


class SpecialModelShulkerBox(SpecialModelBase):
    type: Literal["minecraft:shulker_box", "shulker_box"]
    texture: str
    openness: float = 0.0
    orientation: Literal["down", "east", "north", "south", "up", "west"] = "up"


class SpecialModelShield(SpecialModelBase):
    type: Literal["minecraft:shield", "shield"]


class SpecialModelTrident(SpecialModelBase):
    type: Literal["minecraft:trident", "trident"]


class SpecialModelDecoratedPot(SpecialModelBase):
    type: Literal["minecraft:decorated_pot", "decorated_pot"]


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
    type: Literal["minecraft:standing_sign", "standing_sign"]
    texture: Optional[str] = None
    wood_type: wood_types


class SpecialModelHangingSign(SpecialModelBase):
    type: Literal["minecraft:hanging_sign", "hanging_sign"]
    texture: Optional[str] = None
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
