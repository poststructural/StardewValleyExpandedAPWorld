#!/usr/bin/env python3
"""Build artifacts/release/: the apworld, one cross-platform mod zip, and SHA256SUMS.txt."""
import argparse
import hashlib
import shutil
import struct
import zipfile
from pathlib import Path

from common import ROOT, die, load_lock

NATIVE_EXTS = {".so", ".dylib", ".exe"}


def is_managed_pe(path: Path) -> bool:
    """True if path is a PE file with a CLR (.NET) header; False for native or non-PE files."""
    try:
        with open(path, "rb") as f:
            data = f.read(4096)
            if data[:2] != b"MZ" or len(data) < 0x40:
                return False
            pe = struct.unpack_from("<I", data, 0x3C)[0]
            if pe + 24 > len(data):
                f.seek(pe)
                data = f.read(512)
                pe = 0
            if data[pe:pe + 4] != b"PE\0\0":
                return False
            opt = pe + 24
            magic = struct.unpack_from("<H", data, opt)[0]
            if magic == 0x10B:
                dd = opt + 96
            elif magic == 0x20B:
                dd = opt + 112
            else:
                return False
            count = struct.unpack_from("<I", data, dd - 4)[0]
            if count <= 14:
                return False
            rva, size = struct.unpack_from("<II", data, dd + 14 * 8)
            return rva != 0 and size != 0
    except (OSError, struct.error):
        return False


def scan_native(root: Path) -> list:
    """Return [(relative path, reason)] for non-managed binaries under root."""
    found = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        rel = p.relative_to(root).as_posix()
        if ext in NATIVE_EXTS:
            found.append((rel, f"{ext} binary"))
        elif ext == ".dll" and not is_managed_pe(p):
            found.append((rel, "native (no CLR header) dll"))
    return found


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_mod_dirs(mod_dir: Path, mod_name: str, cp_dir: Path) -> list:
    """[(source dir, name under Mods/)]: the built mod plus every subfolder of cp/ if it exists."""
    mods = [(mod_dir, mod_name)]
    if cp_dir.is_dir():
        mods += [(d, d.name) for d in sorted(cp_dir.iterdir()) if d.is_dir()]
    return mods


def write_mod_zip(mods: list, out_zip: Path) -> None:
    """Zip each (dir, name) under Mods/<name>/ with forward-slash paths."""
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, name in mods:
            for p in sorted(src.rglob("*"), key=lambda q: q.relative_to(src).as_posix()):
                if p.is_file() and "__pycache__" not in p.parts:
                    zf.write(p, f"Mods/{name}/{p.relative_to(src).as_posix()}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifacts", type=Path, default=ROOT / "artifacts")
    ap.add_argument("--cp-dir", type=Path, default=ROOT / "cp")
    ap.add_argument("--allow-native", action="store_true", help="do not fail on non-managed binaries")
    args = ap.parse_args()

    lock = load_lock()
    version = (lock.get("release") or {}).get("version")
    if not version:
        die('versions.lock has no "release": {"version": ...}')
    apworld = args.artifacts / lock["artifacts"]["apworld"]
    mod_dir = args.artifacts / lock["artifacts"]["mod_dir"]
    if not apworld.is_file():
        die(f"missing {apworld} - run scripts/build_world.py first")
    if not (mod_dir / "StardewArchipelago.dll").is_file():
        die(f"missing built mod in {mod_dir} - run scripts/build_mod.py first")

    mods = collect_mod_dirs(mod_dir, lock["artifacts"]["mod_dir"], args.cp_dir)
    native = [(f"Mods/{name}/{rel}", why) for src, name in mods for rel, why in scan_native(src)]
    if native:
        print("non-managed binaries found:")
        for rel, why in native:
            print(f"  {rel}  [{why}]")
        if not args.allow_native:
            die("refusing to package non-managed binaries (the zip must work on Windows, macOS and Linux); "
                "rerun with --allow-native to override")
    else:
        print("native-binary scan: none (all .dll files are managed; no .so/.dylib/.exe)")

    out = args.artifacts / "release"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy2(apworld, out / apworld.name)
    zip_path = out / f"StardewValleyExpandedAP-{version}.zip"
    write_mod_zip(mods, zip_path)

    sums = [f"{sha256(p)}  {p.name}" for p in sorted(out.iterdir()) if p.name != "SHA256SUMS.txt"]
    (out / "SHA256SUMS.txt").write_bytes(("\n".join(sums) + "\n").encode("utf-8"))

    print(f"\nrelease {version} -> {out}")
    for line in sums:
        print(f"  {line}")
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    print(f"\n{zip_path.name}: {len(names)} entries (first 20)")
    for n in names[:20]:
        print(f"  {n}")


if __name__ == "__main__":
    main()
