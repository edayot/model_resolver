"""One structure rendered in several biomes: water, grass and foliage take the biome's colors,
the campfire flame is lit like a top face (shade_direction_override)."""

from typing import Any

from beet import Context, Structure
from nbtlib import Compound, Int, List, String
from model_resolver import Render

PALETTE: list[dict[str, Any]] = [
    {"Name": "minecraft:stone"},
    {"Name": "minecraft:water", "Properties": {"level": "0"}},
    {"Name": "minecraft:grass_block", "Properties": {"snowy": "false"}},
    {
        "Name": "minecraft:oak_leaves",
        "Properties": {"distance": "1", "persistent": "true", "waterlogged": "false"},
    },
    {
        "Name": "minecraft:campfire",
        "Properties": {
            "facing": "south",
            "lit": "true",
            "signal_fire": "false",
            "waterlogged": "false",
        },
    },
    {
        "Name": "minecraft:oak_slab",
        "Properties": {"type": "bottom", "waterlogged": "true"},
    },
    {"Name": "minecraft:short_grass"},
    {
        "Name": "minecraft:birch_leaves",
        "Properties": {"distance": "1", "persistent": "true", "waterlogged": "false"},
    },
    {"Name": "minecraft:lily_pad"},
    {"Name": "minecraft:sugar_cane", "Properties": {"age": "0"}},
    {"Name": "minecraft:water", "Properties": {"level": "4"}},
]
BLOCKS = [
    (1, (0, 1, 0)),
    (1, (1, 1, 0)),
    (1, (0, 1, 1)),
    (1, (1, 1, 1)),
    (8, (1, 2, 1)),
    (10, (2, 1, 0)),
    (5, (2, 1, 1)),
    (2, (4, 1, 0)),
    (6, (4, 2, 0)),
    (9, (3, 1, 0)),
    (3, (4, 1, 4)),
    (7, (3, 1, 4)),
    (4, (0, 1, 4)),
    (2, (1, 1, 4)),
]
CAMERA = {"rotation": [30, 225, 0], "translation": [0, 0, 0], "scale": [2.2, 2.2, 2.2]}
BIOMES = [
    "plains",
    "swamp",
    "warm_ocean",
    "badlands",
    "dark_forest",
    "cherry_grove",
    "snowy_plains",
]


def nbt(value: Any) -> Any:
    if isinstance(value, dict):
        return Compound({key: nbt(x) for key, x in value.items()})
    if isinstance(value, list):
        if all(isinstance(x, int) for x in value):
            return List[Int]([Int(x) for x in value])
        return List[Compound]([nbt(x) for x in value])
    if isinstance(value, int):
        return Int(value)
    return String(value)


def beet_default(ctx: Context):
    blocks = [{"state": 0, "pos": [x, 0, z]} for x in range(5) for z in range(5)]
    blocks += [{"state": state, "pos": list(pos)} for state, pos in BLOCKS]
    ctx.data.structures["biomes:pond"] = Structure(
        nbt(
            {
                "DataVersion": 4400,
                "size": [5, 3, 5],
                "palette": PALETTE,
                "blocks": blocks,
                "entities": [],
            }
        )
    )
    render = Render(ctx)
    for biome in BIOMES:
        render.add_structure_task(
            "biomes:pond",
            path_ctx=f"biomes:render/{biome}",
            render_size=256,
            biome=biome,
            display_option=CAMERA,
        )
    # animated water, as a webp: a source flowing down a step (still and flowing textures)
    stream = [{"state": 0, "pos": [x, 0, z]} for x in range(3) for z in range(2)]
    stream += [{"state": 0, "pos": [0, 1, z]} for z in range(2)]
    stream += [{"state": 1, "pos": [0, 2, z]} for z in range(2)]
    stream += [{"state": 2, "pos": [x, 1, z]} for x in (1, 2) for z in range(2)]
    ctx.data.structures["biomes:stream"] = Structure(
        nbt(
            {
                "DataVersion": 4400,
                "size": [3, 3, 2],
                "palette": [
                    {"Name": "minecraft:stone"},
                    {"Name": "minecraft:water", "Properties": {"level": "0"}},
                    {"Name": "minecraft:water", "Properties": {"level": "2"}},
                ],
                "blocks": stream,
                "entities": [],
            }
        )
    )
    render.add_structure_task(
        "biomes:stream",
        path_ctx="biomes:render/animated",
        render_size=96,
        display_option={**CAMERA, "scale": [2.5, 2.5, 2.5]},
        animation_mode="webp",
    )
    # a custom biome, as a worldgen/biome object
    custom = {
        "temperature": 0.5,
        "downfall": 0.5,
        "effects": {"water_color": "#ff5500", "grass_color": "#ff00ff"},
    }
    render.add_structure_task(
        "biomes:pond",
        path_ctx="biomes:render/custom",
        render_size=256,
        biome=custom,
        display_option=CAMERA,
    )
    render.run()
