"""Helpers for the GL-free unit tests.

Everything here runs without an OpenGL context, network access or the vanilla jar:
packs are built in memory and GL calls are replaced by a recorder.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pytest
from beet import DataPack, ResourcePack

from model_resolver.item_model.item import Item
from model_resolver.pack_getter import PackGetter, PackGetterLookup
from model_resolver.utils import ModelResolverOptions

PLAN = "docs/migration-plan.md"


def gap(item_id: str, reason: str):
    """Mark a test that asserts vanilla behaviour model_resolver does not have yet.

    Strict, so the test turns red once the gap is fixed and the marker must be removed.
    """
    return pytest.mark.xfail(strict=True, reason=f"{item_id} ({PLAN}): {reason}")


class OfflineCache:
    """Stands in for ctx.cache[...]; unit tests must never download anything."""

    def __getitem__(self, name: str) -> "OfflineCache":
        return self

    def download(self, url: str) -> Any:
        raise RuntimeError(f"unit tests are offline, refusing to download {url}")


class FakeContext:
    """Just enough of beet's Context for code paths that call ctx.validate()."""

    def __init__(self, opts: ModelResolverOptions):
        self.opts = opts
        self.cache = OfflineCache()

    def validate(self, key: str, cls: Any) -> ModelResolverOptions:
        return self.opts


def make_getter(
    assets: Optional[ResourcePack] = None,
    data: Optional[DataPack] = None,
    **options: Any,
) -> PackGetter:
    opts = ModelResolverOptions(**options)
    lookup = PackGetterLookup(assets=assets or ResourcePack(), data=data or DataPack())
    return PackGetter(FakeContext(opts), None, lookup, opts, ["_static_lookup"])  # type: ignore


def make_layered_getter(*layers: ResourcePack, **options: Any) -> PackGetter:
    """A getter over several resource packs, highest priority first (like ctx, static, vanilla)."""
    opts = ModelResolverOptions(**options)
    names = [f"_layer{i}" for i in range(len(layers))]
    getter = PackGetter(FakeContext(opts), None, PackGetterLookup(), opts, names)  # type: ignore
    for name, assets in zip(names, layers):
        setattr(getter, name, PackGetterLookup(assets=assets, data=DataPack()))
    return getter


def make_item(
    id: str = "minecraft:stone",
    components: Optional[dict[str, Any]] = None,
    default_components: Optional[dict[str, Any]] = None,
) -> Item:
    item = Item(
        id=id,
        components=components or {},
        default_components=default_components or {},
    )
    item.__resolved__ = True
    return item


def model_node(model: str) -> dict[str, Any]:
    return {"type": "minecraft:model", "model": model}


def resolve_item_model(
    node: dict[str, Any],
    item: Optional[Item] = None,
    getter: Optional[PackGetter] = None,
) -> list[str]:
    """Resolve an item model tree and return the ids of the models it would draw."""
    from model_resolver.item_model.model import ItemModel

    parsed = ItemModel.model_validate({"model": node})
    resolved = parsed.resolve(getter or make_getter(), item or make_item())
    return [
        model.model if isinstance(model.model, str) else type(model).__name__
        for model in resolved
    ]


def rotation_matrix(angle: float, x: float, y: float, z: float) -> np.ndarray:
    """4x4 rotation of `angle` degrees around (x, y, z), like glRotatef."""
    norm = math.sqrt(x * x + y * y + z * z)
    x, y, z = x / norm, y / norm, z / norm
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    t = 1 - c
    return np.array(
        [
            [t * x * x + c, t * x * y - s * z, t * x * z + s * y, 0],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x, 0],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c, 0],
            [0, 0, 0, 1],
        ]
    )


def translation_matrix(x: float, y: float, z: float) -> np.ndarray:
    m = np.identity(4)
    m[:3, 3] = (x, y, z)
    return m


@dataclass
class Quad:
    texture: int
    vertices: list[tuple[float, float, float]] = field(default_factory=list)
    uvs: list[tuple[float, float]] = field(default_factory=list)
    colors: list[tuple[float, float, float]] = field(default_factory=list)


class GLRecorder:
    """Stand-in for the fixed-function GL calls model_resolver makes.

    Matrix calls post-multiply like OpenGL, immediate-mode quads are recorded
    with their vertices already transformed by the current matrix.
    """

    def __init__(self):
        self.matrix = np.identity(4)
        self._stack: list[np.ndarray] = []
        self.texture_pixels: dict[int, tuple[int, ...]] = {}
        """The first RGBA pixel of every uploaded texture."""
        self.quads: list[Quad] = []
        self._texture = 0
        self._next_texture = 0
        self._uv = (0.0, 0.0)
        self._color = (1.0, 1.0, 1.0)
        self._quad: Optional[Quad] = None

    def install(self, monkeypatch: pytest.MonkeyPatch, *modules: Any) -> "GLRecorder":
        for module in modules:
            for name in dir(module):
                if name.startswith("gl") and callable(getattr(module, name)):
                    monkeypatch.setattr(module, name, getattr(self, name, self._noop))
        return self

    def _noop(self, *args: Any, **kwargs: Any) -> None:
        return None

    def glLoadIdentity(self):
        self.matrix = np.identity(4)

    def glPushMatrix(self):
        self._stack.append(self.matrix.copy())

    def glPopMatrix(self):
        self.matrix = self._stack.pop()

    def glTranslatef(self, x, y, z):
        self.matrix = self.matrix @ translation_matrix(x, y, z)

    def glRotatef(self, angle, x, y, z):
        self.matrix = self.matrix @ rotation_matrix(angle, x, y, z)

    def glScalef(self, x, y, z):
        self.matrix = self.matrix @ np.diag([x, y, z, 1.0])

    def glMultMatrixf(self, m):
        # GL matrices are column-major
        self.matrix = self.matrix @ np.array(m, dtype=float).reshape(4, 4).T

    def glGenTextures(self, n):
        self._next_texture += 1
        return self._next_texture

    def glBindTexture(self, target, texture):
        self._texture = texture

    def glTexImage2D(
        self, target, level, internal, width, height, border, fmt, kind, data
    ):
        self.texture_pixels[self._texture] = tuple(data[:4])

    def glGetIntegerv(self, pname):
        return 0

    def glBegin(self, mode):
        self._quad = Quad(texture=self._texture)

    def glColor3f(self, r, g, b):
        self._color = (r, g, b)

    def glTexCoord2f(self, u, v):
        self._uv = (u, v)

    def glVertex3fv(self, v):
        assert self._quad is not None
        x, y, z, _ = self.matrix @ np.array([*v, 1.0])
        self._quad.vertices.append((float(x), float(y), float(z)))
        self._quad.uvs.append(self._uv)
        self._quad.colors.append(self._color)

    def glEnd(self):
        assert self._quad is not None
        self.quads.append(self._quad)
        self._quad = None
