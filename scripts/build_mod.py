#!/usr/bin/env python3
"""Build the patched StardewArchipelago mod into artifacts/StardewArchipelago/."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import sync_id_tables
from common import DEFAULT_CACHE, ROOT, die, get_ci, load_lock, read_json_lenient

GAME_DLL = "Stardew Valley.dll"


def default_game_paths() -> list:
    home = Path.home()
    if sys.platform == "win32":
        return [
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\Stardew Valley"),
            Path(r"C:\Steam\steamapps\common\Stardew Valley"),
            Path(r"C:\Program Files (x86)\GOG Galaxy\Games\Stardew Valley"),
            Path(r"C:\GOG Games\Stardew Valley"),
        ]
    if sys.platform == "darwin":
        return [
            home / "Library/Application Support/Steam/steamapps/common/Stardew Valley/Contents/MacOS",
            Path("/Applications/Stardew Valley.app/Contents/MacOS"),
            Path("/Users/Shared/GOG.com/Galaxy/Applications/Stardew Valley/Stardew Valley.app/Contents/MacOS"),
        ]
    return [
        home / ".local/share/Steam/steamapps/common/Stardew Valley",
        home / ".steam/steam/steamapps/common/Stardew Valley",
        home / "GOG Games/Stardew Valley/game",
    ]


def find_game(explicit):
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not (p / GAME_DLL).is_file():
            die(f"--game-path does not look like a Stardew Valley install (no {GAME_DLL}): {p}")
        return p
    for cand in default_game_paths():
        if (cand / GAME_DLL).is_file():
            print(f"auto-detected game at {cand}")
            return cand
    tried = "\n  ".join(str(c) for c in default_game_paths())
    die(f"could not find Stardew Valley; pass --game-path. Looked in:\n  {tried}")


def windows_file_version(path: Path):
    """Numeric FileVersion (a.b.c.d) of a PE file via version.dll, or None if unavailable."""
    import ctypes
    from ctypes import wintypes

    ver = ctypes.WinDLL("version", use_last_error=True)
    size = ver.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(str(path), 0, size, buf):
        return None
    ptr = ctypes.c_void_p()
    length = wintypes.UINT()
    if not ver.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(length)) or length.value < 52:
        return None
    ms, ls = ctypes.c_uint32.from_address(ptr.value + 8).value, ctypes.c_uint32.from_address(ptr.value + 12).value
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"


def check_game_version(game: Path, expected: str) -> None:
    if sys.platform != "win32":
        print(f"note: skipping game FileVersion check on {sys.platform}; make sure the install is {expected}")
        return
    try:
        found = windows_file_version(game / GAME_DLL)
    except Exception as e:  # pragma: no cover - best effort only
        print(f"note: could not read game FileVersion ({e})")
        return
    if found and not found.startswith(expected):
        print(f"warning: game build is {found} but versions.lock pins {expected} - "
              f"build against the pinned version before shipping", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-path", help="Stardew Valley install folder (auto-detected from Steam/GOG defaults if omitted)")
    ap.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--configuration", default="Release")
    args = ap.parse_args()

    lock = load_lock()
    project = args.cache_root / "stardew_archipelago" / "StardewArchipelago" / "StardewArchipelago.csproj"
    if not project.is_file():
        die(f"missing {project} - run scripts/fetch_upstream.py first")
    if shutil.which("dotnet") is None:
        die("dotnet SDK not found on PATH")
    game = find_game(args.game_path)
    check_game_version(game, lock["game"]["version"])

    # Make the client know the ids of the locations/items this project adds to the world, before it is compiled.
    if sync_id_tables.main(["--cache-root", str(args.cache_root)]) != 0:
        die("sync_id_tables failed")

    print(f"building {args.configuration} against {game}")
    # EnableModDeploy/EnableModZip are Pathoschild.Stardew.ModBuildConfig properties; turn them off so the build
    # never copies into (or zips from) a game's Mods folder.
    cmd = ["dotnet", "build", str(project), "-c", args.configuration, f"-p:GamePath={game}",
           "-p:EnableModDeploy=false", "-p:EnableModZip=false", "--nologo"]
    if subprocess.run(cmd).returncode != 0:
        die("dotnet build failed")

    bin_dir = project.parent / "bin" / args.configuration / "net6.0"
    if not (bin_dir / "StardewArchipelago.dll").is_file():
        die(f"build output not found in {bin_dir}")

    out_dir = ROOT / "artifacts" / lock["artifacts"]["mod_dir"]
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(bin_dir, out_dir)

    # BSD-3 requires the notice to travel with binary redistributions
    lic = args.cache_root / "stardew_archipelago" / "LICENSE.md"
    if lic.is_file():
        shutil.copy2(lic, out_dir / "LICENSE.md")

    # the csproj uses manifest.json as ApplicationManifest, so it is not part of the build output
    if not (out_dir / "manifest.json").exists():
        shutil.copy2(project.parent / "manifest.json", out_dir / "manifest.json")

    dll = out_dir / "StardewArchipelago.dll"
    version = get_ci(read_json_lenient(out_dir / "manifest.json"), "Version")
    print(f"built {out_dir} ({dll.stat().st_size / 1024:,.0f} KB, mod version {version})")


if __name__ == "__main__":
    main()
