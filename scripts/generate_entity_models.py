"""Generate model_resolver/data/entity_models.json from a Minecraft client jar.

Special models and block entities draw entity models (ModelPart trees) that only exist as
code, in the `create*Layer` methods of the model and renderer classes. This decompiles
those classes and interprets their `addOrReplaceChild(name, CubeListBuilder..., PartPose...)`
statements, following calls to other classes and the method's parameters.

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
from typing import Any, Optional

DIRECTIONS = ["down", "up", "west", "north", "east", "south"]
"""Direction values, in the order ModelPart.Cube makes its polygons."""

# layer name: (class, method, arguments, texture size when the method returns a mesh),
# like LayerDefinitions.createRoots
LAYERS: dict[str, tuple[str, str, list[Any], Optional[tuple[int, int]]]] = {
    "banner": ("BannerModel", "createBodyLayer", [True], None),
    "wall_banner": ("BannerModel", "createBodyLayer", [False], None),
    "banner_flag": ("BannerFlagModel", "createFlagLayer", [True], None),
    "wall_banner_flag": ("BannerFlagModel", "createFlagLayer", [False], None),
    "bell": ("BellModel", "createBodyLayer", [], None),
    "book": ("BookModel", "createBodyLayer", [], None),
    "chest": ("ChestModel", "createSingleBodyLayer", [], None),
    "double_chest_left": ("ChestModel", "createDoubleBodyLeftLayer", [], None),
    "double_chest_right": ("ChestModel", "createDoubleBodyRightLayer", [], None),
    "conduit_shell": ("ConduitRenderer", "createShellLayer", [], None),
    "copper_golem": ("CopperGolemModel", "createBodyLayer", [], None),
    "copper_golem_running": (
        "CopperGolemModel",
        "createRunningPoseBodyLayer",
        [],
        None,
    ),
    "copper_golem_sitting": (
        "CopperGolemModel",
        "createSittingPoseBodyLayer",
        [],
        None,
    ),
    "copper_golem_star": ("CopperGolemModel", "createStarPoseBodyLayer", [], None),
    "decorated_pot_base": ("DecoratedPotRenderer", "createBaseLayer", [], None),
    "decorated_pot_sides": ("DecoratedPotRenderer", "createSidesLayer", [], None),
    "dragon_skull": ("DragonHeadModel", "createHeadLayer", [], None),
    "mob_head": ("SkullModel", "createMobHeadLayer", [], None),
    "humanoid_head": ("SkullModel", "createHumanoidHeadLayer", [], None),
    "piglin_head": ("PiglinHeadModel", "createHeadModel", [], (64, 64)),
    "shield": ("ShieldModel", "createLayer", [], None),
    "shulker_box": ("ShulkerModel", "createBoxLayer", [], None),
    "trident": ("TridentModel", "createLayer", [], None),
}
OUTPUT = Path(__file__).parent.parent / "model_resolver" / "data" / "entity_models.json"


class Classes:
    """Decompiled classes of the jar, by simple name."""

    def __init__(self, archive: zipfile.ZipFile, cfr: Path, workdir: Path):
        self.archive, self.cfr, self.workdir = archive, cfr, workdir
        self.names = archive.namelist()
        self.sources: dict[str, str] = {}

    def path(self, name: str) -> str:
        matches = [n for n in self.names if n.endswith("/" + name + ".class")]
        if len(matches) != 1:
            raise KeyError(f"{name} not found in the jar ({matches})")
        return matches[0]

    def source(self, name: str) -> str:
        if name not in self.sources:
            path = self.path(name)
            target = self.workdir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.archive.read(path))
            subprocess.run(
                [
                    "java",
                    "-jar",
                    str(self.cfr),
                    str(target),
                    "--outputdir",
                    str(self.workdir / "src"),
                ],
                check=True,
                capture_output=True,
            )
            text = (self.workdir / "src" / path.replace(".class", ".java")).read_text()
            # without the rest of the jar on its classpath, CFR adds casts: (float)8.0f, (MeshDefinition)mesh
            self.sources[name] = re.sub(
                r"\((?:float|int|double|[A-Z]\w*)\)(?=[\w(-])", "", text
            )
        return self.sources[name]

    def method(self, name: str, method: str) -> tuple[str, list[str], str]:
        """(class, parameter names, body) of a static method, looked up in superclasses too."""
        source = self.source(name)
        match = re.search(rf"static [\w<>.\[\], ]+? {method}\(([^)]*)\) \{{", source)
        if match is None:
            parent = re.search(rf"class {name}\b[^{{]*?extends (\w+)", source)
            if parent is None:
                raise KeyError(f"{name}.{method} not found")
            return self.method(parent.group(1), method)
        params = [p.split()[-1] for p in split_args(match.group(1))]
        return name, params, block(source, match.end() - 1)


def block(text: str, start: int) -> str:
    """The text between the brace at `start` and the one closing it."""
    depth = 0
    for i in range(start, len(text)):
        depth += text[i] == "{"
        depth -= text[i] == "}"
        if depth == 0:
            return text[start + 1 : i]
    raise ValueError("unbalanced braces")


def split_args(text: str, separator: str = ",") -> list[str]:
    args, depth, current, quoted = [], 0, "", False
    for char in text:
        quoted ^= char == '"'
        if char == separator and depth == 0 and not quoted:
            args.append(current.strip())
            current = ""
            continue
        if not quoted:
            depth += char in "([{"
            depth -= char in ")]}"
        current += char
    if current.strip():
        args.append(current.strip())
    return args


def statements(body: str) -> list[str]:
    """Top-level statements, whitespace collapsed; `if (...) {...} else {...}` stays one."""
    result, current, depth, quoted = [], "", 0, False
    for i, char in enumerate(body):
        current += char
        quoted ^= char == '"'
        if quoted:
            continue
        depth += char in "([{"
        depth -= char in ")]}"
        ends_block = (
            char == "}" and depth == 0 and not body[i + 1 :].lstrip().startswith("else")
        )
        if depth == 0 and (char == ";" or ends_block):
            result.append(" ".join(current.removesuffix(";").split()))
            current = ""
    return [s for s in result if s]


def closing(text: str, start: int) -> int:
    """The index of the parenthesis closing the one at `start`."""
    depth = 0
    for i in range(start, len(text)):
        depth += text[i] == "("
        depth -= text[i] == ")"
        if depth == 0:
            return i
    raise ValueError("unbalanced parentheses")


def calls(chain: str) -> list[tuple[str, list[str]]]:
    """`.a(1).b(2, 3)` -> [("a", ["1"]), ("b", ["2", "3"])], nested parentheses allowed."""
    result = []
    i = 0
    while i < len(chain):
        match = re.compile(r"\.?(\w+)\(").match(chain, i)
        if not match:
            i += 1
            continue
        depth, j, quoted = 1, match.end(), False
        while depth:
            quoted ^= chain[j] == '"'
            if not quoted:
                depth += chain[j] == "("
                depth -= chain[j] == ")"
            j += 1
        result.append((match.group(1), split_args(chain[match.end() : j - 1])))
        i = j
    return result


def new_part(name: str, pose: dict[str, Any], cubes: list[dict]) -> dict[str, Any]:
    part = {"name": name, "pose": pose["pose"], "cubes": cubes, "children": []}
    if pose["scale"] != [1.0, 1.0, 1.0]:
        part["scale"] = pose["scale"]
    return part


class Interpreter:
    def __init__(self, classes: Classes):
        self.classes = classes

    def run(self, name: str, method: str, args: list[Any]) -> Any:
        owner, params, body = self.classes.method(name, method)
        constants = dict(
            re.findall(r'String (\w+) = "([^"]*)";', self.classes.source(owner))
        )
        env: dict[str, Any] = {**constants, **dict(zip(params, args))}
        return self.execute(body, env)

    def execute(self, body: str, env: dict[str, Any]) -> Any:
        for statement in statements(body):
            if statement.startswith("if ("):
                condition = statement[4 : closing(statement, 3)]
                then_start = statement.index("{")
                then_body = block(statement, then_start)
                rest = statement[then_start + len(then_body) + 2 :].strip()
                if self.value(condition, env):
                    result = self.execute(then_body, env)
                elif rest.startswith("else"):
                    result = self.execute(block(rest, rest.index("{")), env)
                else:
                    result = None
                if result is not None:
                    return result
                continue
            if statement.startswith("return "):
                return self.value(statement[len("return ") :], env)
            declaration = re.match(
                r"(?:final )?[\w.]+(?:<[\w, <>]+>)? (\w+) = (.+)$", statement
            )
            if declaration:
                env[declaration.group(1)] = self.value(declaration.group(2), env)
            else:
                self.value(statement, env)
        return None

    def number(self, text: str, env: dict[str, Any]) -> float:
        """Evaluate a Java float expression such as -1.5707964f or Math.PI / 2.0f."""
        text = text.strip()
        text = re.sub(r"(?<=[\d.])[fFdDL]\b", "", text).replace(
            "Math.PI", repr(math.pi)
        )
        text = re.sub(
            r"\b[a-zA-Z_]\w*\b",
            lambda m: repr(env[m.group(0)]) if m.group(0) in env else m.group(0),
            text,
        )
        tree = ast.parse(text, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(
                node,
                (
                    ast.Expression,
                    ast.BinOp,
                    ast.UnaryOp,
                    ast.Constant,
                    ast.operator,
                    ast.unaryop,
                ),
            ):
                raise ValueError(f"not a number: {text}")
        return float(eval(compile(tree, "<number>", "eval")))

    def float(self, expr: str, env: dict[str, Any]) -> float:
        return float(self.value(expr, env))

    def value(self, expr: str, env: dict[str, Any]) -> Any:
        expr = expr.strip()
        if expr.startswith("(") and closing(expr, 0) == len(expr) - 1:
            return self.value(expr[1:-1], env)
        ternary = split_args(expr, "?")
        if len(ternary) == 2:
            choices = split_args(ternary[1], ":")
            return self.value(
                choices[0] if self.value(ternary[0], env) else choices[1], env
            )
        if expr in ("true", "false"):
            return expr == "true"
        if expr.startswith('"'):
            return expr.strip('"')
        if expr in env:
            return env[expr]
        if expr == "PartPose.ZERO":
            return {"pose": [0.0] * 6, "scale": [1.0] * 3}
        if expr == "CubeDeformation.NONE":
            return [0.0, 0.0, 0.0]
        if expr.startswith("Direction."):
            return expr.removeprefix("Direction.").lower()
        head = re.match(r"(new \w+|\w+)", expr)
        if head is None or head.end() == len(expr):
            return self.number(expr, env)
        chain = (
            calls(expr[head.end() :])
            if not head.group(1).startswith("new ")
            else calls(expr[len("new ") :])
        )
        if not chain:
            # Math.PI / 2.0f, 1.5707964f
            return self.number(expr, env)
        if head.group(1).startswith("new "):
            kind, args = chain[0]
            if kind == "MeshDefinition":
                return {"root": new_part("root", self.value("PartPose.ZERO", env), [])}
            if kind == "CubeDeformation":
                values = [self.float(x, env) for x in args]
                return values * 3 if len(values) == 1 else values
            raise ValueError(f"unknown constructor {expr}")
        name = head.group(1)
        if name == "CubeListBuilder":
            return self.cubes(chain, env)
        if name == "PartPose":
            return self.pose(chain, env)
        if name == "LayerDefinition":
            ((_, (mesh, width, height)),) = chain
            return {
                "texture_size": [
                    int(self.float(width, env)),
                    int(self.float(height, env)),
                ],
                "root": self.value(mesh, env)["root"],
            }
        if name == "Util" and chain[0][0] == "allOfEnumExcept":
            excluded = {self.value(arg, env) for arg in chain[0][1]}
            return [d for d in DIRECTIONS if d not in excluded]
        if name == "EnumSet" and chain[0][0] == "of":
            return [self.value(arg, env) for arg in chain[0][1]]
        if name in env:
            return self.method_calls(env[name], chain, env)
        # a static method of another class
        method, args = chain[0]
        result = self.run(name, method, [self.value(arg, env) for arg in args])
        return self.method_calls(result, chain[1:], env)

    def method_calls(
        self, target: Any, chain: list[tuple[str, list[str]]], env: dict[str, Any]
    ) -> Any:
        for method, args in chain:
            if method == "getRoot":
                target = target["root"]
            elif method == "getChild":
                name = self.value(args[0], env)
                target = next(
                    child for child in target["children"] if child["name"] == name
                )
            elif method == "addOrReplaceChild":
                name, cubes, pose = (self.value(arg, env) for arg in args)
                part = new_part(name, pose, [dict(cube) for cube in cubes])
                target["children"] = [
                    c for c in target["children"] if c["name"] != name
                ] + [part]
                target = part
            else:
                raise ValueError(f"unknown method {method}")
        return target

    def cubes(
        self, chain: list[tuple[str, list[str]]], env: dict[str, Any]
    ) -> list[dict]:
        result: list[dict] = []
        uv, mirror = [0.0, 0.0], False
        for name, args in chain:
            if name == "create":
                continue
            if name == "texOffs":
                uv = [self.float(args[0], env), self.float(args[1], env)]
            elif name == "mirror":
                mirror = args == [] or self.value(args[0], env)
            elif name == "addBox":
                box_uv = uv
                if args[0].startswith('"'):
                    # addBox(name, x, y, z, w, h, d[, texX, texY])
                    args = args[1:]
                    if len(args) == 8:
                        box_uv = [self.float(args[6], env), self.float(args[7], env)]
                        args = args[:6]
                cube = {
                    "uv": box_uv,
                    "origin": [self.float(x, env) for x in args[0:3]],
                    "size": [self.float(x, env) for x in args[3:6]],
                    "grow": [0.0, 0.0, 0.0],
                    "mirror": mirror,
                }
                for extra in args[6:]:
                    value = self.value(extra, env)
                    if isinstance(value, bool):
                        cube["mirror"] = value
                    elif value and isinstance(value[0], str):
                        cube["faces"] = [d for d in DIRECTIONS if d in value]
                    else:
                        cube["grow"] = value
                result.append(cube)
            else:
                raise ValueError(f"unknown CubeListBuilder method {name}")
        return result

    def pose(
        self, chain: list[tuple[str, list[str]]], env: dict[str, Any]
    ) -> dict[str, Any]:
        """[x, y, z, xRot, yRot, zRot] and the scale of a PartPose expression."""
        pose, scale = [0.0] * 6, [1.0] * 3
        for name, args in chain:
            values = [self.float(x, env) for x in args]
            if name == "offset":
                pose[0:3] = values
            elif name == "rotation":
                pose[3:6] = values
            elif name == "offsetAndRotation":
                pose = values
            elif name == "scaled":
                scale = [
                    s * f
                    for s, f in zip(scale, values * 3 if len(values) == 1 else values)
                ]
            else:
                raise ValueError(f"unknown pose {name}")
        return {"pose": pose, "scale": scale}


def main():
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("jar", type=Path)
    parser.add_argument("cfr", type=Path)
    parser.add_argument("--version", default="26.3")
    args = parser.parse_args()
    layers = {}
    with tempfile.TemporaryDirectory() as workdir, zipfile.ZipFile(args.jar) as archive:
        interpreter = Interpreter(Classes(archive, args.cfr, Path(workdir)))
        for name, (owner, method, arguments, size) in LAYERS.items():
            result = interpreter.run(owner, method, arguments)
            if size is not None:
                result = {"texture_size": list(size), "root": result["root"]}
            layers[name] = result
    tables = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    tables[args.version] = layers
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(tables, indent=1, sort_keys=True) + "\n")
    print(f"{len(layers)} layers -> {OUTPUT}")


if __name__ == "__main__":
    main()
