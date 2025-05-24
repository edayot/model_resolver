from beet import Context

from model_resolver.render import Render






def beet_default(ctx: Context):
    render = Render(ctx, default_render_size=1024)
    for structure in ctx.data.structures.keys():
        render.add_structure_task(structure, path_ctx=structure, animation_mode="webp")
    render.run()


