from model_resolver.cli import main


main(
    render_size=256,
    load_dir="/home/erwan/Documents/dev/model_resolver",
    output_dir="/home/erwan/Documents/dev/model_resolver/build",
    filter=None,
    use_cache=False,
    load_vanilla=True,
    resolve_vanilla_atlas=False,
    minecraft_version="latest",
    __special_filter__={"minecraft:item/glass": "/home/erwan/glasssss.png"},
)
