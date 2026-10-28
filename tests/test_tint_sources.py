"""Tint sources of minecraft:model item models, checked against 26.3 behaviour."""

import pytest
from beet import ResourcePack, Texture
from PIL import Image

from model_resolver.tasks.structure import TempTintSource
from resolver_testkit import gap, make_getter, make_item

POTION_DEFAULT = -13083194  # vanilla items/potion.json
FIREWORK_DEFAULT = -7697782  # vanilla items/firework_star.json


def tint(data, components=None, getter=None):
    (source,) = TempTintSource.model_validate({"tints": [data]}).tints
    return source.resolve(getter or make_getter(), make_item(components=components))


def rgb(argb):
    return ((argb >> 16) & 0xFF, (argb >> 8) & 0xFF, argb & 0xFF)


class TestConstantAndDye:
    @pytest.mark.parametrize(
        "value, expected", [(-1, (255, 255, 255)), (-16711936, (0, 255, 0))]
    )
    def test_constant_argb_ints(self, value, expected):
        assert tint({"type": "minecraft:constant", "value": value}) == expected

    def test_constant_float_vector(self):
        data = {"type": "minecraft:constant", "value": [1.0, 0.5, 0.0]}
        assert tint(data) == (255, 127, 0)

    def test_dye_uses_dyed_color(self):
        data = {"type": "minecraft:dye", "default": -1}
        assert tint(data, {"minecraft:dyed_color": 0x3366FF}) == (0x33, 0x66, 0xFF)

    def test_dye_default(self):
        assert tint({"type": "minecraft:dye", "default": -6265536}) == rgb(-6265536)

    def test_dye_with_float_vector_component(self):
        data = {"type": "minecraft:dye", "default": -1}
        assert tint(data, {"minecraft:dyed_color": [1.0, 0.0, 0.0]}) == (255, 0, 0)


class TestPotion:
    def test_default_without_component(self):
        data = {"type": "minecraft:potion", "default": POTION_DEFAULT}
        assert tint(data) == rgb(POTION_DEFAULT)

    def test_custom_color_alone(self):
        data = {"type": "minecraft:potion", "default": POTION_DEFAULT}
        components = {"minecraft:potion_contents": {"custom_color": 0xFF0000}}
        assert tint(data, components) == (255, 0, 0)

    def test_color_comes_from_the_potion_effects(self):
        data = {"type": "minecraft:potion", "default": POTION_DEFAULT}
        components = {"minecraft:potion_contents": {"potion": "minecraft:healing"}}
        assert tint(data, components) == (0xF8, 0x24, 0x23)

    def test_custom_effects_are_weighted_by_amplifier(self):
        # speed 0x33EBFF at amplifier 1 counts twice, instant_health 0xF82423 once
        data = {"type": "minecraft:potion", "default": POTION_DEFAULT}
        effects = [{"id": "speed", "amplifier": 1}, {"id": "minecraft:instant_health"}]
        components = {"minecraft:potion_contents": {"custom_effects": effects}}
        expected = (
            (2 * 0x33 + 0xF8) // 3,
            (2 * 0xEB + 0x24) // 3,
            (2 * 0xFF + 0x23) // 3,
        )
        assert tint(data, components) == expected

    def test_hidden_effects_do_not_count(self):
        data = {"type": "minecraft:potion", "default": POTION_DEFAULT}
        hidden = {"id": "minecraft:speed", "show_particles": False}
        components = {
            "minecraft:potion_contents": {
                "potion": "minecraft:healing",
                "custom_effects": [hidden],
            }
        }
        assert tint(data, components) == (0xF8, 0x24, 0x23)

    def test_potion_id_alone(self):
        data = {"type": "minecraft:potion", "default": POTION_DEFAULT}
        components = {"minecraft:potion_contents": "healing"}
        assert tint(data, components) == (0xF8, 0x24, 0x23)

    def test_water_has_no_effect_so_uses_the_default(self):
        data = {"type": "minecraft:potion", "default": POTION_DEFAULT}
        components = {"minecraft:potion_contents": {"potion": "minecraft:water"}}
        assert tint(data, components) == rgb(POTION_DEFAULT)


class TestFirework:
    def test_default_without_component(self):
        data = {"type": "minecraft:firework", "default": FIREWORK_DEFAULT}
        assert tint(data) == rgb(FIREWORK_DEFAULT)

    def test_averages_explosion_colors(self):
        data = {"type": "minecraft:firework", "default": FIREWORK_DEFAULT}
        components = {
            "minecraft:firework_explosion": {
                "shape": "small_ball",
                "colors": [0xFF0000, 0x0000FF],
            }
        }
        assert tint(data, components) == (127, 0, 127)


class TestCustomModelData:
    def test_reads_colors_at_index(self):
        data = {"type": "minecraft:custom_model_data", "index": 1}
        components = {"minecraft:custom_model_data": {"colors": [0x111111, 0x00FF00]}}
        assert tint(data, components) == (0, 255, 0)

    def test_default_without_component(self):
        data = {"type": "minecraft:custom_model_data", "default": 0xFF00FF}
        assert tint(data) == (255, 0, 255)

    def test_default_when_index_is_out_of_range(self):
        data = {"type": "minecraft:custom_model_data", "index": 3, "default": 0xFF00FF}
        components = {"minecraft:custom_model_data": {"colors": [0x00FF00]}}
        assert tint(data, components) == (255, 0, 255)


def colormap_getter():
    # pixel (x, y) has color (x, y, 0), so the result is the sampled coordinate
    image = Image.new("RGB", (256, 256))
    image.putdata([(x, y, 0) for y in range(256) for x in range(256)])
    assets = ResourcePack()
    assets.textures["minecraft:colormap/grass"] = Texture(image)
    return make_getter(assets)


class TestGrass:
    def test_hot_and_wet_corner(self):
        data = {"type": "minecraft:grass", "temperature": 1.0, "downfall": 1.0}
        assert tint(data, getter=colormap_getter()) == (0, 0, 0)

    def test_samples_like_vanilla_colormap_util(self):
        # every vanilla grass-tinted item uses temperature 0.5, downfall 1.0
        data = {"type": "minecraft:grass", "temperature": 0.5, "downfall": 1.0}
        assert tint(data, getter=colormap_getter()) == (127, 127, 0)

    def test_temperature_out_of_range_is_rejected(self):
        with pytest.raises(ValueError):
            tint({"type": "minecraft:grass", "temperature": 2, "downfall": 0.5})


def test_every_effect_has_a_color():
    # CFR writes some effect colors in hex, the generator must read them
    from model_resolver.item_model.tint_source import potion_table

    effects = potion_table("26.3")["effects"]
    assert effects["minecraft:fire_resistance"] == 0xFF9900
    assert all(color != 0 for color in effects.values())
