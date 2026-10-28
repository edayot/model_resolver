"""Block tints in the world (BlockColors) and the biome colors they depend on.

A structure has no biome of its own, so a render uses one biome for every block:
grass, foliage, dry foliage and water colors come from it like BiomeColors.getAverage*.
"""

from functools import cache
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
from beet import LATEST_MINECRAFT_VERSION
from pydantic import BaseModel, Field, field_validator

from model_resolver.item_model.tint_source import colormap_color
from model_resolver.pack_getter import PackGetter
from model_resolver.utils import clamp, log, resolve_key

FOLIAGE_DEFAULT = 0x48B518  # FoliageColor.FOLIAGE_DEFAULT
DRY_FOLIAGE_DEFAULT = 0x5C3C32  # DryFoliageColor.FOLIAGE_DRY_DEFAULT


def parse_color(value: Any) -> int:
    """Biome colors are "#rrggbb" since 26.1 and ints before."""
    if isinstance(value, str):
        return int(value.removeprefix("#"), 16)
    return int(value) & 0xFFFFFF


class BiomeEffects(BaseModel):
    water_color: int = 0x3F76E4
    grass_color: Optional[int] = None
    foliage_color: Optional[int] = None
    dry_foliage_color: Optional[int] = None
    grass_color_modifier: str = "none"

    @field_validator("water_color", "grass_color", "foliage_color", "dry_foliage_color", mode="before")
    @classmethod
    def color(cls, value: Any) -> Any:
        return None if value is None else parse_color(value)


class Biome(BaseModel):
    """The parts of a worldgen/biome file that colors need."""

    temperature: float = 0.8
    downfall: float = 0.4
    effects: BiomeEffects = Field(default_factory=BiomeEffects)

    def climate(self) -> tuple[float, float]:
        return clamp(0.0, self.temperature, 1.0), clamp(0.0, self.downfall, 1.0)

    def water_color(self) -> int:
        return self.effects.water_color

    def grass_color(self, getter: PackGetter) -> int:
        """Biome.getGrassColor, without position: swamps use their usual (non-noise) color."""
        if self.effects.grass_color is not None:
            color = self.effects.grass_color
        else:
            color = colormap_color(getter, "minecraft:colormap/grass", *self.climate())
        match self.effects.grass_color_modifier:
            case "dark_forest":
                return ((color & 0xFEFEFE) + 0x28340A) >> 1
            case "swamp":
                # BIOME_INFO_NOISE >= -0.1 at most positions, 0x4C763C elsewhere
                return 0x6A7039
        return color

    def foliage_color(self, getter: PackGetter) -> int:
        if self.effects.foliage_color is not None:
            return self.effects.foliage_color
        return colormap_color(getter, "minecraft:colormap/foliage", *self.climate(), FOLIAGE_DEFAULT)

    def dry_foliage_color(self, getter: PackGetter) -> int:
        if self.effects.dry_foliage_color is not None:
            return self.effects.dry_foliage_color
        return colormap_color(
            getter, "minecraft:colormap/dry_foliage", *self.climate(), DRY_FOLIAGE_DEFAULT
        )


@cache
def vanilla_biomes(version: str) -> dict[str, Any]:
    """Biomes of the vanilla data pack, see scripts/generate_biome_table.py."""
    tables = json.loads((Path(__file__).parent / "data" / "biomes.json").read_text())
    if version == "latest":
        version = LATEST_MINECRAFT_VERSION
    if version in tables:
        return tables[version]
    return tables[max(tables, key=lambda v: tuple(map(int, v.split("."))))]


def load_biome(getter: PackGetter, biome: str | dict[str, Any]) -> Biome:
    """A biome by id (the project's data pack first, then vanilla), or a biome object."""
    if isinstance(biome, dict):
        return Biome.model_validate(biome)
    key = resolve_key(biome)
    try:
        from beet.contrib.worldgen import WorldgenBiome

        file = getter._ctx.data[WorldgenBiome].get(key)
        if file is not None:
            return Biome.model_validate(file.data)
    except (AttributeError, KeyError, TypeError):
        pass
    data = vanilla_biomes(getter.opts.minecraft_version).get(key)
    if data is None:
        log.warning(f"Unknown biome {key}, using plains")
        data = vanilla_biomes(getter.opts.minecraft_version)["minecraft:plains"]
    return Biome.model_validate(data)


def redstone_color(power: int) -> int:
    """RedstoneWireBlock.COLORS, in float32 like Java (power 15 has green 50, not 51)."""
    f32 = np.float32
    f = f32(power) / f32(15)
    r = f * f32(0.6) + (f32(0.4) if f > 0 else f32(0.3))
    g = np.clip(f * f * f32(0.7) - f32(0.5), f32(0), f32(1))
    b = np.clip(f * f * f32(0.6) - f32(0.7), f32(0), f32(1))
    channel = lambda v: int(np.floor(v * f32(255)))
    return channel(r) << 16 | channel(g) << 8 | channel(b)


GRASS = {"fern", "short_grass", "potted_fern", "bush", "large_fern", "tall_grass", "grass_block", "sugar_cane"}
FOLIAGE = {"oak_leaves", "jungle_leaves", "acacia_leaves", "dark_oak_leaves", "vine", "mangrove_leaves"}
CONSTANT = {
    "spruce_leaves": 0x619961,
    "birch_leaves": 0x80A755,
    "attached_melon_stem": 0xE0C71C,
    "attached_pumpkin_stem": 0xE0C71C,
    "lily_pad": 0x208030,
}


def block_tints(
    getter: PackGetter, biome: Biome, name: str, properties: dict[str, str]
) -> Optional[list[Optional[int]]]:
    """BlockColors.createDefault with colorInWorld: the color of each tintindex,
    None for a block BlockColors doesn't register (its faces are untinted)."""
    namespace, path = resolve_key(name).split(":", 1)
    if namespace != "minecraft":
        return None
    if path in GRASS:
        return [biome.grass_color(getter)]
    if path in ("pink_petals", "wildflowers"):
        return [None, biome.grass_color(getter)]
    if path in FOLIAGE:
        return [biome.foliage_color(getter)]
    if path == "leaf_litter":
        return [biome.dry_foliage_color(getter)]
    if path == "water_cauldron":
        return [biome.water_color()]
    if path in ("water", "bubble_column"):
        # tinted by the fluid renderer, the block itself is white
        return [None]
    if path == "redstone_wire":
        return [redstone_color(int(properties.get("power", 0)))]
    if path in ("melon_stem", "pumpkin_stem"):
        age = int(properties.get("age", 0))
        return [(age * 32) << 16 | (255 - age * 8) << 8 | age * 4]
    if path in CONSTANT:
        return [CONSTANT[path]]
    return None


def model_blocks(getter: PackGetter) -> dict[str, tuple[str, dict[str, str]]]:
    """For every model a blockstate uses, the first block state that uses it, so a model
    rendered on its own can be tinted like that block. Computed once per getter."""
    cached = getattr(getter, "_model_blocks", None)
    if cached is not None:
        return cached
    result: dict[str, tuple[str, dict[str, str]]] = {}

    def add(apply: Any, block: str, properties: dict[str, str]):
        for variant in apply if isinstance(apply, list) else [apply]:
            if isinstance(variant, dict) and isinstance(variant.get("model"), str):
                result.setdefault(resolve_key(variant["model"]), (block, properties))

    for block in getter.assets.blockstates:
        data = getter.assets.blockstates[block].data
        for key, apply in (data.get("variants") or {}).items():
            properties = dict(pair.split("=", 1) for pair in key.split(",") if "=" in pair)
            add(apply, resolve_key(block), properties)
        for part in data.get("multipart") or []:
            when = part.get("when") or {}
            # simple conditions only, enough for the properties tints read (power, age)
            properties = {k: str(v).split("|")[0] for k, v in when.items() if k not in ("OR", "AND")}
            add(part.get("apply"), resolve_key(block), properties)
    setattr(getter, "_model_blocks", result)
    return result


def model_tints(getter: PackGetter, biome: Biome, model: str) -> Optional[list[Optional[int]]]:
    """The tints of a block model shown on its own: those of the block that uses it."""
    block = model_blocks(getter).get(resolve_key(model))
    if block is None:
        return None
    return block_tints(getter, biome, *block)
