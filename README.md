# Model Resolver

A beet plugin that render all models in the beet project.


## Usage

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

### Linux

Generally, you don't need to install anything.


### Common installation

Using poetry, add this to your pyproject.toml file:

```toml
[tool.poetry.dependencies]
# (other dependencies ...)
model-resolver = {git = "https://github.com/edayot/model_resolver.git", branch = "master"}
```



