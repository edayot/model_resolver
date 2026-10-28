"""Item stacks: component patches over the item's default components."""

from beet import ItemModel as ItemModelFile, ResourcePack

from model_resolver.tasks.item import ItemRenderTask
from resolver_testkit import gap, make_getter, make_item, model_node

DEFAULTS = {"minecraft:item_model": "minecraft:stone", "minecraft:max_stack_size": 64}


def test_user_components_override_defaults():
    item = make_item(
        components={"minecraft:item_model": "test:a"}, default_components=DEFAULTS
    )
    assert item.components["minecraft:item_model"] == "test:a"
    assert item.components["minecraft:max_stack_size"] == 64


def test_get_accepts_both_key_forms():
    item = make_item(components={"minecraft:item_model": "test:a"})
    assert item.get("item_model") == item.get("minecraft:item_model") == "test:a"


def test_component_keys_without_namespace_override_defaults():
    item = make_item(components={"item_model": "test:a"}, default_components=DEFAULTS)
    assert item.components["minecraft:item_model"] == "test:a"


def test_component_removal():
    item = make_item(
        components={"!minecraft:max_stack_size": {}}, default_components=DEFAULTS
    )
    assert "minecraft:max_stack_size" not in item.components


def parsed_item_model_id(item_model):
    assets = ResourcePack()
    assets.item_models["minecraft:apple"] = ItemModelFile(
        {"model": model_node("test:apple")}
    )
    task = ItemRenderTask(
        getter=make_getter(assets),
        item=make_item(components={"minecraft:item_model": item_model}),
    )
    parsed = task.get_parsed_item_model()
    return [model.model for model in parsed.resolve(task.getter, task.item)]


def test_item_model_lookup():
    assert parsed_item_model_id("minecraft:apple") == ["test:apple"]


def test_item_model_lookup_without_namespace():
    assert parsed_item_model_id("apple") == ["test:apple"]


def test_rendering_an_item_in_a_context_leaves_the_item_alone():
    from model_resolver.render import Render

    render = Render.__new__(Render)
    render.ctx = None  # type: ignore
    render.tasks = []  # type: ignore
    render.default_render_size = 16
    render.default_animated_path_padding = 3
    render.getter = make_getter()
    item = make_item()
    render.add_item_task(item, display_context="fixed")
    render.add_item_task(item)
    assert [task.item.display_context for task in render.tasks] == ["fixed", "gui"]  # type: ignore
    assert item.display_context == "gui"


def test_unknown_options_warn_once(caplog):
    from model_resolver.utils import ModelResolverOptions

    with caplog.at_level("WARNING", logger="model_resolver"):
        for _ in range(3):
            ModelResolverOptions.model_validate({"not_an_option_42": 1})
    assert len([r for r in caplog.records if "not_an_option_42" in r.message]) == 1
