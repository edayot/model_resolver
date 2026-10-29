# Installation

model_resolver requires Python 3.14 or newer.

```bash
pip install model-resolver
# or, in a uv project
uv add model-resolver
```

The package is on [PyPI](https://pypi.org/project/model-resolver/).

## System requirements

Rendering needs an OpenGL context. On a desktop machine this usually works out of the box.

### Windows

Install the [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
and select the **C++ build tools** workload.

### Ubuntu / Linux

Generally nothing is needed. If you get an OpenGL or GLUT error, install:

```bash
sudo apt-get -y install \
    freeglut3-dev libgl1-mesa-dev libxcursor-dev libpulse-dev \
    libxinerama-dev libxrandr-dev libxv-dev mesa-utils libgl1 \
    libglx-mesa0 mesa-common-dev libglapi-mesa libgbm1 \
    libgl1-mesa-dri libsdl1.2-dev libfreetype6-dev xvfb x11-utils
```

### Headless machines

Servers and CI runners have no display. See the [CI/CD guide](../guides/ci-cd.md).
