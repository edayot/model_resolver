# Rendering models

Render a model from the pack (or vanilla) by its id:

```python
render.add_model_task("minecraft:block/stone", path_ctx="ns:stone")
```

Or pass the model as a dictionary:

```python
render.add_model_dict_task(
    {"parent": "minecraft:block/cube_all", "textures": {"all": "minecraft:block/dirt"}},
    path_ctx="ns:dirt_cube",
)
```

Blocks are tinted like in the game; pass `biome="minecraft:swamp"` to change the colors of
grass, foliage and water.

## Custom view

[`DisplayOptionModel`](../reference/api.md#model_resolver.minecraft_model.DisplayOptionModel)
sets the rotation, translation and scale of the camera view.
