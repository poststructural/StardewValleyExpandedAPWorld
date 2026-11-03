"""Every item/NPC name behind a location this project adds must exist in SVE 1.15 (or be a known client alias).

Skipped when the SVE content pack source is not on disk. Point SVE_CP_DIR at the "code" folder of
"[CP] Stardew Valley Expanded" to run it; the default is the SVE_Mod folder next to this repo.
Standard library + pytest (json5 is used when installed, else the tolerant parser in scripts/common.py).
"""
import os
import re
from pathlib import Path

import pytest

import common
import sync_id_tables as sync

DEFAULT_SVE_CP_DIR = common.ROOT.parent / "SVE_Mod" / "Stardew Valley Expanded" / "[CP] Stardew Valley Expanded" / "code"

# Used when the client source is not fetched; kept in step with SVENameMapper.cs / NameAliases.cs.
FALLBACK_ITEM_ALIASES = {"Bearberrys": "Bearberry", "Big Conch": "Conch", "Dried Sand Dollar": "Sand Dollar",
                         "Lucky Four Leaf Clover": "Four Leaf Clover", "Smelly Rafflesia": "Rafflesia",
                         "Ancient Ferns Seed": "Ancient Fern Seed"}
FALLBACK_NPC_ALIASES = {"SVE_Henchman": "Henchman"}

PREFIXES = ("Fishsanity: ", "Shipsanity: ", "Museumsanity: ", "Harvest ", "Cook ", "Craft ", "Eat ", "Drink ")


def sve_dir():
    path = Path(os.environ.get("SVE_CP_DIR") or DEFAULT_SVE_CP_DIR)
    if not (path / "Items" / "Objects.json").is_file():
        pytest.skip(f"SVE 1.15 content pack not found at {path} (set SVE_CP_DIR)")
    return path


def load_json(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    try:
        import json5
        return json5.loads(text)
    except ImportError:
        return common.loads_lenient(text)


def walk(node, names: set, keys: set):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "Name" and isinstance(v, str):
                names.add(v)
            if k == "Entries" and isinstance(v, dict):
                keys.update(v)
            walk(v, names, keys)
    elif isinstance(node, list):
        for v in node:
            walk(v, names, keys)


def collect_item_names(root: Path) -> set:
    names, keys = set(), set()
    for folder in ("Items", "Other", "Trees"):
        for f in sorted((root / folder).glob("*.json")):
            try:
                walk(load_json(f), names, keys)
            except ValueError:
                continue  # an unparsable unrelated file must not hide the rest
    # Entry keys are ids ("FlashShifter..._Foo") or recipe names ("Fish Dumpling"); accept both forms.
    out = set(names)
    for k in keys:
        out.add(k)
        out.add(k.split("_", 1)[-1].replace("_", " "))
        out.add(k.rsplit(".", 1)[-1])
    return out


def collect_npc_keys(root: Path) -> set:
    names, keys = set(), set()
    for f in sorted((root / "NPCs").glob("*.json")):
        try:
            walk(load_json(f), names, keys)
        except ValueError:
            continue
    return keys


def client_aliases():
    client = common.DEFAULT_CACHE / "stardew_archipelago" / "StardewArchipelago"
    items, npcs = dict(FALLBACK_ITEM_ALIASES), dict(FALLBACK_NPC_ALIASES)
    mapper = client / "Stardew" / "NameMapping" / "SVENameMapper.cs"
    if mapper.is_file():
        items = dict(re.findall(r'\{\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\}', mapper.read_text(encoding="utf-8-sig").split("EnglishToSVE")[0]))
    aliases = client / "Constants" / "Vanilla" / "NameAliases.cs"
    if aliases.is_file():
        text = aliases.read_text(encoding="utf-8-sig")
        block = text.split("NPCNameAliases", 1)[-1].split("};", 1)[0]
        npcs.update(dict(re.findall(r'\{\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\}', block)))
    return items, npcs


def new_location_names():
    world = common.DEFAULT_CACHE / sync.WORLD_REL
    csv_path = world / "data" / "locations.csv"
    lock = common.load_lock()
    if not csv_path.is_file() or "id_blocks" not in lock:
        pytest.skip("world not fetched or no id_blocks in versions.lock")
    rows = sync.read_rows(csv_path, sync.read_block(lock, "locations"), "locations")
    return [r["name"] for r in rows]


def target_of(location_name: str):
    """Return ('npc'|'item', name) for the thing a location is about."""
    m = re.fullmatch(r"Friendsanity: (.+) \d+ <3", location_name)
    if m:
        return "npc", m.group(1)
    for prefix in PREFIXES:
        if location_name.startswith(prefix):
            return "item", location_name[len(prefix):]
    if location_name.endswith(" Recipe"):
        return "item", location_name[:-len(" Recipe")]
    raise AssertionError(f"unrecognised location name shape: {location_name}")


def test_new_locations_resolve_to_sve_objects_or_npcs():
    root = sve_dir()
    names = new_location_names()
    item_aliases, npc_aliases = client_aliases()
    sve_items = collect_item_names(root)
    sve_npcs = collect_npc_keys(root)
    # The client turns the SVE internal name into the English one, so an alias value is what the world uses.
    sve_items |= set(item_aliases.values())
    resolvable_npcs = sve_npcs | set(npc_aliases.values())
    assert len(sve_items) > 500, "SVE data barely parsed; install json5 or check SVE_CP_DIR"
    assert "Scarlett" in resolvable_npcs

    unresolved = []
    for location in names:
        kind, name = target_of(location)
        pool = resolvable_npcs if kind == "npc" else sve_items
        if name not in pool:
            unresolved.append(location)
    assert unresolved == [], f"{len(unresolved)} locations point at names missing from SVE 1.15: {unresolved[:20]}"
