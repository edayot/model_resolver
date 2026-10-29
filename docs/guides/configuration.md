# Configuration

Options are set in `beet.yaml` under `meta.model_resolver`:

```yaml
meta:
  model_resolver:
    minecraft_version: "1.21.4"
    use_cache: true
    special_rendering: true
    render_size: 512
```

| Option | Default | Description |
| --- | --- | --- |
| `minecraft_version` | `"latest"` | Version of the vanilla assets to load. |
| `use_cache` | `false` | Cache the downloaded vanilla assets between runs. |
| `special_rendering` | `false` | Render special models (chests, beds, heads, shields...). |
| `preferred_minecraft_generated` | `"misode/mcmeta"` | Where generated data (default components...) comes from: `"misode/mcmeta"` or `"java"` (runs the server jar, needs Java). |
| `transparent_missingno` | `true` | Render the missing texture as transparent. |
| `render_size` | unset | Default size in pixels of the renders that don't set their own. |
