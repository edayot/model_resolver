import os
from pathlib import Path

import pytest
from beet import DataPack, ResourcePack, run_beet
from pytest_insta import SnapshotFixture
from pytest_insta.fixture import SnapshotRecorder

from model_resolver.tasks.model import TextureWebP
from render_compare import pack_differences

SNAPSHOTS = Path(__file__).parent / "snapshots"
EXAMPLES = [f for f in os.listdir("examples") if not f.startswith("nosnap_")]


def assert_matches(
    snapshot: SnapshotFixture, directory: str, name: str, pack: DataPack | ResourcePack
):
    expected = snapshot(name)
    if not isinstance(expected, SnapshotRecorder) and isinstance(
        expected, (DataPack, ResourcePack)
    ):
        stored = SNAPSHOTS / f"example__build_{directory}__1.resource_pack"
        if isinstance(expected, ResourcePack) and stored.is_dir():
            # animated renders are .webp, a file type only model_resolver registers
            reloaded = ResourcePack()
            reloaded.extend_namespace.append(TextureWebP)
            reloaded.load(stored)
            expected = reloaded
        # renders differ slightly between GPUs and drivers, see render_compare.py
        assert pack_differences(expected, pack) == []
    else:
        # recording (--insta update, or a new snapshot): a proxy that stores what it's compared with
        assert expected == pack


@pytest.mark.parametrize("directory", EXAMPLES)
def test_build(snapshot: SnapshotFixture, directory: str):
    with run_beet(directory=f"examples/{directory}") as ctx:
        if os.environ.get("MODEL_RESOLVER_TEST_BUILD"):
            return
        assert_matches(snapshot, directory, "data_pack", ctx.data)
        assert_matches(snapshot, directory, "resource_pack", ctx.assets)
