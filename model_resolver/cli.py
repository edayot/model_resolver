import typer
from pathlib import Path
from beet import run_beet, ProjectConfig
from time import perf_counter
from rich import print

app = typer.Typer(
    rich_markup_mode="markdown",
)


# a simple command
@app.command()
def main(
    # fmt: off
    render_size: int = typer.Option(256, help="Size of the rendered image"),
    load_dir: Path = typer.Option(Path.cwd(), help="Directory where the resourcepack is located"),
    output_dir: Path = typer.Option(Path.cwd() / "build", help="Where you want to save the new resourcepack, with new textures corresponding to the model"), 
    use_cache: bool = typer.Option(False, help="Use cache for model rendering)"),
    load_vanilla: bool = typer.Option(False, help="Load vanilla model"),
    resolve_vanilla_atlas: bool = typer.Option(False, help="Resolve vanilla model textures, True if load_vanilla is True"),
    vanilla_filter: list[str] = typer.Option(None, help="Filter vanilla models to load"),
    minecraft_version: str = typer.Option("latest", help="Minecraft version to use for vanilla models")
    # fmt: on
):
    """
    A simple CLI to render models from a resourcepack, can also load vanilla models.
    """
    t_start = perf_counter()
    config = ProjectConfig(
        pipeline=["model_resolver"],
        output=output_dir,
        resource_pack={"load": load_dir, "name": load_dir.name},
        meta={
            "model_resolver": {
                "load_vanilla": load_vanilla,
                "use_cache": use_cache,
                "render_size": render_size,
                "minecraft_version": minecraft_version,
                "resolve_vanilla_atlas": resolve_vanilla_atlas,
                "vanilla_filter": vanilla_filter,
            },
        },
    )
    with run_beet(config=config) as ctx:
        pass
    t_end = perf_counter()
    print(f"[green][bold]✔️[/bold]  Finished in {t_end - t_start:.2f} seconds [/green]")


if __name__ == "__main__":
    app()
