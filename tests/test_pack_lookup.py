"""Which pack wins when the project, the bundled static models and vanilla define the same file."""

import pytest
from beet import Blockstate, Model, ResourcePack, Texture
from PIL import Image

import model_resolver.tasks.generic_render as generic_render
import model_resolver.tasks.structure as structure
from model_resolver.tasks.structure import (
    BlockModel,
    PaletteModel,
    StructureDataModel,
    StructureRenderTask,
)
from resolver_testkit import GLRecorder, gap, make_layered_getter

ALL_FACES = ("down", "up", "north", "south", "west", "east")


@pytest.fixture
def gl(monkeypatch):
    return GLRecorder().install(monkeypatch, generic_render, structure)


def box(from_, to):
    return Model(
        {
            "textures": {"a": "test:block/a"},
            "elements": [
                {
                    "from": from_,
                    "to": to,
                    "faces": {face: {"texture": "#a"} for face in ALL_FACES},
                }
            ],
        }
    )


def vanilla_pack(blockstate):
    pack = ResourcePack()
    pack.textures["test:block/a"] = Texture(Image.new("RGBA", (16, 16), (255,) * 4))
    pack.models["test:block/full"] = box([0, 0, 0], [16, 16, 16])
    pack.blockstates["test:block"] = Blockstate(blockstate)
    return pack


def project_pack(blockstate):
    pack = ResourcePack()
    pack.models["test:block/post"] = box([6, 0, 6], [10, 16, 10])
    pack.blockstates["test:block"] = Blockstate(blockstate)
    return pack


def draw(gl, getter, **properties):
    gl.quads.clear()
    task = StructureRenderTask(getter=getter, structure_key="test:unused")
    palette = PaletteModel(Name="test:block", Properties=properties)
    task.__dict__["structure"] = StructureDataModel(
        DataVersion=0, size=(1, 1, 1), palette=[palette], blocks=[], entities=[]
    )
    task.render_block(BlockModel(state=0, pos=(0, 0, 0)), (0, 0, 0))
    return list(gl.quads)


def widest_x(quads):
    return max(abs(vertex[0]) for quad in quads for vertex in quad.vertices)


def test_project_model_overrides_vanilla():
    project, vanilla = ResourcePack(), ResourcePack()
    project.models["minecraft:block/stone"] = Model({"textures": {"all": "project"}})
    vanilla.models["minecraft:block/stone"] = Model({"textures": {"all": "vanilla"}})
    getter = make_layered_getter(project, vanilla)
    assert getter.assets.models["minecraft:block/stone"].data["textures"] == {
        "all": "project"
    }


def test_bundled_chest_model_overrides_vanilla():
    static, vanilla = ResourcePack(), ResourcePack()
    static.models["minecraft:block/chest"] = Model(
        {"parent": "minecraft:block/generic_chest"}
    )
    vanilla.models["minecraft:block/chest"] = Model(
        {"textures": {"particle": "minecraft:block/oak_planks"}}
    )
    getter = make_layered_getter(ResourcePack(), static, vanilla)
    assert getter.assets.models["minecraft:block/chest"].data == {
        "parent": "minecraft:block/generic_chest"
    }


VARIANTS = {
    "variants": {
        "facing=north": {"model": "test:block/full"},
        "facing=south": {"model": "test:block/full"},
    }
}


def test_states_missing_from_the_top_pack_fall_back_to_vanilla(gl):
    getter = make_layered_getter(
        project_pack({"variants": {"facing=north": {"model": "test:block/post"}}}),
        vanilla_pack(VARIANTS),
    )
    assert widest_x(draw(gl, getter, facing="south")) == pytest.approx(8)


def test_variant_from_the_top_pack_wins(gl):
    getter = make_layered_getter(
        project_pack({"variants": {"facing=north": {"model": "test:block/post"}}}),
        vanilla_pack(VARIANTS),
    )
    assert widest_x(draw(gl, getter, facing="north")) == pytest.approx(2)


MULTIPART_FULL = {"multipart": [{"apply": {"model": "test:block/full"}}]}
MULTIPART_POST = {"multipart": [{"apply": {"model": "test:block/post"}}]}


def test_top_pack_multipart_replaces_vanilla(gl):
    getter = make_layered_getter(
        project_pack(MULTIPART_POST), vanilla_pack(MULTIPART_FULL)
    )
    assert widest_x(draw(gl, getter)) == pytest.approx(2)


def test_drawing_a_block_twice_draws_the_same_geometry(gl):
    getter = make_layered_getter(
        project_pack(MULTIPART_POST), vanilla_pack(MULTIPART_FULL)
    )
    assert len(draw(gl, getter)) == len(draw(gl, getter))
