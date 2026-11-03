"""Shared helpers for the build scripts. Standard library only; behaves the same on Windows, macOS and Linux."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE = ROOT / ".cache"
LOCK_PATH = ROOT / "versions.lock"


def _scan_json(text: str, strip_comments: bool, strip_commas: bool) -> str:
    """String-aware pass over JSON-ish text: optionally drop // and /* */ comments and trailing commas."""
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
        elif strip_comments and text.startswith("//", i):
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        elif strip_comments and text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        elif strip_commas and c == ",":
            j = i + 1
            while j < n and text[j].isspace():
                j += 1
            if j < n and text[j] in "}]":
                i += 1
                continue
        out.append(c)
        i += 1
    return "".join(out)


def loads_lenient(text: str):
    """json.loads that tolerates a BOM, comments and trailing commas (SMAPI manifests often have them)."""
    text = text.lstrip("﻿")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    return json.loads(_scan_json(_scan_json(text, True, False), False, True))


def read_json_lenient(path):
    return loads_lenient(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data) -> None:
    """UTF-8 without BOM, LF newlines, key order preserved."""
    Path(path).write_bytes((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def load_lock(path=LOCK_PATH) -> dict:
    return read_json_lenient(path)


def get_ci(mapping: dict, key: str, default=None):
    """Case-insensitive dict lookup (SMAPI manifests use 'Version'; PowerShell did not care about case)."""
    for k, v in mapping.items():
        if k.lower() == key.lower():
            return v
    return default


def _run_git(args, cwd, ssl_openssl: bool):
    cmd = ["git"]
    if ssl_openssl:
        cmd += ["-c", "http.sslBackend=openssl"]
    if cwd:
        cmd += ["-C", str(cwd)]
    return subprocess.run(cmd + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")


def git(args, cwd=None, check: bool = True) -> subprocess.CompletedProcess:
    """Run git; on failure retry once with -c http.sslBackend=openssl.

    schannel has no credentials in some sandboxed Windows environments; openssl works there.
    Output is captured and echoed only on final failure when check is set.
    """
    res = _run_git(args, cwd, False)
    if res.returncode != 0:
        res = _run_git(args, cwd, True)
    if res.returncode != 0 and check:
        sys.stderr.write(res.stdout + res.stderr)
        raise SystemExit(f"error: git {' '.join(args)} failed")
    return res


def die(msg: str):
    raise SystemExit(f"error: {msg}")
