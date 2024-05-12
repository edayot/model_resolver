# Model Resolver

A beet plugin that render all models in the beet project.


## Usage


### Renders project

Without any installlation, all vanilla models are rendered in this [repository](https://github.com/edayot/renders/tree/renders)

### With the CLI

This command will show all available options:

```bash
model_resolver --help
```

```bash
# this will render the current resource pack models
model_resolver 
```

```bash
# this will render the current resource pack models and load vanilla models
model_resolver --load-vanilla
```



### As a beet plugin
Add the plugin to your pipeline:

```yaml
# beet.yaml
pipeline:
  (...)  # other plugins you may have
  - model_resolver

# setup an output directory
output: build

meta:
  model_resolver:
    # load vanilla item models
    load_vanilla: true

```

Renders are now available in your ctx !


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


