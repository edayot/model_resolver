"""item_display entities in a structure: display contexts, transformations, rotations."""

import math
from typing import Any

from beet import Context, Structure
from nbtlib import Byte, Compound, Double, Float, Int, List, String
from nbtlib.tag import Base
from model_resolver import Render

IDENTITY = {
    "translation": [0.0, 0.0, 0.0],
    "left_rotation": [0.0, 0.0, 0.0, 1.0],
    "right_rotation": [0.0, 0.0, 0.0, 1.0],
    "scale": [1.0, 1.0, 1.0],
}
HALF = math.sqrt(0.5)


def display(pos, item: dict[str, Any], **nbt: Any) -> dict[str, Any]:
    return {
        "pos": List[Double]([Double(c) for c in pos]),
        "blockPos": [math.floor(c) for c in pos],
        "nbt": {"id": "minecraft:item_display", "item": {"count": 1, **item}, **nbt},
    }


ENTITIES = [
    # the same item in four display contexts (none is the default)
    display(
        (0.5, 1.5, 0.5),
        {
            "id": "minecraft:stone",
            "components": {"minecraft:item_model": "display:by_context"},
        },
    ),
    display(
        (1.5, 1.5, 0.5),
        {
            "id": "minecraft:stone",
            "components": {"minecraft:item_model": "display:by_context"},
        },
        item_display="fixed",
    ),
    display(
        (2.5, 1.5, 0.5),
        {
            "id": "minecraft:stone",
            "components": {"minecraft:item_model": "display:by_context"},
        },
        item_display="ground",
    ),
    display(
        (3.5, 1.5, 0.5),
        {
            "id": "minecraft:stone",
            "components": {"minecraft:item_model": "display:by_context"},
        },
        item_display="head",
    ),
    # a flat item, turned by yaw, and tipped over by pitch
    display(
        (0.5, 1.5, 2.5),
        {"id": "minecraft:diamond_sword"},
        item_display="fixed",
        Rotation=[45.0, 0.0],
    ),
    display(
        (1.5, 1.2, 2.5),
        {"id": "minecraft:apple"},
        item_display="fixed",
        Rotation=[0.0, 90.0],
    ),
    # decomposed transformation: half size, a quarter turn around y, raised
    display(
        (2.5, 1.5, 2.5),
        {"id": "minecraft:oak_stairs"},
        transformation={
            **IDENTITY,
            "translation": [0.0, 0.25, 0.0],
            "left_rotation": [0.0, HALF, 0.0, HALF],
            "scale": [0.5, 0.5, 0.5],
        },
    ),
    # matrix transformation (row-major): stretched along x
    display(
        (3.5, 1.5, 2.5),
        {"id": "minecraft:glowstone"},
        transformation=[
            1.5,
            0.0,
            0.0,
            0.0,
            0.0,
            0.5,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        ],
    ),
    # a special model and an enchanted item
    display(
        (4.5, 1.5, 0.5),
        {
            "id": "minecraft:red_banner",
            "components": {
                "minecraft:banner_patterns": [
                    {"pattern": "minecraft:creeper", "color": "black"}
                ]
            },
        },
        item_display="fixed",
        Rotation=[180.0, 0.0],
    ),
    display(
        (4.5, 1.5, 2.5),
        {"id": "minecraft:enchanted_golden_apple"},
        item_display="ground",
    ),
]


FLOATS = {
    "Rotation": Float,
    "translation": Float,
    "left_rotation": Float,
    "right_rotation": Float,
    "scale": Float,
    "transformation": Float,
}


def nbt(value: Any, number: Any = Int) -> Any:
    if isinstance(value, Base):
        return value
    if isinstance(value, dict):
        return Compound({key: nbt(x, FLOATS.get(key, Int)) for key, x in value.items()})
    if isinstance(value, list):
        if all(isinstance(x, dict) for x in value):
            return List[Compound]([nbt(x) for x in value])
        return List[number]([number(x) for x in value])
    if isinstance(value, bool):
        return Byte(value)
    if isinstance(value, float):
        return Double(value)
    if isinstance(value, int):
        return Int(value)
    return String(value)


def beet_default(ctx: Context):
    blocks = [{"state": 0, "pos": [x, 0, z]} for x in range(5) for z in range(3)]
    ctx.data.structures["display:showcase"] = Structure(
        nbt(
            {
                "DataVersion": 4400,
                "size": [5, 3, 3],
                "palette": [{"Name": "minecraft:smooth_stone"}],
                "blocks": blocks,
                "entities": ENTITIES,
            }
        )
    )
    render = Render(ctx)
    render.add_structure_task(
        "display:showcase",
        path_ctx="display:render/showcase",
        render_size=512,
        display_option={
            "rotation": [30, 200, 0],
            "translation": [0, 0, 0],
            "scale": [2.0, 2.0, 2.0],
        },
    )
    render.run()
