"""Resolution of item model definitions (assets/<namespace>/items/*.json), no rendering."""

import pytest

from model_resolver.item_model.model import ItemModel, ItemModelRecursive
from resolver_testkit import (
    gap,
    make_getter,
    make_item,
    model_node,
    resolve_item_model as resolve,
)


def custom_model_data_range(thresholds, scale=None):
    node = {
        "type": "minecraft:range_dispatch",
        "property": "minecraft:custom_model_data",
        "entries": [
            {"threshold": t, "model": model_node(f"test:{t}")} for t in thresholds
        ],
        "fallback": model_node("test:fallback"),
    }
    if scale is not None:
        node["scale"] = scale
    return node


def with_floats(*floats):
    return make_item(
        components={"minecraft:custom_model_data": {"floats": list(floats)}}
    )


def select(property, cases, **extra):
    return {
        "type": "minecraft:select",
        "property": property,
        "cases": [{"when": when, "model": model_node(model)} for when, model in cases],
        "fallback": model_node("test:fallback"),
        **extra,
    }


def condition(property, **extra):
    return {
        "type": "minecraft:condition",
        "property": property,
        "on_true": model_node("test:true"),
        "on_false": model_node("test:false"),
        **extra,
    }


class TestRangeDispatch:
    def test_picks_the_last_threshold_below_the_value(self):
        assert resolve(custom_model_data_range([0, 1, 2]), with_floats(1.5)) == [
            "test:1"
        ]

    def test_threshold_is_inclusive(self):
        assert resolve(custom_model_data_range([0, 1, 2]), with_floats(2)) == ["test:2"]

    def test_entries_do_not_need_to_be_sorted(self):
        assert resolve(custom_model_data_range([2, 0, 1]), with_floats(1.5)) == [
            "test:1"
        ]

    def test_value_below_every_threshold_uses_the_fallback(self):
        assert resolve(custom_model_data_range([1, 2]), with_floats(0.5)) == [
            "test:fallback"
        ]

    def test_scale_multiplies_the_value(self):
        node = custom_model_data_range([0, 5], scale=10)
        assert resolve(node, with_floats(0.5)) == ["test:5"]

    def test_negative_thresholds(self):
        assert resolve(custom_model_data_range([-1, 0]), with_floats(-0.5)) == [
            "test:-1"
        ]

    def test_damage_of_a_non_damageable_item_uses_the_fallback(self):
        node = {
            "type": "minecraft:range_dispatch",
            "property": "minecraft:damage",
            "entries": [{"threshold": 0, "model": model_node("test:0")}],
            "fallback": model_node("test:fallback"),
        }
        assert resolve(node, make_item()) == ["test:fallback"]


class TestSelect:
    def test_case_with_a_list_of_values(self):
        node = select("minecraft:display_context", [(["fixed", "gui"], "test:gui")])
        assert resolve(node) == ["test:gui"]

    def test_fallback_is_optional(self):
        node = select("minecraft:display_context", [("gui", "test:gui")])
        del node["fallback"]
        assert resolve(node) == ["test:gui"]

    def test_charge_type_without_projectiles(self):
        node = select(
            "minecraft:charge_type", [("arrow", "test:arrow"), ("none", "test:none")]
        )
        assert resolve(node) == ["test:none"]

    @pytest.mark.parametrize(
        "projectile, expected",
        [
            ("minecraft:arrow", "test:arrow"),
            ("minecraft:firework_rocket", "test:rocket"),
        ],
    )
    def test_charge_type_reads_charged_projectiles(self, projectile, expected):
        node = select(
            "minecraft:charge_type",
            [("arrow", "test:arrow"), ("rocket", "test:rocket")],
        )
        item = make_item(
            components={
                "minecraft:charged_projectiles": [{"id": projectile, "count": 1}]
            }
        )
        assert resolve(node, item) == [expected]

    def test_main_hand_defaults_to_right(self):
        node = select("minecraft:main_hand", [("right", "test:right")])
        assert resolve(node) == ["test:right"]

    def test_trim_material(self):
        node = select("minecraft:trim_material", [("minecraft:gold", "test:gold")])
        item = make_item(components={"minecraft:trim": {"material": "minecraft:gold"}})
        assert resolve(node, item) == ["test:gold"]

    def test_trim_material_without_namespace(self):
        node = select("minecraft:trim_material", [("minecraft:gold", "test:gold")])
        item = make_item(components={"minecraft:trim": {"material": "gold"}})
        assert resolve(node, item) == ["test:gold"]

    def test_custom_model_data_strings(self):
        node = select("minecraft:custom_model_data", [("b", "test:b")], index=1)
        item = make_item(
            components={"minecraft:custom_model_data": {"strings": ["a", "b"]}}
        )
        assert resolve(node, item) == ["test:b"]


class TestCondition:
    def test_has_component(self):
        node = condition("minecraft:has_component", component="minecraft:dyed_color")
        item = make_item(components={"minecraft:dyed_color": 0xFF0000})
        assert resolve(node, item) == ["test:true"]

    def test_has_component_without_namespace(self):
        node = condition("minecraft:has_component", component="dyed_color")
        item = make_item(components={"minecraft:dyed_color": 0xFF0000})
        assert resolve(node, item) == ["test:true"]

    @pytest.mark.parametrize("damage, expected", [(8, "test:false"), (9, "test:true")])
    def test_broken_when_the_next_hit_breaks_it(self, damage, expected):
        item = make_item(
            components={"minecraft:damage": damage, "minecraft:max_damage": 10}
        )
        assert resolve(condition("minecraft:broken"), item) == [expected]

    def test_custom_model_data_flag_out_of_range_is_false(self):
        node = condition("minecraft:custom_model_data", index=3)
        item = make_item(components={"minecraft:custom_model_data": {"flags": [True]}})
        assert resolve(node, item) == ["test:false"]


class TestTreeShape:
    def test_composite_keeps_child_order(self):
        node = {
            "type": "minecraft:composite",
            "models": [model_node("test:a"), model_node("test:b")],
        }
        assert resolve(node) == ["test:a", "test:b"]

    def test_empty_and_bundle_selected_item_draw_nothing(self):
        node = {
            "type": "minecraft:composite",
            "models": [
                {"type": "minecraft:empty"},
                {"type": "minecraft:bundle/selected_item"},
            ],
        }
        assert resolve(node) == []

    def test_resolving_twice_gives_the_same_transformation(self):
        parsed = ItemModel.model_validate(
            {
                "model": {
                    "type": "minecraft:composite",
                    "transformation": {
                        "translation": [1, 2, 3],
                        "left_rotation": [0, 0, 0, 1],
                        "right_rotation": [0, 0, 0, 1],
                        "scale": [1, 1, 1],
                    },
                    "models": [model_node("test:a")],
                }
            }
        )
        getter, item = make_getter(), make_item()

        def matrices():
            return [
                model.transformation.get_matrix() if model.transformation else None
                for model in parsed.resolve(getter, item)
            ]

        assert matrices() == matrices()

    def test_unknown_type_raises_a_readable_error(self):
        with pytest.raises(ValueError, match="not_a_model_type"):
            ItemModelRecursive.model_validate(
                {"type": "minecraft:not_a_model_type"}
            ).model


class TestSelectValidation:
    # SelectItemModelProperty.Type.validateCases rejects these, the definition fails to load
    def test_duplicate_case_values_are_rejected(self):
        node = select(
            "minecraft:display_context",
            [("gui", "test:a"), (["fixed", "gui"], "test:b")],
        )
        with pytest.raises(ValueError, match="gui"):
            resolve(node)

    def test_empty_case_list_is_rejected(self):
        with pytest.raises(ValueError):
            resolve(select("minecraft:display_context", []))


# ItemStack.isDamageableItem: max_damage and damage present, unbreakable absent
UNBREAKABLE = {
    "minecraft:damage": 9,
    "minecraft:max_damage": 10,
    "minecraft:unbreakable": {},
}
NO_MAX_DAMAGE = {"minecraft:damage": 9}


@pytest.mark.parametrize(
    "property, components",
    [
        pytest.param(
            "minecraft:damaged",
            UNBREAKABLE,
            id="damaged-unbreakable",
        ),
        pytest.param(
            "minecraft:damaged",
            NO_MAX_DAMAGE,
            id="damaged-no_max_damage",
        ),
        pytest.param(
            "minecraft:broken",
            UNBREAKABLE,
            id="broken-unbreakable",
        ),
        pytest.param("minecraft:broken", NO_MAX_DAMAGE, id="broken-no_max_damage"),
    ],
)
def test_only_damageable_items_are_damaged_or_broken(property, components):
    assert resolve(condition(property), make_item(components=components)) == [
        "test:false"
    ]


def test_has_component_ignore_default_compares_with_the_default():
    node = condition(
        "minecraft:has_component",
        component="minecraft:max_stack_size",
        ignore_default=True,
    )
    item = make_item(
        components={"minecraft:max_stack_size": 64},
        default_components={"minecraft:max_stack_size": 64},
    )
    assert resolve(node, item) == ["test:false"]


def fullness(contents, table=None):
    node = {
        "type": "minecraft:range_dispatch",
        "property": "minecraft:bundle/fullness",
        "entries": [
            {"threshold": t, "model": model_node(f"test:{t}")}
            for t in (0, 0.25, 0.5, 0.75, 1)
        ],
    }
    item = make_item(components={"minecraft:bundle_contents": contents})
    if table is not None:
        item.fill_from(table)
    return resolve(node, item)


STACK_SIZES = {
    "minecraft:stone": {"minecraft:max_stack_size": 64},
    "minecraft:ender_pearl": {"minecraft:max_stack_size": 16},
    "minecraft:bundle": {"minecraft:max_stack_size": 1},
}


class TestBundleFullness:
    # BundleContents.weight
    def test_stacks_weigh_count_over_max_stack_size(self):
        contents = [
            {"id": "minecraft:stone", "count": 16},
            {"id": "minecraft:ender_pearl", "count": 4},
        ]
        assert fullness(contents, STACK_SIZES) == ["test:0.5"]

    def test_a_nested_bundle_weighs_its_contents_plus_a_sixteenth(self):
        inner = {
            "id": "minecraft:bundle",
            "components": {
                "minecraft:bundle_contents": [{"id": "minecraft:stone", "count": 44}]
            },
        }
        assert fullness([inner], STACK_SIZES) == ["test:0.75"]

    def test_empty_bundle(self):
        assert fullness([]) == ["test:0"]


def test_display_context_comes_from_the_item():
    node = select("minecraft:display_context", [("fixed", "test:fixed")])
    item = make_item()
    item.display_context = "fixed"
    assert resolve(node, item) == ["test:fixed"]


def test_item_display_has_no_owner():
    node = select("minecraft:main_hand", [("right", "test:right")])
    item = make_item()
    item.owner = None
    assert resolve(node, item) == ["test:fallback"]


def test_count_is_clamped_to_one():
    node = {
        "type": "minecraft:range_dispatch",
        "property": "minecraft:count",
        "entries": [{"threshold": 1, "model": model_node("test:full")}],
        "scale": 2,
        "fallback": model_node("test:fallback"),
    }
    item = make_item(components={"minecraft:max_stack_size": 16})
    item.count = 64
    assert resolve(node, item) == ["test:full"]


@pytest.mark.parametrize("kind", ["minecraft:select", "minecraft:range_dispatch"])
def test_a_missing_fallback_draws_the_missing_model(kind):
    node = (
        select("minecraft:display_context", [("head", "test:head")])
        if kind == "minecraft:select"
        else custom_model_data_range([5])
    )
    del node["fallback"]
    assert resolve(node) == ["minecraft:builtin/missing"]
