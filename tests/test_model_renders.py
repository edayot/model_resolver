"""Block models rendered on their own (Render.add_model_task): tinted like their block in a
biome, shade overrides honoured. Items keep the vanilla GUI behaviour."""

import pytest
from beet import Blockstate, ItemModel as ItemModelFile, Model, ResourcePack, Texture
from PIL import Image

import model_resolver.tasks.generic_render as generic_render
from model_resolver.block_colors import model_blocks
from model_resolver.item_model.tint_source import TintSourceConstant
from model_resolver.tasks.item import ItemRenderTask
from model_resolver.tasks.model import ModelPathRenderTask
from resolver_testkit import GLRecorder, make_getter, make_item

FACES = ("down", "up", "north", "south", "west", "east")


@pytest.fixture
def gl(monkeypatch):
    return GLRecorder().install(monkeypatch, generic_render)


def getter(**options):
    assets = ResourcePack()
    assets.textures["test:block/white"] = Texture(
        Image.new("RGBA", (16, 16), (255,) * 4)
    )
    tinted = {face: {"texture": "#all", "tintindex": 0} for face in FACES}
    assets.models["minecraft:block/water_cauldron_full"] = Model(
        {
            "textures": {"all": "test:block/white"},
            "elements": [
                {"from": [2, 15, 2], "to": [14, 15, 14], "faces": {"up": tinted["up"]}}
            ],
        }
    )
    assets.models["minecraft:block/campfire"] = Model(
        {
            "textures": {"all": "test:block/white"},
            "elements": [
                {
                    "from": [0.8, 1, 8],
                    "to": [15.2, 17, 8],
                    "rotation": {
                        "origin": [8, 8, 8],
                        "axis": "y",
                        "angle": 45,
                        "rescale": True,
                    },
                    "shade_direction_override": "up",
                    "faces": {
                        "north": {"texture": "#all"},
                        "south": {"texture": "#all"},
                    },
                }
            ],
        }
    )
    assets.models["test:block/unused"] = Model(
        {
            "textures": {"all": "test:block/white"},
            "elements": [{"from": [0, 0, 0], "to": [16, 16, 16], "faces": tinted}],
        }
    )
    assets.blockstates["minecraft:water_cauldron"] = Blockstate(
        {
            "variants": {
                "level=1": {"model": "minecraft:block/water_cauldron_level1"},
                "level=3": {"model": "minecraft:block/water_cauldron_full"},
            }
        }
    )
    assets.blockstates["minecraft:campfire"] = Blockstate(
        {"variants": {"lit=true": {"model": "minecraft:block/campfire"}}}
    )
    assets.item_models["test:campfire"] = ItemModelFile(
        {"model": {"type": "minecraft:model", "model": "minecraft:block/campfire"}}
    )
    return make_getter(assets, **options)


def colors(gl):
    return {tuple(round(c * 255) for c in quad.colors[0]) for quad in gl.quads}


def render_model(gl, model, **options):
    gl.quads.clear()
    task = ModelPathRenderTask(
        getter=options.pop("getter", None) or getter(), model=model, **options
    )
    task.run()
    return task


def test_models_map_to_the_block_that_uses_them():
    assert model_blocks(getter())["minecraft:block/water_cauldron_full"] == (
        "minecraft:water_cauldron",
        {"level": "3"},
    )


@pytest.mark.parametrize(
    "biome, water", [("minecraft:plains", 0x3F76E4), ("minecraft:swamp", 0x617B64)]
)
def test_cauldron_water_takes_the_biome_color(gl, biome, water):
    render_model(gl, "minecraft:block/water_cauldron_full", biome=biome)
    (color,) = colors(gl)
    # the top face, lit by the GUI light at its full brightness
    assert color == ((water >> 16) & 0xFF, (water >> 8) & 0xFF, water & 0xFF)


def test_given_tints_win(gl):
    tint = TintSourceConstant(type="minecraft:constant", value=0xFF0000)
    render_model(
        gl, "minecraft:block/water_cauldron_full", tints=[tint], item=make_item()
    )
    assert colors(gl) == {(255, 0, 0)}


def test_models_no_block_uses_are_untinted(gl):
    render_model(gl, "test:block/unused")
    assert all(r == g == b for r, g, b in colors(gl))


def test_colorize_blocks_off_leaves_models_untinted(gl):
    render_model(
        gl, "minecraft:block/water_cauldron_full", getter=getter(colorize_blocks=False)
    )
    assert colors(gl) == {(255, 255, 255)}


class TestCampfireFlame:
    # shade_direction_override: up
    def test_a_model_render_lights_the_flame_like_a_top_face(self, gl):
        render_model(gl, "minecraft:block/campfire")
        assert colors(gl) == {(255, 255, 255)}

    def test_an_item_render_keeps_the_vanilla_gui_light(self, gl):
        # the item shader only sees the quad's normal, the override is a terrain feature
        item = make_item(components={"minecraft:item_model": "test:campfire"})
        task = ItemRenderTask(getter=getter(), item=item)
        gl.quads.clear()
        task.run()
        assert all(color != (255, 255, 255) for color in colors(gl))
