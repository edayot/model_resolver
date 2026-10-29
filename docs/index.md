# model_resolver

![logo](assets/logo.png)

**model_resolver** is a [beet](https://mcbeet.dev) plugin that renders the models of a
Minecraft resource pack to images: items, block models, and whole structures.

It resolves models the way the game does (item model definitions, data components,
parent models, `display` transforms, tints, special models, atlases, animated textures),
then draws them with OpenGL and writes the result as PNG or WebP files, either into
your pack or on disk.

## What is it for?

- Adding items rendering in text.
- Generating icons for a wiki, a README or a website from your pack's items.
- Previewing custom items and models without opening the game.
- Rendering structures (`.nbt`) as images or animations.
- Producing renders in CI on every push.

## Where to start

<div class="grid cards" markdown>

- **[Installation](getting-started/installation.md)** - install the package and its OpenGL prerequisites.
- **[First render](getting-started/first-render.md)** - render an apple in a few lines.
- **[CI/CD](guides/ci-cd.md)** - render on headless runners such as GitHub Actions.
- **[API reference](reference/api.md)** - every public class and function.

</div>

## Pre-rendered vanilla assets

You don't need to install anything to get renders of vanilla models: they are published in the
[renders repository](https://github.com/edayot/renders/tree/renders).

