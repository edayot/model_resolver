from beet import Context, Texture

from model_resolver.render import Render, DisplayOptionModel
from model_resolver.tasks.structure import StructureRenderTask


def beet_default(ctx: Context):
    render = Render(ctx, default_render_size=1024)
    tasks: dict[str, StructureRenderTask] = {}
    for structure in ctx.data.structures.keys():
        tasks[structure] = render.add_structure_task(
            structure, animation_mode="one_file",
            display_option=DisplayOptionModel(
                scale=(1.5, 1.5, 1.5),
                rotation=(30, 225, 0),
                translation=(-16, 32, 0),
            ),
        )
    render.run()

    for path, task in tasks.items():
        if task.tasks:
            ctx.assets.textures[path] = Texture(task.tasks[0].saved_img)
        else:
            ctx.assets.textures[path] = Texture(task.saved_img)

