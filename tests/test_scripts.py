"""Unit tests for the pure parts of the build scripts. Standard library + pytest only."""
import json
import struct
import zipfile

import pytest

import build_world
import common
import package_release

LOCK = {
    "apworld_container": {"compatible_version": 7, "version": 7},
    "upstream": {"archipelago": {"tag": "0.6.8"}},
    "artifacts": {"apworld": "stardew_valley.apworld", "mod_dir": "StardewArchipelago"},
}


def make_pe(path, managed: bool, pe32plus: bool = False):
    """Write a minimal PE image; managed sets the CLR data directory (index 14)."""
    opt_size = 240 if pe32plus else 224
    dd_off = 112 if pe32plus else 96
    opt = bytearray(opt_size)
    struct.pack_into("<H", opt, 0, 0x20B if pe32plus else 0x10B)
    struct.pack_into("<I", opt, dd_off - 4, 16)
    if managed:
        struct.pack_into("<II", opt, dd_off + 14 * 8, 0x2000, 0x48)
    dos = bytearray(0x40)
    dos[:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, 0x40)
    path.write_bytes(bytes(dos) + b"PE\0\0" + bytes(20) + bytes(opt))


def test_lenient_json_bom_comments_trailing_commas():
    text = '﻿{\n // c\n "Version": "8.1.12", /* x */ "a": "http://x,}", "l": [1, 2,],\n}\n'
    d = common.loads_lenient(text)
    assert d == {"Version": "8.1.12", "a": "http://x,}", "l": [1, 2]}


def test_get_ci():
    assert common.get_ci({"version": "1"}, "Version") == "1"
    assert common.get_ci({}, "Version", "d") == "d"


def test_write_json_no_bom(tmp_path):
    p = tmp_path / "a.json"
    common.write_json(p, {"k": "é"})
    raw = p.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert json.loads(raw.decode("utf-8")) == {"k": "é"}


def test_inject_manifest_adds_missing_and_keeps_existing():
    m = build_world.inject_manifest({"game": "Stardew Valley", "world_version": "7.4.25"}, LOCK, "8.1.12")
    assert m["compatible_version"] == 7 and m["version"] == 7 and m["maximum_ap_version"] == "0.6.8"
    assert m["world_version"] == "8.1.12"
    assert list(m)[-1] == "world_version"
    kept = build_world.inject_manifest({"compatible_version": 9, "version": 3, "maximum_ap_version": "1"}, LOCK, None)
    assert (kept["compatible_version"], kept["version"], kept["maximum_ap_version"]) == (9, 3, "1")
    assert "world_version" not in kept


def test_pair_version_from_mod_manifest_with_bom_and_trailing_comma(tmp_path):
    mdir = tmp_path / "stardew_archipelago" / "StardewArchipelago"
    mdir.mkdir(parents=True)
    (mdir / "manifest.json").write_bytes('﻿{"Version": "8.1.12",}'.encode("utf-8"))
    assert build_world.read_pair_version(tmp_path, LOCK) == "8.1.12"
    assert build_world.read_pair_version(tmp_path / "none", {"pairing": {"mod_version": "1.0"}}) == "1.0"
    assert build_world.read_pair_version(tmp_path / "none", LOCK) is None


def test_build_world_end_to_end(tmp_path):
    cache = tmp_path / "cache"
    w = cache / "archipelago" / "worlds" / "stardew_valley"
    (w / "sub" / "__pycache__").mkdir(parents=True)
    (w / "__pycache__").mkdir()
    (w / "__init__.py").write_text("x")
    (w / "sub" / "a.py").write_text("y")
    (w / "sub" / "__pycache__" / "a.pyc").write_text("z")
    (w / "__pycache__" / "b.pyc").write_text("z")
    (w / "archipelago.json").write_text('{"game": "Stardew Valley", "world_version": "7.4.25"}')
    mod = cache / "stardew_archipelago" / "StardewArchipelago"
    mod.mkdir(parents=True)
    (mod / "manifest.json").write_text('{"Version": "8.1.12"}')
    out = build_world.build(cache, tmp_path / "artifacts", LOCK)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert all(n.startswith("stardew_valley/") for n in names)
        assert not any("\\" in n or "__pycache__" in n for n in names)
        assert {"stardew_valley/__init__.py", "stardew_valley/sub/a.py", "stardew_valley/archipelago.json"} <= set(names)
        raw = zf.read("stardew_valley/archipelago.json")
    assert not raw.startswith(b"\xef\xbb\xbf")
    m = json.loads(raw)
    assert (m["compatible_version"], m["version"], m["world_version"]) == (7, 7, "8.1.12")
    assert not (tmp_path / "artifacts" / "_stage").exists()


def test_is_managed_pe(tmp_path):
    for plus in (False, True):
        make_pe(tmp_path / "m.dll", True, plus)
        make_pe(tmp_path / "n.dll", False, plus)
        assert package_release.is_managed_pe(tmp_path / "m.dll")
        assert not package_release.is_managed_pe(tmp_path / "n.dll")
    (tmp_path / "elf.dll").write_bytes(b"\x7fELF" + bytes(100))
    assert not package_release.is_managed_pe(tmp_path / "elf.dll")


def test_scan_native(tmp_path):
    make_pe(tmp_path / "ok.dll", True)
    make_pe(tmp_path / "native.dll", False)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "x.so").write_bytes(b"1")
    (tmp_path / "y.dylib").write_bytes(b"1")
    (tmp_path / "z.exe").write_bytes(b"1")
    (tmp_path / "data.json").write_text("{}")
    found = {rel for rel, _ in package_release.scan_native(tmp_path)}
    assert found == {"native.dll", "lib/x.so", "y.dylib", "z.exe"}


def test_mod_zip_layout_with_cp(tmp_path):
    mod = tmp_path / "StardewArchipelago"
    (mod / "IdTables").mkdir(parents=True)
    (mod / "StardewArchipelago.dll").write_bytes(b"1")
    (mod / "IdTables" / "t.json").write_text("{}")
    cp = tmp_path / "cp"
    (cp / "[CP] Patch").mkdir(parents=True)
    (cp / "[CP] Patch" / "content.json").write_text("{}")
    (cp / "README.txt").write_text("not a folder")
    mods = package_release.collect_mod_dirs(mod, "StardewArchipelago", cp)
    assert [n for _, n in mods] == ["StardewArchipelago", "[CP] Patch"]
    z = tmp_path / "r.zip"
    package_release.write_mod_zip(mods, z)
    with zipfile.ZipFile(z) as zf:
        assert set(zf.namelist()) == {
            "Mods/StardewArchipelago/StardewArchipelago.dll",
            "Mods/StardewArchipelago/IdTables/t.json",
            "Mods/[CP] Patch/content.json",
        }
    assert [n for _, n in package_release.collect_mod_dirs(mod, "StardewArchipelago", tmp_path / "nocp")] == ["StardewArchipelago"]
