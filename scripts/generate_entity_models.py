"""Generate model_resolver/data/entity_models.json from a Minecraft client jar.

Some special models draw entity models (ModelPart trees) that only exist as code, in
the `createBodyLayer` methods of the model classes. This decompiles those classes and
reads their `addOrReplaceChild(name, CubeListBuilder..., PartPose...)` calls.

    python scripts/generate_entity_models.py <client.jar> <cfr.jar> [--version 26.3]

CFR is https://github.com/leibnitz27/cfr.
"""

import argparse
import ast
import json
import math
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

# layer name: (model class, method)
LAYERS = {
    "bell": ("net/minecraft/client/model/object/bell/BellModel", "createBodyLayer"),
    "book": ("net/minecraft/client/model/object/book/BookModel", "createBodyLayer"),
    "copper_golem": ("net/minecraft/client/model/animal/golem/CopperGolemModel", "createBodyLayer"),
    "copper_golem_running": ("net/minecraft/client/model/animal/golem/CopperGolemModel", "createRunningPoseBodyLayer"),
    "copper_golem_sitting": ("net/minecraft/client/model/animal/golem/CopperGolemModel", "createSittingPoseBodyLayer"),
    "copper_golem_star": ("net/minecraft/client/model/animal/golem/CopperGolemModel", "createStarPoseBodyLayer"),
}
OUTPUT = Path(__file__).parent.parent / "model_resolver" / "data" / "entity_models.json"


def find_class(archive: zipfile.ZipFile, path: str) -> str:
    """The class path in the jar, also when the package moved (only the name is kept)."""
    names = archive.namelist()
    if f"{path}.class" in names:
        return f"{path}.class"
    simple = path.split("/")[-1] + ".class"
    matches = [n for n in names if n.endswith("/" + simple)]
    if len(matches) != 1:
        raise KeyError(f"{path} not found in the jar ({matches})")
    return matches[0]


def decompile(archive: zipfile.ZipFile, cfr: Path, path: str, workdir: Path) -> str:
    name = find_class(archive, path)
    target = workdir / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(archive.read(name))
    subprocess.run(
        ["java", "-jar", str(cfr), str(target), "--outputdir", str(workdir / "src")],
        check=True,
        capture_output=True,
    )
    return (workdir / "src" / name.replace(".class", ".java")).read_text()


def number(text: str) -> float:
    """Evaluate a Java float expression such as -1.5707964f or (float)Math.PI / 2.0f."""
    text = text.strip().replace("(float)", "").replace("(double)", "")
    text = re.sub(r"(?<=[\d.])[fFdD]\b", "", text).replace("Math.PI", repr(math.pi))
    tree = ast.parse(text, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.operator, ast.unaryop)):
            raise ValueError(f"not a number: {text}")
    return float(eval(compile(tree, "<number>", "eval")))


def split_args(text: str) -> list[str]:
    args, depth, current = [], 0, ""
    for char in text:
        if char == "," and depth == 0:
            args.append(current.strip())
            current = ""
            continue
        depth += char in "([{"
        depth -= char in ")]}"
        current += char
    if current.strip():
        args.append(current.strip())
    return args


def calls(chain: str) -> list[tuple[str, list[str]]]:
    """`a(1).b(2, 3)` -> [("a", ["1"]), ("b", ["2", "3"])], nested parentheses allowed."""
    result = []
    i = 0
    while i < len(chain):
        match = re.compile(r"\.?(\w+)\(").match(chain, i)
        if not match:
            i += 1
            continue
        depth, j = 1, match.end()
        while depth:
            depth += chain[j] == "("
            depth -= chain[j] == ")"
            j += 1
        result.append((match.group(1), split_args(chain[match.end() : j - 1])))
        i = j
    return result


def cubes(chain: str, builders: dict[str, list[dict]]) -> list[dict]:
    if chain in builders:
        return builders[chain]
    result: list[dict] = []
    uv, mirror = [0.0, 0.0], False
    for name, args in calls(chain):
        if name == "texOffs":
            uv = [number(args[0]), number(args[1])]
        elif name == "mirror":
            mirror = args == [] or args[0] == "true"
        elif name == "addBox":
            grow = [0.0, 0.0, 0.0]
            box_mirror = mirror
            for extra in args[6:]:
                if extra in ("true", "false"):
                    box_mirror = extra == "true"
                elif extra.startswith("new CubeDeformation("):
                    values = [number(x) for x in split_args(extra[len("new CubeDeformation(") : -1])]
                    grow = values * 3 if len(values) == 1 else values
            result.append(
                {
                    "uv": uv,
                    "origin": [number(x) for x in args[0:3]],
                    "size": [number(x) for x in args[3:6]],
                    "grow": grow,
                    "mirror": box_mirror,
                }
            )
    return result


def pose(text: str) -> list[float]:
    """[x, y, z, xRot, yRot, zRot] of a PartPose expression."""
    if text.strip() == "PartPose.ZERO":
        return [0.0] * 6
    ((name, args),) = calls(text.strip().removeprefix("PartPose"))
    values = [number(x) for x in args]
    if name == "offset":
        return values + [0.0, 0.0, 0.0]
    if name == "rotation":
        return [0.0, 0.0, 0.0] + values
    if name == "offsetAndRotation":
        return values
    raise ValueError(f"unknown pose {text}")


def parse_layer(source: str, method: str) -> dict:
    constants = dict(re.findall(r'String (\w+) = "([^"]*)";', source))
    body = source[source.index(f" {method}()") :]
    body = body[: body.index("return LayerDefinition.create(") + 200]
    # without the rest of the jar on its classpath, CFR adds casts: (float)8.0f, (MeshDefinition)mesh
    body = re.sub(r"\((?:float|int|double|[A-Z]\w*)\)(?=[\w(-])", "", body)
    size = re.search(r"return LayerDefinition\.create\(\w+, (\d+), (\d+)\)", body)
    assert size, f"no texture size in {method}"
    root = {"name": "root", "pose": [0.0] * 6, "cubes": [], "children": []}
    parts = {}
    builders: dict[str, list[dict]] = {}
    for statement in body.split(";"):
        statement = " ".join(statement.split())
        if match := re.search(r"PartDefinition (\w+) = \w+\.getRoot\(\)", statement):
            parts[match.group(1)] = root
            continue
        if match := re.search(r"CubeListBuilder (\w+) = (CubeListBuilder\.create\(\).*)$", statement):
            builders[match.group(1)] = cubes(match.group(2), builders)
            continue
        match = re.search(r"(?:PartDefinition (\w+) = )?(\w+)\.addOrReplaceChild\((.*)\)$", statement)
        if not match:
            continue
        variable, parent, args = match.groups()
        name, chain, part_pose = split_args(args)
        name = name.strip('"') if name.startswith('"') else constants[name]
        part = {"name": name, "pose": pose(part_pose), "cubes": cubes(chain, builders), "children": []}
        parts[parent]["children"].append(part)
        if variable:
            parts[variable] = part
    return {"texture_size": [int(size.group(1)), int(size.group(2))], "root": root}


def main():
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("jar", type=Path)
    parser.add_argument("cfr", type=Path)
    parser.add_argument("--version", default="26.3")
    args = parser.parse_args()
    layers = {}
    with tempfile.TemporaryDirectory() as workdir, zipfile.ZipFile(args.jar) as archive:
        sources: dict[str, str] = {}
        for name, (path, method) in LAYERS.items():
            if path not in sources:
                sources[path] = decompile(archive, args.cfr, path, Path(workdir))
            layers[name] = parse_layer(sources[path], method)
    tables = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    tables[args.version] = layers
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(tables, indent=1, sort_keys=True) + "\n")
    print(f"{len(layers)} layers -> {OUTPUT}")


if __name__ == "__main__":
    main()
