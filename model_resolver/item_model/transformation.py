import math

from pydantic import BaseModel, RootModel
from typing import NamedTuple, Union


class Vector(NamedTuple):
    x: float
    y: float
    z: float

class Quaternion(NamedTuple):
    x: float
    y: float
    z: float
    w: float

class AxisAngle(BaseModel):
    axis: Vector
    angle: float

type Matrix = tuple[
    float, float, float, float,
    float, float, float, float,
    float, float, float, float,
    float, float, float, float,
]

type Rotation = Union[AxisAngle, Quaternion]


def _rotation_to_quaternion(rotation: Rotation) -> Quaternion:
    if isinstance(rotation, Quaternion):
        return rotation
    half = rotation.angle / 2.0
    s = math.sin(half)
    return Quaternion(rotation.axis.x * s, rotation.axis.y * s, rotation.axis.z * s, math.cos(half))


def _quat_to_mat4(q: Quaternion) -> Matrix:
    """Column-major 4x4 rotation matrix from quaternion."""
    x, y, z, w = q
    return (
        1-2*(y*y+z*z), 2*(x*y+w*z),   2*(x*z-w*y),   0,  # col 0
        2*(x*y-w*z),   1-2*(x*x+z*z), 2*(y*z+w*x),   0,  # col 1
        2*(x*z+w*y),   2*(y*z-w*x),   1-2*(x*x+y*y), 0,  # col 2
        0,             0,             0,              1,  # col 3
    )


def _mat4_mul(a: Matrix, b: Matrix) -> Matrix:
    """Column-major 4x4 matrix multiplication: result = a * b."""
    result = [0.0] * 16
    for col in range(4):
        for row in range(4):
            result[col * 4 + row] = sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
    return tuple(result)  # type: ignore


def _compose(translation: Vector, left_rotation: Rotation, scale: Vector, right_rotation: Rotation) -> Matrix:
    """Column-major matrix for T * L * S * R (matches Mojang's Transformation.compose)."""
    t: Matrix = (
        1, 0, 0, 0,  # col 0
        0, 1, 0, 0,  # col 1
        0, 0, 1, 0,  # col 2
        translation.x, translation.y, translation.z, 1,  # col 3
    )
    l = _quat_to_mat4(_rotation_to_quaternion(left_rotation))
    s: Matrix = (
        scale.x, 0, 0, 0,  # col 0
        0, scale.y, 0, 0,  # col 1
        0, 0, scale.z, 0,  # col 2
        0, 0, 0, 1,         # col 3
    )
    r = _quat_to_mat4(_rotation_to_quaternion(right_rotation))
    return _mat4_mul(_mat4_mul(_mat4_mul(t, l), s), r)


class TransformationDecomposed(BaseModel):
    right_rotation: Rotation
    left_rotation: Rotation
    translation: Vector
    scale: Vector

type TransformationType = Union[
    Matrix, 
    TransformationDecomposed
]

class Transformation(RootModel[TransformationType]):
    root: TransformationType

    def get_matrix(self) -> Matrix:
        if isinstance(self.root, tuple):
            return self.root
        d = self.root
        return _compose(d.translation, d.left_rotation, d.scale, d.right_rotation)

    def compose(self, other: "Transformation") -> "Transformation":
        """Compose transformations: self * other (self applied after other)."""
        return Transformation(root=_mat4_mul(self.get_matrix(), other.get_matrix()))

