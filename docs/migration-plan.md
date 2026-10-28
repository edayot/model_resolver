# 26.3 parity: status

Baseline: `master` at `613cca8`, Minecraft 26.3. Entities are out of scope, except `item_display`.

Every gap of the original plan (IDs below) was checked against the decompiled 26.3 client, then implemented. This page records what each fix does, where model_resolver still differs from the game, and the decisions that a reviewer should know about.

## Tests

```sh
.venv/bin/python -m pytest tests --ignore=tests/test_example.py   # 339 passed, ~1 s, no GL or network
cd examples/test_item_model && ../../.venv/bin/beet                # one cheap end-to-end render
```

- The unit tests now run in CI (`artifact.yml`, `release.yml`) before anything that needs OpenGL.
- Strict `@gap` markers are gone: every test that asserted vanilla behaviour passes. The `gap()` helper stays in `resolver_testkit.py` for new gaps.
- `test_example.py` compares render snapshots with a tolerance ([render_compare.py](../tests/render_compare.py)): a PNG/WebP differs when more than 1% of its drawn pixels change by more than 2 levels, or more than 0.1% change silhouette. JSON is compared by value, everything else exactly.

**The snapshots need one reviewed refresh.** They predate this work (and `campfire_structure`'s already lacked `campfire.nbt`). Renders of beds, banners, shields, heads, generated items with extruded sides, structures (culling, uvlock, water) and lighting all change on purpose. Review a fresh build of each example, then run `pytest tests/test_example.py --insta update`. The `potions`, `biomes` and `item_display` examples are new and already have reviewed snapshots.

Two examples cover the newer features: [examples/potions](../examples/potions) (potion ids, custom colors and effects on potions, splash and lingering potions and tipped arrows) [examples/biomes](../examples/biomes) (one structure with water, grass, leaves and a campfire, rendered in seven vanilla biomes and a custom one) and [examples/item_display](../examples/item_display) (item displays in every display context, with yaw and pitch, both transformation forms, a banner and an enchanted item).

## What changed, by area

### R: pack resolution

- **R1.** A file found in several packs resolves to the highest-priority copy (project, then bundled `static_models`, then vanilla). Blockstates resolve state by state through every pack's file (`PackGetter.get_stack`, `StructureRenderTask.get_block_variants`), like `BlockStateModelLoader`; cached files are never mutated. Single, ender and copper chests render again in structures.

### I: item model definitions and item stacks

- **I1** `range_dispatch`: `value * scale`, NaN takes the fallback, the last threshold `<= value` wins, a missing fallback is the missing model.
- **I2** `select.fallback` is optional (missing model). **I12** an empty case list or a value listed twice is rejected, as `validateCases` does.
- **I3** an unknown or invalid node raises a `ValueError` naming its type (`utils.validate_dispatched`, also used for special models).
- **I4** `charge_type` reads `charged_projectiles`. **I5** `main_hand` is `right` when the item has an owner. **I6** ids are compared namespaced (`trim_material`, `has_component`, component `select`, `context_*`); `ignore_default` is `hasNonDefault`.
- **I7** `damage` / `count` are clamped and NaN for non-damageable items; `damaged` / `broken` follow `isDamageableItem`. **I8** `bundle/fullness` is the bundle weight. **I9** resolving never mutates the cached tree.
- **I10 / D1** `Item.display_context` (and `Render.add_item_task(display_context=...)`) drives `select display_context` and the display transform (`display.<context>`, mirrored for left hands). `Item.owner` is the holder's entity type, `None` for an item_display.
- **I11** component patches are normalized: un-namespaced keys, `!component` removals, defaults compared like `PatchedDataComponentMap`. The `item_model` id is namespaced.

### T: tints

- **T1** potions use `custom_color`, else the average color of the visible effects weighted by amplifier + 1. The effect and potion tables are generated from the jar by [scripts/generate_potion_table.py](../scripts/generate_potion_table.py) into `model_resolver/data/potions.json` (one entry per version, the closest one is used).
- **T2** firework averages `firework_explosion` colors. **T3** `custom_model_data` falls back to `default`. **T4** float `[r, g, b]` colors (float32 like Java). **T5** the grass colormap is sampled like `ColorMapColorUtil`, and out-of-range values are rejected.

### P: component predicates

Rewritten after `net.minecraft.core.component.predicates` ([data_component_predicate.py](../model_resolver/item_model/data_component_predicate.py)): `MinMaxBounds`, holder sets with tags and `{id, required}` entries, `CollectionPredicate` (`contains` / `count` / `size`), nested `ItemPredicate`s, every 26.3 predicate, any other component id as a presence check, and `custom_data` with `NbtUtils.compareNbt` (partial lists, typed tags, JSON numbers read as doubles like `NbtOps`). Pre-26.1 shapes of `potion_contents` and `jukebox_playable` are still read.

### G: geometry, model files, lighting

- **G1 / G2** item model `transformation`s apply in blocks after the display transform, like `LayerRenderState.applyTransform`; matrices are row-major. Beds have their two halves.
- **G3** default UVs are `FaceBakery.defaultFaceUV`. **G4** rescale is `1 / max(|R · axis|)`; element rotations take x, y and z. **G7** parent cycles raise a clear error; texture references resolve to a fixed point. **G8** undefined texture variables draw missingno; faces can name a texture directly.
- **G6 / D2** `builtin/generated` is `ItemModelGenerator`: layer0 to the first missing layer, quads from z 7.5 to 8.5, extruded sides on every opaque edge (computed at draw time from the texture), `gui_light: front`, own elements win.
- **G9** display translation and scale are clamped. **G11** a file's missing left-hand entries copy its right-hand ones. An explicit identity entry is kept (vanilla compares with `NO_TRANSFORM` by reference); the earlier plan was wrong on that point.
- **G10 / G5** faces are lit on the CPU (GL lighting is off), with one of three lightings (`GenericModelRenderTask.lighting`):
  - `gui`, items: `light.glsl` with the `ITEMS_3D` / `ITEMS_FLAT` light directions (`GuiLighting`). Isometric blocks are unchanged (within 3 levels), faces seen head-on lose the old over-brightening.
  - `terrain`, blocks and fluids in structures: `CardinalLighting` (up 1.0, north/south 0.8, west/east 0.6, down 0.5), using `shade_direction_override` when an element has one (`BlockModelLighter.getDirectionalBrightness`). That is what makes the campfire flame full bright. A pre-26.3 `shade: false` is drawn unshaded.
  - `level`, block entity specials and item displays in structures: `light.glsl` with the world-space lights of `Lighting.Entry.LEVEL`.

  In every case a face is lit by the axis nearest to its normal after the element and block rotations, as `FaceBakery.calculateFacing` gives baked quads one `Direction`.
- **Blending.** Colors blend by their alpha and the alpha accumulates (`BlendFunction.TRANSLUCENT`), and the read-back image is un-premultiplied. Before, translucent texels (water, stained glass) added their full color and looked washed out.
- Items now use no transform for a display context that no model in their chain defines (`ItemTransform.NO_TRANSFORM`); model renders (`add_model_task`) keep the block-like gui default.

### S: special models

- **S1 / S2** copper golem statues (4 poses), bell and book are built from the 26.3 entity models. [scripts/generate_entity_models.py](../scripts/generate_entity_models.py) parses the `createBodyLayer` methods into `model_resolver/data/entity_models.json`; [entity_model.py](../model_resolver/item_model/entity_model.py) turns `ModelPart` trees into elements (cube UV layout, part poses, `setupAnim` overrides). **S3** `end_cube` is a still starfield.
- **S4** head texture overrides map to `entity/<path>`. **S5** profile skin patches (`texture`), string UUIDs, `properties` without a download, and an offline fallback to `DefaultPlayerSkin.get(uuid)` (name-only profiles use the offline UUID). **S6** banner patterns use the registry's `asset_id`, inline patterns work.
- **S7 (decision).** The older hand-made special geometries (banner, shield, heads, shulker box, conduit) were tuned with vanilla's item transformation applied the old way. Rather than re-deriving them, `ItemModelSpecial.split_transformation` applies that vanilla transformation as a *calibration* and only what an item definition adds on top with the correct semantics. Vanilla items render as before; custom transformations compose correctly. New specials (golem, bell, book) use entity-space geometry and no calibration.

### A: textures and atlases

- **A1 / A2 / A5** animations follow `SpriteContents`: frame size from `width` / `height` or `min(w, h)`, frames row by row in a grid, `time` defaulting to `frametime`, invalid entries dropped, interpolation per entry in thousandths like the shader. Banner and shield layers stay animated. The `.mcmeta` `texture` section only affects mipmaps for atlas sprites, so it has no effect here.
- **A3** `animation_framerate` resamples ticks (1/20 s) instead of speeding playback up.
- **A4** `directory` (for the blocks and items atlases, the only ones models read), `unstitch`, `filter` (on sprites added earlier by the same atlas) and the `paletted_permutations` `separator`. **A6** `PaletteMapping`: row-major, last key wins, transparent keys skipped, target alpha multiplied in.

### B: blockstates and structures

- **B1** `uvlock` through `BlockMath.getFaceTransformation`. **B2** variant `z`. **B3** `!` terms. **B8** a state no file covers draws the missing model; `multipart` covers the states `variants` miss.
- **B4** banners, heads, decorated pots, conduits, bells, enchanting-table books, copper golem statues and end portals / gateways draw their special model with `BuiltInBlockModels`' block transformation (`builtin_block`), using block entity NBT for patterns, sherds and profiles.
- **B5** water and lava (waterlogged blocks included) are tesselated like `FluidRenderer`, in [fluids.py](../model_resolver/tasks/fluids.py), and drawn after the rest: corner heights averaged with the neighbours (`calculateAverageHeight`), a full height under the same fluid, a still top or the flowing texture turned along `FlowingFluid.getFlow`, sides as high as their corners with the water overlay against glass and leaves, back faces, faces hidden by the same fluid or full blocks. Water is tinted with the biome's water color. Past the structure's sides (not above or below), heights and flow assume the world goes on like the structure's edge, so water at the edge doesn't slope down into nothing; the cut sides at the edge are still drawn, like any other block side there.
  - **Animated:** the still and flowing textures take part in the structure's animation like any model texture, so `animation_mode="webp"` (or `multi_files`) animates the water. The loop is the least common multiple of every animated texture's loop (320 ticks with water, a campfire's fire and its interpolated logs).
  - **Block facts from the game:** [blocks.py](../model_resolver/blocks.py) reads `model_resolver/data/blocks.json`, generated by [scripts/generate_block_table.py](../scripts/generate_block_table.py), which runs [scripts/java/DumpBlocks.java](../scripts/java/DumpBlocks.java) against the server jar (it needs a JDK). For every state it has `isSolid` (heights: a non-solid neighbour such as grass pulls the surface down, a solid one is ignored), the fluid it holds, and its occlusion shape. `#blocks_fluid_flow` (`#blocks_motion` and signs) decides where water drains down. Blocks of other namespaces fall back to "solid unless air" and their model's full-cube check.
  - **Waterlogged blocks:** besides `waterlogged=true`, kelp, kelp plants, seagrass, tall seagrass and bubble columns always hold a water source. Faces follow `isFaceOccludedBySelf` and `isFaceOccludedByNeighbor` on the real shapes (`Shapes.blockOccludes`): the water of a waterlogged bottom slab has no bottom face, and a slab next to water only hides the part of the side it covers.
- **B6** faces with a `cullface` are hidden by full opaque cubes, and see-through full cubes (glass) cull against the same block.
- **B7** block tints follow `BlockColors` with a biome ([block_colors.py](../model_resolver/block_colors.py)): grass, foliage and dry foliage from the colormaps or the biome's overrides (with the `dark_forest` modifier), water cauldrons, constant spruce, birch and lily pad colors, stems by age, redstone by power (float32, like the game). `add_structure_task(biome=...)` takes a biome id or a worldgen/biome object, `minecraft:plains` by default. Biomes come from the project's data pack, then from `model_resolver/data/biomes.json`, generated from the jar by [scripts/generate_biome_table.py](../scripts/generate_biome_table.py). Blocks of other namespaces still use their item model's tints.
- **Model renders** (`add_model_task`, `render_all_vanilla`): the model of a block is shown as that block. Its tints come from the first block state whose blockstate uses it (`block_colors.model_blocks`), in `add_model_task(biome=...)` (plains by default), and `shade_direction_override` is honoured under the GUI light, so the campfire flame is lit like a top face. Item renders keep the vanilla GUI behaviour. Covered by [test_model_renders.py](../tests/test_model_renders.py) and [examples/block_models](../examples/block_models).

### D: item_display

- **D3** `item_display` entities in structures: position, fixed billboard (`rotationYXZ(-yaw, pitch, 0)`), `transformation` (decomposed or a row-major matrix), a half turn, then the item for its `item_display` context (`none` by default), with no owner, lit like an entity in the world. Covered by [test_item_display.py](../tests/test_item_display.py) and the `item_display` example.

### X: infrastructure

- **X1** see Tests. **X2** `render_size` under `meta.model_resolver` is the default render size; unknown keys log a warning; the dead `load_vanilla: false` lines are gone from the examples.
- **X3 (decision).** Instead of gating on `minecraft_version`, parsing accepts both the 26.3 and the older shapes (pot decorations, predicates, `map_color`, `bed` / sign specials), and generated tables are keyed by version.
- **X4** a still enchantment glint (`hasFoil`): the glint texture at time 0, scaled by 8 and turned 10°, added at the default strength where the item was drawn.

## Still different from the game

| Area | Difference |
| --- | --- |
| Snapshots | Stale, need the reviewed refresh described above. `load_vanilla` was not built. |
| Specials (S7) | The calibrated geometries are only as exact as their original tuning (for example the chest lock depth). Re-deriving them from the entity models with `entity_model.py` would remove the calibration. Shulker boxes in structures still use their own hand-written code; chests come from `static_models`. |
| Built-in blocks (B4) | Placement follows the vanilla transformations, but was only checked by eye; there are no reference screenshots in the repo. |
| Culling (B6) | Partial occluders (slabs, stairs) never cull; hidden faces are only extra work. Leaves never cull. |
| Fluids (B5) | Shapes that depend on the world (fences, walls and panes connecting to neighbours) use the state's own occlusion shape, which is what the game does too, but the structure's blocks of other namespaces only occlude as full cubes. |
| Biomes (B7) | One biome for the whole structure. Swamp grass always has its usual color (the game varies it with position noise). |
| Lighting | No ambient occlusion and no light levels: every block is fully lit. |
| item_display | Only the `fixed` billboard; brightness and glow overrides are ignored. |
| Player heads | Real skins need the network; offline, the default skin for the UUID. |
| Glint | One still frame, not animated. |

Kept static on purpose: `using_item`, `fishing_rod/cast`, `selected`, `carried`, `extended_view`, `keybind_down`, `view_entity`, `cooldown`, `time`, `compass`, `crossbow/pull`, `use_duration`, `use_cycle`, `local_time`, `context_dimension` (overworld) and the `team` tint (`default`). Users can override any of them by subclassing, as `MyImpl` does in [examples/test_item_model/my_pipeline.py](../examples/test_item_model/my_pipeline.py).
