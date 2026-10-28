"""Model geometry: default UVs, rotation rescale, item model transformations, model loading."""

import math

import numpy as np
import pytest
from beet import Model, ResourcePack, Texture
from PIL import Image

import model_resolver.tasks.generic_render as generic_render
from model_resolver.item_model.model import ItemModel
from model_resolver.item_model.transformation import Transformation
from model_resolver.minecraft_model import (
    MinecraftModel,
    SingleAxisRotationModel,
    resolve_model,
)
from model_resolver.tasks.base import RenderError
from model_resolver.tasks.generic_render import GenericModelRenderTask
from resolver_testkit import (
    GLRecorder,
    gap,
    make_getter,
    make_item,
    model_node,
    rotation_matrix,
    translation_matrix,
)


@pytest.fixture
def gl(monkeypatch):
    return GLRecorder().install(monkeypatch, generic_render)


def make_task(getter=None):
    return GenericModelRenderTask(getter=getter or make_getter(), item=make_item())


def identity_transformation(**overrides):
    return {
        "translation": [0, 0, 0],
        "left_rotation": [0, 0, 0, 1],
        "right_rotation": [0, 0, 0, 1],
        "scale": [1, 1, 1],
        **overrides,
    }


# FaceBakery.defaultFaceUV in 26.3
def vanilla_uv(face, f, t):
    return {
        "down": (f[0], 16 - t[2], t[0], 16 - f[2]),
        "up": (f[0], f[2], t[0], t[2]),
        "north": (16 - t[0], 16 - t[1], 16 - f[0], 16 - f[1]),
        "south": (f[0], 16 - t[1], t[0], 16 - f[1]),
        "west": (f[2], 16 - t[1], t[2], 16 - f[1]),
        "east": (16 - t[2], 16 - t[1], 16 - f[2], 16 - f[1]),
    }[face]


def samples_same_texels(uv, expected):
    """Equal under GL_REPEAT: same start modulo 16 and same signed extent."""
    same_start = all((a - b) % 16 == 0 for a, b in zip(uv[:2], expected[:2]))
    same_extent = (uv[2] - uv[0], uv[3] - uv[1]) == (
        expected[2] - expected[0],
        expected[3] - expected[1],
    )
    return same_start and same_extent


@pytest.mark.parametrize(
    "from_, to",
    [
        pytest.param((0, 0, 0), (16, 16, 16), id="full_cube"),
        pytest.param((0, 0, 0), (16, 8, 16), id="bottom_slab"),
        pytest.param(
            (5, 0, 0),
            (11, 14, 8),
            id="template_wall_side",
        ),
        pytest.param((0, 10, 0), (16, 11, 16), id="hopper_rim"),
        pytest.param((0, 3, 0), (2, 16, 16), id="cauldron_wall"),
    ],
)
def test_default_uv_matches_vanilla(from_, to):
    wrong = {
        face: (GenericModelRenderTask.get_uv(None, face, from_, to), vanilla_uv(face, from_, to))  # type: ignore
        for face in ("down", "up", "north", "south", "west", "east")
        if not samples_same_texels(
            GenericModelRenderTask.get_uv(None, face, from_, to),  # type: ignore
            vanilla_uv(face, from_, to),
        )
    }
    assert wrong == {}


@pytest.mark.parametrize(
    "angle",
    [
        45,
        -45,
        22.5,
        -22.5,
    ],
)
def test_rescale_factor(angle):
    # CuboidRotation.computeRescale: 1 / max(|R * axis|), so 1 / cos(22.5) at 22.5 degrees
    expected = 1 / max(
        abs(math.cos(math.radians(angle))), abs(math.sin(math.radians(angle)))
    )
    rotation = SingleAxisRotationModel(
        origin=(8, 8, 8), axis="y", angle=angle, rescale=True
    )
    ((x, y, z), (ax, ay, az)) = make_task().rotate_vertices(
        ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]), rotation
    )
    assert math.hypot(x, z) == pytest.approx(expected)
    assert (ax, ay, az) == pytest.approx((0, 1, 0))


def placed(gl, transformation, point):
    """Where a model-space pixel point lands once the gui display transform is undone."""
    task = make_task()
    model = MinecraftModel()
    task.rotate_camera(model, None)
    display = gl.matrix.copy()
    task.rotate_camera(model, transformation)
    local = np.linalg.inv(display) @ gl.matrix
    centered = [c - 8 for c in point]  # what center_element feeds to GL
    return (local @ np.array([*centered, 1.0]))[:3]


def vanilla_placed(local, point):
    # ItemTransform.apply ends with translate(-0.5); the item model transformation is
    # applied after it, on geometry in block units
    block = np.array([*(c / 16 for c in point), 1.0])
    return 16 * (translation_matrix(-0.5, -0.5, -0.5) @ local @ block)[:3]


POINTS = [(0, 0, 0), (16, 16, 16), (3, 9, 12)]
HALF_TURN_Y = [0, math.sin(math.pi / 4), 0, math.cos(math.pi / 4)]


@pytest.mark.parametrize(
    "transformation, local",
    [
        pytest.param(identity_transformation(), np.identity(4), id="identity"),
        pytest.param(
            identity_transformation(translation=[0, 0, 1]),
            translation_matrix(0, 0, 1),
            id="translation_in_blocks",
        ),
        pytest.param(
            identity_transformation(left_rotation=HALF_TURN_Y),
            rotation_matrix(90, 0, 1, 0),
            id="rotation_pivot",
        ),
    ],
)
def test_item_model_transformation_space(gl, transformation, local):
    parsed = Transformation.model_validate(transformation)
    for point in POINTS:
        assert placed(gl, parsed, point) == pytest.approx(vanilla_placed(local, point))


def test_vanilla_bed_foot_is_one_block_from_the_head(gl):
    # assets/minecraft/items/red_bed.json in 26.3
    node = {
        "type": "minecraft:composite",
        "models": [
            model_node("minecraft:block/red_bed_head"),
            {
                **model_node("minecraft:block/red_bed_foot"),
                "transformation": identity_transformation(translation=[0, 0, 1]),
            },
        ],
    }
    head, foot = ItemModel.model_validate({"model": node}).resolve(
        make_getter(), make_item()
    )
    point = (8, 4, 8)
    delta = placed(gl, foot.transformation, point) - placed(
        gl, head.transformation, point
    )
    assert delta == pytest.approx((0, 0, 16))


def apply(transformation, point):
    matrix = np.array(transformation.get_matrix()).reshape(4, 4).T
    return (matrix @ np.array([*point, 1.0]))[:3]


def test_decomposed_transformation_is_t_l_s_r():
    transformation = Transformation.model_validate(
        identity_transformation(
            translation=[5, 0, 0], scale=[2, 2, 2], right_rotation=HALF_TURN_Y
        )
    )
    # R first: +x turns to -z, then S doubles it, then T moves it
    assert apply(transformation, (1, 0, 0)) == pytest.approx((5, 0, -2))


def test_matrix_form_is_row_major():
    matrix = Transformation.model_validate(
        [1, 0, 0, 5, 0, 1, 0, 6, 0, 0, 1, 7, 0, 0, 0, 1]
    )
    assert apply(matrix, (0, 0, 0)) == pytest.approx((5, 6, 7))


class TestModelLoading:
    def test_child_textures_override_parent(self):
        assets = ResourcePack()
        assets.models["test:parent"] = Model(
            {
                "textures": {"all": "test:a", "particle": "test:p"},
                "elements": [{"from": [0, 0, 0], "to": [16, 16, 16], "faces": {}}],
            }
        )
        merged = resolve_model(
            {"parent": "test:parent", "textures": {"all": "test:b"}},
            make_getter(assets),
        )
        assert merged["textures"] == {"all": "test:b", "particle": "test:p"}
        assert len(merged["elements"]) == 1

    def test_parent_cycle_raises_a_clear_error(self):
        assets = ResourcePack()
        assets.models["test:a"] = Model({"parent": "test:b"})
        assets.models["test:b"] = Model({"parent": "test:a"})
        with pytest.raises((ValueError, RenderError), match="test:a"):
            resolve_model({"parent": "test:a"}, make_getter(assets))

    def test_texture_reference_loop_resolves_to_nothing(self):
        textures = {"a": "#b", "b": "#a"}
        assert make_task().get_real_key("a", textures) is None  # type: ignore

    def test_long_texture_reference_chain(self):
        textures = {f"t{i}": f"#t{i + 1}" for i in range(12)}
        textures["t12"] = "minecraft:block/stone"
        assert make_task().get_real_key("t0", textures) == "minecraft:block/stone"  # type: ignore

    def test_generated_model_bakes_one_quad_per_layer(self):
        model = MinecraftModel.model_validate(
            {
                "parent": "minecraft:builtin/generated",
                "textures": {"layer0": "test:a", "layer1": "test:b"},
            }
        ).bake()
        assert [e.faces["south"].tintindex for e in model.elements] == [0, 1]

    def test_generated_model_keeps_its_gui_display(self):
        model = MinecraftModel.model_validate(
            {
                "parent": "minecraft:builtin/generated",
                "textures": {"layer0": "test:a"},
                "display": {"gui": {"scale": [2, 2, 2]}},
            }
        ).bake()
        assert model.display.gui.scale == (2, 2, 2)


def textured_getter(**options):
    assets = ResourcePack()
    assets.textures["test:block/a"] = Texture(
        Image.new("RGBA", (16, 16), (255, 0, 0, 255))
    )
    return make_getter(assets, **options)


def cube(faces):
    return MinecraftModel.model_validate(
        {
            "textures": {"a": "test:block/a"},
            "elements": [{"from": [0, 0, 0], "to": [16, 16, 16], "faces": faces}],
        }
    )


class TestDrawing:
    def test_full_face_uv_spans_the_texture(self, gl):
        make_task(textured_getter()).render_model(
            cube({"up": {"texture": "#a", "uv": [0, 0, 16, 16]}}), []
        )
        (quad,) = gl.quads
        assert sorted(quad.uvs) == [(0, 0), (0, 1), (1, 0), (1, 1)]

    def test_tintindex_colors_the_face(self, gl):
        from model_resolver.item_model.tint_source import TintSourceConstant

        tint = TintSourceConstant(type="minecraft:constant", value=0x00FF00)
        make_task(textured_getter()).render_model(
            cube({"up": {"texture": "#a", "tintindex": 0}}), [tint]
        )
        (quad,) = gl.quads
        assert set(quad.colors) == {(0.0, 1.0, 0.0)}

    def test_undefined_texture_variable_draws_missingno(self, gl):
        model = cube({"up": {"texture": "#undefined"}})
        make_task(textured_getter(transparent_missingno=False)).render_model(model, [])
        assert len(gl.quads) == 1


# FaceInfo vertex order in 26.3, for a full cube centered like center_element does
LO, HI = -8.0, 8.0
FACE_INFO = {
    "down": [(LO, LO, HI), (LO, LO, LO), (HI, LO, LO), (HI, LO, HI)],
    "up": [(LO, HI, LO), (LO, HI, HI), (HI, HI, HI), (HI, HI, LO)],
    "north": [(HI, HI, LO), (HI, LO, LO), (LO, LO, LO), (LO, HI, LO)],
    "south": [(LO, HI, HI), (LO, LO, HI), (HI, LO, HI), (HI, HI, HI)],
    "west": [(LO, HI, LO), (LO, LO, LO), (LO, LO, HI), (LO, HI, HI)],
    "east": [(HI, HI, HI), (HI, LO, HI), (HI, LO, LO), (HI, HI, LO)],
}


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("face", list(FACE_INFO))
def test_face_uv_corners_match_vanilla(gl, face, rotation):
    # vertex i takes UV corner (i + rotation / 90) % 4: CuboidFace.getU / getV
    uv = (2, 4, 10, 14)
    model = cube({face: {"texture": "#a", "uv": list(uv), "rotation": rotation}})
    task = GenericModelRenderTask(
        getter=textured_getter(), item=make_item(), do_rotate_camera=False
    )
    task.render_model(model, [])
    (quad,) = gl.quads
    drawn = {
        tuple(round(c, 4) for c in vertex): (round(u * 16, 4), round(v * 16, 4))
        for vertex, (u, v) in zip(quad.vertices, quad.uvs)
    }
    expected = {}
    for index, corner in enumerate(FACE_INFO[face]):
        j = (index + rotation // 90) % 4
        expected[corner] = (
            uv[0] if j in (0, 1) else uv[2],
            uv[1] if j in (0, 3) else uv[3],
        )
    assert drawn == expected


def ortho(left, right, bottom, top, near, far):
    return np.array(
        [
            [2 / (right - left), 0, 0, -(right + left) / (right - left)],
            [0, 2 / (top - bottom), 0, -(top + bottom) / (top - bottom)],
            [0, 0, -2 / (far - near), -(far + near) / (far - near)],
            [0, 0, 0, 1],
        ]
    )


@pytest.mark.parametrize(
    "display",
    [
        {"rotation": [30, 225, 0], "translation": [0, 0, 0], "scale": [0.625] * 3},
        {
            "rotation": [-20, 75, 40],
            "translation": [2, -3, 1.5],
            "scale": [0.5, 1.2, 0.8],
        },
        {"rotation": [180, 0, 180], "translation": [0, 0, 0], "scale": [1, 1, 1]},
    ],
)
def test_gui_camera_matches_vanilla_item_transform(gl, display):
    task = make_task()
    task.rotate_camera(
        MinecraftModel.model_validate({"display": {"gui": display}}), None
    )
    # the projection Task.change_params sets up
    z = task.zoom
    projection = ortho(z, -z, -z, z, task.render_size, -task.render_size)
    rx, ry, rz = display["rotation"]
    rotation = (
        rotation_matrix(rx, 1, 0, 0)
        @ rotation_matrix(ry, 0, 1, 0)
        @ rotation_matrix(rz, 0, 0, 1)
    )[:3, :3]
    depths = []
    for point in POINTS:
        clip = projection @ gl.matrix @ np.array([*(c - 8 for c in point), 1.0])
        # ItemTransform.apply: translate (pixels / 16), rotationXYZ, scale, translate(-0.5)
        block = np.array(point) / 16 - 0.5
        item = np.array(display["translation"]) / 16 + rotation @ (
            np.array(display["scale"]) * block
        )
        # the 16-pixel GUI slot is one block wide and maps to [-1, 1]
        assert clip[:2] == pytest.approx(2 * item[:2])
        depths.append((clip[2], -item[2]))
    # nearer in vanilla (larger z) must be nearer here too
    assert sorted(depths) == sorted(depths, key=lambda d: d[1])


@pytest.mark.parametrize(
    "display, scale, translation",
    [
        ({"scale": [8, 8, 8]}, 4, 0),
        ({"translation": [100, 0, 0]}, 1, 80),
    ],
)
def test_display_transform_is_clamped(gl, display, scale, translation):
    make_task().rotate_camera(
        MinecraftModel.model_validate({"display": {"gui": display}}), None
    )
    assert np.linalg.norm(gl.matrix[:3, 0]) == pytest.approx(scale)
    assert abs(gl.matrix[0, 3]) == pytest.approx(translation)


class TestDisplayInheritance:
    def test_an_explicit_identity_entry_is_kept(self):
        # findTopTransform compares with NO_TRANSFORM by reference: only a missing entry
        # falls back to the parent, an explicit {} is a transform like any other
        assets = ResourcePack()
        assets.models["test:parent"] = Model(
            {"display": {"gui": {"rotation": [30, 225, 0], "scale": [0.625] * 3}}}
        )
        merged = resolve_model(
            {"parent": "test:parent", "display": {"gui": {}}}, make_getter(assets)
        )
        assert MinecraftModel.model_validate(merged).display.gui.rotation == (0, 0, 0)

    def test_a_missing_entry_comes_from_the_parent(self):
        assets = ResourcePack()
        assets.models["test:parent"] = Model(
            {"display": {"gui": {"rotation": [1, 2, 3]}}}
        )
        merged = resolve_model(
            {"parent": "test:parent", "display": {"head": {}}}, make_getter(assets)
        )
        assert MinecraftModel.model_validate(merged).display.gui.rotation == (1, 2, 3)

    def test_left_hand_comes_from_the_same_file_first(self):
        assets = ResourcePack()
        assets.models["test:parent"] = Model(
            {"display": {"thirdperson_lefthand": {"rotation": [1, 1, 1]}}}
        )
        merged = resolve_model(
            {
                "parent": "test:parent",
                "display": {"thirdperson_righthand": {"rotation": [2, 2, 2]}},
            },
            make_getter(assets),
        )
        display = MinecraftModel.model_validate(merged).display
        assert display.thirdperson_lefthand.rotation == (2, 2, 2)

    def test_left_hand_defaults_to_right_hand(self):
        model = MinecraftModel.model_validate(
            {"display": {"thirdperson_righthand": {"rotation": [75, 45, 0]}}}
        )
        assert model.display.thirdperson_lefthand.rotation == (75, 45, 0)


def generated(**model):
    return MinecraftModel.model_validate(
        {"parent": "minecraft:builtin/generated", **model}
    ).bake()


class TestGeneratedModels:
    def test_layers_stop_at_the_first_gap(self):
        model = generated(textures={"layer0": "test:a", "layer2": "test:c"})
        assert len(model.elements) == 1

    def test_own_elements_replace_generated_layers(self):
        element = {"from": [0, 0, 0], "to": [16, 16, 16], "faces": {}}
        model = generated(textures={"layer0": "test:a"}, elements=[element])
        assert len(model.elements) == 1

    def test_generated_models_default_to_front_light(self):
        assert generated(textures={"layer0": "test:a"}).gui_light == "front"


class TestSpecialModelTransformation:
    # special geometries are calibrated for the transformation vanilla gives them
    BANNER = {
        "translation": [0.5, 0, 0.5],
        "left_rotation": [0, 0, 0, 1],
        "right_rotation": [0, 0, 0, 1],
        "scale": [0.6666667, -0.6666667, -0.6666667],
    }

    def special(self, transformation):
        from model_resolver.item_model.model import ItemModelSpecial

        node = {
            "type": "minecraft:special",
            "base": "minecraft:item/white_banner",
            "model": {"type": "minecraft:banner", "color": "white"},
        }
        if transformation is not None:
            node["transformation"] = transformation
        return ItemModelSpecial.model_validate(node)

    def test_the_vanilla_transformation_only_calibrates(self):
        transformation, calibration = self.special(self.BANNER).split_transformation()
        assert transformation is None
        assert calibration is not None

    def test_what_a_pack_adds_is_applied_on_top(self):
        composed = Transformation.model_validate(
            identity_transformation(translation=[0, 1, 0])
        ).compose(Transformation.model_validate(self.BANNER))
        node = self.special(None)
        node.transformation = composed
        transformation, _ = node.split_transformation()
        assert transformation is not None
        assert apply(transformation, (0, 0, 0)) == pytest.approx((0, 1, 0))

    def test_types_without_a_vanilla_transformation_are_left_alone(self):
        from model_resolver.item_model.model import ItemModelSpecial

        node = ItemModelSpecial.model_validate(
            {
                "type": "minecraft:special",
                "base": "minecraft:item/chest",
                "model": {"type": "minecraft:chest", "texture": "minecraft:normal"},
                "transformation": identity_transformation(translation=[1, 0, 0]),
            }
        )
        transformation, calibration = node.split_transformation()
        assert calibration is None
        assert apply(transformation, (0, 0, 0)) == pytest.approx((1, 0, 0))


def test_generated_sides_outline_the_opaque_pixels():
    from model_resolver.minecraft_model import extruded_sides

    image = Image.new("RGBA", (16, 16))
    image.putpixel((3, 4), (255, 0, 0, 255))
    image.putpixel((4, 4), (255, 0, 0, 255))
    sides = extruded_sides(image, 0)
    faces = sorted(face for side in sides for face in side.faces)
    # two pixels side by side: 2 tops, 2 bottoms and the two outer edges
    assert faces == ["down", "down", "east", "up", "up", "west"]
    (east,) = [side for side in sides if "east" in side.faces]
    assert east.from_[0] == east.to[0] == 3  # LEFT faces EAST in vanilla


def test_generated_model_is_extruded_from_7_5_to_8_5():
    model = generated(textures={"layer0": "test:a"})
    (element,) = model.elements
    assert (element.from_[2], element.to[2]) == (7.5, 8.5)
    assert model.display.gui.rotation == (0, 0, 0)


class TestGuiLighting:
    # light.glsl with Lighting.Entry.ITEMS_3D / ITEMS_FLAT
    def levels(self, gui_light, **display):
        from model_resolver.minecraft_model import DisplayOptionModel
        from model_resolver.tasks.generic_render import FACE_NORMALS, GuiLighting

        light = GuiLighting.create(gui_light, DisplayOptionModel(**display))
        return {
            face: round(light.brightness(n) * 255) for face, n in FACE_NORMALS.items()
        }

    def test_isometric_block(self):
        levels = self.levels("side", rotation=(30, 225, 0), scale=(0.625,) * 3)
        assert levels["up"] == 255
        assert levels["down"] == 102  # only the 0.4 ambient

    def test_flat_item_faces_the_light(self):
        assert self.levels("front")["south"] == 255

    def test_head_on_face_with_side_light_is_not_full_bright(self):
        assert self.levels("side")["south"] == 131

    def test_light_follows_the_item_transformation(self):
        from model_resolver.minecraft_model import DisplayOptionModel
        from model_resolver.tasks.generic_render import FACE_NORMALS, GuiLighting

        turn = Transformation.model_validate(
            identity_transformation(left_rotation=HALF_TURN_Y)
        )
        light = GuiLighting.create("front", DisplayOptionModel(), turn)
        # +90 degrees around y turns the west face to the front
        assert round(light.brightness(FACE_NORMALS["west"]) * 255) == 255


class TestDisplayContexts:
    def item_task(self, context):
        from model_resolver.tasks.item import ItemRenderTask

        item = make_item()
        item.display_context = context
        return ItemRenderTask(getter=make_getter(), item=item)

    def test_the_context_picks_the_display_transform(self, gl):
        model = MinecraftModel.model_validate(
            {"display": {"fixed": {"scale": [2, 2, 2]}, "gui": {"scale": [3, 3, 3]}}}
        )
        self.item_task("fixed").rotate_camera(model)
        assert np.linalg.norm(gl.matrix[:3, 0]) == pytest.approx(2)

    def test_items_without_the_transform_use_none(self, gl):
        # ResolvedModel.findTopTransform: NO_TRANSFORM when no model defines it
        self.item_task("gui").rotate_camera(MinecraftModel())
        assert np.linalg.norm(gl.matrix[:3, 0]) == pytest.approx(1)

    def test_left_hands_mirror_the_transform(self, gl):
        model = MinecraftModel.model_validate(
            {"display": {"thirdperson_righthand": {"translation": [4, 0, 0]}}}
        )
        self.item_task("thirdperson_righthand").rotate_camera(model)
        right = gl.matrix[0, 3]
        self.item_task("thirdperson_lefthand").rotate_camera(model)
        assert gl.matrix[0, 3] == pytest.approx(-right)
