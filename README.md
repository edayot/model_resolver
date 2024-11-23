# Model Resolver

A beet plugin that render all models in the beet project.


## Usage


### Renders project

Without any installlation, all vanilla models are rendered in this [repository](https://github.com/edayot/renders/tree/renders)


### As a beet service

Example plugin to render an apple:
```python

from beet import Context
from model_resolver import Render, Item




def beet_default(ctx: Context):
    render = Render(ctx)

    item = Item(
        id="minecraft:apple",
    )
    render.add_item_task(item, path_ctx="my_namespace:my_apple")
    render.run()
```

Additionally, you can customize the config :
```yaml
meta:
  model_resolver:
    # load vanilla item models
    minecraft_version: "1.21.4-pre1"
    use_cache: true
    special_rendering: true
```

## Installation

### Windows

Install https://visualstudio.microsoft.com/fr/visual-cpp-build-tools/ and add C++ build tools in the installation.

### Ubuntu

Generally, you don't need to install anything, but if you have an error, you can try to install the following packages:

```bash
sudo apt-get -y install \
    freeglut3-dev \
    libgl1-mesa-dev \
    libxcursor-dev \
    libpulse-dev \
    libxinerama-dev \
    libxrandr-dev \
    libxv-dev \
    mesa-utils \
    libgl1-mesa-glx \
    mesa-common-dev \
    libglapi-mesa \
    libgbm1 \
    libgl1-mesa-dri \
    libsdl1.2-dev \
    libfreetype6-dev \
    xvfb \
    x11-utils
```

This is particularly useful in CI, see [the github action](./.github/workflows/artifact.yml) for an example.

### Common installation

Install the plugin by running:

```bash
pip install model-resolver
```

Pypi: https://pypi.org/project/model-resolver/




## Credits

- RedCoal27 for this big item model : https://github.com/RedCoal27/Custom-Item