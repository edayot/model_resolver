# Documentation plan (Zensical)

Goal: publish a documentation site for model_resolver at
https://edayot.github.io/model_resolver, built with [Zensical](https://zensical.org),
and slim the README down to a pointer to it.

## 1. Repository layout

`docs/` becomes the Zensical source directory, so internal plans
(`migration-plan.md`, this file) move to a new `plans/` folder to keep them off the site.

```
zensical.toml              # site config
docs/
  index.md                 # What is model_resolver
  getting-started/
    installation.md        # pip/uv install + OS prerequisites (Windows C++ tools, Ubuntu GL libs)
    first-render.md        # render an apple, end to end
  guides/
    configuration.md       # meta.model_resolver options (ModelResolverOptions)
    rendering-items.md     # Item + add_item_task, components, render_size
    rendering-models.md    # add_model_task / add_model_dict_task, DisplayOptionModel
    rendering-structures.md# add_structure_task
    animated-textures.md   # TextureWebP, *_webp plugins
    builtin-plugins.md     # render_all_context / render_all_vanilla / render_all_items (+ _webp / _option)
    ci-cd.md               # headless rendering in CI (see §3)
  reference/
    api.md                 # mkdocstrings pages (see §4)
  credits.md
  assets/logo.png          # copied from rp_logo/
```

## 2. Content

- **index.md — What is model_resolver**: a beet plugin that renders Minecraft
  item/block models, structures and item model definitions to PNG/WebP using
  OpenGL; what it is used for (wiki/README icons, pack previews, snapshot tests);
  link to the pre-rendered vanilla renders repo (edayot/renders).
- **Beet primer**: 1–2 paragraphs only (beet = pack development toolchain,
  `beet.yaml`, plugins receive a `Context`), then redirect to https://mcbeet.dev
  rather than re-documenting beet.
- **Guides**: each built from a runnable project in `examples/` (main,
  item_display, structure_example, potions, campfire_structure…), so snippets
  stay accurate. Show both the `beet.yaml` config and the Python plugin.
- **Configuration**: table of every `ModelResolverOptions` field
  (`use_cache`, `minecraft_version`, `special_rendering`,
  `preferred_minecraft_generated`, `transparent_missingno`, `render_size`)
  with defaults, generated or kept in sync with `model_resolver/utils.py`.

## 3. CI/CD guide (`guides/ci-cd.md`)

- Why: rendering needs an OpenGL context; CI runners are headless.
- **GitHub Actions**: use the repo's composite action
  `edayot/model_resolver@master` (`action.yml`), which installs Mesa and runs
  commands under `xvfb-run` (Linux), `setup-mesa-dist-win` (Windows) or
  XQuartz Xvfb (macOS). Full workflow example: checkout → setup-python → uv
  → action with `commands: uv run beet` → upload-artifact. Recommend pinning a
  tag instead of `@master`.
- **Other CI (GitLab, Docker…)**: the apt package list + `LIBGL_ALWAYS_SOFTWARE=1`
  + `xvfb-run -s "-screen 0 2560x1440x24 +extension GLX +extension RENDER"`.
- Caveats: software rendering output differs slightly from local GPU output —
  don't do pixel-exact snapshot comparisons in CI; enable `use_cache` and cache
  the beet cache dir between runs.

## 4. API reference

- Use mkdocstrings (Python handler) through Zensical's mkdocstrings support;
  document the public surface exported from `model_resolver/__init__.py`:
  `Render`, `Item`, `ModelResolverOptions`, `TextureWebP`,
  `DisplayOptionModel`, plus the plugin entry points in `model_resolver.plugins`.
- Pass: add/complete docstrings on those classes and on `Render.add_*_task`,
  `Render.run`. Verify mkdocstrings works with the current Zensical release
  before committing to it; fallback is a hand-written reference page.

## 5. Tooling

- Add a `docs` dependency group in `pyproject.toml`: `zensical`,
  `mkdocstrings-python`.
- `zensical.toml`: `site_name = "model_resolver"`,
  `site_url = "https://edayot.github.io/model_resolver/"`,
  `repo_url = "https://github.com/edayot/model_resolver"`, nav as in §1,
  logo, light/dark palette.
- Local: `uv run --group docs zensical serve`; build: `zensical build` → `site/`
  (add `site/` to `.gitignore`).

## 6. Deploy workflow (`.github/workflows/docs.yml`)

```yaml
name: Docs
on:
  push:
    branches: [master]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: false
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v7
      - run: uv sync --group docs
      - run: uv run zensical build --clean
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site
      - id: deployment
        uses: actions/deploy-pages@v4
```

One-time manual step: repo Settings → Pages → Source = "GitHub Actions".
Optionally add a `pull_request` job that only runs `zensical build` to catch
broken docs.

## 7. README rewrite

Keep: logo, one-sentence description, `pip install model-resolver`, the
minimal apple example, and links to the docs site, PyPI and the renders repo.
Move installation prerequisites, config, CI details and credits into the docs.

## 8. Order of work

1. Move plans to `plans/`, add docs dependency group and `zensical.toml`.
2. Write index, getting-started and the beet primer.
3. Guides (one per example), then CI/CD guide.
4. Docstrings + API reference.
5. Docs workflow; enable Pages; verify the site at edayot.github.io/model_resolver.
6. Rewrite README.
