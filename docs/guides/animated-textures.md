# Animated textures

Models with animated textures can be rendered as an animation. Every `add_*_task` method
takes an `animation_mode`:

| Mode | Result |
| --- | --- |
| `multi_files` | One image per frame (default for items and models). |
| `webp` | A single animated WebP, stored in the pack as a `TextureWebP`. |
| `one_file` | Only the first frame of the animation (default for structures). |

