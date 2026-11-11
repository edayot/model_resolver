"""Where sprites sit in the game's texture atlases, like SpriteLoader and Stitcher.

Models are drawn from their own textures, but some effects use the atlas coordinates of a
sprite: the enchantment glint is sampled with them, so its look depends on where the
sprite was stitched.
"""

from dataclasses import dataclass
import math
import re
from typing import Any, Optional

from beet import Atlas, Context

from model_resolver.pack_getter import PackGetter
from model_resolver.utils import log, resolve_key

MISSING_SPRITE = "minecraft:missingno"
# Options.mipmapLevels, only used by the atlases AtlasManager creates mipmaps for
DEFAULT_MIPMAP_LEVELS = 4
MIPMAPPED_ATLASES = {"minecraft:blocks"}
# RenderSystem's max texture size: only reached by atlases the game couldn't load
MAX_TEXTURE_SIZE = 1 << 15


@dataclass
class AtlasLayout:
    width: int
    height: int
    sprites: dict[str, tuple[int, int, int, int]]
    """x, y, width and height of each sprite, padding excluded."""

    def uv(self, sprite: str) -> Optional[tuple[float, float, float, float]]:
        """TextureAtlasSprite u0, v0, u1, v1."""
        if sprite not in self.sprites:
            return None
        x, y, width, height = self.sprites[sprite]
        return (
            x / self.width,
            y / self.height,
            (x + width) / self.width,
            (y + height) / self.height,
        )


class Atlases:
    """The layout of each atlas, computed once per beet context (`ctx.inject(Atlases)`)."""

    def __init__(self, ctx: Context):
        self.layouts: dict[str, AtlasLayout] = {}

    def layout(self, getter: PackGetter, atlas: str) -> AtlasLayout:
        atlas = resolve_key(atlas)
        if atlas not in self.layouts:
            sprites = atlas_sprites(getter, atlas)
            max_mip = DEFAULT_MIPMAP_LEVELS if atlas in MIPMAPPED_ATLASES else 0
            self.layouts[atlas] = stitch(sprites, mip_level(sprites, max_mip))
        return self.layouts[atlas]

    def model_sprite_uv(self, getter: PackGetter, sprite: str) -> Optional[tuple[float, float, float, float]]:
        """MaterialBaker: a model texture comes from the items atlas, else the blocks atlas."""
        for atlas in ("minecraft:items", "minecraft:blocks"):
            uv = self.layout(getter, atlas).uv(resolve_key(sprite))
            if uv is not None:
                return uv
        return None


def sprite_size(getter: PackGetter, texture: str) -> Optional[tuple[int, int]]:
    """SpriteContents width and height: a frame of an animated texture."""
    from model_resolver.tasks.generic_render import TextureMcMetaModel

    image = getter.assets.textures.get(texture)
    if image is None:
        return None
    width, height = image.image.size
    mcmeta = getter.assets.textures_mcmeta.get(texture)
    if mcmeta is not None:
        animation = TextureMcMetaModel.model_validate(mcmeta.data).animation
        if animation is not None:
            return animation.frame_size(width, height)
    return width, height


def atlas_sprites(getter: PackGetter, atlas: str) -> dict[str, tuple[int, int]]:
    """SpriteSourceList.list: the sources of every pack's copy of the atlas, lowest
    priority first, then the missing sprite."""
    sprites: dict[str, tuple[int, int]] = {}
    for file in reversed(getter.get_stack(Atlas, atlas)):
        for source in file.data.get("sources", []):
            run_source(getter, source, sprites)
    sprites[MISSING_SPRITE] = (16, 16)
    return sprites


def run_source(getter: PackGetter, source: dict[str, Any], sprites: dict[str, tuple[int, int]]):
    source_type = resolve_key(source["type"])
    if source_type == "minecraft:single":
        resource = resolve_key(source["resource"])
        size = sprite_size(getter, resource)
        if size is not None:
            sprites[resolve_key(source.get("sprite", resource))] = size
    elif source_type == "minecraft:directory":
        directory = source["source"].rstrip("/") + "/"
        for texture in getter.assets.textures:
            namespace, path = resolve_key(texture).split(":", 1)
            if path.startswith(directory):
                size = sprite_size(getter, texture)
                if size is not None:
                    sprites[f"{namespace}:{source['prefix']}{path.removeprefix(directory)}"] = size
    elif source_type == "minecraft:paletted_permutations":
        separator = source.get("separator", "_")
        for texture in source["textures"]:
            size = sprite_size(getter, resolve_key(texture))
            if size is None:
                continue
            for permutation in source["permutations"]:
                sprites[resolve_key(f"{texture}{separator}{permutation}")] = size
    elif source_type == "minecraft:unstitch":
        size = sprite_size(getter, resolve_key(source["resource"]))
        if size is None:
            return
        x_scale = size[0] / source.get("divisor_x", 1.0)
        y_scale = size[1] / source.get("divisor_y", 1.0)
        for region in source["regions"]:
            sprites[resolve_key(region["sprite"])] = (
                math.floor(region["width"] * x_scale),
                math.floor(region["height"] * y_scale),
            )
    elif source_type == "minecraft:filter":
        pattern = source["pattern"]
        for sprite in list(sprites):
            namespace, path = sprite.split(":", 1)
            if re.search(pattern.get("namespace", ""), namespace) and re.search(
                pattern.get("path", ""), path
            ):
                del sprites[sprite]
    else:
        log.warning(f"Unknown atlas source {source_type}")


def lowest_one_bit(x: int) -> int:
    return x & -x


def mip_level(sprites: dict[str, tuple[int, int]], max_mip: int) -> int:
    """SpriteLoader.stitch: small or odd-sized sprites lower the mip level."""
    min_texel = min((min(w, h) for w, h in sprites.values()), default=1 << 30)
    lowest = 1 << max_mip
    for width, height in sprites.values():
        lowest = min(lowest, lowest_one_bit(width), lowest_one_bit(height))
    return min(max_mip, max(0, int(math.log2(min(min_texel, lowest)))))


def smallest_fitting_min_texel(value: int, mip: int) -> int:
    return ((value >> mip) + (0 if value & ((1 << mip) - 1) == 0 else 1)) << mip


def smallest_encompassing_power_of_two(value: int) -> int:
    """Mth.smallestEncompassingPowerOfTwo, 0 for 0."""
    return 0 if value <= 0 else 1 << (value - 1).bit_length()


class Region:
    """Stitcher.Region"""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.x, self.y, self.width, self.height = x, y, width, height
        self.sub_slots: Optional[list[Region]] = None
        self.holder: Optional[tuple[str, int, int]] = None

    def add(self, holder: tuple[str, int, int]) -> bool:
        if self.holder is not None:
            return False
        _, width, height = holder
        if width > self.width or height > self.height:
            return False
        if width == self.width and height == self.height:
            self.holder = holder
            return True
        if self.sub_slots is None:
            self.sub_slots = [Region(self.x, self.y, width, height)]
            spare_width, spare_height = self.width - width, self.height - height
            if spare_height > 0 and spare_width > 0:
                if max(self.height, spare_width) >= max(self.width, spare_height):
                    self.sub_slots.append(Region(self.x, self.y + height, width, spare_height))
                    self.sub_slots.append(Region(self.x + width, self.y, spare_width, self.height))
                else:
                    self.sub_slots.append(Region(self.x + width, self.y, spare_width, height))
                    self.sub_slots.append(Region(self.x, self.y + height, self.width, spare_height))
            elif spare_width == 0:
                self.sub_slots.append(Region(self.x, self.y + height, width, spare_height))
            elif spare_height == 0:
                self.sub_slots.append(Region(self.x + width, self.y, spare_width, height))
        return any(slot.add(holder) for slot in self.sub_slots)

    def walk(self, output: dict[str, tuple[int, int]]):
        if self.holder is not None:
            output[self.holder[0]] = (self.x, self.y)
        for slot in self.sub_slots or []:
            slot.walk(output)


def identifier_order(name: str) -> tuple[str, str]:
    """Identifier.compareTo: the path, then the namespace."""
    namespace, path = name.split(":", 1)
    return path, namespace


def stitch(sprites: dict[str, tuple[int, int]], mip: int) -> AtlasLayout:
    """Stitcher, without anisotropic filtering (the default)."""
    padding = 1 << mip
    holders = [
        (
            name,
            smallest_fitting_min_texel(width + padding * 2, mip),
            smallest_fitting_min_texel(height + padding * 2, mip),
        )
        for name, (width, height) in sprites.items()
    ]
    holders.sort(key=lambda h: (-h[2], -h[1], identifier_order(h[0])))
    storage: list[Region] = []
    storage_x = storage_y = 0
    for holder in holders:
        if any(region.add(holder) for region in storage):
            continue
        # Stitcher.expand
        x_current = smallest_encompassing_power_of_two(storage_x)
        y_current = smallest_encompassing_power_of_two(storage_y)
        x_new = smallest_encompassing_power_of_two(storage_x + holder[1])
        y_new = smallest_encompassing_power_of_two(storage_y + holder[2])
        x_can_grow, y_can_grow = x_new <= MAX_TEXTURE_SIZE, y_new <= MAX_TEXTURE_SIZE
        if not x_can_grow and not y_can_grow:
            raise ValueError(f"Unable to fit {holder[0]} in the atlas")
        x_will_grow = x_can_grow and x_current != x_new
        y_will_grow = y_can_grow and y_current != y_new
        if x_will_grow ^ y_will_grow:
            grow_on_x = x_will_grow
        else:
            grow_on_x = x_can_grow and x_current <= y_current
        if grow_on_x:
            if storage_y == 0:
                storage_y = y_new
            slot = Region(storage_x, 0, x_new - storage_x, storage_y)
            storage_x = x_new
        else:
            slot = Region(0, storage_y, storage_x, y_new - storage_y)
            storage_y = y_new
        slot.add(holder)
        storage.append(slot)
    positions: dict[str, tuple[int, int]] = {}
    for region in storage:
        region.walk(positions)
    return AtlasLayout(
        width=storage_x,
        height=storage_y,
        sprites={
            name: (x + padding, y + padding, *sprites[name]) for name, (x, y) in positions.items()
        },
    )
