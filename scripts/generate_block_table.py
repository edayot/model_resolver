"""Generate model_resolver/data/blocks.json from the Minecraft server and client jars.

What fluids and face occlusion need about every block state is computed in code, not
stored in any data file: whether the state is solid (BlockState.isSolid), the fluid it
holds (kelp and seagrass always hold water) and its occlusion shape. This runs
scripts/java/DumpBlocks.java against the server, so it needs a JDK (java and javac).

    python scripts/generate_block_table.py <server.jar> <client.jar> [--version 26.3]

The server jar can be the bundler jar beet caches (`.beet_cache/vanilla/*.jar`), the
client jar is `.beet_cache/vanilla/<version>-client/client.jar` (for the block tags).
"""

import argparse
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
OUTPUT = ROOT.parent / "model_resolver" / "data" / "blocks.json"
FLUIDS = {
    "minecraft:flowing_water": "minecraft:water",
    "minecraft:flowing_lava": "minecraft:lava",
}


def extract_server(jar: Path, workdir: Path) -> list[Path]:
    """The server jar and its libraries: the bundler's nested jars, or the jar itself."""
    paths = []
    with zipfile.ZipFile(jar) as archive:
        for name in archive.namelist():
            if name.startswith(
                ("META-INF/libraries/", "META-INF/versions/")
            ) and name.endswith(".jar"):
                path = workdir / Path(name).name
                path.write_bytes(archive.read(name))
                paths.append(path)
    return paths or [jar]


def dump(server: Path, workdir: Path) -> list[dict[str, Any]]:
    classpath = ":".join(str(path) for path in extract_server(server, workdir))
    source = ROOT / "java" / "DumpBlocks.java"
    subprocess.run(
        ["javac", "-nowarn", "-cp", classpath, "-d", str(workdir), str(source)],
        check=True,
    )
    output = workdir / "states.jsonl"
    subprocess.run(
        ["java", "-cp", f"{workdir}:{classpath}", "DumpBlocks", str(output)],
        check=True,
        capture_output=True,
        cwd=workdir,  # the game's bootstrap writes logs/ in the working directory
    )
    return [json.loads(line) for line in output.read_text().splitlines()]


def tag(archive: zipfile.ZipFile, name: str) -> set[str]:
    """The blocks of a block tag, nested tags resolved."""
    data = json.loads(archive.read(f"data/minecraft/tags/block/{name}.json"))
    blocks: set[str] = set()
    for value in data["values"]:
        value = value["id"] if isinstance(value, dict) else value
        if value.startswith("#"):
            blocks |= tag(archive, value[1:].removeprefix("minecraft:"))
        else:
            blocks.add(value if ":" in value else f"minecraft:{value}")
    return blocks


def derived_fluid(block: str, properties: dict[str, str]) -> Any:
    """The fluid model_resolver already infers: waterlogged blocks, and water and lava by level."""
    if block in ("minecraft:water", "minecraft:lava"):
        level = int(properties["level"])
        return [block, 8, True] if level >= 8 else [block, 8 - level, False]
    if properties.get("waterlogged") == "true":
        return ["minecraft:water", 8, False]
    return None


def compress(values: list[Any]) -> Any:
    """A constant, or {"by_state": the value of every state}."""
    return (
        values[0]
        if all(value == values[0] for value in values)
        else {"by_state": values}
    )


def build(states: list[dict[str, Any]]) -> dict[str, Any]:
    shapes: list[Any] = [[], [[0.0, 0.0, 0.0, 1.0, 1.0, 1.0]]]
    shape_ids = {json.dumps(shape): i for i, shape in enumerate(shapes)}
    by_block: dict[str, list[dict[str, Any]]] = {}
    for state in states:
        by_block.setdefault(state["block"], []).append(state)
    blocks = {}
    for block, block_states in by_block.items():
        properties: dict[str, list[str]] = {}
        for state in block_states:
            for key, value in state["properties"].items():
                properties.setdefault(key, [])
                if value not in properties[key]:
                    properties[key].append(value)
        size = len(block_states)
        solid: list[Any] = [None] * size
        fluid: list[Any] = [None] * size
        occlusion: list[Any] = [None] * size
        for state in block_states:
            # mixed radix over the properties in the order listed
            index = 0
            for key, values in properties.items():
                index = index * len(values) + values.index(state["properties"][key])
            solid[index] = state["solid"]
            dumped = state["fluid"] and [
                FLUIDS.get(state["fluid"][0], state["fluid"][0]),
                *state["fluid"][1:],
            ]
            fluid[index] = (
                None
                if dumped == derived_fluid(block, state["properties"])
                else (dumped or "none")
            )
            key = json.dumps(sorted(state["occlusion"]))
            if key not in shape_ids:
                shape_ids[key] = len(shapes)
                shapes.append(sorted(state["occlusion"]))
            occlusion[index] = shape_ids[key]
        entry: dict[str, Any] = {
            "solid": compress(solid),
            "occlusion": compress(occlusion),
        }
        if any(value is not None for value in fluid):
            entry["fluid"] = compress(fluid)
        if any(isinstance(value, dict) for value in entry.values()):
            entry["properties"] = properties
        blocks[block] = entry
    return {"shapes": shapes, "blocks": blocks}


def main():
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("server", type=Path)
    parser.add_argument("client", type=Path)
    parser.add_argument("--version", default="26.3")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as workdir:
        table = build(dump(args.server, Path(workdir)))
    with zipfile.ZipFile(args.client) as archive:
        table["blocks_fluid_flow"] = sorted(tag(archive, "blocks_fluid_flow"))
    tables = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    tables[args.version] = table
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(tables, separators=(",", ":"), sort_keys=True) + "\n")
    print(f"{len(table['blocks'])} blocks, {len(table['shapes'])} shapes -> {OUTPUT}")


if __name__ == "__main__":
    main()
