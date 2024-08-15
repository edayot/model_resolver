import typer
from pathlib import Path
from beet import run_beet, ProjectConfig
from time import perf_counter
from rich import print
from typing import Annotated, Optional

app = typer.Typer(
    rich_markup_mode="markdown",
)


# a simple command
@app.command()
def main(
    # fmt: off
    render_size: Annotated[int, typer.Option(help="Size of the rendered image")] = 256,
    load_dir:  Annotated[Path, typer.Option(help="Directory where the resourcepack is located")] = Path.cwd(),
    output_dir: Annotated[Path, typer.Option(help="Where you want to save the new resourcepack, with new textures corresponding to the model")] = Path.cwd() / "build", 
    save_namespace: Annotated[str, typer.Option(help="Namespace to save the rendered models, default is the namespace the model is in")] = None,
    filter: Annotated[list[str], typer.Option(help="Filter models in directory")] = None,
    use_cache: Annotated[bool, typer.Option(help="Use cache for model rendering)")] = False,
    load_vanilla: Annotated[bool, typer.Option(help="Load vanilla model")] = False,
    resolve_vanilla_atlas: Annotated[bool, typer.Option(help="Resolve vanilla model textures, True if load_vanilla is True")] = False,
    minecraft_version: Annotated[str, typer.Option(help="Minecraft version to use for vanilla models")] = "latest",
    __special_filter__ : Annotated[str, typer.Option(hidden=True)] = "",
    __light__ : Annotated[str, typer.Option(hidden=True)] = "",
    resource_pack_name: Annotated[Optional[str], typer.Option(help="Name of the resourcepack")] = None,
    # fmt: on
):
    """
    A simple CLI to render models from a resourcepack, can also load vanilla models.
    """
    t_start = perf_counter()
    if isinstance(load_dir, str):
        load_dir = Path(load_dir)
    if isinstance(output_dir, str):
        output_dir = Path(output_dir)
    if isinstance(__special_filter__, str):
        __special_filter__ = {}
    if isinstance(__light__, str):
        __light__ = {}
    config = ProjectConfig(
        pipeline=["model_resolver"],
        output=output_dir,
        resource_pack={"load": load_dir, "name": resource_pack_name or load_dir.name},
        meta={
            "model_resolver": {
                "load_vanilla": load_vanilla,
                "use_cache": use_cache,
                "render_size": render_size,
                "minecraft_version": minecraft_version,
                "resolve_vanilla_atlas": resolve_vanilla_atlas,
                "filter": filter,
                "special_filter": __special_filter__,
                "save_namespace": save_namespace,
                "light": __light__,
            },
        },
    )
    with run_beet(config=config) as ctx:
        pass
    t_end = perf_counter()
    print(f"[green][bold]✔️[/bold]  Finished in {t_end - t_start:.2f} seconds [/green]")


if __name__ == "__main__":
    app()
