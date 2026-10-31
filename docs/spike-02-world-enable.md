# Spike 02 (world half) — SVE re-enables in the generator

**Date:** 2026-10-31
**Question:** with `ModNames.sve` removed from `disabled_mods`, does the pinned Archipelago 0.6.8 world
accept SVE and generate a seed that actually contains SVE content?

**Answer: yes.** Generation succeeds, and the resulting seed contains SVE locations that a vanilla
seed does not.

## Control vs patched

Same yaml, same seed (`--seed 1`), Archipelago 0.6.8, only the `stardew_valley.apworld` differs.

| Run | `mods:` | Result |
|---|---|---|
| Upstream 0.6.8 world | `[Stardew Valley Expanded]` | **rejected**: `OptionError: Found unexpected key Stardew Valley Expanded in Mods. Allowed keys: frozenset({... 15 mods ...})` |
| This repo's patched world | `[Stardew Valley Expanded]` | **generated**, exit 0, `Location Count: 492` |
| This repo's patched world | `[]` (vanilla control) | generated, exit 0, `Location Count: 472`, zero SVE hits |

SVE-only content observed in the patched spoiler log: Aurora Vineyard (5), Fable Reef (2), Junimo
Woods (1), Sprite Spring (1), Grandpa's Shed (9), Nexus warps (10), plus SVE NPC checks (Andy 14,
Victor 9, Sophia 2, Lance 2, Marlon 2, Scarlett 1, Morgan 1).

## Two build bugs this surfaced

1. **`archipelago.json` in the repo has no container fields.** AP's own build injects
   `compatible_version` and `version` (and here, `maximum_ap_version`); the source manifest only has
   `game`, `authors`, `minimum_ap_version`, `world_version`. Without them the loader raises
   `InvalidDataError: compatible_version - This might be the incorrect world version for this file`
   and the world registers as version `0.0.0`, which then fails the `requires.game` check:
   *"Settings reports required version of world Stardew Valley is at least 7.4.25, however world is of
   version 0.0.0."*
   `scripts/build-world.ps1` now injects them from `versions.lock.apworld_container`.

2. **Packaging the tree.** `Copy-Item -Path "dir\*"` drops subdirectories, and
   `Get-ChildItem -Recurse -Directory -Include '__pycache__' | Remove-Item -Recurse` matches *every*
   directory in PowerShell 5.1, deleting the staged world. Both are fixed; the artifact now has 393
   entries instead of 8.

## Reproduce

```powershell
./scripts/fetch-upstream.ps1     # or seed .cache from a pinned local checkout
./scripts/apply-patches.ps1
./scripts/build-world.ps1        # -> artifacts/stardew_valley.apworld

# swap into an AP 0.6.8 install (keep the original!), generate, restore
#   lib/worlds/stardew_valley.apworld  <- artifacts/stardew_valley.apworld
#   ArchipelagoGenerate.exe --player_files_path <dir> --outputpath <dir> --seed 1
```

Minimal player file:

```yaml
name: SVE_Spike
game: Stardew Valley
requires:
  version: 0.6.8
  game:
    Stardew Valley: 7.4.25
Stardew Valley:
  mods:
    - Stardew Valley Expanded
```

## Caveats before this counts as "supported"

- The +20 location delta is for **default options**. Friendsanity, shipsanity, chefsanity and
  cropsanity will each amplify SVE content and are untested here.
- 1.15 content is not reconciled: SVE 1.15 added Henchman, made Scarlett marriageable, and added
  Frontier Farm / 18 maps / 12 fish / 4 crops / ~26 recipes. Some of those are already reachable
  through generic code paths; others need explicit mapping. Generation passing does not mean every
  1.15 check exists or is correctly gated.
- The mod side is not yet built or connected, so "the seed generates" is not "the slot is playable".

## Next

Mod half of spike 02: build the patched mod with `scripts/build-mod.ps1`, drop it into the testbed,
connect to this generated seed, and read the SMAPI log for SVE Harmony binding failures.
