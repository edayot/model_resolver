# First render

Create a folder with this `beet.yaml`:

```yaml
resource_pack:
  load: .

pipeline:
  - my_plugin

output: dist
```

and a `my_plugin.py` next to it:

```python
from beet import Context
from model_resolver import Render, Item


def beet_default(ctx: Context):
    render = Render(ctx)
    render.add_item_task(
        Item(id="minecraft:apple"),
        path_ctx="my_namespace:my_apple",
    )
    render.run()
```

Run `beet`. The render is added to the built pack as
`assets/my_namespace/textures/my_apple.png`.

- `path_ctx` saves the result **in the pack** (`namespace:path`).
- `path_save` saves it to a **file on disk** instead.

!!! note
    `render.run()` opens a hidden OpenGL window and renders every queued task. Add all your
    tasks first, then call it once.

Next: [configure](../guides/configuration.md) the version of Minecraft to use, or see
the guides for [items](../guides/rendering-items.md), [models](../guides/rendering-models.md)
and [structures](../guides/rendering-structures.md).
