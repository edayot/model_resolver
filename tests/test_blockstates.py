"""Blockstate variants and multipart conditions, as drawn by structure rendering."""

from typing import Any

import numpy as np

import pytest
from beet import Model, ResourcePack, Texture
from PIL import Image

import model_resolver.tasks.generic_render as generic_render
import model_resolver.tasks.structure as structure
from model_resolver.minecraft_model import MinecraftModel
from model_resolver.tasks.structure import (
    BlockModel,
    BlockState,
    PaletteModel,
    StructureRenderTask,
    VariantModel,
    verify_when,
)
from resolver_testkit import GLRecorder, gap, make_getter

ALL_FACES = ("down", "up", "north", "south", "west", "east")


@pytest.fixture
def gl(monkeypatch):
    return GLRecorder().install(monkeypatch, generic_render, structure)


def block_getter():
    assets = ResourcePack()
    assets.textures["test:block/a"] = Texture(
        Image.new("RGBA", (16, 16), (255, 255, 255, 255))
    )
    assets.models["test:block/top"] = Model(
        {
            "textures": {"a": "test:block/a"},
            "elements": [
                {
                    "from": [0, 0, 0],
                    "to": [16, 16, 16],
                    "faces": {"up": {"texture": "#a", "uv": [0, 0, 16, 16]}},
                }
            ],
        }
    )
    assets.models["test:block/bottom_slab"] = Model(
        {
            "textures": {"a": "test:block/a"},
            "elements": [
                {
                    "from": [0, 0, 0],
                    "to": [16, 8, 16],
                    "faces": {face: {"texture": "#a"} for face in ALL_FACES},
                }
            ],
        }
    )
    return make_getter(assets)


def draw(gl, **variant):
    gl.quads.clear()
    task = StructureRenderTask(getter=block_getter(), structure_key="test:unused")
    task.render_variant(
        VariantModel(**variant),
        BlockModel(state=0, pos=(0, 0, 0)),
        (0, 0, 0),
        PaletteModel(Name="test:block"),
    )
    return list(gl.quads)


def uv_at_corners(quads):
    (quad,) = quads
    return {
        tuple(round(c, 4) for c in vertex): tuple(round(c, 4) for c in uv)
        for vertex, uv in zip(quad.vertices, quad.uvs)
    }


def heights(quads):
    return [vertex[1] for quad in quads for vertex in quad.vertices]


class TestVariantRotation:
    def test_y_rotation_turns_the_texture_without_uvlock(self, gl):
        unrotated = uv_at_corners(draw(gl, model="test:block/top"))
        assert uv_at_corners(draw(gl, model="test:block/top", y=90)) != unrotated

    def test_uvlock_keeps_the_texture_aligned_with_the_world(self, gl):
        unrotated = uv_at_corners(draw(gl, model="test:block/top"))
        locked = uv_at_corners(draw(gl, model="test:block/top", y=90, uvlock=True))
        assert locked == unrotated

    def test_x_rotation_moves_a_bottom_slab_to_the_top(self, gl):
        assert min(
            heights(draw(gl, model="test:block/bottom_slab", x=180))
        ) == pytest.approx(0)

    def test_z_rotation_moves_a_bottom_slab_to_the_top(self, gl):
        assert min(
            heights(draw(gl, model="test:block/bottom_slab", z=180))
        ) == pytest.approx(0)


STATE = {"north": "side", "east": "none", "power": "15"}


class TestMultipartWhen:
    def test_alternatives(self):
        assert verify_when({"north": "up|side"}, STATE)

    def test_or(self):
        assert verify_when({"OR": [{"north": "up"}, {"east": "none"}]}, STATE)

    def test_and_with_nested_or(self):
        # WhenCondition does not model nesting, verify_when supports it
        when: Any = {
            "AND": [{"power": "15"}, {"OR": [{"north": "up"}, {"north": "side"}]}]
        }
        assert verify_when(when, STATE)

    def test_unknown_property_does_not_match(self):
        assert not verify_when({"south": "side"}, STATE)

    def test_negation(self):
        assert verify_when({"north": "!none"}, STATE)
        assert not verify_when({"east": "!none"}, STATE)


class TestMultipartTerms:
    def test_each_alternative_can_be_negated(self):
        assert not verify_when({"east": "!none|side"}, STATE)
        assert verify_when({"east": "!up|none"}, STATE)

    def test_boolean_and_number_values(self):
        when: Any = {"lit": True, "power": 15}
        assert verify_when(when, {"lit": "true", "power": "15"})


def models(variants):
    return [variant.model for variant in variants]


class TestDefinitionCoverage:
    # BlockStateModelDispatcher.instantiate
    DEFINITION = BlockState.model_validate(
        {
            "variants": {"facing=north": {"model": "test:block/top"}},
            "multipart": [
                {"apply": {"model": "test:block/bottom_slab"}},
                {"when": {"facing": "east"}, "apply": {"model": "test:block/top"}},
            ],
        }
    )

    def test_a_matching_variant_wins(self):
        assert models(self.DEFINITION.select({"facing": "north"})) == ["test:block/top"]

    def test_multipart_covers_the_states_variants_miss(self):
        assert models(self.DEFINITION.select({"facing": "east"})) == [
            "test:block/bottom_slab",
            "test:block/top",
        ]

    def test_a_file_without_multipart_does_not_cover_other_states(self):
        definition = BlockState.model_validate(
            {"variants": {"facing=north": {"model": "test:block/top"}}}
        )
        assert definition.select({"facing": "south"}) is None

    def test_empty_variant_key_matches_every_state(self):
        definition = BlockState.model_validate(
            {"variants": {"": {"model": "test:block/top"}}}
        )
        assert models(definition.select({"facing": "south"})) == ["test:block/top"]


def structure_getter():
    from beet import Blockstate

    getter = block_getter()
    assets = getter._static_lookup.assets
    assert assets is not None
    face = {"texture": "#a"}
    assets.models["test:block/cube"] = Model(
        {
            "textures": {"a": "test:block/a"},
            "elements": [
                {
                    "from": [0, 0, 0],
                    "to": [16, 16, 16],
                    "faces": {f: {**face, "cullface": f} for f in ALL_FACES},
                }
            ],
        }
    )
    glass = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
    glass.putpixel((0, 0), (0, 0, 0, 0))
    assets.textures["test:block/glass"] = Texture(glass)
    assets.models["test:block/glass"] = Model(
        {"parent": "test:block/cube", "textures": {"a": "test:block/glass"}}
    )
    assets.textures["minecraft:block/water_still"] = Texture(
        Image.new("RGBA", (16, 32), (200, 200, 200, 180))
    )
    assets.textures["minecraft:block/water_flow"] = Texture(
        Image.new("RGBA", (32, 64), (200, 200, 200, 180))
    )
    assets.blockstates["minecraft:oak_slab"] = Blockstate(
        {"variants": {"": {"model": "test:block/bottom_slab"}}}
    )
    for name, model in (
        ("test:stone", "test:block/cube"),
        ("test:glass", "test:block/glass"),
        ("minecraft:water", "test:block/air"),
    ):
        assets.blockstates[name] = Blockstate({"variants": {"": {"model": model}}})
    assets.models["test:block/air"] = Model({})
    return getter


def structure_quads(gl, blocks, palette, getter=None, size=(4, 4, 4), **options):
    from model_resolver.tasks.structure import StructureDataModel

    gl.quads.clear()
    task = StructureRenderTask(
        getter=getter or structure_getter(),
        structure_key="test:unused",
        do_rotate_camera=False,
        **options,
    )
    task.__dict__["structure"] = StructureDataModel(
        DataVersion=0,
        size=size,
        palette=[PaletteModel(**entry) for entry in palette],
        blocks=[BlockModel(state=state, pos=pos) for state, pos in blocks],
        entities=[],
    )
    task.run()
    return list(gl.quads)


class TestStructures:
    def test_faces_between_two_opaque_cubes_are_culled(self, gl):
        quads = structure_quads(
            gl, [(0, (0, 0, 0)), (0, (1, 0, 0))], [{"Name": "test:stone"}]
        )
        assert len(quads) == 10

    def test_glass_only_culls_against_glass(self, gl):
        palette = [{"Name": "test:glass"}, {"Name": "test:stone"}]
        assert len(structure_quads(gl, [(0, (0, 0, 0)), (0, (1, 0, 0))], palette)) == 10
        # stone hides the glass face, glass hides nothing
        assert len(structure_quads(gl, [(0, (0, 0, 0)), (1, (1, 0, 0))], palette)) == 11

    def test_water_is_eight_ninths_high(self, gl):
        # alone in its structure: past its sides the water is assumed to go on, so it's flat
        quads = structure_quads(
            gl, [(0, (0, 0, 0))], [{"Name": "minecraft:water"}], size=(1, 1, 1)
        )
        heights = {vertex[1] for quad in quads for vertex in quad.vertices}
        # FluidRenderer moves the top and the bottom 0.001 inside
        assert max(heights) - min(heights) == pytest.approx(16 * (8 / 9 - 0.002))

    def test_waterlogged_blocks_hold_water(self, gl):
        palette = [
            {
                "Name": "minecraft:oak_slab",
                "Properties": {"type": "bottom", "waterlogged": "true"},
            }
        ]
        quads = structure_quads(gl, [(0, (0, 0, 0))], palette)
        # 6 slab faces, the water's top and 4 sides (both drawn from behind too):
        # the slab's own shape hides the water's bottom (isFaceOccludedBySelf)
        assert len(quads) == 6 + 2 + 8

    def test_a_waterlogged_full_block_only_shows_its_water_top(self, gl):
        palette = [{"Name": "test:stone", "Properties": {"waterlogged": "true"}}]
        assert len(structure_quads(gl, [(0, (0, 0, 0))], palette)) == 6 + 2

    @pytest.mark.parametrize(
        "name", ["minecraft:kelp", "minecraft:seagrass", "minecraft:bubble_column"]
    )
    def test_some_blocks_always_hold_water(self, gl, name):
        task = StructureRenderTask(
            getter=structure_getter(), structure_key="test:unused"
        )
        assert task.fluid_of(PaletteModel(Name=name)) == "minecraft:water"

    def test_an_uncovered_state_draws_the_missing_model(self, gl):
        from beet import Blockstate

        getter = structure_getter()
        assets = getter._static_lookup.assets
        assert assets is not None
        assets.blockstates["test:block"] = Blockstate(
            {"variants": {"facing=north": {"model": "test:block/cube"}}}
        )
        task = StructureRenderTask(getter=getter, structure_key="test:unused")
        (variant,) = task.get_block_variants(
            PaletteModel(Name="test:block", Properties={"facing": "south"})
        )
        assert not isinstance(variant, list) and not isinstance(variant.model, str)
        assert variant.model.elements[0].faces["up"].texture == "#missingno"


def test_stems_are_tinted_by_age():
    task = StructureRenderTask(getter=block_getter(), structure_key="test:unused")
    (tint,) = task.get_tints(
        "minecraft:block/pumpkin_stem_stage7",
        PaletteModel(Name="minecraft:pumpkin_stem", Properties={"age": "7"}),
    )
    assert tint.resolve(task.getter, task.item) == (224, 199, 28)


def test_item_display_entities_are_drawn(gl):
    from beet import ItemModel as ItemModelFile

    from model_resolver.tasks.structure import StructureDataModel

    getter = structure_getter()
    assets = getter._static_lookup.assets
    assert assets is not None
    assets.item_models["test:thing"] = ItemModelFile(
        {"model": {"type": "minecraft:model", "model": "test:block/cube"}}
    )
    entity = {
        "pos": [2.5, 0.5, 0.5],
        "blockPos": [2, 0, 0],
        "nbt": {
            "id": "minecraft:item_display",
            "item": {
                "id": "minecraft:stone",
                "components": {"item_model": "test:thing"},
            },
            "transformation": {
                "translation": [0, 1, 0],
                "left_rotation": [0, 0, 0, 1],
                "right_rotation": [0, 0, 0, 1],
                "scale": [0.5, 0.5, 0.5],
            },
        },
    }
    task = StructureRenderTask(
        getter=getter, structure_key="test:unused", do_rotate_camera=False
    )
    task.__dict__["structure"] = StructureDataModel(
        DataVersion=0, size=(0, 0, 0), palette=[], blocks=[], entities=[entity]
    )
    gl.quads.clear()
    task.run()
    vertices = np.array([v for quad in gl.quads for v in quad.vertices])
    assert len(gl.quads) == 6
    # centered on the entity, one block up, half a block wide
    assert vertices.mean(axis=0) == pytest.approx((40, 24, 8))
    assert np.ptp(vertices, axis=0) == pytest.approx((8, 8, 8))


WATER = [{"Name": "minecraft:water", "Properties": {"level": "0"}}]


def face_colors(quads):
    """{face direction: color} of axis-aligned quads, from their normal."""
    result = {}
    for quad in quads:
        a, b, c = (np.array(v) for v in quad.vertices[:3])
        normal = np.cross(b - a, c - a)
        axis = int(np.argmax(np.abs(normal)))
        result[(axis, bool(normal[axis] > 0))] = quad.colors[0]
    return result


def rgb(color):
    return tuple(round(c * 255) for c in color)


class TestWater:
    # FluidRenderer: tinted by the biome's water color, shaded by CardinalLighting
    @pytest.mark.parametrize(
        "biome, water",
        [
            ("minecraft:plains", 0x3F76E4),
            ("minecraft:swamp", 0x617B64),
            ("warm_ocean", 0x43D5EE),
            ({"effects": {"water_color": "#123456"}}, 0x123456),
        ],
    )
    def test_water_takes_the_biome_color(self, gl, biome, water):
        quads = structure_quads(gl, [(0, (0, 0, 0))], WATER, biome=biome)
        colors = [rgb(quad.colors[0]) for quad in quads]
        top = ((water >> 16) & 0xFF, (water >> 8) & 0xFF, water & 0xFF)
        assert top in colors

    def test_sides_are_darker_than_the_top(self, gl):
        quads = structure_quads(gl, [(0, (0, 0, 0))], WATER)
        shades = sorted({round(quad.colors[0][2] / (0xE4 / 255), 3) for quad in quads})
        # down 0.5, east/west 0.6, north/south 0.8, up 1.0
        assert shades == [0.5, 0.6, 0.8, 1.0]

    def test_sides_use_the_flowing_texture(self, gl):
        quads = structure_quads(gl, [(0, (0, 0, 0))], WATER, size=(1, 1, 1))
        still = quads[0].texture  # the top face
        sides = [quad for quad in quads if quad.texture != still]
        assert len(sides) == 8  # front and back
        vs = sorted({round(v, 9) for _, v in sides[0].uvs})
        # the top (1 - height) / 2 of the flowing texture's left half
        assert vs == pytest.approx([(1 - (8 / 9 - 0.001)) / 2, 0.5])

    def test_an_unknown_biome_falls_back_to_plains(self, gl):
        quads = structure_quads(gl, [(0, (0, 0, 0))], WATER, biome="test:nowhere")
        assert (0x3F, 0x76, 0xE4) in [rgb(quad.colors[0]) for quad in quads]


def biome_getter():
    getter = structure_getter()
    assets = getter._static_lookup.assets
    assert assets is not None
    # pixel (x, y) has color (x, y, 0): the color is where the colormap was sampled
    colormap = Image.new("RGB", (256, 256))
    colormap.putdata([(x, y, 0) for y in range(256) for x in range(256)])
    for name in ("grass", "foliage", "dry_foliage"):
        assets.textures[f"minecraft:colormap/{name}"] = Texture(colormap)
    return getter


class TestBlockColors:
    # BlockColors.createDefault with the structure's biome
    def tint(self, name, biome="minecraft:plains", **properties):
        task = StructureRenderTask(
            getter=biome_getter(), structure_key="test:unused", biome=biome
        )
        tints = task.get_tints(
            "minecraft:block/x", PaletteModel(Name=name, Properties=properties)
        )
        return [tint.resolve(task.getter, task.item) for tint in tints]

    def test_grass_samples_the_biome_climate(self):
        # plains: temperature 0.8, downfall 0.4
        x, y = int((1 - 0.8) * 255), int((1 - 0.4 * 0.8) * 255)
        assert self.tint("minecraft:grass_block") == [(x, y, 0)]

    def test_biome_overrides_win(self):
        assert self.tint("minecraft:oak_leaves", "minecraft:swamp") == [
            (0x6A, 0x70, 0x39)
        ]
        assert self.tint("minecraft:grass_block", "minecraft:badlands") == [
            (0x90, 0x81, 0x4D)
        ]

    def test_swamp_grass(self):
        assert self.tint("minecraft:short_grass", "minecraft:swamp") == [
            (0x6A, 0x70, 0x39)
        ]

    def test_dark_forest_darkens_grass(self):
        x, y = int((1 - 0.7) * 255), int((1 - 0.8 * 0.7) * 255)
        base = x << 16 | y << 8
        expected = ((base & 0xFEFEFE) + 0x28340A) >> 1
        assert self.tint("minecraft:grass_block", "minecraft:dark_forest") == [
            ((expected >> 16) & 0xFF, (expected >> 8) & 0xFF, expected & 0xFF)
        ]

    def test_constant_leaves(self):
        assert self.tint("minecraft:birch_leaves", "minecraft:swamp") == [
            (0x80, 0xA7, 0x55)
        ]

    def test_water_cauldron(self):
        assert self.tint("minecraft:water_cauldron", "minecraft:swamp") == [
            (0x61, 0x7B, 0x64)
        ]

    def test_flowers_tint_their_second_layer(self):
        assert self.tint("minecraft:pink_petals")[0] == (255, 255, 255)

    def test_redstone_by_power(self):
        # 0.7f - 0.5f is 0.19999999 in float32, so green is 50
        assert self.tint("minecraft:redstone_wire", power="15") == [(255, 50, 0)]


def flame_model(**element):
    return MinecraftModel.model_validate(
        {
            "textures": {"a": "test:block/a"},
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
                    "faces": {"north": {"texture": "#a"}, "south": {"texture": "#a"}},
                    **element,
                },
                {
                    "from": [0, 0, 0],
                    "to": [16, 1, 16],
                    "faces": {f: {"texture": "#a"} for f in ALL_FACES},
                },
            ],
        }
    )


class TestBlockShading:
    def draw(self, gl, model, lighting):
        from model_resolver.tasks.model import ModelRenderTask

        gl.quads.clear()
        ModelRenderTask(
            getter=block_getter(),
            model=model,
            do_rotate_camera=False,
            lighting=lighting,
        ).run()
        return [round(quad.colors[0][0], 3) for quad in gl.quads]

    def test_shade_direction_override_lights_the_campfire_flame_like_a_top(self, gl):
        shades = self.draw(gl, flame_model(shade_direction_override="up"), "terrain")
        assert shades[:2] == [1.0, 1.0]
        # the base: down, up, north, south, west, east
        assert shades[2:] == [0.5, 1.0, 0.8, 0.8, 0.6, 0.6]

    def test_without_override_the_rotated_face_takes_its_nearest_axis(self, gl):
        shades = self.draw(gl, flame_model(), "terrain")
        assert set(shades[:2]) <= {0.6, 0.8}

    def test_legacy_shade_false_is_unshaded(self, gl):
        assert self.draw(gl, flame_model(shade=False), "terrain")[:2] == [1.0, 1.0]

    def test_items_ignore_the_override(self, gl):
        # the item shader lights the quad's (axis-snapped) normal
        with_override = self.draw(gl, flame_model(shade_direction_override="up"), "gui")
        assert with_override == self.draw(gl, flame_model(), "gui")


def test_unpremultiply():
    from model_resolver.render import unpremultiply

    image = Image.new("RGBA", (2, 1))
    image.putdata([(100, 50, 0, 128), (0, 0, 0, 0)])
    result = unpremultiply(image)
    assert [result.getpixel((x, 0)) for x in range(2)] == [
        (199, 100, 0, 128),
        (0, 0, 0, 0),
    ]


class TestAnimatedWater:
    def task(self):
        from model_resolver.tasks.structure import StructureDataModel

        task = StructureRenderTask(
            getter=structure_getter(), structure_key="test:unused"
        )
        task.__dict__["structure"] = StructureDataModel(
            DataVersion=0,
            size=(1, 1, 1),
            palette=[PaletteModel(**WATER[0])],
            blocks=[BlockModel(state=0, pos=(0, 0, 0))],
            entities=[],
        )
        return task

    def test_fluid_textures_take_part_in_the_animation(self):
        textures = list(self.task().get_all_textures())
        assert {
            "still": "minecraft:block/water_still",
            "flow": "minecraft:block/water_flow",
        } in textures

    def test_water_is_animated_when_its_texture_is(self):
        from beet import TextureMcmeta

        from model_resolver.tasks.generic_render import Animation

        task = self.task()
        assets = task.getter._static_lookup.assets
        assert assets is not None
        assets.textures_mcmeta["minecraft:block/water_still"] = TextureMcmeta(
            {"animation": {"frametime": 3}}
        )
        animation = Animation(
            textures=list(task.get_all_textures()),
            getter=task.getter,
            animation_framerate=20,
        )
        # 16x32: two frames of 3 ticks
        assert [duration for _, (_, duration) in animation.get_frames()] == [3, 3]

    def test_each_frame_draws_its_own_image(self, gl):
        frame = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
        override = {"minecraft:block/water_still": frame}
        quads = structure_quads(
            gl, [(0, (0, 0, 0))], WATER, size=(1, 1, 1), images_override=override
        )
        top = max(quads, key=lambda quad: max(v[1] for v in quad.vertices))
        assert gl.texture_pixels[top.texture] == (255, 0, 0, 255)


@pytest.mark.parametrize(
    "entry",
    [
        {"id": "minecraft:water", "properties": {"level": "1"}},  # 26.1 and later
        {"Name": "minecraft:water", "Properties": {"level": "1"}},  # legacy
    ],
)
def test_structure_palettes_in_both_formats(entry):
    from model_resolver.tasks.structure import StructureDataModel

    structure = StructureDataModel.model_validate(
        {"DataVersion": 5023, "size": [1, 1, 1], "palette": [entry], "blocks": [], "entities": []}
    )
    (palette,) = structure.palette
    assert (palette.Name, palette.Properties) == ("minecraft:water", {"level": "1"})
