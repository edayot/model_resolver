# Rendering structures

Structures (`.nbt` files from `data/<namespace>/structure/`) can be rendered too:

```python
from beet import Context
from model_resolver import Render


def beet_default(ctx: Context):
    render = Render(ctx, default_render_size=1024)
    for structure in ctx.data.structures.keys():
        render.add_structure_task(structure, path_ctx=structure, animation_mode="one_file")
    render.run()
```

with this `beet.yaml`:

```yaml
resource_pack:
  load: .
data_pack:
  load: .
pipeline:
  - my_plugin
meta:
  model_resolver:
    render_size: 1024
    special_rendering: true
```

`biome` colors the grass, foliage and water, and `display_option` changes the viewing angle.
The `examples/structure_example` and `examples/item_display` folders of the repository
contain complete projects.
