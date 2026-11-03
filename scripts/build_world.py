#!/usr/bin/env python3
"""Package the patched world into artifacts/stardew_valley.apworld."""
import argparse
import shutil
import zipfile
from pathlib import Path

from common import DEFAULT_CACHE, ROOT, die, get_ci, load_lock, read_json_lenient, write_json

WORLD_NAME = "stardew_valley"


def inject_manifest(manifest: dict, lock: dict, pair_version) -> dict:
    """Stamp container fields the way AP's own build does, plus world_version.

    AP's build injects compatible_version/version/maximum_ap_version into archipelago.json; the world folder in
    the repo does not carry them, and without compatible_version the loader refuses the archive with "This might
    be the incorrect world version". Existing values are kept.

    world_version is always overwritten: the mod refuses a slot whose client_version differs from its own
    ModVersion, and slot data carries world_version verbatim. pair_version comes from the mod manifest (falling
    back to lock pairing.mod_version) so the pair can never drift.
    """
    container = lock["apworld_container"]
    if manifest.get("compatible_version") is None:
        manifest["compatible_version"] = container["compatible_version"]
    if manifest.get("version") is None:
        manifest["version"] = container["version"]
    if manifest.get("maximum_ap_version") is None:
        manifest["maximum_ap_version"] = lock["upstream"]["archipelago"]["tag"]
    if pair_version:
        manifest.pop("world_version", None)  # re-add at the end, matching the old PowerShell key order
        manifest["world_version"] = pair_version
    return manifest


def read_pair_version(cache: Path, lock: dict):
    """Version of the mod we ship alongside the world: mod manifest first, then lock pairing.mod_version."""
    pair = (lock.get("pairing") or {}).get("mod_version")
    mod_manifest = cache / "stardew_archipelago" / "StardewArchipelago" / "manifest.json"
    if mod_manifest.exists():
        pair = get_ci(read_json_lenient(mod_manifest), "Version", pair)
    return pair


def stage_world(src: Path, dest: Path) -> None:
    """Copy the world tree (subdirectories included) without bytecode caches."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))


def zip_tree(base_dir: Path, top: str, out_zip: Path) -> None:
    """Zip base_dir/top into out_zip with `top/` as the archive's top-level folder and forward-slash paths.

    Mirrors shutil.make_archive: sorted walk, directory entries included.
    """
    root = base_dir / top
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(root, top + "/")
        for p in sorted(root.rglob("*"), key=lambda q: q.relative_to(root).as_posix()):
            arc = f"{top}/{p.relative_to(root).as_posix()}"
            zf.write(p, arc + "/" if p.is_dir() else arc)


def build(cache: Path, artifacts: Path, lock: dict) -> Path:
    world_src = cache / "archipelago" / "worlds" / WORLD_NAME
    if not world_src.is_dir():
        die(f"missing {world_src} - run scripts/fetch_upstream.py first")

    stage = artifacts / "_stage"
    artifacts.mkdir(parents=True, exist_ok=True)
    if stage.exists():
        shutil.rmtree(stage)
    print("staging patched world...")
    stage_world(world_src, stage / WORLD_NAME)

    apworld = artifacts / lock["artifacts"]["apworld"]
    if apworld.exists():
        apworld.unlink()

    manifest_path = stage / WORLD_NAME / "archipelago.json"
    manifest = read_json_lenient(manifest_path)
    pair = read_pair_version(cache, lock)
    inject_manifest(manifest, lock, pair)
    if pair:
        print(f"stamped world_version={pair} (must equal the mod's ModVersion)")
    else:
        print(f"warning: no pairing.mod_version in versions.lock and no mod checkout; "
              f"leaving world_version={manifest.get('world_version')}")
    write_json(manifest_path, manifest)
    print(f"injected container manifest fields (compatible_version={manifest['compatible_version']}, "
          f"version={manifest['version']})")

    print(f"zipping -> {apworld}")
    zip_tree(stage, WORLD_NAME, apworld)
    shutil.rmtree(stage)
    print(f"created {apworld} ({apworld.stat().st_size / 1024:,.0f} KB)")
    print("install it as a custom world, or drop it in lib/worlds to replace the built-in one.")
    return apworld


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--artifacts", type=Path, default=ROOT / "artifacts")
    args = ap.parse_args()
    build(args.cache_root, args.artifacts, load_lock())


if __name__ == "__main__":
    main()
