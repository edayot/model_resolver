"""Facts about block states that only the game's code knows, from data/blocks.json
(see scripts/generate_block_table.py): solidity, the fluid a state holds, its occlusion shape.
"""

from dataclasses import dataclass
from functools import cache
import json
from pathlib import Path
from typing import Any, Optional

from beet import LATEST_MINECRAFT_VERSION

from model_resolver.utils import resolve_key

Box = tuple[float, float, float, float, float, float]
"""min x, y, z and max x, y, z in blocks"""

FULL_BLOCK: list[Box] = [(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)]


@cache
def block_table(version: str) -> dict[str, Any]:
    tables = json.loads((Path(__file__).parent / "data" / "blocks.json").read_text())
    if version == "latest":
        version = LATEST_MINECRAFT_VERSION
    if version in tables:
        return tables[version]
    return tables[max(tables, key=lambda v: tuple(map(int, v.split("."))))]


@dataclass(frozen=True)
class BlockInfo:
    known: bool
    """False for blocks the table doesn't have (other namespaces): the other fields are guesses."""
    solid: bool
    """BlockState.isSolid"""
    fluid: Optional[tuple[str, int, bool]]
    """(fluid, amount, falling) of BlockState.getFluidState, None when empty"""
    occlusion: list[Box]
    """The occlusion shape (empty for blocks that can't occlude, like glass and leaves)"""
    blocks_fluid_flow: bool
    """In #blocks_fluid_flow: fluids don't flow down past it"""


def derived_fluid(name: str, properties: dict[str, str]) -> Optional[tuple[str, int, bool]]:
    """LiquidBlock.getFluidState for water and lava, and a source for waterlogged blocks."""
    if name in ("minecraft:water", "minecraft:lava"):
        level = int(properties.get("level", 0))
        return (name, 8, True) if level >= 8 else (name, 8 - level, False)
    if properties.get("waterlogged") == "true":
        return ("minecraft:water", 8, False)
    return None


def _value(entry: dict[str, Any], key: str, properties: dict[str, str], default: Any) -> Any:
    value = entry.get(key, default)
    if not isinstance(value, dict):
        return value
    # one value per state, in the mixed radix order of the listed properties
    index = 0
    for name, values in entry["properties"].items():
        current = properties.get(name, values[0])
        index = index * len(values) + (values.index(current) if current in values else 0)
    return value["by_state"][index]


def block_info(version: str, name: str, properties: dict[str, str]) -> BlockInfo:
    name = resolve_key(name)
    table = block_table(version)
    entry = table["blocks"].get(name)
    if entry is None:
        return BlockInfo(
            known=False,
            solid=not name.endswith("air"),
            fluid=derived_fluid(name, properties),
            occlusion=[],
            blocks_fluid_flow=not name.endswith("air"),
        )
    fluid = _value(entry, "fluid", properties, None)
    if fluid is None:
        fluid = derived_fluid(name, properties)
    elif fluid == "none":
        fluid = None
    else:
        fluid = tuple(fluid)
    shape = table["shapes"][_value(entry, "occlusion", properties, 0)]
    return BlockInfo(
        known=True,
        solid=_value(entry, "solid", properties, False),
        fluid=fluid,  # type: ignore
        occlusion=[tuple(box) for box in shape],  # type: ignore
        blocks_fluid_flow=name in _flow_blockers(version),
    )


@cache
def _flow_blockers(version: str) -> frozenset[str]:
    return frozenset(block_table(version)["blocks_fluid_flow"])
