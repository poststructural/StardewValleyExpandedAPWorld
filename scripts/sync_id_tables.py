#!/usr/bin/env python3
"""Merge the world's SVE 1.15 locations and items into the client's IdTables JSON files.

Every row of the world's data/locations.csv and data/items.csv whose id lies in the blocks recorded in
versions.lock ("id_blocks") is written into the StardewArchipelago client tables, so the client knows the ids
the generated multiworld uses. Idempotent: running it twice changes nothing. It refuses to run when a name or
a code in a block collides with a different entry already in the tables.

The client source is only touched by this script (build_mod.py calls it before the dotnet build).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from common import DEFAULT_CACHE, die, load_lock

ID_OFFSET = 717000  # world "id" column + this = the code used by the multiworld and by the client tables
GINGER_ISLAND_PACK = "Ginger Island (Vanilla)"  # content pack the world adds to every GINGER_ISLAND-tagged location
UNSUPPORTED_IMPLICIT_PACK_TAGS = ("SPECIAL_ORDER_QI", "REQUIRES_QI_ORDERS")  # the world adds the Qi board pack for these

WORLD_REL = Path("archipelago") / "worlds" / "stardew_valley"
CLIENT_REL = Path("stardew_archipelago") / "StardewArchipelago" / "IdTables"


class SyncError(Exception):
    pass


def read_block(lock: dict, key: str) -> tuple[int, int]:
    blocks = lock.get("id_blocks")
    if not blocks or key not in blocks:
        raise SyncError(f'versions.lock has no "id_blocks"."{key}"')
    first, last = blocks[key]
    if not (isinstance(first, int) and isinstance(last, int) and first <= last):
        raise SyncError(f'id_blocks.{key} must be [first, last] integers, got {blocks[key]!r}')
    return first, last


def read_rows(csv_path: Path, block: tuple[int, int], what: str) -> list[dict]:
    first, last = block
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["id"] and first <= int(row["id"]) <= last:
                rows.append(row)
    ids = [int(r["id"]) for r in rows]
    if len(set(ids)) != len(ids):
        raise SyncError(f"{what}: duplicate ids inside block {block}")
    missing = sorted(set(range(first, last + 1)) - set(ids))
    if missing:
        raise SyncError(f"{what}: block {block} is not contiguous in {csv_path.name}; missing ids {missing[:10]}")
    names = [r["name"] for r in rows]
    if len(set(names)) != len(names):
        raise SyncError(f"{what}: duplicate names inside block {block}")
    rows.sort(key=lambda r: int(r["id"]))
    return rows


def location_entry(row: dict) -> dict:
    tags = [t for t in row["tags"].split(",") if t]
    packs = {p for p in row["content_packs"].split(",") if p}
    bad = [t for t in tags if t in UNSUPPORTED_IMPLICIT_PACK_TAGS]
    if bad:
        raise SyncError(f"location '{row['name']}' uses {bad}, whose implicit content pack this script does not know")
    if "GINGER_ISLAND" in tags:
        packs.add(GINGER_ISLAND_PACK)
    return {"code": ID_OFFSET + int(row["id"]), "region": row["region"], "tags": tags, "content_packs": sorted(packs)}


def item_entry(row: dict) -> dict:
    return {"code": ID_OFFSET + int(row["id"]), "classification": row["classification"].replace(",", "|")}


def merge(table: dict, wanted: dict, what: str) -> int:
    """Merge wanted {name: entry} into table in place; return the number of entries added or changed."""
    by_code = {v["code"]: k for k, v in table.items()}
    changed = 0
    for name, entry in wanted.items():
        existing = table.get(name)
        if existing is not None and existing["code"] != entry["code"]:
            raise SyncError(f"{what} name conflict: '{name}' is {existing['code']} in the client tables but {entry['code']} in the world")
        owner = by_code.get(entry["code"])
        if owner is not None and owner != name:
            raise SyncError(f"{what} id conflict: code {entry['code']} is '{owner}' in the client tables but '{name}' in the world")
        if existing != entry:
            table[name] = entry
            changed += 1
    return changed


def newline_of(raw: bytes) -> str:
    return "\r\n" if b"\r\n" in raw else "\n"


def dump_locations(data: dict, newline: str) -> bytes:
    """Same layout as the shipped file: 4-space indent, tag and pack lists on one line."""
    lines = ["{", '    "locations": {']
    items = list(data["locations"].items())
    for i, (name, entry) in enumerate(items):
        lines.append("        " + json.dumps(name, ensure_ascii=False) + ": {")
        keys = list(entry)
        for k, key in enumerate(keys):
            comma = "," if k < len(keys) - 1 else ""
            lines.append(f'            "{key}": {json.dumps(entry[key], ensure_ascii=False)}{comma}')
        lines.append("        }" + ("," if i < len(items) - 1 else ""))
    lines += ["    }", "}"]
    return (newline.join(lines) + newline).encode("utf-8")


def dump_items(data: dict, newline: str) -> bytes:
    text = json.dumps(data, indent=4, ensure_ascii=False) + "\n"
    return text.replace("\n", newline).encode("utf-8")


def sync_file(path: Path, root_key: str, wanted: dict, dump, what: str, check_only: bool) -> int:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    changed = merge(data[root_key], wanted, what)
    if changed:
        out = dump(data, newline_of(raw))
        if not check_only:
            path.write_bytes(out)
    return changed


def sync(world_dir: Path, client_dir: Path, lock: dict, check_only: bool = False) -> dict:
    loc_block = read_block(lock, "locations")
    item_block = read_block(lock, "items")
    loc_rows = read_rows(world_dir / "data" / "locations.csv", loc_block, "locations")
    item_rows = read_rows(world_dir / "data" / "items.csv", item_block, "items")
    loc_path = client_dir / "stardew_valley_location_table.json"
    item_path = client_dir / "stardew_valley_item_table.json"
    for p in (loc_path, item_path):
        if not p.is_file():
            raise SyncError(f"missing client table {p}")
    locs = sync_file(loc_path, "locations", {r["name"]: location_entry(r) for r in loc_rows}, dump_locations, "location", check_only)
    items = sync_file(item_path, "items", {r["name"]: item_entry(r) for r in item_rows}, dump_items, "item", check_only)
    return {"locations": locs, "items": items, "location_rows": len(loc_rows), "item_rows": len(item_rows)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--world-dir", type=Path, help="default: <cache-root>/archipelago/worlds/stardew_valley")
    ap.add_argument("--client-dir", type=Path, help="default: <cache-root>/stardew_archipelago/StardewArchipelago/IdTables")
    ap.add_argument("--check", action="store_true", help="do not write; exit 1 if the client tables are out of date")
    args = ap.parse_args(argv)

    world_dir = args.world_dir or args.cache_root / WORLD_REL
    client_dir = args.client_dir or args.cache_root / CLIENT_REL
    try:
        res = sync(world_dir, client_dir, load_lock(), args.check)
    except SyncError as e:
        die(str(e))
    verb = "would update" if args.check else "updated"
    print(f"sync_id_tables: {verb} {res['locations']} of {res['location_rows']} locations and "
          f"{res['items']} of {res['item_rows']} items")
    return 1 if args.check and (res["locations"] or res["items"]) else 0


if __name__ == "__main__":
    sys.exit(main())
