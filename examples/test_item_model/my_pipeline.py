from beet import Context
from model_resolver import Item, Render
from model_resolver.item_model.model import ItemModelRangeDispatchCompass, ItemModelRecursive


class MyImpl(ItemModelRangeDispatchCompass):
    def resolve_range_dispatch(self, getter, item):
        comp = item.components.get("model_resolver:myimpl")
        if comp is not None:
            return comp
        return super().resolve_range_dispatch(getter, item)
MyImpl.model_rebuild()


def beet_default(ctx: Context):
    render = Render(ctx)

    item = Item(id="minecraft:player_head", components={"minecraft:profile": "AirDox_"})
    # render.add_item_task(item, path_ctx="test:head", render_size=512)

    # render.add_item_task(Item(id="minecraft:chest"), path_ctx="test:chest", render_size=512)

    # render.add_item_task(Item(id="minecraft:creeper_head"), path_ctx="test:creeper_head", render_size=512)
    # render.add_item_task(Item(id="minecraft:zombie_head"), path_ctx="test:zombie_head", render_size=512)

    render.add_item_task(
        Item(
            id="minecraft:diamond", components={"minecraft:item_model": "test:skeleton"}
        ),
        path_ctx="test:render/skeleton",
        render_size=512,
    )
    render.add_item_task(
        Item(
            id="minecraft:diamond", components={"minecraft:item_model": "test:piglin"}
        ),
        path_ctx="test:render/piglin",
        render_size=512,
    )
    render.add_item_task(
        Item(
            id="minecraft:diamond",
            components={"minecraft:item_model": "test:real_piglin"},
        ),
        path_ctx="test:render/real_piglin",
        render_size=512,
    )
    render.add_item_task(
        Item(
            id="minecraft:diamond", components={"minecraft:item_model": "test:dragon"}
        ),
        path_ctx="test:render/dragon",
        render_size=512,
    )
    render.add_item_task(
        Item(
            id="minecraft:diamond",
            components={"minecraft:item_model": "test:real_dragon"},
        ),
        path_ctx="test:render/real_dragon",
        render_size=80,
    )

    render.add_item_task(
        Item(
            id="minecraft:diamond",
            components={"minecraft:item_model": "test:dragon_scales"},
        ),
        path_ctx="test:render/dragon_scales",
        render_size=512,
    )
    render.add_item_task(
        Item(
            id="minecraft:grass", components={"minecraft:item_model": "freerot:diamond"}
        ),
        path_ctx="test:render/model_resolver",
        render_size=512,
    )
    render.add_item_task(
        Item(
            id="minecraft:sculk_sensor",
        ),
        path_ctx="test:render/sculk_sensor",
        render_size=512,
    )
    render.add_item_task(
        Item(
            id="minecraft:diamond",
            components={"minecraft:item_model": "test:test_shulker"},
        ),
        path_ctx="test:render/yellow_shulker_box",
        render_size=512,
    )

    render.add_item_task(
        Item(
            id="minecraft:diamond",
            components={"minecraft:item_model": "test:component_select"},
        ),
        path_ctx="test:render/component_select",
        render_size=512,
    )
    render.add_item_task(
        Item(
            id="minecraft:diamond",
            components={
                "minecraft:item_model": "test:component_select",
                "minecraft:glider": {},
            },
        ),
        path_ctx="test:render/component_select2",
        render_size=512,
    )

    render.add_item_task(
        Item(
            id="minecraft:diamond",
            components={
                "minecraft:item_model": "test:component_condition",
                "minecraft:custom_data": {},
            },
        ),
        path_ctx="test:render/component_condition_on_false",
        render_size=512,
    )
    render.add_item_task(
        Item(
            id="minecraft:diamond",
            components={
                "minecraft:item_model": "test:component_condition",
                "minecraft:custom_data": {"test": "airdox_"},
            },
        ),
        path_ctx="test:render/component_condition_on_true",
        render_size=512,
    )

    patterns = [
        {"color": "cyan", "pattern": "minecraft:rhombus"},
        {"color": "light_gray", "pattern": "minecraft:stripe_bottom"},
        {"color": "gray", "pattern": "minecraft:stripe_center"},
        {"color": "light_gray", "pattern": "minecraft:border"},
        {"color": "black", "pattern": "minecraft:stripe_middle"},
        {"color": "light_gray", "pattern": "minecraft:half_horizontal"},
        {"color": "light_gray", "pattern": "minecraft:circle"},
        {"color": "black", "pattern": "minecraft:border"},
    ]

    for i in range(len(patterns) + 1):

        render.add_item_task(
            Item(
                id="minecraft:white_banner",
                components={
                    "minecraft:banner_patterns": patterns[:i],
                },
            ),
            path_ctx=f"test:render/shield/{i}",
            render_size=512,
        )

    render.add_item_task(
        Item(
            id="minecraft:diamond",
            components={"minecraft:item_model": "minecraft:red_bed"},
        ),
        path_ctx="test:render/red_bed",
        render_size=512,
    )

    render.add_item_task(
        Item(
            id="minecraft:bedrock",
            components={
                "minecraft:item_model": "minecraft:decorated_pot",
                # "minecraft:pot_decorations": ["minecraft:blade_pottery_sherd", "minecraft:archer_pottery_sherd", "minecraft:brewer_pottery_sherd", "minecraft:burn_pottery_sherd"]
            },
        ),
        path_ctx="test:render/pot",
        render_size=512,
    )

    render.add_item_task(
        Item(
            id="minecraft:diamond",
            components={
                "minecraft:item_model": "test:hanging_sign",
            },
        ),
        path_ctx="test:render/hanging_sing",
        render_size=512,
    )

    render.add_item_task(
        Item(
            id="minecraft:diamond",
            components={
                "minecraft:item_model": "test:trident",
            },
        ),
        path_ctx="test:render/trident",
        render_size=512,
    )

    render.add_model_task(
        "test:item/conduit", path_ctx="test:render/conduit", render_size=512
    )
    render.add_item_task(
        Item(id="stone", components={"minecraft:item_model": "test:sign"}),
        path_ctx="test:render/sign",
        render_size=512,
    )

    render.add_item_task(
        Item(id="compass"),
        path_ctx="test:render/compass",
        render_size=512,
    )
    render.add_item_task(
        Item(id="compass", components={"model_resolver:myimpl": 10}),
        path_ctx="test:render/compass_my_impl",
        render_size=512,
    )

    test = render.add_item_task(
        Item(id="compass"),
        render_size=512,
    )

    render.run()

    print(test.saved_img)
