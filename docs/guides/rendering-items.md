# Rendering items

```python
from model_resolver import Render, Item

render = Render(ctx)
render.add_item_task(
    Item(
        id="minecraft:diamond_sword",
        components={"minecraft:custom_model_data": {"floats": [1]}},
    ),
    path_ctx="my_namespace:sword",
    render_size=256,
)
render.run()
```

The item is resolved through its `item_model` definition, so components such as
`custom_model_data`, `damage`, or dyed colors affect the result.

## Display context

By default an item is drawn as in the inventory (`gui`). Use `display_context` to render
it as it appears elsewhere: `fixed`, `ground`, `head`, `thirdperson_righthand`...

```python
render.add_item_task(Item(id="minecraft:stone"), path_ctx="ns:ground", display_context="ground")
```

## Item options

See [`Item`](../reference/api.md#model_resolver.item_model.item.Item) and
[`Render.add_item_task`](../reference/api.md#model_resolver.render.Render.add_item_task).
