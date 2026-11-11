# Configuration

Options are set in `beet.yaml` under `meta.model_resolver`:

```yaml
meta:
  model_resolver:
    use_cache: true
    special_rendering: true
    render_size: 512
```

| Option | Default | Description |
| --- | --- | --- |
| `minecraft_version` | `"latest"` | Version of the vanilla assets to load. Only the latest version is supported, see below. |
| `use_cache` | `false` | Cache the downloaded vanilla assets between runs. |
| `special_rendering` | `false` | Render special models (chests, beds, heads, shields...). |
| `preferred_minecraft_generated` | `"misode/mcmeta"` | Where generated data (default components...) comes from: `"misode/mcmeta"` or `"java"` (runs the server jar, needs Java). |
| `transparent_missingno` | `true` | Render the missing texture as transparent. |
| `render_size` | unset | Default size in pixels of the renders that don't set their own. |

## Supported Minecraft version

model_resolver follows the latest Minecraft version only. What it knows from the game's code
(special models, block shapes and fluids, potion and biome colors) is generated for that
version. With another `minecraft_version`, the vanilla assets of that version are loaded but
this data is still the latest version's, and a warning is logged.
