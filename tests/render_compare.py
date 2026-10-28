"""Compare rendered packs with a tolerance, so render snapshots can run on CI.

CI's Mesa renders differ from local GPU renders: in most images 7-20% of the drawn pixels
are off by one level (rounding), and a few edge texels flip. A real change is far bigger
(see X1 in docs/migration-plan.md for the measurements behind these thresholds).
"""

import gzip
import io
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageSequence

LEVELS = 2
"""Channel difference above which a pixel counts as changed."""
MAX_CHANGED = 0.01
"""Share of the drawn pixels (opaque in either image) allowed to change."""
MAX_SILHOUETTE = 0.001
"""Share of the drawn pixels allowed to become transparent or opaque."""

IMAGE_EXTENSIONS = (".png", ".webp")


@dataclass
class ImageDiff:
    changed: float
    silhouette: float

    @property
    def ok(self) -> bool:
        return self.changed <= MAX_CHANGED and self.silhouette <= MAX_SILHOUETTE


def frames(data: bytes) -> list[np.ndarray]:
    with Image.open(io.BytesIO(data)) as image:
        return [
            np.asarray(frame.convert("RGBA")).astype(int)
            for frame in ImageSequence.Iterator(image)
        ]


def compare_images(expected: bytes, actual: bytes) -> ImageDiff:
    a, b = frames(expected), frames(actual)
    if len(a) != len(b) or any(x.shape != y.shape for x, y in zip(a, b)):
        return ImageDiff(1.0, 1.0)
    changed = silhouette = drawn = 0
    for x, y in zip(a, b):
        visible = (x[..., 3] > 0) | (y[..., 3] > 0)
        drawn += visible.sum()
        changed += ((np.abs(x - y).max(axis=-1) > LEVELS) & visible).sum()
        silhouette += ((x[..., 3] > 0) != (y[..., 3] > 0)).sum()
    drawn = max(1, int(drawn))
    return ImageDiff(changed / drawn, silhouette / drawn)


def file_bytes(file: Any) -> bytes:
    data = file.ensure_serialized()
    return data if isinstance(data, bytes) else data.encode()


def pack_differences(expected: Any, actual: Any) -> list[str]:
    """What differs between two beet packs, images compared with a tolerance."""
    expected_files = dict(expected.list_files())
    actual_files = dict(actual.list_files())
    problems = [
        f"missing {path}"
        for path in sorted(expected_files.keys() - actual_files.keys())
    ]
    problems += [
        f"unexpected {path}"
        for path in sorted(actual_files.keys() - expected_files.keys())
    ]
    for path in sorted(expected_files.keys() & actual_files.keys()):
        a, b = file_bytes(expected_files[path]), file_bytes(actual_files[path])
        if a == b:
            continue
        if path.endswith((".json", ".mcmeta")):
            if json.loads(a) != json.loads(b):
                problems.append(f"{path} differs")
        elif path.endswith(".nbt"):
            # gzip headers hold the time they were written
            if gzip.decompress(a) != gzip.decompress(b):
                problems.append(f"{path} differs")
        elif path.endswith(IMAGE_EXTENSIONS):
            diff = compare_images(a, b)
            if not diff.ok:
                problems.append(
                    f"{path}: {diff.changed:.2%} of drawn pixels changed, silhouette {diff.silhouette:.3%}"
                )
        else:
            problems.append(f"{path} differs")
    return problems
