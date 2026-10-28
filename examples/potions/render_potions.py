"""Potion tints: potion ids, custom colors and custom effects, on every potion-like item."""

from beet import Context
from model_resolver import Item, Render

POTION_CONTENTS = {
    "water": {"potion": "minecraft:water"},
    "healing": {"potion": "minecraft:healing"},
    "strong_poison": {"potion": "minecraft:strong_poison"},
    # two effects, weighted by amplifier + 1
    "turtle_master": {"potion": "minecraft:turtle_master"},
    # ids without namespace
    "fire_resistance": "fire_resistance",
    "custom_color": {"potion": "minecraft:healing", "custom_color": 0xFF00FF},
    "custom_effects": {
        "custom_effects": [
            {"id": "minecraft:speed", "amplifier": 1, "duration": 200},
            {"id": "minecraft:instant_health", "duration": 1},
        ]
    },
    # hidden effects don't color the potion
    "hidden_effect": {
        "potion": "minecraft:healing",
        "custom_effects": [
            {"id": "minecraft:wither", "duration": 200, "show_particles": False}
        ],
    },
}


def beet_default(ctx: Context):
    render = Render(ctx)
    for name, contents in POTION_CONTENTS.items():
        render.add_item_task(
            Item(
                id="minecraft:potion",
                components={"minecraft:potion_contents": contents},
            ),
            path_ctx=f"potions:render/potion/{name}",
            render_size=128,
        )
    for item in ("splash_potion", "lingering_potion", "tipped_arrow"):
        for name in ("healing", "strong_poison", "turtle_master"):
            render.add_item_task(
                Item(
                    id=f"minecraft:{item}",
                    components={"minecraft:potion_contents": POTION_CONTENTS[name]},
                ),
                path_ctx=f"potions:render/{item}/{name}",
                render_size=128,
            )
    render.run()
