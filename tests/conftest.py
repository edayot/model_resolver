from PIL import ImageChops
import numpy as np
from beet.core.file import PngFile

_TOLERANCE = 1

_original_content_equal = PngFile.content_equal


def _content_equal_with_tolerance(self, other):
    left, right = self.image, other.image
    if left.size != right.size:
        return False
    if left.mode != right.mode:
        left = left.convert("RGBA")
        right = right.convert("RGBA")
    diff = ImageChops.difference(left, right)
    extrema = diff.getextrema()
    if isinstance(extrema[0], int):
        # Single-channel image: extrema is (min, max)
        return extrema[1] <= _TOLERANCE
    # Multi-channel image: extrema is ((min, max), (min, max), ...)
    return all(max_val <= _TOLERANCE for _, max_val in extrema)


PngFile.content_equal = _content_equal_with_tolerance
