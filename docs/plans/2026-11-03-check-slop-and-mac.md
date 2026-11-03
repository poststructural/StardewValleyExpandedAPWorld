# Plan: more SVE checks, Windows + Mac, and the CP patch (2026-11-03)

Continues `HANDOFF.md` §6. The goal is to turn "SVE loads" into "SVE is worth playing": map SVE 1.15
content into the existing sanity options, make the build and install work on Windows and Mac, and
ship the AP gating patch the integration depends on.

Gap numbers come from a census of SVE 1.15.11 data against the pinned world (scratch survey,
2026-11-03). They are estimates until each row is added and tested.

## What I found that changes the handoff

- **`AURORA_EVENT`, `MORGAN_EVENT` and `Clint2Again` are dead constants.** Nothing in the mod reads
  them. The Aurora and Morgan gates work through the mail flags `apAuroraVineyard` and
  `apMorganSchooling`, which only the CP patch reads. So §6.3 shrinks to cleanup plus verifying the
  event ids the mod *does* use (`sveEventSpecialOrders`, the rune events, Lance, Kittyfish, Scarlett).
- **The 1.15 events the CP patch must gate:** Aurora Vineyard purchase `746153081`, Morgan's
  apprenticeship `5978924`, the Apples junimo event `77759254` (now in `OtherEvents/SpecialOrder.json`).
- **Witchybun's CP patch has no licence file.** I will write our own patch from the facts (which
  events and orders to gate), not copy theirs, and replace its `.tbin` with a CP `MapTiles` edit or an
  original map file.
- **Its `content.json` includes lowercase paths for mixed-case files.** That breaks on case-sensitive
  file systems. Our port uses exact-case paths.
- **The client handles most new checks by name.** Shipsanity, fishsanity, cropsanity, cooksanity,
  chefsanity, craftsanity, eatsanity, museumsanity and friendsanity are generic. Special orders,
  vendor checks and entrances are hard-coded and need mod code.

## Phases

### P1. Cross-platform tooling and CI (Windows + Mac)

- Replace the four PowerShell 5.1 scripts with Python (`scripts/*.py`) that run on Windows, macOS
  and Linux. No `.ps1` wrappers are kept (done).
- `build-mod` finds the game on both OSes (Steam default paths, plus `--game-path`), and uses
  `dotnet` on both.
- Release packaging: one cross-platform zip (the mod is managed net6, no native parts; to be
  confirmed), the CP patch, the apworld, and `docs/setup.md` with Windows and Mac install steps.
- GitHub Actions on ubuntu, windows and macos: apply patches, build the apworld, and run
  `pytest worlds/stardew_valley/test` plus our own tests. The mod build needs game DLLs, so CI
  skips it.

### P2. CP patch port and identifier hygiene

- New `cp/[CP] StardewAP - SVE Patch/` written from scratch for 1.15. It gates Aurora behind
  `apAuroraVineyard`, Morgan behind `apMorganSchooling`, and adds the Grandpa's Shed order and drop box.
  Built into the release zip, with `ExtraRequirementsVersions` restored in `ModVersions.cs`.
- Fix the special-order walker. Then add an automated identifier check that compares every SVE
  id/flag/name the mod uses to SVE 1.15 data. It runs locally against an SVE install and is skipped
  in CI.
- Remove the dead constants.

### P3. Check slop: generic categories (world + id table only)

| Category | New locations (est.) | Notes |
|---|---|---|
| Shipsanity | ~84 | skip key items and Joja items |
| Eatsanity | ~75 | SVE food, fish and forage |
| Cooksanity + chefsanity | ~32 | 16 recipes; 9 unlock at 3 hearts |
| Fishsanity | 17 | needs `fish_data` rows and new fishing regions |
| Friendsanity | ~14 | Henchman (~10) needs a one-line alias; Scarlett is datable in 1.15 (+4) |
| Craftsanity | 9 | |
| Museumsanity | 8 | 7 artifacts + Galdoran Gem |
| Cropsanity | 4–7 | Cucumber, Butternut Squash, Sweet Potato, Gold Carrot (+ fruit trees) |

That totals roughly **240 more SVE locations**, all behind existing options, so default yamls are
unchanged in size.

- Every new row gets logic (region + requirements) and an id, and the mod's
  `IdTables/*.json` is regenerated with the world's own `scripts/export_*.py`.
- **Id range:** new ids go in a block upstream does not use, so they cannot collide later. I'll pick
  it from the CSV and record it in `versions.lock`.
- Fix stale data found by the survey: Scarlett's datable flag, and the Haste/Hero/Armor Elixir
  "Recipe" locations (1.15 unlocks them by Combat level; verify in game before changing).

### P4. Check slop: code-needed categories

- 4–7 special orders (A Witch Offering, The Legendary Trio, Townhouse Project, Aurora Vineyard
  Purchase), which need `SpecialOrderNames` plus injections.
- About 35 unmapped `Custom_` locations (Zuzu City block) for logic and entrance rando. These are
  fuzzy matches, so they get confirmed one by one.
- SVE vendor purchase checks are deferred. That is a large mod feature, and I'd do it only after P3
  ships.

### P5. Verification and release

- **Tests:** each new location resolves to a real SVE 1.15 item/NPC name. Ids are unique and match
  the mod table. There are generation fills over many seeds with each sanity option, and upstream's
  SVE tests stay green. Codex reviews each patch before it goes in the game; it does not review docs.
- **Live:** a purpose-built seed (§6.1) with the new categories, then a 30-minute session that
  confirms SVE checks reach the server. That needs a playtest from you, and a Mac playtest if you
  have one available, since I have no Mac.
- **Release:** GitHub release v0.1.0 with the apworld, mod+CP zip and checksums.

## Leaving alone

- No SVE code or assets in the repo. Upstream world/mod stay pinned and patched, not forked.
- No change to vanilla content or default option values.
- SVE vendor checks and Phase 4 decompile diffing (§6.6) stay for later.

## Order

P1 → P2 → P3 → P5 (release 0.1.0) → P4. P3's categories are independent and can go to parallel
subagents, one category each, each verified by me before it merges.
