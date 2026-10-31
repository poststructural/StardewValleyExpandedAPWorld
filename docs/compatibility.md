# Compatibility

What "supported" means here: a specific SVE version, on a specific Stardew Valley build, with a
specific SMAPI, against a specific Archipelago tag. Anything else is untested and will be reported as
such — the mod's version gate exists precisely so players find out before they connect, not after.

## Current pin

See [`versions.lock`](../versions.lock). As of the last validated run:

| Component | Version |
|---|---|
| Stardew Valley | 1.6.15 (build 24356) |
| SMAPI | 4.5.2 |
| Stardew Valley Expanded | 1.15.11 |
| Content Patcher | 2.9.1 |
| Farm Type Manager | 1.26.1 |
| Archipelago | 0.6.8 (`54803be0`) |
| StardewArchipelago | 8.1.12-era main (`abbef519`) |

SVE 1.15.11 runs natively on SDV 1.6.15 — **no rebuilt SVE code DLL is shipped or required**. See
[spike-01](spike-01-sve-loads-natively.md).

## Why the pin is narrow

SVE is closed-source and ships breaking content changes in minor versions: 1.15 added a new farm
type (Frontier Farm), 18 maps, a marriage candidate (Scarlett), a new NPC (Henchman), 12 fish, 4
crops and ~26 recipes, and it injects SVE items into Community Center bundles by default. Every one
of those touches a mapping in `worlds/stardew_valley` or a Harmony target in the mod.

Upstream disabled SVE because that cadence outran a volunteer. The pin is how we refuse to repeat it:
SVE ships, we stay put, and the version gate tells players why.

## Validation checklist

Run before moving any pin in `versions.lock`. Both halves must pass; a green generator with a broken
client is not a release.

### World (generator)

1. `scripts/build-world.ps1` produces an `.apworld` that loads in the pinned Archipelago build
   (`ArchipelagoGenerate.exe` reports no world-load error).
2. Generate with `mods: [Stardew Valley Expanded]` together with each supported combination:
   vanilla-only, SVE + Ginger Island, SVE + Distant Lands, SVE + all enabled mods.
3. `pytest worlds/stardew_valley/test` passes, including `test/mods/TestSVE.py`,
   `TestFishsanity.py`, `TestMonstersanity.py`, `TestFill.py` and the long mods test.
4. Location and item counts are plausible against the previous pin (no silent content loss — this
   matters more than the tests passing).
5. Spot-check that SVE-only locations are reachable-only with SVE items, and that non-SVE slots are
   byte-identical to upstream for the same seed (our patch must not leak into vanilla games).

### Mod (client)

6. `scripts/build-mod.ps1` builds clean against the pinned game DLLs.
7. Launch the testbed with the built mod + SVE 1.15.11 + CP + FTM. SMAPI log has **zero** patch
   exceptions at startup; every SVE Harmony target still binds.
8. Connect to an SVE slot. Confirm: version gate accepts 1.15.11, no "incompatible mod" false
   positive, SVE checks report, SVE items grant.
9. Exercise the SVE-specific subsystems that have their own code paths: shop replacement, cutscene
   injections, Junimo shop stock, Nexus warp unlocks, Grandpa's Shed, Aurora Vineyard, Fable Reef.
10. Load a save with SVE *disabled* on the slot side and confirm the "incompatible mod" guard fires
    rather than silently corrupting the save.

## When SVE ships an update

1. Do nothing to `main`. The pin holds.
2. Open an issue titled `SVE <version> re-validation` capturing the changelog deltas that look
   structural (maps, NPCs, quests, bundle changes).
3. Run the checklist against the new version in a scratch branch.
4. Move the pin and the mod's `ModVersions` entry together, in one commit, with the checklist
   results pasted into the PR.

## When Archipelago ships a release

The world patch is a diff against `worlds/stardew_valley`; rebase it onto the new tag before touching
anything else. If the rebase conflicts, the conflict is information: upstream changed something our
integration depends on, and that is the first thing to read.
