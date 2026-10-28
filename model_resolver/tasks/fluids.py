"""Fluid surfaces, like FluidRenderer.tesselate: sloped tops, flowing textures, corner heights.

`tesselate_fluid` only needs to know the fluids, solidity and occlusion shapes of the blocks
around one position, through a `FluidWorld`, and returns the quads to draw in block units.
"""

from dataclasses import dataclass
import math
from typing import Literal, Optional, Protocol

from model_resolver.blocks import FULL_BLOCK, Box

Position = tuple[int, int, int]
MAX_FLUID_HEIGHT = 8 / 9


@dataclass(frozen=True)
class FluidState:
    fluid: str
    """minecraft:water or minecraft:lava"""
    amount: int
    """1 to 8, 8 for sources and falling fluids"""
    falling: bool = False

    @property
    def own_height(self) -> float:
        # FlowingFluid.getOwnHeight
        return self.amount / 9


class FluidWorld(Protocol):
    def fluid(self, pos: Position) -> Optional[FluidState]:
        """The fluid at a position, None for none."""
        ...

    def solid(self, pos: Position) -> bool:
        """BlockState.isSolid: whether a block without fluid there stops the surface from sinking."""
        ...

    def blocks_flow(self, pos: Position) -> bool:
        """In #blocks_fluid_flow: the fluid doesn't flow down past it."""
        ...

    def occlusion(self, pos: Position) -> list[Box]:
        """The block's occlusion shape in blocks (BlockState.getOcclusionShape), empty for none."""
        ...

    def overlay(self, pos: Position) -> bool:
        """Glass-like blocks and leaves: sides against them use the overlay texture."""
        ...


@dataclass
class FluidQuad:
    vertices: list[tuple[float, float, float]]
    """In block units, relative to the fluid's block."""
    uvs: list[tuple[float, float]]
    """In the texture's 0..1 space."""
    texture: Literal["still", "flow", "overlay"]
    shade: float
    """CardinalLighting brightness, the tint multiplies it."""
    back_face: bool
    """Also drawn from behind (the top and the sides seen from inside the fluid)."""


HORIZONTAL = {"north": (0, 0, -1), "south": (0, 0, 1), "west": (-1, 0, 0), "east": (1, 0, 0)}
CARDINAL = {"down": 0.5, "up": 1.0, "north": 0.8, "south": 0.8, "west": 0.6, "east": 0.6}


def offset(pos: Position, *steps: tuple[int, int, int]) -> Position:
    x, y, z = pos
    for dx, dy, dz in steps:
        x, y, z = x + dx, y + dy, z + dz
    return (x, y, z)


UP, DOWN = (0, 1, 0), (0, -1, 0)
DIRECTIONS = {**HORIZONTAL, "up": UP, "down": DOWN}
OPPOSITE = {"north": "south", "south": "north", "west": "east", "east": "west", "up": "down", "down": "up"}
EPSILON = 1e-7


def face_rectangles(shape: list[Box], direction: str) -> list[tuple[float, float, float, float]]:
    """The parts of a shape on one face of its block (Shapes.getFaceShape), as rectangles over
    the two other axes."""
    step = DIRECTIONS[direction]
    axis = next(i for i, c in enumerate(step) if c)
    u, v = (i for i in range(3) if i != axis)
    rectangles = []
    for box in shape:
        on_face = box[axis + 3] >= 1 - EPSILON if step[axis] > 0 else box[axis] <= EPSILON
        if on_face:
            rectangles.append((box[u], box[v], box[u + 3], box[v + 3]))
    return rectangles


def covered(area: tuple[float, float, float, float], rectangles: list[tuple[float, float, float, float]]) -> bool:
    """Whether the rectangles cover the area, cell by cell between their edges."""
    us = sorted({area[0], area[2], *(r[0] for r in rectangles), *(r[2] for r in rectangles)})
    vs = sorted({area[1], area[3], *(r[1] for r in rectangles), *(r[3] for r in rectangles)})
    for u0, u1 in zip(us, us[1:]):
        for v0, v1 in zip(vs, vs[1:]):
            if u1 <= area[0] or u0 >= area[2] or v1 <= area[1] or v0 >= area[3] or u1 - u0 < EPSILON or v1 - v0 < EPSILON:
                continue
            cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
            if not any(r[0] <= cu <= r[2] and r[1] <= cv <= r[3] for r in rectangles):
                return False
    return True


def occluded_by_state(direction: str, height: float, occluder: list[Box]) -> bool:
    """FluidRenderer.isFaceOccludedByState: whether a block with shape `occluder` next to the
    fluid in `direction` hides the fluid's face there, the fluid being `height` high."""
    face = face_rectangles(occluder, OPPOSITE[direction])
    if not face:
        return False
    if occluder == FULL_BLOCK:
        return direction != "up" or height >= 1
    # Shapes.blockOccludes: the fluid's box must reach that face and be covered there
    if direction == "up":
        if height < 1 - EPSILON:
            return False
        area = (0.0, 0.0, 1.0, 1.0)
    elif direction == "down":
        area = (0.0, 0.0, 1.0, 1.0)
    elif direction in ("north", "south"):
        area = (0.0, 0.0, 1.0, height)  # x, y
    else:
        area = (0.0, 0.0, height, 1.0)  # y, z
    return covered(area, face)


def occluded_by_neighbour(world: "FluidWorld", pos: Position, direction: str, height: float) -> bool:
    return occluded_by_state(direction, height, world.occlusion(offset(pos, DIRECTIONS[direction])))


def occluded_by_self(world: "FluidWorld", pos: Position, direction: str) -> bool:
    """FluidRenderer.isFaceOccludedBySelf: a waterlogged block's own shape hides the faces of
    its water where it fills that side (a bottom slab hides the water's bottom)."""
    return occluded_by_state(OPPOSITE[direction], 1.0, world.occlusion(pos))


def height(world: FluidWorld, fluid: str, pos: Position) -> float:
    """FluidRenderer.getHeight: 1 under the same fluid, the fluid's height,
    0 for a non-solid block and -1 (ignored) for a solid one."""
    state = world.fluid(pos)
    if state is not None and state.fluid == fluid:
        above = world.fluid(offset(pos, UP))
        if above is not None and above.fluid == fluid:
            return 1.0
        return state.own_height
    return -1.0 if world.solid(pos) else 0.0


def average_height(
    world: FluidWorld, fluid: str, own: float, height2: float, height1: float, corner: Position
) -> float:
    """FluidRenderer.calculateAverageHeight: heights of 0.8 and more weigh 10 times more."""
    if height1 >= 1 or height2 >= 1:
        return 1.0
    total = weight = 0.0

    def add(value: float):
        nonlocal total, weight
        if value >= 0.8:
            total, weight = total + value * 10, weight + 10
        elif value >= 0:
            total, weight = total + value, weight + 1

    if height1 > 0 or height2 > 0:
        corner_height = height(world, fluid, corner)
        if corner_height >= 1:
            return 1.0
        add(corner_height)
    add(own)
    add(height1)
    add(height2)
    return total / weight


def flow(world: FluidWorld, state: FluidState, pos: Position) -> tuple[float, float]:
    """FlowingFluid.getFlow, horizontally: towards lower neighbours, normalized."""
    flow_x = flow_z = 0.0
    for dx, _, dz in HORIZONTAL.values():
        neighbour_pos = offset(pos, (dx, 0, dz))
        neighbour = world.fluid(neighbour_pos)
        if neighbour is not None and neighbour.fluid != state.fluid:
            continue  # another fluid doesn't affect the flow
        neighbour_height = neighbour.own_height if neighbour is not None else 0.0
        distance = 0.0
        if neighbour_height == 0:
            below = world.fluid(offset(neighbour_pos, DOWN))
            # the fluid can fall into a neighbour not in #blocks_fluid_flow
            if not world.blocks_flow(neighbour_pos) and below is not None and below.fluid == state.fluid:
                distance = state.own_height - (below.own_height - MAX_FLUID_HEIGHT)
        else:
            distance = state.own_height - neighbour_height
        flow_x += dx * distance
        flow_z += dz * distance
    length = math.hypot(flow_x, flow_z)
    if length < 1e-5:
        return (0.0, 0.0)
    return (flow_x / length, flow_z / length)


def tesselate_fluid(
    world: FluidWorld, pos: Position, faces: Optional[FluidWorld] = None
) -> list[FluidQuad]:
    """The quads of the fluid at `pos`. Heights and flow are read from `world`, which faces
    are hidden from `faces` (the same world by default)."""
    faces = faces or world
    state = world.fluid(pos)
    if state is None:
        return []
    fluid = state.fluid

    def same(position: Position) -> bool:
        neighbour = faces.fluid(position)
        return neighbour is not None and neighbour.fluid == fluid

    def should_render(direction: str) -> bool:
        # FluidRenderer.shouldRenderFace
        return not same(offset(pos, DIRECTIONS[direction])) and not occluded_by_self(faces, pos, direction)

    render_up = not same(offset(pos, UP))
    render_down = should_render("down") and not occluded_by_neighbour(faces, pos, "down", MAX_FLUID_HEIGHT)
    own = height(world, fluid, pos)
    if own >= 1:
        north_east = north_west = south_east = south_west = 1.0
    else:
        heights = {name: height(world, fluid, offset(pos, step)) for name, step in HORIZONTAL.items()}

        def corner(a: str, b: str) -> float:
            return average_height(
                world, fluid, own, heights[a], heights[b], offset(pos, HORIZONTAL[a], HORIZONTAL[b])
            )

        north_east = corner("north", "east")
        north_west = corner("north", "west")
        south_east = corner("south", "east")
        south_west = corner("south", "west")

    quads: list[FluidQuad] = []
    bottom = 0.001 if render_down else 0.0
    lowest = min(north_west, south_west, south_east, north_east)
    if render_up and not occluded_by_neighbour(faces, pos, "up", lowest):
        # lowered in place, the sides below use these heights too
        north_west, south_west = north_west - 0.001, south_west - 0.001
        south_east, north_east = south_east - 0.001, north_east - 0.001
        nw, sw, se, ne = north_west, south_west, south_east, north_east
        flow_x, flow_z = flow(world, state, pos)
        if flow_x == 0 and flow_z == 0:
            texture: Literal["still", "flow"] = "still"
            uvs = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
        else:
            # the flowing texture, turned along the flow and showing its middle half
            texture = "flow"
            angle = math.atan2(flow_z, flow_x) - math.pi / 2
            s, c = math.sin(angle) * 0.25, math.cos(angle) * 0.25
            uvs = [
                (0.5 + (-c - s), 0.5 + (-c + s)),
                (0.5 + (-c + s), 0.5 + (c + s)),
                (0.5 + (c + s), 0.5 + (c - s)),
                (0.5 + (c - s), 0.5 + (-c - s)),
            ]
        vertices = [(0.0, nw, 0.0), (0.0, sw, 1.0), (1.0, se, 1.0), (1.0, ne, 0.0)]
        quads.append(FluidQuad(vertices, uvs, texture, CARDINAL["up"], True))
    if render_down:
        vertices = [(0.0, bottom, 0.0), (1.0, bottom, 0.0), (1.0, bottom, 1.0), (0.0, bottom, 1.0)]
        uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        quads.append(FluidQuad(vertices, uvs, "still", CARDINAL["down"], False))
    e = 0.001
    sides = {
        "north": (north_west, north_east, (0.0, e), (1.0, e)),
        "south": (south_east, south_west, (1.0, 1 - e), (0.0, 1 - e)),
        "west": (south_west, north_west, (e, 1.0), (e, 0.0)),
        "east": (north_east, south_east, (1 - e, 0.0), (1 - e, 1.0)),
    }
    for name, (h0, h1, (x0, z0), (x1, z1)) in sides.items():
        neighbour = offset(pos, HORIZONTAL[name])
        if not should_render(name) or occluded_by_neighbour(faces, pos, name, max(h0, h1)):
            continue
        overlay = fluid == "minecraft:water" and faces.overlay(neighbour)
        vertices = [(x0, h0, z0), (x1, h1, z1), (x1, bottom, z1), (x0, bottom, z0)]
        # the top of the flowing texture's left half, as high as the corners
        uvs = [(0.0, (1 - h0) * 0.5), (0.5, (1 - h1) * 0.5), (0.5, 0.5), (0.0, 0.5)]
        shade = CARDINAL["up"] * (CARDINAL["north"] if name in ("north", "south") else CARDINAL["west"])
        quads.append(FluidQuad(vertices, uvs, "overlay" if overlay else "flow", shade, not overlay))
    return quads
