#!/usr/bin/env python3
"""End-to-end smoke test: SVE checks reach an Archipelago server and items arrive.

Generates a seed with the patched world (.cache/archipelago), hosts it locally, builds+installs the patched client,
the CP gate pack and the APSmokeTest mod into the disposable testbed, launches the game, lets the mod create a new
"APSmoke" Archipelago save and fire one check per path, then compares server and SMAPI logs against what was expected.

    python tools/sve-smoketest/run.py --work-dir <scratch dir>              # single-player (default)
    python tools/sve-smoketest/run.py --mode coop --work-dir <scratch dir>  # host + farmhand over LAN, one AP slot

Never touches the live Steam install, C:\\ProgramData\\Archipelago, or saves whose name does not start with APSmoke.
Contains no SVE or game files.
"""
import argparse
import atexit
import ctypes
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                       # STE-APWorld
CACHE = ROOT / ".cache"
AP_DIR = CACHE / "archipelago"
VENV_PY = CACHE / "venv312" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
DEFAULT_TESTBED = ROOT.parent / "_testbed" / "sdv-sve"
SAVES = Path(os.environ.get("APPDATA", "")) / "StardewValley" / "Saves"
SMAPI_LOG_DIR = Path(os.environ.get("APPDATA", "")) / "StardewValley" / "ErrorLogs"
SMAPI_LOG = SMAPI_LOG_DIR / "SMAPI-latest.txt"
SMAPI_LOG2 = SMAPI_LOG_DIR / "SMAPI-latest.player-2.txt"   # SMAPI gives a second concurrent instance this name
PREFS = Path(os.environ.get("APPDATA", "")) / "StardewValley" / "startup_preferences"
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
{extra}"""

# Co-op only: start without tools and backpack, so the per-farmer starting restrictions and progressive tools are exercised.
COOP_YAML_EXTRA = '  start_without: ["Tools", "Backpack"]\n'

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


_prefs_backup = None


def restore_prefs():
    global _prefs_backup
    if _prefs_backup is not None:
        if _prefs_backup.exists():
            shutil.copy2(_prefs_backup, PREFS)
        _prefs_backup = None


def prepare_prefs(work):
    """Windowed, 800x600, keep running unfocused. The owner's real game shares this file, so back it up and restore it."""
    global _prefs_backup
    if not PREFS.exists():
        return
    backup = work / "startup_preferences.backup"
    if not backup.exists():                      # never overwrite the first (genuine) backup if a previous run died
        shutil.copy2(PREFS, backup)
    _prefs_backup = backup
    atexit.register(restore_prefs)
    text = backup.read_text(encoding="utf-8")
    for tag, val in (("windowMode", "1"), ("fullscreen", "false"), ("windowedBorderlessFullscreen", "false"),
                     ("preferredResolutionX", "800"), ("preferredResolutionY", "600"), ("pauseWhenOutOfFocus", "false")):
        text = re.sub(rf"<{tag}>[^<]*</{tag}>", f"<{tag}>{val}</{tag}>", text)
    PREFS.write_text(text, encoding="utf-8")


def launch_game(testbed, extra_env=None):
    """Start SMAPI minimised and without activating its windows (the owner uses the PC meanwhile)."""
    env = dict(os.environ)
    env["SDL_WINDOW_NO_ACTIVATION_WHEN_SHOWN"] = "1"
    env.update(extra_env or {})
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 7                            # SW_SHOWMINNOACTIVE
    proc = subprocess.Popen([str(testbed / "StardewModdingAPI.exe")], cwd=testbed, env=env, startupinfo=si)
    threading.Thread(target=_keep_minimised, args=(proc,), daemon=True).start()
    return proc


def _keep_minimised(proc):
    """Minimise (without activating) every window the process opens; never raises or focuses anything."""
    user32 = ctypes.windll.user32
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    seen = {}

    def cb(hwnd, _):
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == proc.pid and user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 7)            # SW_SHOWMINNOACTIVE
        return True

    cb_ptr = enum_proc(cb)
    while proc.poll() is None:
        user32.EnumWindows(cb_ptr, 0)
        time.sleep(0.5)


def mod_version():
    manifest = ROOT / "artifacts" / "StardewArchipelago" / "manifest.json"
    text = manifest.read_text(encoding="utf-8-sig")
    return re.search(r'"Version"\s*:\s*"([^"]+)"', text, re.I).group(1)


def generate(work, seed, extra=""):
    # The mod refuses a slot whose world_version differs from its ModVersion (build_world.py stamps this into the
    # apworld). Generating from the checkout needs the same stamp; apply it for the duration of generation only.
    wm = AP_DIR / "worlds" / "stardew_valley" / "archipelago.json"
    original = wm.read_text(encoding="utf-8")
    doc = json.loads(original)
    doc["world_version"] = mod_version()
    wm.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    try:
        return _generate(work, seed, extra)
    finally:
        wm.write_text(original, encoding="utf-8")


def _generate(work, seed, extra=""):
    players = work / "players"
    out = work / "gen"
    for d in (players, out):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    (players / f"{SLOT}.yaml").write_text(YAML.format(slot=SLOT, extra=extra))
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
    # No tester.json: the co-op host gets its cabin from the real Host New Farm menu, like a player would.
    (mods / "StardewArchipelago" / "tester.json").unlink(missing_ok=True)
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
    ap.add_argument("--mode", choices=["single", "coop"], default="single")
    ap.add_argument("--port", type=int, default=38290)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--skip-build", action="store_true", help="reuse artifacts/ and the built APSmokeTest")
    ap.add_argument("--skip-generate", action="store_true", help="reuse the seed in <work-dir>/gen")
    ap.add_argument("--report-only", action="store_true", help="re-analyse the logs already in --work-dir")
    ap.add_argument("--timeout", type=int, default=900, help="seconds to wait for the game to finish")
    args = ap.parse_args()

    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if args.mode == "coop" and not args.report_only:
        sys.exit(run_coop(args, work))
    if args.report_only and args.mode == "coop":
        sys.exit(report_coop(work))
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
    prepare_prefs(work)

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

        game = launch_game(testbed, {"APSMOKE_CONFIG": ""})
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
        restore_prefs()
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


def wait_for(pred, timeout, what, procs=()):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        for p in procs:
            if p.poll() is not None:
                print(f"a game (pid {p.pid}, exit {p.returncode}) exited early while waiting for {what}")
                return False
        time.sleep(2)
    print(f"timed out waiting for {what}")
    return False


COOP_TEAM_ITEMS = ["Resource Pack: 500 Money"]
COOP_PER_FARMER_ITEMS = ["Progressive Backpack", "Fish Dumpling Recipe", "Friendship Bonus (2 <3)", "Henchman <3"]
COOP_FARMHAND_CHECKS = ["Fishsanity: Gar", "Cook Fish Dumpling", "Craft Hedge Fence", "Shipsanity: Cucumber"]
COOP_HOST_CHECKS = ["Fishsanity: Bonefish", "Cook Void Delight"]


def run_coop(args, work):
    """Host instance + farmhand instance of one testbed install on this PC, one AP slot, LAN at 127.0.0.1.

    Session 1 (new farm through Co-op > Host New Farm; the farmhand 'Hand'):
      day 1: the host earns money and claims a gift box, then the farmhand rejoins twice (team setup must not rerun);
             items are sent, both sleep.
      day 2: mail, checks fired (the farmhand gains AP XP), the farmhand leaves mid-day, the host sleeps alone (saves).
      day 3: the farmhand rejoins (AP XP kept); each farmer puts its axe in a farm chest; one Progressive Axe; both sleep.
      day 4: mail: each farmer's own axe goes up exactly one level.
    Session 2: the host reloads that save, 'Hand' rejoins and nothing may replay; then 'Late' joins for the first time."""
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
    for old in work.glob("SMAPI-*.txt"):
        old.unlink()
    if args.skip_generate:
        zip_path = next((work / "gen").glob("AP_*.zip"))
        locs = {int(k): v for k, v in json.loads((work / "locations.json").read_text()).items()}
    else:
        zip_path, locs = generate(work, args.seed, COOP_YAML_EXTRA)
    print(f"seed {zip_path.name}: {len(locs)} locations")
    base = {"Server": f"127.0.0.1:{args.port}", "Slot": SLOT, "FarmName": SAVE_PREFIX, "FlagDir": str(flags)}
    host_cfg, fh_cfg, late_cfg = work / "host.json", work / "farmhand.json", work / "farmhand-late.json"
    host_cfg.write_text(json.dumps({**base, "Role": "host", "ResultPath": str(work / "host-result.json")}, indent=2))
    fh_cfg.write_text(json.dumps({**base, "Role": "farmhand", "JoinAddress": "127.0.0.1", "FarmerName": "Hand", "ResultPath": str(work / "farmhand-result.json")}, indent=2))
    late_cfg.write_text(json.dumps({**base, "Role": "farmhand", "JoinAddress": "127.0.0.1", "FarmerName": "Late", "ResultPath": str(work / "late-result.json")}, indent=2))
    build_and_install(args, work, {**base, "ResultPath": str(work / "result.json")})
    clean_smoke_saves()
    prepare_prefs(work)
    server = None
    games = {}
    server_log = work / "server.log"
    state = {"n": 0, "ok": True}
    BOTH = ("host", "farmhand")

    def step(action, tag="", who=BOTH, timeout=600):
        if not state["ok"] and action != "quit":
            return False                     # an earlier step failed: skip to quit
        state["n"] += 1
        n = state["n"]
        (flags / "step.json").write_text(json.dumps({"N": n, "Action": action, "Tag": tag, "Who": "" if len(who) > 1 else who[0]}))
        print(f"step {n}: {action} {tag} ({'+'.join(who)})")
        ok = wait_for(lambda: all((flags / f"{r}.done.{n}").exists() for r in who), timeout, f"step {n} {action} {tag}", list(games.values()))
        state["ok"] &= ok
        return ok

    def send(items):
        for item in items:
            server.stdin.write(f"/send {SLOT} {item}\n")
            server.stdin.flush()
            time.sleep(1)

    def fh_join(cfg, label):
        """Start a farmhand game against the running host; True once it is in the world and caught up."""
        if not state["ok"]:
            return False
        for f in (SMAPI_LOG2, flags / "farmhand.ready.flag"):
            f.unlink(missing_ok=True)
        games["farmhand"] = launch_game(testbed, {"APSMOKE_CONFIG": str(cfg)})   # SMAPI logs this one to SMAPI-latest.player-2.txt
        print(f"farmhand {label} launched, pid", games["farmhand"].pid)
        ok = wait_for(lambda: (flags / "farmhand.ready.flag").exists(), args.timeout, f"farmhand.ready.flag ({label})", list(games.values()))
        state["ok"] &= ok
        if ok:
            time.sleep(20)                   # handshake, connect and catch-up
        return ok

    def fh_leave(label):
        """The farmhand quits mid-session (the host keeps running); keeps its log as SMAPI-farmhand-<label>.txt."""
        g = games.pop("farmhand", None)
        if g is None:
            return
        if state["ok"]:
            n = state["n"] + 1
            (flags / "step.json").write_text(json.dumps({"N": n, "Action": "quit", "Tag": label, "Who": "farmhand"}))
            state["n"] = n
            print(f"step {n}: quit {label} (farmhand)")
        try:
            g.wait(90)
        except subprocess.TimeoutExpired:
            pass
        kill_tree(g)
        time.sleep(3)
        if SMAPI_LOG2.exists():
            shutil.copy2(SMAPI_LOG2, work / f"SMAPI-farmhand-{label}.txt")

    def host_start(host_json, suffix):
        for f in (SMAPI_LOG, SMAPI_LOG2, flags / "host.ready.flag", flags / "farmhand.ready.flag", flags / "step.json"):
            f.unlink(missing_ok=True)
        games.clear()
        games["host"] = launch_game(testbed, {"APSMOKE_CONFIG": str(host_json)})
        print(f"host{suffix} launched, pid", games["host"].pid)
        ok = wait_for(lambda: (flags / "host.ready.flag").exists(), args.timeout, "host.ready.flag", list(games.values()))
        state["ok"] &= ok
        if ok:
            time.sleep(10)                   # let the host finish its own AP connect + init before a farmhand asks
        return ok

    def end_session(suffix, fh_label):
        step("quit", who=tuple(games.keys()) or BOTH)
        for g in games.values():
            try:
                g.wait(60)
            except subprocess.TimeoutExpired:
                pass
        for g in games.values():
            kill_tree(g)
        time.sleep(3)
        if SMAPI_LOG.exists():
            shutil.copy2(SMAPI_LOG, work / f"SMAPI-host{suffix}.txt")
        if "farmhand" in games and SMAPI_LOG2.exists():
            shutil.copy2(SMAPI_LOG2, work / f"SMAPI-farmhand-{fh_label}.txt")
        games.clear()

    try:
        slog = open(server_log, "w", encoding="utf-8", errors="replace")
        server = subprocess.Popen([str(VENV_PY), "-u", "MultiServer.py", str(zip_path), "--port", str(args.port),
                                   "--log_network", "--disable_save", "--loglevel", "info"],
                                  cwd=AP_DIR, env=run_env(), stdin=subprocess.PIPE, stdout=slog, stderr=subprocess.STDOUT, text=True)
        for _ in range(60):
            time.sleep(1)
            if "server started" in server_log.read_text(errors="replace").lower():
                break
        if host_start(host_cfg, "") and fh_join(fh_cfg, "a1"):
            step("prep")
            step("earn", who=("host",))
            step("snap", "d1")
            fh_leave("a1")                   # [1] rejoin twice on day 1: no team setup on the farmhand
            fh_join(fh_cfg, "a2")
            step("snap", "j1")
            fh_leave("a2")
            fh_join(fh_cfg, "a3")
            step("snap", "j2")
            send(COOP_TEAM_ITEMS + COOP_PER_FARMER_ITEMS + ["Progressive Axe"])
            time.sleep(10)
            step("snap", "d1b")
            step("sleep", "night1", timeout=900)
            step("snap", "d2pre")
            step("mail")
            step("snap", "d2")
            step("fire")
            time.sleep(5)                    # the farmhand writes its AP XP to modData once a second
            step("snap", "d2f")
            fh_leave("a3")                   # [3] leave mid-day; the host sleeps (and saves) alone
            step("sleep", "night2", who=("host",), timeout=900)
            fh_join(fh_cfg, "a4")
            step("snap", "d3")
            step("stash")                    # [4] both axes into farm chests, then one Progressive Axe
            step("snap", "d3s")
            send(["Progressive Axe"])
            time.sleep(10)
            step("sleep", "night3", timeout=900)
            step("snap", "d4pre")
            step("mail")
            step("snap", "d4")
        else:
            state["ok"] = False
        end_session("", "a4")
        save = None
        try:
            save = json.loads((flags / "host.snap.d4.json").read_text())["save"]
        except (OSError, ValueError, KeyError):
            pass
        if save and state["ok"]:
            host2_cfg = work / "host2.json"
            host2_cfg.write_text(json.dumps({**base, "Role": "host", "LoadSave": save, "ResultPath": str(work / "host2-result.json")}, indent=2))
            if host_start(host2_cfg, "2") and fh_join(fh_cfg, "r"):
                step("snap", "r1")
                step("mail")
                step("snap", "r2")
                fh_leave("r")
                fh_join(late_cfg, "late")    # [2] a farmer whose first join is on day 4
                step("mail", who=("farmhand",))
                step("snap", "late")
            end_session("2", "late")
        else:
            print("skipping the reload session (session 1 did not finish)")
    finally:
        for g in games.values():
            kill_tree(g)
        kill_tree(server)
        time.sleep(2)
        try:
            slog.close()
        except Exception:
            pass
        restore_prefs()
    code = report_coop(work)
    left = process_running("StardewModdingAPI.exe") + process_running("Stardew Valley.exe")
    if left:
        print("WARNING: game processes still running:", left)
    return code


def _server_checked_ids(server_log):
    checked = set()
    for line in Path(server_log).read_text(errors="replace").splitlines():
        if "Incoming message: " not in line or "LocationChecks" not in line:
            continue
        try:
            for m in json.loads(line.split("Incoming message: ", 1)[1]):
                if m.get("cmd") == "LocationChecks":
                    checked.update(m["locations"])
        except ValueError:
            pass
    return checked


def _server_has_check(server_log, locs, name):
    ids = {v: k for k, v in locs.items()}
    return ids.get(name) in _server_checked_ids(server_log)

def report_coop(work):
    locs = {int(k): v for k, v in json.loads((work / "locations.json").read_text()).items()}
    flags = work / "flags"
    server = (work / "server.log").read_text(errors="replace")
    logs = {p.stem[len("SMAPI-"):]: p.read_text(errors="replace") for p in sorted(work.glob("SMAPI-*.txt"))}
    lines, ok = [], True

    def check(cond, text):
        nonlocal ok
        ok &= bool(cond)
        lines.append(("PASS  " if cond else "FAIL  ") + text)

    def snap(role, tag):
        try:
            return json.loads((flags / f"{role}.snap.{tag}.json").read_text())
        except (OSError, ValueError):
            return None

    def ap_errors(text):
        return [l for l in text.splitlines() if re.match(r"\[\d\d:\d\d:\d\d ERROR ", l) and ("StardewArchipelago" in l.split("]")[0] or "APSmokeTest" in l.split("]")[0])]

    for role in ("host", "farmhand-a1", "farmhand-a2", "farmhand-a3", "farmhand-a4", "host2", "farmhand-r", "farmhand-late"):
        text = logs.get(role, "")
        # Errors after SMAPI starts disposing (game closing) are shutdown races, e.g. an AP "left the game" chat line
        # arriving after the content manager is gone; counted but not failed.
        live, _, closing = text.partition("TRACE SMAPI] Disposing...")
        err = ap_errors(live)
        unexpected = [l for l in err if not any(k in l for k in KNOWN_BENIGN_ERRORS)]
        late = ap_errors(closing)
        check(text and not unexpected, f"{role} log: {len(err)} ERROR from StardewArchipelago/APSmokeTest, {len(unexpected)} unexpected"
              + (f", {len(late)} during shutdown" if late else "") + ("" if text else " (LOG MISSING)"))
        lines.extend("      ERR " + l[:240] for l in unexpected[:8])

    fh = logs.get("farmhand-a1", "")
    check("Farmhand connected to Archipelago" in fh, "farmhand connected through the host's handshake")
    names = re.findall(r'"cmd": ?"Connect".*?"name": ?"([^"]*)"', server)
    check(names.count(SLOT) >= 8, f"server Connect packets for {SLOT}: {names.count(SLOT)} (want >= 8: 2 hosts + 6 farmhand joins)")
    check("source HostNewFarm" in logs.get("host", ""), "host farm created through Co-op > Host New Farm")
    cab = re.search(r"cabins=(\d+)", logs.get("host", ""))
    check(cab and int(cab.group(1)) >= 2, f"cabins on the new farm (1 from the menu + 1 for the late joiner): {cab.group(1) if cab else 'NOT FOUND'}")

    S = {f"{r}.{t}": snap(r, t) for r in ("host", "farmhand") for t in
         ("d1", "j1", "j2", "d1b", "d2pre", "d2", "d2f", "d3", "d3s", "d4pre", "d4", "r1", "r2", "late")}
    need = [k for k in S if not k.endswith(("r1", "r2", "late"))]
    have = all(S[k] for k in need)
    check(have, "session 1 snapshots written by both games" + ("" if have else f" (missing: {[k for k in need if not S[k]]})"))
    if have:
        h1, f1, h1b, f1b = S["host.d1"], S["farmhand.d1"], S["host.d1b"], S["farmhand.d1b"]
        h2p, f2p, h2, f2 = S["host.d2pre"], S["farmhand.d2pre"], S["host.d2"], S["farmhand.d2"]
        h4, f4 = S["host.d4"], S["farmhand.d4"]
        # [1] team start-up runs on the host only
        for t in ("j1", "j2"):
            h = S[f"host.{t}"]
            check(h["money"] == h1["money"] and h["giftBoxes"] == h1["giftBoxes"],
                  f"farmhand rejoin {t} on day 1: money {h1['money']} -> {h['money']}, starter gift boxes {len(h1['giftBoxes'])} -> {len(h['giftBoxes'])}")
            f = S[f"farmhand.{t}"]
            check(f["maxItems"] == f1["maxItems"] and f["inventoryTools"] == f1["inventoryTools"],
                  f"farmhand rejoin {t}: backpack {f1['maxItems']} -> {f['maxItems']}, tools {f1['inventoryTools']} -> {f['inventoryTools']}")
        check(f1["restrictionsApplied"] and not f1["inventoryTools"], f"farmhand first join: starting restrictions applied once (tools {f1['inventoryTools']}, backpack {f1['maxItems']})")

        def letters(s, word):
            alt = word.replace("_", " ")
            return [m for m in s["mailbox"] + s["apLettersReceived"] if word in m or alt in m]
        lines.append(f"      mailbox host d2pre: {h2p['mailbox']}")
        lines.append(f"      mailbox farmhand d2pre: {f2p['mailbox']}")
        check(len(letters(h2p, "Money")) == 1 and not letters(f2p, "Money"), f"team letter: money letter for the host x{len(letters(h2p, 'Money'))}, farmhand x{len(letters(f2p, 'Money'))}")
        for word in ("Backpack", "Dumpling", "Friendship_Bonus", "Henchman"):
            hh, ff = letters(h2p, word), letters(f2p, word)
            want = 2 if word == "Backpack" else 1   # Backpack: the start_without starting backpack plus the one sent
            check(len(hh) == want and len(ff) == want, f"per-farmer letter '{word.replace('_', ' ')}': host x{len(hh)}, farmhand x{len(ff)}")
        delta = h2["money"] - h1b["money"]
        check(delta == 500, f"money: host {h1b['money']} -> {h2['money']} (delta {delta}, want exactly one grant of 500); farmhand sees {f2['money']} (shared wallet)")
        check(f2["money"] == h2["money"], "farmhand wallet equals host wallet after the mail")
        bh, bf = h2["maxItems"] - h1["maxItems"], f2["maxItems"] - f1["maxItems"]
        check(bh > 0 and bh == bf, f"backpack: host {h1['maxItems']} -> {h2['maxItems']}, farmhand {f1['maxItems']} -> {f2['maxItems']}")
        check(not h1["knowsFishDumpling"] and not f1["knowsFishDumpling"] and h2["knowsFishDumpling"] and f2["knowsFishDumpling"],
              f"recipe Fish Dumpling: host {h1['knowsFishDumpling']} -> {h2['knowsFishDumpling']}, farmhand {f1['knowsFishDumpling']} -> {f2['knowsFishDumpling']}")
        check(h2["apFriendAbigail"] > h1["apFriendAbigail"] and f2["apFriendAbigail"] > f1["apFriendAbigail"],
              f"friendship bonus (AP points, Abigail): host {h1['apFriendAbigail']} -> {h2['apFriendAbigail']}, farmhand {f1['apFriendAbigail']} -> {f2['apFriendAbigail']}")
        def axes(tools):   # upgrade levels of the axes in a tool list ("Copper Axe:1" -> "1"), pickaxes left out
            return [t.split(":")[-1] for t in tools if t.split(":")[0].endswith("Axe") and "Pickaxe" not in t]
        check(axes(h2["ownTools"]) == ["0"] and axes(f2["ownTools"]) == ["0"], f"Progressive Axe #1 (no axe yet): host {h2['ownTools']}, farmhand {f2['ownTools']}")
        # [3] AP XP survives a mid-day leave + a night the farmhand missed
        d2f, d3 = S["farmhand.d2f"], S["farmhand.d3"]
        check(d2f["apXpFishing"] > f2["apXpFishing"] and d3["apXpFishing"] == d2f["apXpFishing"],
              f"farmhand AP fishing XP: {f2['apXpFishing']} -> {d2f['apXpFishing']} after the checks, {d3['apXpFishing']} after leaving mid-day and rejoining next day")
        # [4] per-farmer progressive tools upgrade only the receiving farmer's tool
        hs, fs = S["host.d3s"], S["farmhand.d3s"]
        lines.append(f"      chest tools d3 after stash: {hs['chestTools']}")
        lines.append(f"      chest tools d4 after mail: {h4['chestTools']}")
        check(axes(hs["ownTools"]) == ["0"] and axes(fs["ownTools"]) == ["0"] and not axes(hs["inventoryTools"]) and not axes(fs["inventoryTools"]),
              f"both axes stashed in farm chests and tagged: host {hs['ownTools']}, farmhand {fs['ownTools']}")
        check(axes(h4["ownTools"]) == ["1"] and axes(f4["ownTools"]) == ["1"] and sorted(axes(t.split(":", 1)[1].rsplit(":", 1)[0] for t in h4["chestTools"])) == ["1", "1"],
              f"Progressive Axe #2 with both axes in farm chests: host {h4['ownTools']}, farmhand {f4['ownTools']} (each exactly one level)")
        h3 = S["host.d3"]
        check(h1["buildings"] == h4["buildings"] and h1["pets"] == h4["pets"],
              f"world after three shared days: buildings {len(h1['buildings'])} -> {len(h4['buildings'])} {h4['buildings']}, pets {h1['pets']} -> {h4['pets']}")
        check(f4["buildings"] == h4["buildings"], f"farmhand sees the same buildings as the host ({len(f4['buildings'])})")
        lines.append(f"      cursors d4: farmhand {f4['cursor']}, host processed {h4['processedItems']}; farmhand apXpFishing {f4['apXpFishing']}")
    for name in COOP_FARMHAND_CHECKS + COOP_HOST_CHECKS:
        who = "farmhand" if name in COOP_FARMHAND_CHECKS else "host"
        check(_server_has_check(work / "server.log", locs, name), f"server got {who}-fired check '{name}'")
    fired = [l for t in logs.values() for l in t.splitlines() if "farmhand fired" in l]
    lines.append("      " + (fired[0][fired[0].find("farmhand fired"):][:220] if fired else "farmhand fired: NOT FOUND"))

    r1h, r1f, r2h, r2f, lh, lf = (S[k] for k in ("host.r1", "farmhand.r1", "host.r2", "farmhand.r2", "host.late", "farmhand.late"))
    have2 = all([r1h, r1f, r2h, r2f]) and have
    check(have2, "reload session snapshots written by both games")
    if have2:
        h4, f4 = S["host.d4"], S["farmhand.d4"]
        check(r2h["money"] == h4["money"], f"reload: money {h4['money']} -> {r2h['money']} (no replay)")
        check(r2h["maxItems"] == h4["maxItems"] and r2f["maxItems"] == f4["maxItems"],
              f"reload: backpack host {h4['maxItems']} -> {r2h['maxItems']}, farmhand {f4['maxItems']} -> {r2f['maxItems']}")
        check(r2h["ownTools"] == h4["ownTools"] and r2f["ownTools"] == f4["ownTools"], f"reload: tools host {r2h['ownTools']}, farmhand {r2f['ownTools']}")
        check(r1f["cursor"] == f4["cursor"] and r1f["cursor"] is not None, f"reload: farmhand cursor {f4['cursor']} -> {r1f['cursor']}")
        check(r1h["processedItems"] == h4["processedItems"], f"reload: host processed items {h4['processedItems']} -> {r1h['processedItems']}")
        for role, before, after in (("host", S["host.d4pre"], r1h), ("farmhand", S["farmhand.d4pre"], r1f)):   # d4pre = what the day-4 save holds
            old = [m for m in before["mailbox"] if "|" in m]
            new = [m for m in after["mailbox"] + after["mailForTomorrow"] if "|" in m and m not in old]
            check(not new, f"reload: no AP letters re-sent to the {role} ({len(old)} unopened in the day-4 save kept, {len(new)} new: {new[:3]})")
        check(r1f["apXpFishing"] == f4["apXpFishing"] and f4["apXpFishing"] > 0, f"reload: farmhand AP fishing XP {f4['apXpFishing']} -> {r1f['apXpFishing']}")
        check(r1f["apFriendAbigail"] == f4["apFriendAbigail"], f"reload: farmhand AP friendship {f4['apFriendAbigail']} -> {r1f['apFriendAbigail']}")
        check(r2h["buildings"] == h4["buildings"] and r2h["pets"] == h4["pets"], f"reload: buildings {len(r2h['buildings'])}, pets {r2h['pets']}")
    check(lh and lf, "late joiner snapshots written")
    if lh and lf:
        check(lf["player"] == "Late" and lf["restrictionsApplied"], f"late joiner {lf['player']} (first join on day {lf['day']}): starting restrictions applied")
        check(lf["maxItems"] == lh["maxItems"] and lf["ownTools"] == lh["ownTools"],
              f"late joiner ends like the host: backpack {lf['maxItems']} vs {lh['maxItems']}, tools {lf['ownTools']} vs {lh['ownTools']}")
        check(lh["money"] == S["host.r2"]["money"] if S["host.r2"] else False, f"late join leaves the shared money alone: {lh['money']}")
    coop_lines = [l for t in logs.values() for l in t.splitlines() if "[coop]" in l or "caught up on received items" in l]
    lines.append(f"client co-op item lines: {len(coop_lines)}")
    lines.extend("      " + l[l.find("]") + 1:].strip()[:200] for l in coop_lines[:40])
    lines.append("")
    lines.append("COOP OVERALL: " + ("PASS" if ok else "FAIL"))
    text = "\n".join(lines)
    (work / "report-coop.txt").write_text(text, encoding="utf-8")
    print(text)
    return 0 if ok else 1


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
