from pydantic import BaseModel
from typing import Literal, Optional, Union
from model_resolver.utils import clamp
from PIL import Image
from model_resolver.item_model.item import Item
from model_resolver.utils import PackGetterV2

type Color = int | tuple[int, int, int]


def to_rgb(color: Color) -> tuple[int, int, int]:
    if isinstance(color, tuple):
        return color
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

    def resolve(self, getter: PackGetterV2, item: Item) -> tuple[int, int, int]:
        raise NotImplementedError()


class TintSourceConstant(TintSourceBase):
    type: Literal["constant", "minecraft:constant"]
    value: Color

    def resolve(self, getter: PackGetterV2, item: Item) -> tuple[int, int, int]:
        return to_rgb(self.value)


class TintSourceDye(TintSourceBase):
    type: Literal["dye", "minecraft:dye"]
    default: Color

    def resolve(self, getter: PackGetterV2, item: Item) -> tuple[int, int, int]:
        if item.components and "minecraft:dyed_color" in item.components:
            return to_rgb(item.components["minecraft:dyed_color"])
        return to_rgb(self.default)


class TintSourceGrass(TintSourceBase):
    type: Literal["grass", "minecraft:grass"]
    temperature: float
    downfall: float

    def resolve(self, getter: PackGetterV2, item: Item) -> tuple[int, int, int]:
        texture_key = "minecraft:colormap/grass"
        if texture_key in getter.assets.textures:
            texture = getter.assets.textures[texture_key]
        else:
            raise ValueError(f"{texture_key} not found in Context or Vanilla")
        img: Image.Image = texture.image
        img = img.convert(mode="RGB")
        temperature = clamp(0, self.temperature, 1)
        downfall = clamp(0, self.downfall, 1)
        adjusted_downfall = downfall * temperature
        width, height = img.size
        x = int(temperature * (width - 1))
        y = int(adjusted_downfall * (height - 1))
        x = width - 1 - x
        y = height - 1 - y
        color = img.getpixel((x, y))
        if not color:
            raise ValueError(f"Color not found at {temperature}, {downfall}")
        return color  # type: ignore


class TintSourceFirework(TintSourceBase):
    type: Literal["firework", "minecraft:firework"]
    default: Color

    def resolve(self, getter: PackGetterV2, item: Item) -> tuple[int, int, int]:
        if item.components and "minecraft:firework_color" in item.components:
            colors = [
                to_rgb(color)
                for color in item.components["minecraft:firework_color"]["colors"]
            ]
            return (
                sum(color[0] for color in colors) // len(colors),
                sum(color[1] for color in colors) // len(colors),
                sum(color[2] for color in colors) // len(colors),
            )
        return to_rgb(self.default)


class TintSourcePotion(TintSourceBase):
    type: Literal["potion", "minecraft:potion"]
    default: Color

    def resolve(self, getter: PackGetterV2, item: Item) -> tuple[int, int, int]:
        if not item.components:
            return to_rgb(self.default)
        if not "minecraft:potion_contents" in item.components:
            return to_rgb(self.default)
        if not "custom_color" in item.components["minecraft:potion_contents"]:
            return to_rgb(self.default)
        if len(item.components["minecraft:potion_contents"]["custom_effects"]) == 0:
            return to_rgb(self.default)
        return to_rgb(item.components["minecraft:potion_contents"]["custom_color"])


class TintSourceMap(TintSourceBase):
    type: Literal["map_color", "minecraft:map_color"]
    default: Color

    def resolve(self, getter: PackGetterV2, item: Item) -> tuple[int, int, int]:
        if not item.components:
            return to_rgb(self.default)
        if not "minecraft:map_color" in item.components:
            return to_rgb(self.default)
        return to_rgb(item.components["minecraft:map_color"])


class TintSourceCustomModelData(TintSourceBase):
    type: Literal["custom_model_data", "minecraft:custom_model_data"]
    index: Optional[int] = 0

    def resolve(self, getter: PackGetterV2, item: Item) -> tuple[int, int, int]:
        if not item.components:
            return to_rgb(0)
        if not "minecraft:custom_model_data" in item.components:
            return to_rgb(0)
        if not "colors" in item.components["minecraft:custom_model_data"]:
            return to_rgb(0)
        return to_rgb(
            item.components["minecraft:custom_model_data"]["colors"][self.index or 0]
        )


class TintSourceTeam(TintSourceBase):
    type: Literal["team", "minecraft:team"]
    default: Color

    def resolve(self, getter: PackGetterV2, item: Item) -> tuple[int, int, int]:
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
