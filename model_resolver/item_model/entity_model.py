"""Entity models (ModelPart trees) as model elements, for special models that draw them.

The trees come from scripts/generate_entity_models.py. Elements are placed in the entity
model's own space, in pixels: the item definition's transformation puts them in place
like the game does.
"""

from functools import cache
import json
import math
from pathlib import Path
from typing import Any, Optional

import numpy as np
from beet import LATEST_MINECRAFT_VERSION

# FaceInfo: the corners of each face, low or high on each axis, in vertex order
FACE_CORNERS = {
    "down": [(0, 0, 1), (0, 0, 0), (1, 0, 0), (1, 0, 1)],
    "up": [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)],
    "north": [(1, 1, 0), (1, 0, 0), (0, 0, 0), (0, 1, 0)],
    "south": [(0, 1, 1), (0, 0, 1), (1, 0, 1), (1, 1, 1)],
    "west": [(0, 1, 0), (0, 0, 0), (0, 0, 1), (0, 1, 1)],
    "east": [(1, 1, 1), (1, 0, 1), (1, 0, 0), (1, 1, 0)],
}


@cache
def entity_layers(version: str) -> dict[str, Any]:
    tables = json.loads((Path(__file__).parent.parent / "data" / "entity_models.json").read_text())
    if version == "latest":
        version = LATEST_MINECRAFT_VERSION
    if version in tables:
        return tables[version]
    return tables[max(tables, key=lambda v: tuple(map(int, v.split("."))))]


def _rotation(x: float, y: float, z: float) -> np.ndarray:
    # Quaternionf.rotationZYX(z, y, x): x first, then y, then z (radians)
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rz @ ry @ rx


def _euler_xyz(rotation: np.ndarray) -> tuple[float, float, float]:
    """Degrees (x, y, z) such that Rz @ Ry @ Rx == rotation."""
    y = math.asin(max(-1.0, min(1.0, -rotation[2, 0])))
    if abs(math.cos(y)) > 1e-6:
        x = math.atan2(rotation[2, 1], rotation[2, 2])
        z = math.atan2(rotation[1, 0], rotation[0, 0])
    else:
        x, z = math.atan2(-rotation[1, 2], rotation[1, 1]), 0.0
    return tuple(round(math.degrees(a), 6) for a in (x, y, z))  # type: ignore


def _polygons(cube: dict[str, Any]) -> list[tuple[list[np.ndarray], list[tuple[float, float]]]]:
    """ModelPart.Cube: the faces of a box and the texture pixel of each corner."""
    (ox, oy, oz), (w, h, d), (gx, gy, gz) = cube["origin"], cube["size"], cube["grow"]
    min_x, min_y, min_z = ox - gx, oy - gy, oz - gz
    max_x, max_y, max_z = ox + w + gx, oy + h + gy, oz + d + gz
    mirror = cube["mirror"]
    if mirror:
        min_x, max_x = max_x, min_x
    t0, t1 = np.array([min_x, min_y, min_z]), np.array([max_x, min_y, min_z])
    t2, t3 = np.array([max_x, max_y, min_z]), np.array([min_x, max_y, min_z])
    l0, l1 = np.array([min_x, min_y, max_z]), np.array([max_x, min_y, max_z])
    l2, l3 = np.array([max_x, max_y, max_z]), np.array([min_x, max_y, max_z])
    u, v = cube["uv"]
    u0, u1, u2, u22, u3, u4 = u, u + d, u + d + w, u + d + w + w, u + d + w + d, u + d + w + d + w
    v0, v1, v2 = v, v + d, v + d + h
    polygons = []
    for vertices, (a, b, c, e) in (
        ([l1, l0, t0, t1], (u1, v0, u2, v1)),
        ([t2, t3, l3, l2], (u2, v1, u22, v0)),
        ([t0, l0, l3, t3], (u0, v1, u1, v2)),
        ([t1, t0, t3, t2], (u1, v1, u2, v2)),
        ([l1, t1, t2, l2], (u2, v1, u3, v2)),
        ([l0, l1, l2, l3], (u3, v1, u4, v2)),
    ):
        # ModelPart.Polygon: corners get (u1, v0), (u0, v0), (u0, v1), (u1, v1)
        uvs = [(c, b), (a, b), (a, e), (c, e)]
        if mirror:
            vertices, uvs = vertices[::-1], uvs[::-1]
        polygons.append((vertices, uvs))
    return polygons


def _face(
    vertices: list[np.ndarray], uvs: list[tuple[float, float]], low: np.ndarray, high: np.ndarray
) -> Optional[tuple[str, dict[str, Any]]]:
    """The element face a polygon is, with the uv and rotation that give its corners their uvs."""
    for name, corners in FACE_CORNERS.items():
        positions = [np.where(np.array(corner) == 1, high, low) for corner in corners]
        if {tuple(np.round(p, 5)) for p in positions} != {tuple(np.round(p, 5)) for p in vertices}:
            continue
        if np.allclose(low, high):
            return None
        corner_uvs = []
        for position in positions:
            index = min(range(4), key=lambda i: float(np.abs(vertices[i] - position).sum()))
            corner_uvs.append(uvs[index])
        for shift in range(4):
            # CuboidFace.getU / getV: corner (i + shift) % 4 takes min u for 0, 1 and min v for 0, 3
            us: dict[str, set[float]] = {"min": set(), "max": set()}
            vs: dict[str, set[float]] = {"min": set(), "max": set()}
            for i, (cu, cv) in enumerate(corner_uvs):
                k = (i + shift) % 4
                us["min" if k in (0, 1) else "max"].add(round(cu, 5))
                vs["min" if k in (0, 3) else "max"].add(round(cv, 5))
            if all(len(x) == 1 for x in (*us.values(), *vs.values())):
                uv = (us["min"].pop(), vs["min"].pop(), us["max"].pop(), vs["max"].pop())
                return name, {"uv": uv, "rotation": shift * 90}
    return None


def to_elements(
    layer: dict[str, Any],
    texture: str = "#0",
    poses: Optional[dict[str, dict[str, float]]] = None,
) -> list[dict[str, Any]]:
    """Elements of a layer. `poses` overrides part poses by name (x, y, z, xRot, yRot, zRot),
    like the model's setupAnim."""
    poses = poses or {}
    width, height = layer["texture_size"]
    elements: list[dict[str, Any]] = []

    def visit(part: dict[str, Any], parent: np.ndarray):
        pose: dict[str, float] = dict(zip(("x", "y", "z", "xRot", "yRot", "zRot"), part["pose"]))
        pose.update(poses.get(part["name"], {}))
        x, y, z = pose["x"], pose["y"], pose["z"]
        x_rot, y_rot, z_rot = pose["xRot"], pose["yRot"], pose["zRot"]
        # ModelPart.translateAndRotate
        local = np.identity(4)
        local[:3, :3] = _rotation(x_rot, y_rot, z_rot)
        local[:3, 3] = (x, y, z)
        matrix = parent @ local
        rotation, translation = matrix[:3, :3], matrix[:3, 3]
        for cube in part["cubes"]:
            polygons = _polygons(cube)
            corners = np.array([vertex for vertices, _ in polygons for vertex in vertices])
            low, high = corners.min(axis=0), corners.max(axis=0)
            faces = {}
            for vertices, uvs in polygons:
                face = _face(vertices, uvs, low, high)
                if face is not None:
                    name, data = face
                    u0, v0, u1, v1 = data["uv"]
                    data["uv"] = [u0 * 16 / width, v0 * 16 / height, u1 * 16 / width, v1 * 16 / height]
                    faces[name] = {**data, "texture": texture}
            angles = _euler_xyz(rotation)
            element: dict[str, Any] = {
                "from": (low + translation).tolist(),
                "to": (high + translation).tolist(),
                "faces": faces,
            }
            if any(angles):
                element["rotation"] = {
                    "origin": translation.tolist(),
                    "x": angles[0],
                    "y": angles[1],
                    "z": angles[2],
                }
            elements.append(element)
        for child in part["children"]:
            visit(child, matrix)

    visit(layer["root"], np.identity(4))
    return elements
