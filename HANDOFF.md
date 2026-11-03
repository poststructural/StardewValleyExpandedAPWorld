# Handoff — StardewValleyExpandedAPWorld

Everything a fresh engineer (or agent) needs to continue. Rewritten 2026-11-03 after v0.1.0:
cross-platform tooling, 226 new SVE checks, client-side SVE gating, and an automated in-game test.

---
## 1. What this project is

Re-enable **Stardew Valley Expanded** support in the Stardew Valley Archipelago integration, against
**SVE 1.15.11**, **SDV 1.6.15** and **Archipelago 0.6.8**, and keep it maintainable afterwards.

Upstream disabled SVE in `StardewArchipelago 7.3.2` (Dec 2025) because the integration needed a
rebuilt SVE code DLL on every game update and nobody maintained it. This repo re-enables the existing
integration, pinned, and owns the drift.

**Repo:** https://github.com/poststructural/StardewValleyExpandedAPWorld (public, BSD-3, `main`)

---

## 2. State (v0.1.0, 2026-11-03)

### Done this session (all pushed to `main`)

| Change | Files | Verified by |
|---|---|---|
| Repo moved to `poststructural/StardewValleyExpandedAPWorld`, history on the no-reply email | all | push |
| Python build scripts replace PowerShell; release packager; CI | `scripts/*.py`, `.github/workflows/ci.yml`, `tests/` | apworld byte-identical to the ps1 build except manifest formatting; CI green on ubuntu/windows/macos |
| fetch_upstream never forces the pin over local patch commits | `scripts/fetch_upstream.py` | ran against the live cache |
| 1.15 gating in the client, SVE quest-name fix, gates CP pack | `patches/mod/0004`, `0005`, `cp/` | smoke test; Codex review (found the warn-only pack issue, fixed in 0005) |
| 226 new SVE locations, 20 items | `patches/world/0002`, `scripts/sync_id_tables.py`, `tests/test_sve_names.py` | world suite 1144 passed / 0 failed; new `TestSVE115Content.py` incl. 10-seed max-sanity fills |
| Automated in-game smoke test | `tools/sve-smoketest/` | 9/9 paths PASS on the release build, every check confirmed in the server log |
| Player setup guide (Windows + Mac) | `docs/setup.md` | option values checked against `options.py` |

### What works (proven)

- Generation with `mods: [Stardew Valley Expanded]` on AP 0.6.8; the apworld declares min 0.6.4 / max
  0.6.8 (a test enforces it).
- In a real testbed save against a local server: shipsanity, fishsanity, cooksanity, eatsanity,
  craftsanity, friendsanity (incl. Henchman), museumsanity (new artifacts) and an SVE special order
  (`Quest: Grandpa's Shed`) all reach the server; items arrive by mail; the Aurora/Morgan events stay
  locked until their AP items arrive.
- Release bundle: one zip for Windows and Mac (managed DLLs only, checked by the packager).

### Known issues

- `GetQuestOfTheDay_BalanceQuests_Prefix` logs one ERROR per day: the 8.1.12 client expects
  `help_wanted_quests` slot data that the 7.4.25 world doesn't send. It falls back to vanilla. Same root
  cause as the 5 slot-data WARNs (§6 item 4).
- `LostAndFoundInjections.AnyIncomingLetterContainingKey` "Collection was modified": 1 in 4 runs, upstream race.
- Not exercised in game: donating at the moved Grandpa's Shed drop box (the CP patch applies with no
  errors), the Robin3-at-2554906 path, the Krobus 10-heart relax rule.
- **Mac is untested on hardware.** Nothing platform-specific ships, and CI builds and tests the world on macOS.
- The gate self-check binds 8 of 17 rules on day 1; SVE adds the rest later in the story. Unbound
  rules log at Debug, not Warn.

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
| world `0001-enable-sve-content-pack` | removes `ModNames.sve` from `disabled_mods` |
| world `0002-sve-1.15-content` | 226 SVE locations (ids 90001-90226) + 20 items (90001-90020), logic, tests |
| mod `0001-enable-sve-and-retire-rebuilt-dll-requirement` | re-enables SVE in `ModVersions.cs` |
| mod `0002-dedupe-villager-arrival-unlocks` | duplicate guard in `VillagerUnlockManager` |
| mod `0003-trace-received-items` | item receipt trace + warning |
| mod `0004-sve-1.15-gates-and-quest-names` | `SVEEventGates` (event gating by id), SVE order to `Quest: ...` names, Henchman alias, dead ids removed |
| mod `0005-require-sve-gates-pack` | the gates CP pack is required; self-check logs unbound rules at Debug |

Also: `cp/[CP] StardewAP - SVE Gates` (our Grandpa's Shed drop-box pack, no SVE content),
`tools/sve-smoketest` (automated in-game test), `docs/setup.md` (player guide).
The `.cache/` checkouts carry each applied patch as a local commit ("apply 000N locally"). The client
cache has `core.autocrlf=false`: upstream files are CRLF, and autocrlf rewrote whole files in a diff.

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

Plan file for all of these: `docs/plans/2026-11-03-check-slop-and-mac.md`.

1. **Playtest feedback** from Austin (Windows) and anyone on a Mac; fix what they hit.
2. **P4 special orders**: A Witch Offering, The Legendary Trio, Townhouse Project, Aurora Vineyard
   Purchase (`SpecialOrderNames` + injections + world rows). The client blocks SVE's own
   `UpdateSpecialOrders`, so `MorrisTod2/3`, `LegendaryTrio` and `HenchmanHouseRepaired` are never offered today.
3. **P4 unmapped areas**: ~35 `Custom_` locations (Zuzu City block) for logic and entrance rando, then
   the skipped content that needs them (Alligator, Swamp Crab, Diamond Carp, Razor Trout, swamp items).
4. **World/mod pairing**: the 7.4.25 world with the 8.1.12 client causes the slot-data warnings and
   the help-wanted ERROR. Either patch the client to tolerate the missing keys, or move the pin to a
   world line that matches the client.
5. Smaller: Galdoran Gem, Pineapple Custard Crepe and festival recipes, stale Haste/Hero/Armor Elixir
   recipe-shop rows, `Aurora Vineyard Reclamation` sharing the tablet's flag, SVE vendor checks.
6. Knowledge phases 2, 4, 5 (`docs/sve-knowledge-programme.md`).

## 7. Build and test loop

```sh
python scripts/fetch_upstream.py      # first time / after changing versions.lock
python scripts/apply_patches.py
python scripts/build_world.py         # -> artifacts/stardew_valley.apworld
python scripts/build_mod.py --game-path ../_testbed/sdv-sve   # game closed; syncs id tables first
python scripts/package_release.py     # -> artifacts/release/ (zip + apworld + SHA256SUMS)
python -m pytest tests -q

# world tests (py3.12 venv with AP deps at .cache/venv312; AP refuses Python 3.14)
cd .cache/archipelago && ../venv312/Scripts/python -m pytest worlds/stardew_valley/test -n auto \
    --ignore=worlds/stardew_valley/test/long --ignore=worlds/stardew_valley/test/performance

# end to end in the real game (~4 min, no human: generates, serves, builds, launches the testbed)
.cache/venv312/Scripts/python.exe tools/sve-smoketest/run.py --work-dir <scratch dir>
```

The smoke test hosts from `.cache/archipelago`, not `C:\ProgramData\Archipelago`, and only creates or
deletes saves named `APSmoke*`. A pass is `OVERALL: PASS` in `<work-dir>/report.txt`.

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

---

## 11. Continuation prompt

> Continue the Stardew Valley Expanded Archipelago project in
> `C:\Users\unowi\Documents\APWorldMaker\StardewValleyExpandedAPIntegration\STE-APWorld`
> (repo github.com/poststructural/StardewValleyExpandedAPWorld; commit with the no-reply email, no Claude
> trailer). Read `HANDOFF.md` (§2, §4, §6, §8) and `docs/plans/2026-11-03-check-slop-and-mac.md` first.
> Next task: §6 item 1 if there is playtest feedback, otherwise item 2 (the four missing SVE special
> orders). Acceptance: new world rows and client mapping, world suite green, and the smoke test extended
> with one completion per new order, reporting `OVERALL: PASS`.
