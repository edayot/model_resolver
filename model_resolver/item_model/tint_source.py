from functools import cache
import json
import math
from pathlib import Path
import numpy as np
from pydantic import BaseModel, Field
from typing import Any, Literal, Optional, Union
from beet import LATEST_MINECRAFT_VERSION
from PIL import Image
from model_resolver.item_model.item import Item
from model_resolver.pack_getter import PackGetter
from model_resolver.utils import resolve_key

type Color = int | tuple[float, float, float]


def channel(value: float) -> int:
    # ARGB.as8BitChannel, in float32 like Java
    return math.floor(float(np.float32(value) * np.float32(255.0))) & 0xFF


def to_rgb(color: Color | list[float] | dict[str, Any]) -> tuple[int, int, int]:
    """Read a color like ExtraCodecs.RGB_COLOR_CODEC: an ARGB int, or [r, g, b] floats from 0 to 1."""
    if isinstance(color, dict):
        # dyed_color before 1.21.5: {rgb, show_in_tooltip}
        return to_rgb(color["rgb"])
    if isinstance(color, (tuple, list)):
        red, green, blue = color
        return (channel(red), channel(green), channel(blue))
    red = (color >> 16) & 0xFF
    green = (color >> 8) & 0xFF
    blue = color & 0xFF
    return (red, green, blue)


def to_argb(color: int) -> tuple[int, int, int, int]:
    if isinstance(color, tuple):
        return color
    alpha = (color >> 24) & 0xFF
    red = (color >> 16) & 0xFF
    green = (color >> 8) & 0xFF
    blue = color & 0xFF
    return (alpha, red, green, blue)


class TintSourceBase(BaseModel):
    type: Literal[
        "constant",
        "dye",
        "grass",
        "firework",
        "potion",
        "map_color",
        "custom_model_data",
        "team",
        "minecraft:constant",
        "minecraft:dye",
        "minecraft:grass",
        "minecraft:firework",
        "minecraft:potion",
        "minecraft:map_color",
        "minecraft:custom_model_data",
        "minecraft:team",
    ]

    def resolve(self, getter: PackGetter, item: Item) -> tuple[int, int, int]:
        raise NotImplementedError()


class TintSourceConstant(TintSourceBase):
    type: Literal["constant", "minecraft:constant"]
    value: Color

    def resolve(self, getter: PackGetter, item: Item) -> tuple[int, int, int]:
        return to_rgb(self.value)


class TintSourceDye(TintSourceBase):
    type: Literal["dye", "minecraft:dye"]
    default: Color

    def resolve(self, getter: PackGetter, item: Item) -> tuple[int, int, int]:
        if "minecraft:dyed_color" in item.components:
            return to_rgb(item.components["minecraft:dyed_color"])
        return to_rgb(self.default)


class TintSourceGrass(TintSourceBase):
    type: Literal["grass", "minecraft:grass"]
    temperature: float = Field(ge=0, le=1)
    downfall: float = Field(ge=0, le=1)

    def resolve(self, getter: PackGetter, item: Item) -> tuple[int, int, int]:
        return to_rgb(colormap_color(getter, "minecraft:colormap/grass", self.temperature, self.downfall))


def colormap_color(
    getter: PackGetter, texture_key: str, temperature: float, downfall: float, default: int = 0xFF00FF
) -> int:
    """ColorMapColorUtil.get: the float values widen to double, the colormap is read as a
    256-wide pixel array and an index past its end gives the default."""
    if texture_key in getter.assets.textures:
        texture = getter.assets.textures[texture_key]
    else:
        raise ValueError(f"{texture_key} not found in Context or Vanilla")
    img: Image.Image = texture.image.convert(mode="RGB")
    temperature = float(np.float32(temperature))
    downfall = float(np.float32(downfall)) * temperature
    x = int((1.0 - temperature) * 255.0)
    y = int((1.0 - downfall) * 255.0)
    index = y << 8 | x
    width, height = img.size
    if index >= width * height:
        return default & 0xFFFFFF
    color = img.getpixel((index % width, index // width))
    assert isinstance(color, tuple) and len(color) == 3
    return color[0] << 16 | color[1] << 8 | color[2]


class TintSourceFirework(TintSourceBase):
    type: Literal["firework", "minecraft:firework"]
    default: Color

    def resolve(self, getter: PackGetter, item: Item) -> tuple[int, int, int]:
        # the average of the firework_explosion colors
        explosion = item.components.get("minecraft:firework_explosion") or {}
        colors = [to_rgb(color) for color in explosion.get("colors", [])]
        if not colors:
            return to_rgb(self.default)
        return (
            sum(color[0] for color in colors) // len(colors),
            sum(color[1] for color in colors) // len(colors),
            sum(color[2] for color in colors) // len(colors),
        )


class TintSourcePotion(TintSourceBase):
    type: Literal["potion", "minecraft:potion"]
    default: Color

    def resolve(self, getter: PackGetter, item: Item) -> tuple[int, int, int]:
        contents = item.components.get("minecraft:potion_contents")
        if contents is None:
            return to_rgb(self.default)
        return to_rgb(potion_color(contents, self.default, getter.opts.minecraft_version))


@cache
def potion_table(version: str) -> dict[str, Any]:
    """Effects of every potion and color of every effect, see scripts/generate_potion_table.py."""
    tables = json.loads((Path(__file__).parent.parent / "data" / "potions.json").read_text())
    if version == "latest":
        version = LATEST_MINECRAFT_VERSION
    if version in tables:
        return tables[version]
    return tables[max(tables, key=lambda v: tuple(map(int, v.split("."))))]


def potion_effects(contents: Any, version: str) -> list[dict[str, Any]]:
    """PotionContents.getAllEffects: the potion's effects, then custom_effects."""
    if isinstance(contents, str):
        contents = {"potion": contents}
    potion = contents.get("potion")
    effects = potion_table(version)["potions"].get(resolve_key(potion), []) if potion else []
    return [*effects, *contents.get("custom_effects", [])]


def potion_color(contents: Any, default: Color, version: str) -> Color:
    """PotionContents.getColorOr: custom_color, else the average color of the visible effects
    (the potion's and custom_effects), each weighted by its amplifier + 1."""
    if isinstance(contents, dict) and "custom_color" in contents:
        return contents["custom_color"]
    table = potion_table(version)
    red = green = blue = total = 0
    for effect in potion_effects(contents, version):
        color = table["effects"].get(resolve_key(effect["id"]))
        if color is None or not effect.get("show_particles", True):
            continue
        weight = effect.get("amplifier", 0) + 1
        red += weight * ((color >> 16) & 0xFF)
        green += weight * ((color >> 8) & 0xFF)
        blue += weight * (color & 0xFF)
        total += weight
    if total == 0:
        return default
    return (red // total) << 16 | (green // total) << 8 | blue // total


class TintSourceMap(TintSourceBase):
    type: Literal["map_color", "minecraft:map_color"]
    default: Color

    def resolve(self, getter: PackGetter, item: Item) -> tuple[int, int, int]:
        # removed in 26.3 snapshot 7, kept for older versions
        if "minecraft:map_color" in item.components:
            return to_rgb(item.components["minecraft:map_color"])
        return to_rgb(self.default)


class TintSourceCustomModelData(TintSourceBase):
    type: Literal["custom_model_data", "minecraft:custom_model_data"]
    index: Optional[int] = 0
    default: Color = 0

    def resolve(self, getter: PackGetter, item: Item) -> tuple[int, int, int]:
        colors = (item.components.get("minecraft:custom_model_data") or {}).get("colors", [])
        index = self.index or 0
        if 0 <= index < len(colors):
            return to_rgb(colors[index])
        return to_rgb(self.default)


class TintSourceTeam(TintSourceBase):
    type: Literal["team", "minecraft:team"]
    default: Color

    def resolve(self, getter: PackGetter, item: Item) -> tuple[int, int, int]:
        return to_rgb(self.default)


type TintSource = Union[
    TintSourceDye,
    TintSourceConstant,
    TintSourceGrass,
    TintSourceFirework,
    TintSourcePotion,
    TintSourceMap,
    TintSourceCustomModelData,
    TintSourceTeam,
]
