"""item_display entities in structures, like DisplayRenderer and ItemDisplayRenderer (26.3)."""

import math
from typing import Any

import numpy as np
import pytest
from beet import ItemModel as ItemModelFile
from beet import Model, ResourcePack, Texture
from PIL import Image

import model_resolver.tasks.generic_render as generic_render
import model_resolver.tasks.structure as structure
from model_resolver.tasks.generic_render import DIFFUSE_LIGHTS
from model_resolver.tasks.structure import StructureDataModel, StructureRenderTask
from resolver_testkit import GLRecorder, make_getter

FACES = ("down", "up", "north", "south", "west", "east")


@pytest.fixture
def gl(monkeypatch):
    return GLRecorder().install(monkeypatch, generic_render, structure)


def getter():
    assets = ResourcePack()
    for name, color in (("red", (255, 0, 0, 255)), ("blue", (0, 0, 255, 255))):
        assets.textures[f"test:block/{name}"] = Texture(
            Image.new("RGBA", (16, 16), color)
        )
        assets.models[f"test:block/{name}"] = Model(
            {
                "textures": {"a": f"test:block/{name}"},
                "elements": [
                    {
                        # a slab, so rotations show
                        "from": [0, 0, 0],
                        "to": [16, 8, 16],
                        "faces": {face: {"texture": "#a"} for face in FACES},
                    }
                ],
            }
        )
    assets.item_models["test:red"] = ItemModelFile(
        {"model": {"type": "minecraft:model", "model": "test:block/red"}}
    )
    # red when shown as fixed, blue otherwise
    assets.item_models["test:by_context"] = ItemModelFile(
        {
            "model": {
                "type": "minecraft:select",
                "property": "minecraft:display_context",
                "cases": [
                    {
                        "when": "fixed",
                        "model": {"type": "minecraft:model", "model": "test:block/red"},
                    }
                ],
                "fallback": {"type": "minecraft:model", "model": "test:block/blue"},
            }
        }
    )
    # red in the right hand: an item display has no owner, so no hand
    assets.item_models["test:by_hand"] = ItemModelFile(
        {
            "model": {
                "type": "minecraft:select",
                "property": "minecraft:main_hand",
                "cases": [
                    {
                        "when": "right",
                        "model": {"type": "minecraft:model", "model": "test:block/red"},
                    }
                ],
                "fallback": {"type": "minecraft:model", "model": "test:block/blue"},
            }
        }
    )
    return make_getter(assets)


def entity(item_model: str, pos=(0.5, 0.5, 0.5), **nbt: Any) -> dict[str, Any]:
    return {
        "pos": list(pos),
        "blockPos": [math.floor(c) for c in pos],
        "nbt": {
            "id": "minecraft:item_display",
            "item": {
                "id": "minecraft:stone",
                "count": 1,
                "components": {"minecraft:item_model": item_model},
            },
            **nbt,
        },
    }


def draw(gl, *entities):
    task = StructureRenderTask(
        getter=getter(), structure_key="test:unused", do_rotate_camera=False
    )
    task.__dict__["structure"] = StructureDataModel(
        DataVersion=0, size=(0, 0, 0), palette=[], blocks=[], entities=list(entities)
    )
    gl.quads.clear()
    task.run()
    return list(gl.quads)


def extent(quads) -> np.ndarray:
    vertices = np.array([v for quad in quads for v in quad.vertices])
    return np.ptp(vertices, axis=0)


RED, BLUE = (255, 0, 0, 255), (0, 0, 255, 255)


def colors(gl, quads) -> set[tuple[int, ...]]:
    return {gl.texture_pixels[quad.texture] for quad in quads}


def test_an_item_display_draws_its_item_at_its_position(gl):
    quads = draw(gl, entity("test:red", pos=(2.5, 1.5, 0.5)))
    vertices = np.array([v for quad in quads for v in quad.vertices])
    assert len(quads) == 6
    # the slab is the lower half of the item's block, centered on the entity
    assert vertices.mean(axis=0) == pytest.approx((40, 20, 8))
    assert extent(quads) == pytest.approx((16, 8, 16))


def test_entities_other_than_item_displays_are_ignored(gl):
    other = entity("test:red")
    other["nbt"]["id"] = "minecraft:block_display"
    assert draw(gl, other) == []


def test_an_item_display_without_item_draws_nothing(gl):
    empty = entity("test:red")
    del empty["nbt"]["item"]
    assert draw(gl, empty) == []


class TestOrientation:
    def test_pitch_tips_the_item_over(self, gl):
        # rotationYXZ(-yaw, pitch, 0): a 90 degree pitch stands the slab up
        quads = draw(gl, entity("test:red", Rotation=[0.0, 90.0]))
        assert extent(quads) == pytest.approx((16, 16, 8))

    def test_yaw_turns_around_y(self, gl):
        quads = draw(gl, entity("test:red", Rotation=[90.0, 90.0]))
        assert extent(quads) == pytest.approx((8, 16, 16))

    def test_decomposed_transformation(self, gl):
        transformation = {
            "translation": [0, 0, 0],
            "left_rotation": [0, 0, math.sin(math.pi / 4), math.cos(math.pi / 4)],
            "right_rotation": [0, 0, 0, 1],
            "scale": [2, 2, 2],
        }
        quads = draw(gl, entity("test:red", transformation=transformation))
        # a quarter turn around z, twice as big
        assert extent(quads) == pytest.approx((16, 32, 32))

    def test_matrix_transformation_is_row_major(self, gl):
        # translation in the last column of the rows, in blocks
        matrix = [1, 0, 0, 1, 0, 1, 0, 2, 0, 0, 1, 3, 0, 0, 0, 1]
        quads = draw(gl, entity("test:red", transformation=matrix))
        vertices = np.array([v for quad in quads for v in quad.vertices])
        assert vertices.mean(axis=0) == pytest.approx((8 + 16, 4 + 32, 8 + 48))

    def test_other_billboards_are_drawn_fixed(self, gl):
        assert len(draw(gl, entity("test:red", billboard="center"))) == 6


class TestItem:
    @pytest.mark.parametrize(
        "context, color", [("fixed", RED), ("none", BLUE), ("head", BLUE)]
    )
    def test_the_display_context_selects_the_model(self, gl, context, color):
        # the default item_display context is none
        nbt = {} if context == "none" else {"item_display": context}
        assert colors(gl, draw(gl, entity("test:by_context", **nbt))) == {color}

    def test_an_item_display_has_no_hand(self, gl):
        # main_hand reads the owner's arm, an item_display has none: the fallback
        assert colors(gl, draw(gl, entity("test:by_hand"))) == {BLUE}

    def test_unknown_item_models_are_skipped(self, gl):
        assert draw(gl, entity("test:missing")) == []


def test_item_displays_are_lit_like_entities_in_the_world(gl):
    # light.glsl with Lighting.Entry.LEVEL: world-space lights, no camera
    quads = draw(gl, entity("test:red"))
    up = max(quads, key=lambda quad: min(v[1] for v in quad.vertices))
    light0, light1 = (
        max(0.0, float(light @ np.array([0, 1, 0]))) for light in DIFFUSE_LIGHTS
    )
    expected = min(1.0, (light0 + light1) * 0.6 + 0.4)
    assert up.colors[0][0] == pytest.approx(expected)
