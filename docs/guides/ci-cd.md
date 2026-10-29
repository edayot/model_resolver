# CI/CD

Rendering needs an OpenGL context, and CI runners are headless. model_resolver ships a
GitHub composite action that installs the dependencies and provides a virtual display.

## GitHub Actions

```yaml
name: Render
on: push

jobs:
  render:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
      - run: uv sync
      - name: Render
        uses: edayot/model_resolver@master
        with:
          commands: |
            uv run beet
      - uses: actions/upload-artifact@v4
        with:
          name: renders
          path: dist/
```

The action works on Linux (Mesa + `xvfb-run`), Windows (`setup-mesa-dist-win`) and macOS (XQuartz).
Pin a release tag instead of `@master` for reproducible builds. If you use
`preferred_minecraft_generated: java`, add `actions/setup-java` first.

## Other CI systems

Install the [Linux packages](../getting-started/installation.md#ubuntu-linux) and run the
build under a virtual display with software rendering:

```bash
export LIBGL_ALWAYS_SOFTWARE=1
xvfb-run -s "-screen 0 2560x1440x24 +extension GLX +extension RENDER" uv run beet
```

!!! tip
    Software rendering differs slightly from GPU rendering: avoid pixel-exact comparisons
    of CI renders against renders made locally.
