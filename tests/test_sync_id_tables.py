"""Tests for scripts/sync_id_tables.py. Standard library + pytest only."""
import json
import shutil

import pytest

import common
import sync_id_tables as sync

LOC_CSV = (
    "id,region,name,tags,content_packs\n"
    "1,Farm,Old Location,BUNDLE,\n"
    '90001,Farm,New One,"FISHSANITY,GINGER_ISLAND",Stardew Valley Expanded\n'
    "90002,Shipping,New Two,SHIPSANITY,Stardew Valley Expanded\n"
)
ITEM_CSV = (
    "id,name,classification,groups,content_packs\n"
    "1,Old Item,filler,FILLER,\n"
    '90001,New Item,progression,"CROPSANITY",Stardew Valley Expanded\n'
)
LOCK = {"id_blocks": {"locations": [90001, 90002], "items": [90001, 90001]}}


def write_location_table(path, entries, newline="\r\n"):
    data = {"locations": entries}
    path.write_bytes(sync.dump_locations(data, newline))


def write_item_table(path, entries, newline="\r\n"):
    path.write_bytes(sync.dump_items({"items": entries}, newline))


@pytest.fixture
def env(tmp_path):
    world = tmp_path / "world"
    (world / "data").mkdir(parents=True)
    (world / "data" / "locations.csv").write_text(LOC_CSV, encoding="utf-8", newline="")
    (world / "data" / "items.csv").write_text(ITEM_CSV, encoding="utf-8", newline="")
    client = tmp_path / "client"
    client.mkdir()
    write_location_table(client / "stardew_valley_location_table.json",
                         {"Old Location": {"code": 717001, "region": "Farm", "tags": ["BUNDLE"], "content_packs": []}})
    write_item_table(client / "stardew_valley_item_table.json", {"Old Item": {"code": 717001, "classification": "filler"}})
    return world, client


def test_adds_entries_in_client_shape(env):
    world, client = env
    res = sync.sync(world, client, LOCK)
    assert res["locations"] == 2 and res["items"] == 1
    locs = json.loads((client / "stardew_valley_location_table.json").read_text())["locations"]
    assert locs["New One"] == {"code": 807001, "region": "Farm", "tags": ["FISHSANITY", "GINGER_ISLAND"],
                               "content_packs": ["Ginger Island (Vanilla)", "Stardew Valley Expanded"]}
    assert locs["New Two"]["content_packs"] == ["Stardew Valley Expanded"]
    assert list(locs)[0] == "Old Location"
    items = json.loads((client / "stardew_valley_item_table.json").read_text())["items"]
    assert items["New Item"] == {"code": 807001, "classification": "progression"}


def test_idempotent_and_byte_stable(env):
    world, client = env
    sync.sync(world, client, LOCK)
    first = {p.name: p.read_bytes() for p in client.iterdir()}
    res = sync.sync(world, client, LOCK)
    assert res["locations"] == 0 and res["items"] == 0
    assert {p.name: p.read_bytes() for p in client.iterdir()} == first
    assert b"\r\n" in first["stardew_valley_location_table.json"]


def test_check_only_does_not_write(env, monkeypatch):
    world, client = env
    monkeypatch.setattr(sync, "load_lock", lambda: LOCK)
    before = {p.name: p.read_bytes() for p in client.iterdir()}
    assert sync.sync(world, client, LOCK, check_only=True)["locations"] == 2
    assert {p.name: p.read_bytes() for p in client.iterdir()} == before
    assert sync.main(["--world-dir", str(world), "--client-dir", str(client), "--check"]) == 1


def test_keeps_lf_newlines(env):
    world, client = env
    write_location_table(client / "stardew_valley_location_table.json", {}, newline="\n")
    write_item_table(client / "stardew_valley_item_table.json", {}, newline="\n")
    sync.sync(world, client, LOCK)
    assert b"\r" not in (client / "stardew_valley_location_table.json").read_bytes()
    assert b"\r" not in (client / "stardew_valley_item_table.json").read_bytes()


def test_name_conflict_fails(env):
    world, client = env
    write_location_table(client / "stardew_valley_location_table.json",
                         {"New One": {"code": 717555, "region": "Farm", "tags": [], "content_packs": []}})
    with pytest.raises(sync.SyncError, match="name conflict"):
        sync.sync(world, client, LOCK)


def test_id_conflict_fails(env):
    world, client = env
    write_item_table(client / "stardew_valley_item_table.json", {"Other Item": {"code": 807001, "classification": "filler"}})
    with pytest.raises(sync.SyncError, match="id conflict"):
        sync.sync(world, client, LOCK)


def test_block_must_be_contiguous_and_present(env):
    world, client = env
    with pytest.raises(sync.SyncError, match="not contiguous"):
        sync.sync(world, client, {"id_blocks": {"locations": [90001, 90003], "items": [90001, 90001]}})
    with pytest.raises(sync.SyncError, match="id_blocks"):
        sync.sync(world, client, {})


def test_duplicate_names_in_block_fail(env):
    world, client = env
    (world / "data" / "locations.csv").write_text(LOC_CSV + "90003,Farm,New One,SHIPSANITY,\n", encoding="utf-8", newline="")
    with pytest.raises(sync.SyncError, match="duplicate names"):
        sync.sync(world, client, {"id_blocks": {"locations": [90001, 90003], "items": [90001, 90001]}})


def test_real_tables_round_trip_byte_identical_when_nothing_to_add():
    """The serializers must reproduce the shipped client files exactly, otherwise a sync would produce noisy diffs."""
    client = common.DEFAULT_CACHE / sync.CLIENT_REL
    loc = client / "stardew_valley_location_table.json"
    item = client / "stardew_valley_item_table.json"
    if not (loc.is_file() and item.is_file()):
        pytest.skip("client source not fetched")
    for path, key, dump in ((loc, "locations", sync.dump_locations), (item, "items", sync.dump_items)):
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8-sig"))
        assert dump(data, sync.newline_of(raw)) == raw, path.name


def test_real_world_block_syncs_into_a_copy_of_the_client_tables(tmp_path):
    world = common.DEFAULT_CACHE / sync.WORLD_REL
    client = common.DEFAULT_CACHE / sync.CLIENT_REL
    lock = common.load_lock()
    if not ((world / "data" / "locations.csv").is_file() and client.is_dir()) or "id_blocks" not in lock:
        pytest.skip("cache not fetched")
    copy = tmp_path / "IdTables"
    shutil.copytree(client, copy)
    sync.sync(world, copy, lock)
    again = sync.sync(world, copy, lock)
    assert again["locations"] == 0 and again["items"] == 0
    first, last = lock["id_blocks"]["locations"]
    locs = json.loads((copy / "stardew_valley_location_table.json").read_text(encoding="utf-8"))["locations"]
    assert sum(1 for v in locs.values() if 717000 + first <= v["code"] <= 717000 + last) == last - first + 1
