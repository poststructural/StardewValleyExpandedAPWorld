# Handoff — StardewValleyExpandedAPWorld

Everything a fresh engineer (or agent) needs to take this from "works in a testbed" to "maintainable
release". Written 2026-11-03 at the point the first end-to-end session passed.

---

## 1. What this project is

Re-enable **Stardew Valley Expanded** support in the Stardew Valley Archipelago integration, against
**SVE 1.15.11**, **SDV 1.6.15** and **Archipelago 0.6.8**, and keep it maintainable afterwards.

Upstream disabled SVE in `StardewArchipelago 7.3.2` (Dec 2025) because the integration needed a
rebuilt SVE code DLL on every game update and nobody maintained it. This repo re-enables the existing
integration, pinned, and owns the drift.

**Repo:** https://github.com/poststructural/StardewValleyExpandedAPWorld (public, BSD-3, `main`)

---

## 2. State at handoff

### Proven working (testbed, not speculation)

| Layer | Evidence |
|---|---|
| SVE 1.15.11 loads on SDV 1.6.15 / SMAPI 4.5.2 with **no rebuilt DLL** | `docs/spike-01-sve-loads-natively.md` |
| Generator accepts `Stardew Valley Expanded` and produces SVE content | 492 locations vs 472 vanilla, same seed; `docs/spike-02-world-enable.md` |
| Client connects, version gate passes | `version '8.1.12' connected to a multiworld generated with APWorld version '8.1.12'` |
| Save loads with every SVE Harmony target bound | WARN 5 / ERROR 0 |
| Shops repoint, day cycle completes | `StardewArchipelago edited Data/Shops` ×12 on day rollover |
| Items deliver | `!getitem Iridium Fireplace` → arrives **as a letter** |

### Bugs found and fixed

| # | Bug | Fix |
|---|---|---|
| 1 | apworld built without `compatible_version`/`version` → registers as 0.0.0, `requires.game` rejects | `scripts/build_world.py` injects them from `versions.lock` |
| 2 | Packaging dropped subdirectories, then deleted the staged tree | robocopy; `-Filter` not `-Include` |
| 3 | Patch files written UTF-16 by PowerShell redirection | regenerate with raw byte redirection |
| 4 | World/mod version drift → "Please downgrade to a compatible mod version" | `world_version` stamped from the paired mod manifest |
| 5 | `VillagerUnlockManager` threw `ArgumentException` on duplicate arrival name once SVE adds Marlon/Gunther/Morris | `patches/mod/0002` |
| 6 | Item receipt was silent (`_itemManager?.`) | `patches/mod/0003` traces event + manager state |

### NOT yet proven

- **SVE location checks reaching the server.** The test seed has only quest-gated SVE checks, so
  nothing easy to fire. Needs a purpose-built seed (see §6.1).
- **The AP-gated SVE flags.** `apAuroraVineyard` and `apMorganSchooling` do not exist in SVE 1.15
  data — they only ever existed in Witchybun's CP patch, which has not been ported.
- **1.15 content coverage.** 1.15 additions (Frontier Farm, Henchman, Scarlett, 12 fish, 4 crops,
  ~26 recipes) are unmapped. Not broken — simply not randomized.

---

## 3. Repository layout

```
versions.lock          pinned: SDV 1.6.15/24356, SMAPI 4.5.2, SVE 1.15.11, AP 0.6.8, mod commit
patches/world/         diffs applied to Archipelago's worlds/stardew_valley
patches/mod/           diffs applied to StardewArchipelago
scripts/               fetch_upstream, apply_patches, build_world, build_mod, package_release, common (Python 3, stdlib only)
tests/                 unit tests for the scripts (python -m pytest tests -q)
.github/workflows/     ci.yml: fetch, patch, build apworld, Archipelago world tests on ubuntu/windows/macos
docs/                  status, compatibility, spikes, census, identifier check, knowledge programme
_analysis/             decompiled SVE + census JSON — GITIGNORED, never commit or redistribute
```

Current patches:

| Patch | What |
|---|---|
| `0001-enable-sve-content-pack` | removes `ModNames.sve` from `disabled_mods` in the world |
| `0001-enable-sve-and-retire-rebuilt-dll-requirement` | re-enables SVE in `ModVersions.cs`, drops the `AP_CP_SVE` requirement |
| `0002-dedupe-villager-arrival-unlocks` | duplicate guard in `VillagerUnlockManager` |
| `0003-trace-received-items` | replaces silent item receipt with a trace + warning |

---

## 4. How the integration is wired (read this before changing anything)

- **The apworld lives in Archipelago's monorepo**: `worlds/stardew_valley`. It is pinned here and
  patched, not forked. `versions.lock` names the commit.
- **The mod lives in `agilbert1412/StardewArchipelago`**, patched the same way.
- **SVE is gated, not deleted.** World: `options/options.py` → `disabled_mods` set. Mod:
  `Constants/Modded/ModVersions.cs` → the SVE row is commented out.
- **Version pairing is mandatory.** The mod refuses a slot whose `client_version` differs from its own
  `ModVersion`. `build_world.py` stamps `world_version` from the paired mod manifest; do not break
  that coupling.
- **The integration keys off SVE *data*, not SVE *code*.** Event ids, mail flags, item ids, NPC ids.
  SVE recompiles are harmless; SVE renumbering fails **silently**. See `docs/sve-identifier-check.md`.
- **AP items arrive by mail**, not inventory (`APItemManager.ProcessItem` → `ProcessItemAsLetter`).
  Test via mailbox or save file, never the bag.

---

## 5. Environment

| Thing | Path / value |
|---|---|
| This repo | `C:\Users\unowi\Documents\APWorldMaker\StardewValleyExpandedAPIntegration\STE-APWorld` |
| Testbed (disposable, SDV 1.6.15 + SMAPI + SVE) | `...\StardewValleyExpandedAPIntegration\_testbed\sdv-sve` |
| Testbed logs | `_testbed\logs\` |
| Generated seeds | `_testbed\seeds\sve-spike-1.zip` |
| Live Steam install (regular SVE, no AP) | `C:\Steam\steamapps\common\Stardew Valley` |
| Archipelago 0.6.8 | `C:\ProgramData\Archipelago` |
| Saves (shared by all installs) | `%APPDATA%\StardewValley\Saves` |
| SVE source payload | `...\StardewValleyExpandedAPIntegration\SVE_Mod` |
| Original 1.14 integration (Witchybun) | `...\Witchybun-Stardew Valley Archipelago Content Patcher Content` |

Tooling: `dotnet` 10 SDK (builds net6.0 via NuGet targeting pack), Python 3.14 + `json5`,
`ilspycmd` (`%USERPROFILE%\.dotnet\tools`), `gh` authenticated as `poststructural`.

**git needs `-c http.sslBackend=openssl`** — the default schannel backend fails with
`SEC_E_NO_CREDENTIALS` on this machine.

---

## 6. Work remaining, in priority order

### 6.1 Verify SVE check reporting  ← do this first

Currently unproven because the seed has no reachable SVE check.

1. Write a player yaml with `friendsanity`, `shipsanity`, `cropsanity` enabled plus
   `mods: [Stardew Valley Expanded]`.
2. Build + generate (see §7), start server on a free port.
3. New throwaway save, meet an SVE NPC (Andy/Sophia) or ship an SVE item.
4. Confirm the check arrives server-side (`--log_network` shows `LocationChecks`).

Acceptance: at least one SVE-specific check registered on the server, no client errors.

### 6.2 Port `[CP] StardewAP - SVE Patch` 2.1.2 to 1.15  ← load-bearing

Source: `Witchybun-.../[CP] StardewAP - SVE Patch` (5 JSON files: `Events/ModifiedEventReqs.json`,
`Maps/GrandpaShedPatch.json` + `.tbin`, `SpecialOrders/GrandpasShed.json`, `i18n`).

Why it matters: `apAuroraVineyard` and `apMorganSchooling` exist **only** here; without them the AP
gating for Aurora Vineyard and Morgan's schooling is a no-op. Check each hook still exists in 1.15
(Grandpa's Shed map and special order do; event requirement edits need re-checking against
`746153081`–`746153087`).

Deliver: a new `patches/cp/` half, built into an installable CP mod, and re-add the
`ExtraRequirementsVersions` entry in `ModVersions.cs`.

### 6.3 Fix stale identifiers

From `docs/sve-identifier-check.md`:

- `AURORA_EVENT "658059254"` → 1.15 uses `746153081`–`746153087` (`code/OtherEvents/Aurora.json`).
- `MORGAN_EVENT "658078924"` → find the Morgan schooling event id in 1.15.
- `Clint2Again` mail flag no longer exists → find the railroad-boulder equivalent.
- Special-order name scan was inconclusive (walker bug). Fix and re-run before trusting that row.

Entry points: `Locations/CodeInjections/Modded/SVE/SVECutsceneInjections.cs`,
`Items/Unlocks/Modded/SVEUnlockManager.cs`.

### 6.4 1.15 content mapping

See `docs/sve-1.15-assets.md`: 179 objects, 134 big craftables, 44 fish, 26 cooking recipes,
12 crops, 12 crafting recipes, 37 NPCs, 71 custom locations, 25 SVE vendors.

Decide per item: already randomized / mis-gated / add / out of scope. Friendsanity is the biggest hole
(world has ~14 SVE NPCs, 1.15 names ~25 including Henchman, Hank, Treyvon, Jadu, Jolyne, Camilla).

### 6.5 Release plumbing

- artifacts + checksums, install docs, a version gate that tells players which SVE build is expected
- CI that builds the world and runs `pytest worlds/stardew_valley/test`
- decide whether to patch AP 0.6.8's 7.4.25 world or move the pin to a world line matching the mod

### 6.6 Knowledge phases 2, 4, 5

See `docs/sve-knowledge-programme.md`. Phase 4 (decompile Witchybun's 1.14.31 build and diff against
1.15.11) is the biggest single effort and only worth starting once 6.2–6.3 are done.

---

## 7. Build and test loop

```sh
# 1. sources (first time, or after changing versions.lock)
python scripts/fetch_upstream.py

# 2. apply the patch series onto the pinned checkouts in .cache/
python scripts/apply_patches.py

# 3. apworld  -> artifacts/stardew_valley.apworld (stamps world_version from the mod manifest)
python scripts/build_world.py

# 4. generate a seed with the patched world
#    swap it into C:\ProgramData\Archipelago\lib\worlds\stardew_valley.apworld (KEEP THE ORIGINAL),
#    run ArchipelagoGenerate.exe --player_files_path <dir> --outputpath <dir> --seed 1,
#    then restore the original apworld
#    player yaml must include:
#      requires: { version: 0.6.8, game: { Stardew Valley: <mod version> } }
#      Stardew Valley: { mods: [ Stardew Valley Expanded ] }

# 5. server
& "C:\ProgramData\Archipelago\ArchipelagoServer.exe" --port 38282 --log_network --disable_save <seed.zip>

# 6. mod  (close the game first: locked DLLs fail the build. build_mod.py passes EnableModDeploy=false and
#          EnableModZip=false, so it no longer auto-deploys into a Mods folder; copy artifacts/ yourself)
python scripts/build_mod.py --game-path "_testbed/sdv-sve"

# 6b. release bundle -> artifacts/release/ (needs steps 3 and 6; fails on non-managed binaries)
python scripts/package_release.py

# 7. launch testbed, load save, read %APPDATA%\StardewValley\ErrorLogs\SMAPI-latest.txt
```

Known-good numbers to compare against: SVE seed = **492 locations**, vanilla = **472**; testbed run
should be WARN 5 / ERROR 0 (the 5 are missing post-7.4.25 slot-data keys and are benign).

---

## 8. Traps that will cost you an afternoon

| Trap | Detail |
|---|---|
| Historical (PowerShell; scripts are Python now) | `Copy-Item "dir\*"` drops subdirectories; `-Recurse -Include` matches everything (deleted a staged tree once); `[CP]`/`[FTM]` need `-LiteralPath`. Still relevant if you shell out by hand. |
| PowerShell `>` redirection | writes UTF-16; `git apply` then fails with "No valid patches in input". Redirect via `cmd /c`. |
| `fetch_upstream.py` on a patched cache | when `.cache/<repo>` HEAD is not the pinned commit (e.g. local patch commits) it force-checks out the pinned commit, detaching HEAD and discarding applied patches. Recover with `git -C .cache/<repo> checkout main`. |
| apworld manifest | AP's own build injects `compatible_version`/`version`; the repo's `archipelago.json` lacks them. |
| `world_version` | must equal the mod's `ModVersion` or the client refuses the slot. |
| Harmony `AccessTools` | returns null for a missing member and several call sites tolerate it — a renamed SVE member looks like a working patch. |
| `connect_override` | in 8.1.12 it announces the new host but dials the old one with the new port. Use the save-creation form / server field instead. |
| `!getitem` | delivers by mail. Check the mailbox. |
| `Bepis_433789369` save | made with the AP mod; do not load it without AP installed. |
| Live Steam install | do not test against it; it is the player's install. Use `_testbed`. |
| Slot-data warnings | `entrance_randomization_behavior`, `journey_of_the_prairie_king`, `junimo_kart`, `help_wanted_quests`, `randomized_data` — expected with a `main` mod on a 7.4.25 world. |

---

## 9. Legal

- StardewArchipelago: BSD-3-Clause — keep `LICENSE.md` with any redistributed binary.
- Archipelago: MIT.
- **SVE is closed-source.** Never commit, publish or redistribute decompiled SVE code, and never ship
  a rebuilt SVE assembly. `_analysis/` is gitignored for this reason. Derived facts (counts, name
  lists, matrices) are fine.

---

## 10. Definition of done

1. A seed generated with `mods: [Stardew Valley Expanded]` on the pinned AP tag, with SVE checks that
   report correctly over a 30-minute session.
2. The mod builds from a clean checkout with `scripts/build_mod.py` and connects without warnings
   beyond the known five.
3. `docs/compatibility.md` checklist passes end to end, and `versions.lock` is the only place versions
   appear.
4. A named maintainer and a stated re-validation turnaround.
5. The CP patch shipped, so `apAuroraVineyard` / `apMorganSchooling` gating actually works.
