import gzip
import os
from pathlib import Path

import pytest
from beet import DataPack, JsonFileBase, PngFile, ResourcePack, Structure, run_beet
from pytest_insta import SnapshotFixture
from pytest_insta.fixture import SnapshotRecorder

from model_resolver.tasks.model import TextureWebP
from render_compare import pack_differences

SNAPSHOTS = Path(__file__).parent / "snapshots"
EXAMPLES = [f for f in os.listdir("examples") if not f.startswith("nosnap_")]


def normalize(pack: DataPack | ResourcePack):
    """Re-encode the files the way beet writes them. A file nothing read is copied as is, and
    the snapshot comparison reads files in an order that changes between runs, so without this
    a recorded png (or json, nbt) flips between its source bytes and beet's encoding."""
    for _, file in pack.list_files():
        if isinstance(file, (PngFile, JsonFileBase, Structure)):
            file.ensure_deserialized()
            raw = file.ensure_serialized()
            if isinstance(file, Structure) and isinstance(raw, bytes):
                # gzip headers hold the time they were written
                file.set_content(gzip.compress(gzip.decompress(raw), mtime=0))


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
        normalize(pack)
        assert expected == pack


@pytest.mark.parametrize("directory", EXAMPLES)
def test_build(snapshot: SnapshotFixture, directory: str):
    with run_beet(directory=f"examples/{directory}") as ctx:
        if os.environ.get("MODEL_RESOLVER_TEST_BUILD"):
            return
        assert_matches(snapshot, directory, "data_pack", ctx.data)
        assert_matches(snapshot, directory, "resource_pack", ctx.assets)
