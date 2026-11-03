#!/usr/bin/env python3
"""Fetch the upstream checkouts pinned in versions.lock into .cache/."""
import argparse
from pathlib import Path

from common import DEFAULT_CACHE, git, load_lock


def sync_upstream(cache: Path, name: str, repo: str, commit: str) -> None:
    d = cache / name
    if (d / ".git").exists():
        head = git(["rev-parse", "HEAD"], cwd=d, check=False)
        if head.returncode == 0 and head.stdout.strip() == commit:
            print(f"[{name}] already at {commit}")
            return
        # local commits on top of the pin (e.g. applied patches): never force them away
        if git(["merge-base", "--is-ancestor", commit, "HEAD"], cwd=d, check=False).returncode == 0:
            print(f"[{name}] HEAD has local commits on top of {commit}; leaving it alone")
            return
        if git(["status", "--porcelain"], cwd=d, check=False).stdout.strip():
            raise SystemExit(f"[{name}] has uncommitted changes and is not at {commit}; "
                             f"commit or stash them, or delete {d}, then re-run")
    else:
        d.mkdir(parents=True, exist_ok=True)
        git(["init", "--quiet"], cwd=d)
        git(["remote", "add", "origin", repo], cwd=d, check=False)

    print(f"[{name}] fetching {commit}")
    git(["fetch", "--quiet", "--depth", "1", "origin", commit], cwd=d)
    git(["checkout", "--quiet", "--force", "FETCH_HEAD"], cwd=d)
    print(f"[{name}] at {git(['rev-parse', 'HEAD'], cwd=d).stdout.strip()}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    args = ap.parse_args()
    lock = load_lock()
    args.cache_root.mkdir(parents=True, exist_ok=True)
    up = lock["upstream"]
    for name in ("archipelago", "stardew_archipelago"):
        sync_upstream(args.cache_root, name, up[name]["repo"], up[name]["commit"])
    print(f"\nDone. Sources are in {args.cache_root}")


if __name__ == "__main__":
    main()
