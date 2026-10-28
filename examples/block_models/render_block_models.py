"""Block models rendered on their own and in a structure: tinted like their block in a
biome (cauldron water, grass, leaves...), the campfire flames lit like a top face."""

from typing import Any

from beet import Context, Structure
from nbtlib import Compound, Int, List, String
from model_resolver import Render

MODELS = [
    "water_cauldron_level1",
    "water_cauldron_level2",
    "water_cauldron_full",
    "lava_cauldron",
    "powder_snow_cauldron_full",
    "campfire",
    "soul_campfire",
    "campfire_off",
    "grass_block",
    "short_grass",
    "fern",
    "sugar_cane",
    "oak_leaves",
    "birch_leaves",
    "spruce_leaves",
    "vine",
    "lily_pad",
    "redstone_dust_dot",
]
BIOMES = ["plains", "swamp"]

CAMPFIRE = {
    "facing": "south",
    "lit": "true",
    "signal_fire": "false",
    "waterlogged": "false",
}
PALETTE: list[dict[str, Any]] = [
    {"Name": "minecraft:stone"},
    {"Name": "minecraft:water_cauldron", "Properties": {"level": "3"}},
    {"Name": "minecraft:water_cauldron", "Properties": {"level": "1"}},
    {"Name": "minecraft:lava_cauldron"},
    {"Name": "minecraft:campfire", "Properties": CAMPFIRE},
    {"Name": "minecraft:soul_campfire", "Properties": CAMPFIRE},
    {"Name": "minecraft:grass_block", "Properties": {"snowy": "false"}},
    {
        "Name": "minecraft:oak_leaves",
        "Properties": {"distance": "1", "persistent": "true", "waterlogged": "false"},
    },
]
BLOCKS = [
    (1, (0, 1, 0)),
    (2, (1, 1, 0)),
    (3, (2, 1, 0)),
    (4, (0, 1, 1)),
    (5, (1, 1, 1)),
    (6, (2, 1, 1)),
    (7, (2, 2, 1)),
]
CAMERA = {"rotation": [30, 225, 0], "translation": [0, 0, 0], "scale": [3.0, 3.0, 3.0]}


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
    render = Render(ctx)
    for biome in BIOMES:
        for model in MODELS:
            render.add_model_task(
                f"minecraft:block/{model}",
                path_ctx=f"blocks:render/{biome}/{model}",
                render_size=128,
                animation_mode="one_file",
                biome=biome,
            )
    blocks = [{"state": 0, "pos": [x, 0, z]} for x in range(3) for z in range(2)]
    blocks += [{"state": state, "pos": list(pos)} for state, pos in BLOCKS]
    ctx.data.structures["blocks:showcase"] = Structure(
        nbt(
            {
                "DataVersion": 4400,
                "size": [3, 3, 2],
                "palette": PALETTE,
                "blocks": blocks,
                "entities": [],
            }
        )
    )
    for biome in BIOMES:
        render.add_structure_task(
            "blocks:showcase",
            path_ctx=f"blocks:render/{biome}/structure",
            render_size=256,
            display_option=CAMERA,
            biome=biome,
        )
    render.run()
