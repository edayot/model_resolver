"""Fluid surfaces, checked against FluidRenderer.tesselate and FlowingFluid.getFlow (26.3)."""

from dataclasses import dataclass, field

import pytest

from model_resolver.tasks.fluids import FluidState, Position, tesselate_fluid

WATER = "minecraft:water"
SOURCE = FluidState(WATER, 8)


@dataclass
class World:
    fluids: dict[Position, FluidState] = field(default_factory=dict)
    blocks: set[Position] = field(default_factory=set)
    """full opaque cubes"""
    glass: set[Position] = field(default_factory=set)
    shapes: dict[Position, list] = field(default_factory=dict)
    """other occlusion shapes, in blocks"""

    def fluid(self, pos):
        return self.fluids.get(pos)

    def solid(self, pos):
        return pos in self.blocks or pos in self.glass or pos in self.shapes

    def blocks_flow(self, pos):
        return self.solid(pos)

    def occlusion(self, pos):
        if pos in self.blocks:
            return [(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)]
        return self.shapes.get(pos, [])

    def overlay(self, pos):
        return pos in self.glass


def top(quads):
    (quad,) = [q for q in quads if q.shade == 1.0]
    return quad


def corners(quad):
    """{(x, z): height} of a top quad, without the 0.001 FluidRenderer takes off."""
    return {(x, z): round(y + 0.001, 6) for x, y, z in quad.vertices}


def pool(size=3, state=SOURCE):
    return World({(x, 0, z): state for x in range(size) for z in range(size)})


class TestHeights:
    def test_inside_a_pool_the_surface_is_flat(self):
        quads = tesselate_fluid(pool(), (1, 0, 1))
        assert list(corners(top(quads)).values()) == pytest.approx([8 / 9] * 4)

    def test_corners_sink_towards_open_neighbours(self):
        quads = tesselate_fluid(World({(0, 0, 0): SOURCE}), (0, 0, 0))
        # calculateAverageHeight: own height (weight 10) and two empty neighbours (weight 1)
        expected = (8 / 9 * 10) / 12
        assert list(corners(top(quads)).values()) == pytest.approx([expected] * 4)

    def test_solid_neighbours_are_ignored(self):
        world = World({(0, 0, 0): SOURCE})
        world.blocks |= {(1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)}
        world.blocks |= {(x, 0, z) for x in (-1, 1) for z in (-1, 1)}
        quads = tesselate_fluid(world, (0, 0, 0))
        assert list(corners(top(quads)).values()) == pytest.approx([8 / 9] * 4)

    def test_water_under_water_is_full_and_has_no_top(self):
        world = World({(0, 0, 0): SOURCE, (0, 1, 0): SOURCE})
        quads = tesselate_fluid(world, (0, 0, 0))
        assert all(quad.shade != 1.0 for quad in quads)
        side_heights = {round(y, 6) for q in quads for _, y, _ in q.vertices}
        assert max(side_heights) == pytest.approx(1)

    def test_a_full_neighbour_lifts_the_shared_corners(self):
        world = pool(1)
        world.fluids[(1, 0, 0)] = SOURCE
        world.fluids[(1, 1, 0)] = SOURCE  # height 1
        heights = corners(top(tesselate_fluid(world, (0, 0, 0))))
        assert heights[(1.0, 0.0)] == heights[(1.0, 1.0)] == 1
        assert heights[(0.0, 0.0)] < 1


class TestFlow:
    def test_still_water_uses_the_still_texture(self):
        assert top(tesselate_fluid(pool(), (1, 0, 1))).texture == "still"

    def test_flowing_water_turns_the_flowing_texture_along_the_flow(self):
        # a level 2 block (amount 6) east of a source flows east
        world = World({(0, 0, 0): SOURCE, (1, 0, 0): FluidState(WATER, 6)})
        quad = top(tesselate_fluid(world, (1, 0, 0)))
        assert quad.texture == "flow"
        # angle = atan2(0, 1) - pi / 2: s = -0.25, c = 0
        assert quad.uvs[0] == pytest.approx((0.75, 0.25))

    def test_water_flows_towards_a_drop(self):
        # FlowingFluid.getFlow: an open neighbour with water below it pulls the flow
        world = World({(0, 0, 0): SOURCE, (1, -1, 0): SOURCE})
        world.blocks.add((0, -1, 0))
        assert top(tesselate_fluid(world, (0, 0, 0))).texture == "flow"


class TestFaces:
    def test_faces_against_full_blocks_are_hidden(self):
        world = World({(0, 0, 0): SOURCE}, blocks={(0, -1, 0), (1, 0, 0)})
        quads = tesselate_fluid(world, (0, 0, 0))
        assert len([q for q in quads if q.shade == 0.5]) == 0  # no bottom
        assert len([q for q in quads if q.shade == 0.6]) == 1  # west only

    def test_sides_against_glass_use_the_overlay(self):
        world = World({(0, 0, 0): SOURCE}, glass={(1, 0, 0)})
        textures = {q.texture for q in tesselate_fluid(world, (0, 0, 0))}
        assert "overlay" in textures

    def test_lava_has_no_overlay(self):
        lava = FluidState("minecraft:lava", 8)
        world = World({(0, 0, 0): lava}, glass={(1, 0, 0)})
        textures = {q.texture for q in tesselate_fluid(world, (0, 0, 0))}
        assert "overlay" not in textures

    def test_faces_can_come_from_another_world(self):
        # heights from an extended world, faces from the real one (structure edges)
        quads = tesselate_fluid(pool(3), (0, 0, 0), World({(0, 0, 0): SOURCE}))
        sides = [q for q in quads if q.shade in (0.6, 0.8)]
        assert len(sides) == 4


BOTTOM_SLAB = [(0.0, 0.0, 0.0, 1.0, 0.5, 1.0)]
TOP_SLAB = [(0.0, 0.5, 0.0, 1.0, 1.0, 1.0)]


class TestOcclusionShapes:
    # FluidRenderer.isFaceOccludedByState with Shapes.blockOccludes
    def faces(self, quads):
        names = {1.0: "up", 0.5: "down", 0.8: "north/south", 0.6: "west/east"}
        return sorted(names[q.shade] for q in quads)

    def test_a_waterlogged_bottom_slab_hides_its_water_bottom(self):
        world = World({(0, 0, 0): SOURCE}, shapes={(0, 0, 0): BOTTOM_SLAB})
        assert "down" not in self.faces(tesselate_fluid(world, (0, 0, 0)))

    def test_a_waterlogged_top_slab_keeps_every_face(self):
        # its shape doesn't reach the bottom, and only partly covers the sides
        world = World({(0, 0, 0): SOURCE}, shapes={(0, 0, 0): TOP_SLAB})
        assert self.faces(tesselate_fluid(world, (0, 0, 0))) == sorted(
            ["up", "down", *["north/south"] * 2, *["west/east"] * 2]
        )

    def test_a_slab_neighbour_doesnt_hide_a_taller_side(self):
        world = World({(0, 0, 0): SOURCE}, shapes={(1, 0, 0): BOTTOM_SLAB})
        assert self.faces(tesselate_fluid(world, (0, 0, 0))).count("west/east") == 2

    def test_a_bottom_slab_below_hides_the_bottom(self):
        world = World({(0, 0, 0): SOURCE}, shapes={(0, -1, 0): TOP_SLAB})
        assert "down" not in self.faces(tesselate_fluid(world, (0, 0, 0)))

    def test_a_full_block_above_only_hides_a_full_top(self):
        world = World({(0, 0, 0): SOURCE}, blocks={(0, 1, 0)})
        assert "up" in self.faces(tesselate_fluid(world, (0, 0, 0)))
        world.fluids[(1, 1, 0)] = SOURCE
        world.fluids[(1, 0, 0)] = SOURCE  # its corners reach 1, not the whole top
        assert "up" in self.faces(tesselate_fluid(world, (0, 0, 0)))


def test_water_flows_past_blocks_not_in_the_flow_tag():
    # an open neighbour drains towards the water below it, a #blocks_fluid_flow one doesn't
    world = World({(0, 0, 0): SOURCE, (1, -1, 0): SOURCE}, shapes={(1, 0, 0): []})
    world.blocks.add((0, -1, 0))
    world.shapes.pop((1, 0, 0))
    assert top(tesselate_fluid(world, (0, 0, 0))).texture == "flow"
    world.shapes[(1, 0, 0)] = BOTTOM_SLAB
    assert top(tesselate_fluid(world, (0, 0, 0))).texture == "still"
