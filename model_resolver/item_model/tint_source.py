from pydantic import BaseModel
from typing import Literal, Optional, Any
from beet import Context
from model_resolver.vanilla import Vanilla
from model_resolver.utils import clamp
from PIL import Image
from model_resolver.item_model.item import Item

type Color = int | tuple[int, int, int]
def to_rgb(color: Color) -> tuple[int, int, int]:
    if isinstance(color, tuple):
        return color
    red = (color >> 16) & 0xFF
    green = (color >> 8) & 0xFF
    blue = color & 0xFF 
    return (red, green, blue)

class TintSourceBase(BaseModel):
    type: Literal["minecraft:constant", "minecraft:dye", "minecraft:grass", "minecraft:firework", "minecraft:potion", "minecraft:map_color", "minecraft:custom_model_data"]
    def resolve(self, ctx: Context, vanilla: Vanilla, item: Item) -> tuple[int, int, int]: 
        raise NotImplementedError()

class TintSourceConstant(TintSourceBase):
    type: Literal["minecraft:constant"]
    value: Color
    def resolve(self, ctx: Context, vanilla: Vanilla, item: Item) -> tuple[int, int, int]: 
        return to_rgb(self.value)

class TintSourceDye(TintSourceBase):
    type: Literal["minecraft:dye"]
    default: Color
    def resolve(self, ctx: Context, vanilla: Vanilla, item: Item) -> tuple[int, int, int]: 
        if item.components and "minecraft:dyed_color" in item.components:
            return to_rgb(item.components["minecraft:dyed_color"])
        return to_rgb(self.default)

class TintSourceGrass(TintSourceBase):
    type: Literal["minecraft:grass"]
    temperature: float
    downfall: float
    def resolve(self, ctx: Context, vanilla: Vanilla, item: Item) -> tuple[int, int, int]: 
        texture_key = "minecraft:colormap/grass"
        if texture_key in ctx.assets.textures:
            texture = ctx.assets.textures[texture_key]
        elif texture_key in vanilla.assets.textures:
            texture = vanilla.assets.textures[texture_key]
        else:
            raise ValueError(f"{texture_key} not found in Context or Vanilla")
        img: Image.Image = texture.image
        img = img.convert(mode="RGB")
        y = clamp(0, int(self.temperature * (img.size[0] - 1)), img.size[0] - 1)
        x = clamp(0, int(self.downfall * (img.size[1] - 1)), img.size[1] - 1)
        color = img.getpixel((x, y))
        if not color:
            raise ValueError(f"Color not found at {x}, {y}")
        return color  # type: ignore

class TintSourceFirework(TintSourceBase):
    type: Literal["minecraft:firework"]
    default: Color
    def resolve(self, ctx: Context, vanilla: Vanilla, item: Item) -> tuple[int, int, int]: 
        if item.components and "minecraft:firework_color" in item.components:
            colors = [
                to_rgb(color) for color in item.components["minecraft:firework_color"]["colors"]
            ]
            return (
                sum(color[0] for color in colors) // len(colors),
                sum(color[1] for color in colors) // len(colors),
                sum(color[2] for color in colors) // len(colors),
            )
        return to_rgb(self.default)

class TintSourcePotion(TintSourceBase):
    type: Literal["minecraft:potion"]
    default: Color
    def resolve(self, ctx: Context, vanilla: Vanilla, item: Item) -> tuple[int, int, int]: 
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
    type: Literal["minecraft:map_color"]
    default: Color
    def resolve(self, ctx: Context, vanilla: Vanilla, item: Item) -> tuple[int, int, int]: 
        if not item.components:
            return to_rgb(self.default)
        if not "minecraft:map_color" in item.components:
            return to_rgb(self.default)
        return to_rgb(item.components["minecraft:map_color"])

class TintSourceCustomModelData(TintSourceBase):
    type: Literal["minecraft:custom_model_data"]
    index: Optional[int] = 0
    def resolve(self, ctx: Context, vanilla: Vanilla, item: Item) -> tuple[int, int, int]: 
        if not item.components:
            return to_rgb(0)
        if not "minecraft:custom_model_data" in item.components:
            return to_rgb(0)
        if not "colors" in item.components["minecraft:custom_model_data"]:
            return to_rgb(0)
        return to_rgb(item.components["minecraft:custom_model_data"][self.index or 0])

type TintSource = TintSourceDye | TintSourceConstant | TintSourceGrass | TintSourceFirework | TintSourcePotion | TintSourceMap | TintSourceCustomModelData