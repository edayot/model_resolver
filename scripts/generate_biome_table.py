"""Generate model_resolver/data/biomes.json from a Minecraft client jar.

Keeps what block colors need from every vanilla biome: temperature, downfall and the
color effects (water, grass, foliage, dry foliage, grass color modifier). The biomes are
plain JSON in the jar, so nothing is decompiled.

    python scripts/generate_biome_table.py <client.jar> [--version 26.3]

The client jar is the one beet caches for the vanilla assets
(`.beet_cache/vanilla/<version>-client/client.jar`).
"""

import argparse
import json
import zipfile
from pathlib import Path

OUTPUT = Path(__file__).parent.parent / "model_resolver" / "data" / "biomes.json"
PREFIX = "data/minecraft/worldgen/biome/"
EFFECTS = ("water_color", "grass_color", "foliage_color", "dry_foliage_color", "grass_color_modifier")


def main():
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("jar", type=Path)
    parser.add_argument("--version", default="26.3")
    args = parser.parse_args()
    biomes = {}
    with zipfile.ZipFile(args.jar) as archive:
        for name in sorted(archive.namelist()):
            if not name.startswith(PREFIX) or not name.endswith(".json"):
                continue
            data = json.loads(archive.read(name))
            effects = data.get("effects", {})
            biomes[f"minecraft:{name[len(PREFIX):-5]}"] = {
                "temperature": data["temperature"],
                "downfall": data["downfall"],
                "effects": {key: effects[key] for key in EFFECTS if key in effects},
            }
    tables = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    tables[args.version] = biomes
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(tables, indent=1, sort_keys=True) + "\n")
    print(f"{len(biomes)} biomes -> {OUTPUT}")


if __name__ == "__main__":
    main()
