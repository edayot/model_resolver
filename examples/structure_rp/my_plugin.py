from beet import Context, ResourcePack
from pathlib import Path

from model_resolver.minecraft_model import DisplayOptionModel
from model_resolver.render import Render
from model_resolver.pack_getter import PackGetterLookup


def beet_default(ctx: Context):
    render = Render(ctx, default_render_size=2048)
    render.getter._simpledrawer = PackGetterLookup(assets=ResourcePack(path=Path(__file__).parent / "simpledrawer.zip"))  # pyright: ignore[reportAttributeAccessIssue]
    render.getter.lookups.insert(0, "_simpledrawer")
    for structure in ctx.data.structures.keys():
        render.add_structure_task(
            structure, path_ctx=structure, animation_mode="one_file",
            display_option=DisplayOptionModel(scale=(0.4,0.4,0.4), rotation=(30, 225, 0),)
        )
    render.run()
