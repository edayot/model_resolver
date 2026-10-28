"""Generate model_resolver/data/potions.json from a Minecraft client jar.

Potion colors are not in any data file: the effect colors are constants in
`MobEffects` and the effects of each potion are in `Potions`. Since 26.1 the jar is
not obfuscated, so decompiling those classes is enough.

    python scripts/generate_potion_table.py <client.jar> <cfr.jar> [--version 26.3]

Either the client jar or the server jar works, including the server bundler jar that
beet caches (`.beet_cache/vanilla/*.jar`). CFR is https://github.com/leibnitz27/cfr.
"""

import argparse
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

CLASSES = {
    "effects": "net/minecraft/world/effect/MobEffects",
    "potions": "net/minecraft/world/item/alchemy/Potions",
    "potion_ids": "net/minecraft/world/item/alchemy/PotionIds",
}
OUTPUT = Path(__file__).parent.parent / "model_resolver" / "data" / "potions.json"


def read_class(archive: zipfile.ZipFile, path: str) -> bytes:
    """A class from the jar, or from the server jar nested in a server bundler jar."""
    if path in archive.namelist():
        return archive.read(path)
    for name in archive.namelist():
        if name.startswith("META-INF/versions/") and name.endswith(".jar"):
            with zipfile.ZipFile(archive.open(name)) as nested:
                if path in nested.namelist():
                    return nested.read(path)
    raise KeyError(f"{path} not found in the jar")


def decompile(jar: Path, cfr: Path, workdir: Path) -> dict[str, str]:
    sources: dict[str, str] = {}
    with zipfile.ZipFile(jar) as archive:
        for name, path in CLASSES.items():
            class_file = workdir / f"{name}.class"
            class_file.write_bytes(read_class(archive, f"{path}.class"))
            subprocess.run(
                ["java", "-jar", str(cfr), str(class_file), "--outputdir", str(workdir)],
                check=True,
                capture_output=True,
            )
            sources[name] = (workdir / f"{path}.java").read_text()
    return sources


def parse(sources: dict[str, str]) -> dict:
    # without the rest of the jar on its classpath, CFR adds casts such as (ResourceKey<Potion>)
    # public static final Holder<MobEffect> SPEED = MobEffects.register("speed", new MobEffect(MobEffectCategory.BENEFICIAL, 3402751)...
    # CFR writes some colors in hex: new MobEffect(MobEffectCategory.BENEFICIAL, 0xFF9900)
    effects: dict[str, tuple[str, int]] = {
        const: (f"minecraft:{name}", int(color, 0))
        for const, name, color in re.findall(
            r'(\w+) = MobEffects\.register\("(\w+)", (?:\(\w+\))?new \w+\(MobEffectCategory\.\w+, (-?(?:0x[0-9A-Fa-f]+|\d+))',
            sources["effects"],
        )
    }
    # public static final ResourceKey<Potion> HEALING = PotionIds.register("healing");
    potion_ids = dict(re.findall(r'(\w+) = PotionIds\.register\("(\w+)"\)', sources["potion_ids"]))
    potions: dict[str, list[dict]] = {}
    # Potions.register(PotionIds.HEALING, new Potion("healing", new MobEffectInstance(MobEffects.INSTANT_HEALTH, 1)));
    for const, body in re.findall(
        r"Potions\.register\((?:\([\w<>]+\))?PotionIds\.(\w+), new Potion\((.*)\)\);", sources["potions"]
    ):
        potions[f"minecraft:{potion_ids[const]}"] = [
            {"id": effects[effect][0], "duration": int(duration), "amplifier": int(amplifier or 0)}
            for effect, duration, amplifier in re.findall(
                r"new MobEffectInstance\(MobEffects\.(\w+), (-?\d+)(?:, (\d+))?", body
            )
        ]
    if any(color == 0 for _, color in effects.values()):
        raise ValueError("an effect color was not parsed")
    if len(potions) != len(potion_ids):
        raise ValueError(f"parsed {len(potions)} potions out of {len(potion_ids)} ids")
    return {
        "effects": {name: color for name, color in effects.values()},
        "potions": potions,
    }


def main():
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("jar", type=Path)
    parser.add_argument("cfr", type=Path)
    parser.add_argument("--version", default="26.3")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as workdir:
        table = parse(decompile(args.jar, args.cfr, Path(workdir)))
    tables = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    tables[args.version] = table
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(tables, indent=2, sort_keys=True) + "\n")
    print(f"{len(table['effects'])} effects, {len(table['potions'])} potions -> {OUTPUT}")


if __name__ == "__main__":
    main()
