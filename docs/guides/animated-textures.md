# Animated textures

Models with animated textures can be rendered as an animation. Every `add_*_task` method
takes an `animation_mode`:

| Mode | Result |
| --- | --- |
| `multi_files` | One image per frame (default for items and models). |
| `webp` | A single animated WebP, stored in the pack as a `TextureWebP`. |
| `one_file` | Only the first frame of the animation (default for structures). |

## Enchantment glint

An enchanted item (or one with `enchantment_glint_override: true`) is animated too: the
glint moves like in the game, at the default glint speed, and only loops after 1650 ticks
(82.5 seconds). With `webp` or `multi_files`, an enchanted item gives 1650 frames, or the
least common multiple of 1650 and the loops of its animated textures. `one_file` keeps the
glint where it is at the first tick.

Like in the game, the glint is sampled with the coordinates of the item's sprite in the
items or blocks atlas, so where a sprite was stitched changes how its glint looks. Item
displays in structures get the glint as well.
