# Built-in plugins

Ready-made plugins for the `pipeline` of your `beet.yaml`, so you don't need to write any Python:

| Plugin | Renders |
| --- | --- |
| `model_resolver.plugins.render_all_context` | Every model of your pack. |
| `model_resolver.plugins.render_all_vanilla` | Every vanilla model. |
| `model_resolver.plugins.render_all_items` | Every vanilla item. |

Each also exists with a `_webp` suffix (animated textures as WebP) and an `_option` suffix
(a function taking `animated_as_webp`).

```yaml
pipeline:
  - model_resolver.plugins.render_all_context_webp
```

Results are written under `<namespace>:render/...` in the output pack.
