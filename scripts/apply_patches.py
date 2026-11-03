#!/usr/bin/env python3
"""Apply patches/<half>/*.patch onto the matching .cache/ checkout."""
import argparse
from pathlib import Path

from common import DEFAULT_CACHE, ROOT, die, git


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--reverse", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    targets = [("world", args.cache_root / "archipelago"), ("mod", args.cache_root / "stardew_archipelago")]
    applied = 0
    for half, target in targets:
        patch_dir = ROOT / "patches" / half
        if not patch_dir.is_dir():
            continue
        patches = sorted(patch_dir.glob("*.patch"), key=lambda p: p.name)
        if not patches:
            continue
        if not target.is_dir():
            die(f"missing checkout for '{half}': run scripts/fetch_upstream.py first")
        for patch in patches:
            cmd = ["apply", "--whitespace=nowarn"]
            if args.reverse:
                cmd.append("--reverse")
            if args.check:
                cmd.append("--check")
            cmd.append(str(patch))
            res = git(cmd, cwd=target, check=False)
            if res.returncode != 0:
                # already applied is not an error for our purposes
                already = git(["apply", "--reverse", "--check", str(patch)], cwd=target, check=False)
                if already.returncode == 0:
                    print(f"[{half}] {patch.name} already applied, skipping")
                    continue
                print(res.stdout + res.stderr)
                die(f"failed to apply {patch.name} to {target}")
            print(f"[{half}] applied {patch.name}")
            applied += 1

    print(f"\n{applied} patch(es) applied{' (check only)' if args.check else ''}.")


if __name__ == "__main__":
    main()
