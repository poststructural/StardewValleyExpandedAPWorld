#!/usr/bin/env python3
"""End-to-end smoke test: SVE checks reach an Archipelago server and items arrive.

Generates a seed with the patched world (.cache/archipelago), hosts it locally, builds+installs the patched client,
the CP gate pack and the APSmokeTest mod into the disposable testbed, launches the game, lets the mod create a new
"APSmoke" Archipelago save and fire one check per path, then compares server and SMAPI logs against what was expected.

    python tools/sve-smoketest/run.py --work-dir <scratch dir>

Never touches the live Steam install, C:\\ProgramData\\Archipelago, or saves whose name does not start with APSmoke.
Contains no SVE or game files.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                       # STE-APWorld
CACHE = ROOT / ".cache"
AP_DIR = CACHE / "archipelago"
VENV_PY = CACHE / "venv312" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
DEFAULT_TESTBED = ROOT.parent / "_testbed" / "sdv-sve"
SAVES = Path(os.environ.get("APPDATA", "")) / "StardewValley" / "Saves"
SMAPI_LOG = Path(os.environ.get("APPDATA", "")) / "StardewValley" / "ErrorLogs" / "SMAPI-latest.txt"
SAVE_PREFIX = "APSmoke"
SLOT = "APSmoke"

YAML = """name: {slot}
game: Stardew Valley
requires:
  version: 0.6.8
Stardew Valley:
  progression_balancing: 0
  accessibility: full
  goal: community_center
  mods: ["Stardew Valley Expanded"]
  shipsanity: everything
  fishsanity: all
  friendsanity: all
  friendsanity_heart_size: 1
  cropsanity: enabled
  cooksanity: all
  chefsanity: ["Queen of Sauce", "Purchases", "Friendship", "Skills"]
  craftsanity: all
  museumsanity: all
  eatsanity: ["Cooking", "Crops", "Fish", "Artisan", "Shop", "Poisonous"]
  special_order_locations: board_qi
  quest_locations: 5
  exclude_ginger_island: false
"""

# Items sent from the server console to prove arrival: (item name, kind)
SEND_ITEMS = [
    ("Henchman <3", "new friendsanity heart item (our block)"),
    ("Fish Dumpling Recipe", "new chefsanity recipe item (our block)"),
    ("Cucumber Seed", "new cropsanity item (our block)"),
    ("Sophia <3", "older SVE friendsanity heart item"),
    ("Aurora Vineyard Tablet", "older SVE quest item (gate flag)"),
    ("Morgan's Schooling", "older SVE quest item (gate flag)"),
]


# ERROR lines the client logs for reasons unrelated to SVE: the 7.4.25 world sends no help_wanted_quests slot data, so
# the client's help-wanted balancer dereferences null (HelpWantedQuestInjections.cs CreateWeightedMissingLocations).
KNOWN_BENIGN_ERRORS = ["GetQuestOfTheDay_BalanceQuests_Prefix"]


def sh(cmd, **kw):
    print("+", " ".join(map(str, cmd)))
    return subprocess.run(cmd, **kw)


def run_env():
    env = dict(os.environ)
    env["SKIP_REQUIREMENTS_UPDATE"] = "1"      # otherwise Generate.py blocks on a "press enter to install" prompt
    env["PYTHONUNBUFFERED"] = "1"
    return env


def process_running(image):
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    return [l for l in out.splitlines() if image.lower() in l.lower()]


def kill_tree(proc):
    if proc and proc.poll() is None:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)


def mod_version():
    manifest = ROOT / "artifacts" / "StardewArchipelago" / "manifest.json"
    text = manifest.read_text(encoding="utf-8-sig")
    return re.search(r'"Version"\s*:\s*"([^"]+)"', text, re.I).group(1)


def generate(work, seed):
    # The mod refuses a slot whose world_version differs from its ModVersion (build_world.py stamps this into the
    # apworld). Generating from the checkout needs the same stamp; apply it for the duration of generation only.
    wm = AP_DIR / "worlds" / "stardew_valley" / "archipelago.json"
    original = wm.read_text(encoding="utf-8")
    doc = json.loads(original)
    doc["world_version"] = mod_version()
    wm.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    try:
        return _generate(work, seed)
    finally:
        wm.write_text(original, encoding="utf-8")


def _generate(work, seed):
    players = work / "players"
    out = work / "gen"
    for d in (players, out):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    (players / f"{SLOT}.yaml").write_text(YAML.format(slot=SLOT))
    r = sh([str(VENV_PY), "-u", "Generate.py", "--player_files_path", str(players), "--outputpath", str(out),
            "--seed", str(seed)], cwd=AP_DIR, env=run_env(), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900)
    (work / "generate.log").write_text(r.stdout + r.stderr)
    zips = list(out.glob("AP_*.zip"))
    if r.returncode != 0 or not zips:
        sys.exit("generation failed; see " + str(work / "generate.log"))
    locs = work / "locations.json"
    r = sh([str(VENV_PY), str(HERE / "multidata.py"), str(zips[0]), str(locs)], cwd=AP_DIR, env=run_env(), capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("multidata dump failed: " + r.stderr[-800:])
    return zips[0], {int(k): v for k, v in json.loads(locs.read_text()).items()}


def build_and_install(args, work, cfg):
    testbed = Path(args.testbed)
    mods = testbed / "Mods"
    if not args.skip_build:
        sh([str(VENV_PY), str(ROOT / "scripts" / "build_mod.py"), "--game-path", str(testbed)], check=True, cwd=ROOT)
        sh(["dotnet", "build", str(HERE / "mod" / "APSmokeTest.csproj"), "-c", "Release", f"-p:GamePath={testbed}",
            "-p:EnableModDeploy=false", "-p:EnableModZip=false", "--nologo", "-v", "q"], check=True)
    backup = work / "mods-backup"
    pairs = [
        (ROOT / "artifacts" / "StardewArchipelago", mods / "StardewArchipelago"),
        (ROOT / "cp" / "[CP] StardewAP - SVE Gates", mods / "[CP] StardewAP - SVE Gates"),
    ]
    for src, dst in pairs:
        if dst.exists() and not (backup / dst.name).exists():
            shutil.copytree(dst, backup / dst.name)
        shutil.copytree(src, dst, dirs_exist_ok=True)
    smoke = mods / "APSmokeTest"
    smoke.mkdir(exist_ok=True)
    built = HERE / "mod" / "bin" / "Release" / "net6.0"
    shutil.copy2(built / "APSmokeTest.dll", smoke)
    shutil.copy2(HERE / "mod" / "manifest.json", smoke)
    (smoke / "smoke.json").write_text(json.dumps(cfg, indent=2))


def clean_smoke_saves():
    if SAVES.is_dir():
        for d in SAVES.iterdir():
            if d.name.startswith(SAVE_PREFIX):          # only ever our own saves
                shutil.rmtree(d, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work-dir", type=Path, default=Path(os.environ.get("TEMP", ".")) / "sve-smoketest")
    ap.add_argument("--testbed", default=str(DEFAULT_TESTBED))
    ap.add_argument("--port", type=int, default=38290)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--skip-build", action="store_true", help="reuse artifacts/ and the built APSmokeTest")
    ap.add_argument("--skip-generate", action="store_true", help="reuse the seed in <work-dir>/gen")
    ap.add_argument("--report-only", action="store_true", help="re-analyse the logs already in --work-dir")
    ap.add_argument("--timeout", type=int, default=900, help="seconds to wait for the game to finish")
    args = ap.parse_args()

    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if args.report_only:
        sys.exit(report(work, {int(k): v for k, v in json.loads((work / "locations.json").read_text()).items()}))
    testbed = Path(args.testbed).resolve()
    if not (testbed / "StardewModdingAPI.exe").is_file():
        sys.exit(f"testbed not found: {testbed}")
    if "Steam" in str(testbed):
        sys.exit("refusing to run against a Steam install")
    if process_running("StardewModdingAPI.exe") or process_running("Stardew Valley.exe"):
        sys.exit("a Stardew/SMAPI process is already running; close it first (the build also needs the DLLs unlocked)")

    flags = work / "flags"
    shutil.rmtree(flags, ignore_errors=True)
    flags.mkdir()
    result_path = work / "result.json"
    result_path.unlink(missing_ok=True)

    if args.skip_generate:
        zip_path = next((work / "gen").glob("AP_*.zip"))
        locs = {int(k): v for k, v in json.loads((work / "locations.json").read_text()).items()}
    else:
        zip_path, locs = generate(work, args.seed)
    print(f"seed {zip_path.name}: {len(locs)} locations")

    cfg = {"Server": f"127.0.0.1:{args.port}", "Slot": SLOT, "FarmName": SAVE_PREFIX,
           "ResultPath": str(result_path), "FlagDir": str(flags)}
    build_and_install(args, work, cfg)
    clean_smoke_saves()
    SMAPI_LOG.unlink(missing_ok=True) if SMAPI_LOG.exists() else None

    server = game = None
    server_log = work / "server.log"
    started = time.time()
    try:
        slog = open(server_log, "w", encoding="utf-8", errors="replace")
        server = subprocess.Popen([str(VENV_PY), "-u", "MultiServer.py", str(zip_path), "--port", str(args.port),
                                   "--log_network", "--disable_save", "--loglevel", "info"],
                                  cwd=AP_DIR, env=run_env(), stdin=subprocess.PIPE, stdout=slog, stderr=subprocess.STDOUT, text=True)
        for _ in range(60):
            time.sleep(1)
            if "server started" in server_log.read_text(errors="replace").lower() or "listening" in server_log.read_text(errors="replace").lower():
                break
        print("server up:", server_log.read_text(errors="replace").strip().splitlines()[-1:])

        game = subprocess.Popen([str(testbed / "StardewModdingAPI.exe")], cwd=testbed)
        print("game launched, pid", game.pid)

        sent = False
        while time.time() - started < args.timeout:
            time.sleep(3)
            if (flags / "ready.flag").exists() and not sent:
                sent = True
                time.sleep(3)
                for item, _kind in SEND_ITEMS:
                    server.stdin.write(f"/send {SLOT} {item}\n")
                    server.stdin.flush()
                    time.sleep(1)
                time.sleep(5)
                (flags / "proceed.flag").write_text("go")
                print("items sent from server console; proceeding to sleep")
            if result_path.exists():
                try:
                    doc = json.loads(result_path.read_text())
                    if doc.get("final") or "harnessFailure" in doc.get("extra", {}):
                        break
                except ValueError:
                    pass
            if game.poll() is not None:
                print("game exited early")
                break
        time.sleep(5)
    finally:
        kill_tree(game)
        kill_tree(server)
        time.sleep(2)
        try:
            slog.close()
        except Exception:
            pass
        if SMAPI_LOG.exists():
            shutil.copy2(SMAPI_LOG, work / "SMAPI-latest.txt")

    code = report(work, locs)
    left = process_running("StardewModdingAPI.exe") + process_running("Stardew Valley.exe")
    if left:
        print("WARNING: game processes still running:", left)
    sys.exit(code)


def report(work, locs):
    name_to_id = {v: k for k, v in locs.items()}
    result = json.loads((work / "result.json").read_text()) if (work / "result.json").exists() else {"results": [], "extra": {}}
    server_text = (work / "server.log").read_text(errors="replace")
    smapi = (work / "SMAPI-latest.txt").read_text(errors="replace") if (work / "SMAPI-latest.txt").exists() else ""

    checked, evidence = set(), {}
    for line in server_text.splitlines():
        if "Incoming message: " not in line or "LocationChecks" not in line:
            continue
        try:
            msgs = json.loads(line.split("Incoming message: ", 1)[1])
        except ValueError:
            continue
        for m in msgs:
            if m.get("cmd") == "LocationChecks":
                for i in m["locations"]:
                    checked.add(i)
                    evidence.setdefault(i, line.strip()[:120])

    lines, ok = [], True
    for r in result.get("results", []):
        exp = r["ExpectedLocations"]
        missing = [e for e in exp if e not in name_to_id or name_to_id[e] not in checked]
        unknown = [e for e in exp if e not in name_to_id]
        status = "PASS" if not r.get("Error") and not missing else "FAIL"
        if r["Path"] == "gating":
            status = "PASS" if not r.get("Error") else "FAIL"
        ok &= status == "PASS"
        lines.append(f"{status}  {r['Path']}: {r.get('Detail') or r.get('Error')}")
        for e in exp:
            i = name_to_id.get(e)
            hit = i in checked
            lines.append(f"      {'ok ' if hit else 'MISSING'} {e} [{i}]" + (f"  <- server: {evidence.get(i, '')}" if hit else ""))
        if unknown:
            lines.append(f"      names not in this seed: {unknown}")
    if not result.get("results"):
        ok = False
        lines.append("FAIL  no results written by APSmokeTest (see SMAPI log)")

    # SMAPI log analysis
    err = [l for l in smapi.splitlines() if re.match(r"\[\d\d:\d\d:\d\d ERROR ", l)]
    mine = [l for l in err if "StardewArchipelago" in l.split("]")[0] or "APSmokeTest" in l.split("]")[0]]
    warn = [l for l in smapi.splitlines() if re.match(r"\[\d\d:\d\d:\d\d WARN ", l) and ("StardewArchipelago" in l.split("]")[0] or "APSmokeTest" in l.split("]")[0])]
    gate = re.search(r"SVE event gates: (\d+) of (\d+) rules bound", smapi)
    lines.append("")
    lines.append(f"SMAPI: {len(err)} ERROR lines total, {len(mine)} from StardewArchipelago/APSmokeTest, {len(warn)} WARN from those")
    lines += ["   ERR " + l[:220] for l in mine[:15]]
    lines += ["   WARN " + l[:200] for l in warn[:15]]
    unexpected = [l for l in mine if not any(k in l for k in KNOWN_BENIGN_ERRORS)]
    lines.append(f"   ({len(mine) - len(unexpected)} of those are known-benign: {KNOWN_BENIGN_ERRORS}; {len(unexpected)} unexpected)")
    if unexpected:
        ok = False
    lines.append("gate self-check: " + (f"{gate.group(1)} of {gate.group(2)} rules bound" if gate else "NOT FOUND"))
    if not gate:
        ok = False
    lines.append("gating before/after: " + json.dumps(result.get("extra", {}).get("gating")))
    lines.append("day-2 state: " + json.dumps(result.get("extra", {}).get("day2")))
    recv = [l for l in smapi.splitlines() if re.search(r"received|Received", l) and "StardewArchipelago" in l.split("]")[0]]
    lines.append(f"client item-receipt trace lines: {len(recv)}")
    lines += ["   " + l[:200] for l in recv[:20]]
    send_lines = [l for l in server_text.splitlines() if "ReceivedItems" in l and "Outgoing" in l]
    lines.append(f"server ReceivedItems messages: {len(send_lines)}")
    lines.append("")
    lines.append("OVERALL: " + ("PASS" if ok else "FAIL"))
    text = "\n".join(lines)
    (work / "report.txt").write_text(text, encoding="utf-8")
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    main()
