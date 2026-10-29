![logo](https://github.com/edayot/model_resolver/blob/master/rp_logo/logo.png?raw=true)

A [beet](https://mcbeet.dev) plugin that renders all the models, items and structures of a Minecraft pack.

**Documentation: <https://edayot.github.io/model_resolver>**

## Quick start

```bash
pip install model-resolver
```

```python
from beet import Context
from model_resolver import Render, Item


def beet_default(ctx: Context):
    render = Render(ctx)
    render.add_item_task(Item(id="minecraft:apple"), path_ctx="my_namespace:my_apple")
    render.run()
```

- [Installation and OpenGL requirements](https://edayot.github.io/model_resolver/getting-started/installation/)
- [Guides](https://edayot.github.io/model_resolver/guides/configuration/), including [CI/CD](https://edayot.github.io/model_resolver/guides/ci-cd/)
- [API reference](https://edayot.github.io/model_resolver/reference/api/)

Renders of all vanilla models are available in the [renders repository](https://github.com/edayot/renders/tree/renders). The package is on [PyPI](https://pypi.org/project/model-resolver/).

## Credits

- RedCoal27 for this big item model : https://github.com/RedCoal27/Custom-Item
