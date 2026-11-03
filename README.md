# StardewValleyExpandedAPWorld

Stardew Valley Expanded support for [Archipelago](https://archipelago.gg), maintained against current
Stardew Valley and current Archipelago.

The upstream Stardew Valley integration is already feature-complete for SVE — the content pack, the
regions, the logic and the mod-side patches all still exist in both codebases. They are **switched
off**, not deleted: one set membership in the world (`disabled_mods`) and one commented line in the
mod (`ModVersions.cs`). This repository exists to own that switch, keep it honest, and carry the
1.15.x content reconciliation that nobody has done.

## Status

| Milestone | State |
|---|---|
| Spike 01 — does SVE 1.15.11 need a rebuilt code DLL? | **No.** Loads natively on SDV 1.6.15 / SMAPI 4.5.2, zero warnings. See [docs/spike-01](docs/spike-01-sve-loads-natively.md) |
| Spike 02 — do the mod's SVE Harmony patches bind to 1.15.11? | in progress |
| Content remap (1.15 regions, NPCs, fish, recipes, Frontier Farm) | not started |
| Version lock + release pipeline | scaffolded, not wired |

The 1.14 integration shipped a rebuilt `StardewValleyExpanded.dll` (`1.14.31-archipelago-1`)
because that SVE build could not load on SDV 1.6.9+. Spike 01 showed 1.15.11 does not need that, so
**this project does not redistribute SVE, rebuilt or otherwise.** It ships patches and build scripts
only.

## Layout

```
patches/world/   diff series applied on top of Archipelago's worlds/stardew_valley
patches/mod/     diff series applied on top of StardewArchipelago
scripts/         fetch pinned upstream, apply patches, build artifacts
docs/            compatibility matrix, spike notes, maintainership policy
versions.lock    the only place versions are allowed to be written down
```

Not in this repo, by design: the game, SVE itself, SMAPI, Content Patcher, FTM, and any built
`.apworld` or `.zip`. `scripts/fetch_upstream.py` pulls the pinned upstream commits; everything else
comes from the player.

## Build

```sh
# 1. fetch the pinned upstream commits into .cache/
python scripts/fetch_upstream.py

# 2. apply the patch series
python scripts/apply_patches.py

# 3. produce artifacts/
python scripts/build_world.py                                   # -> artifacts/stardew_valley.apworld
python scripts/build_mod.py --game-path "D:\path\to\Stardew Valley"  # -> artifacts/StardewArchipelago/
                                                                 # (--game-path optional: Steam/GOG defaults on Windows, macOS, Linux)
python scripts/package_release.py                                # -> artifacts/release/ (apworld, mod zip, SHA256SUMS.txt)
```

`build_mod.py` needs a local Stardew Valley install (1.6.15 per `versions.lock`) because the mod
compiles against the game's assemblies. `build_world.py` needs only Python 3 (standard library). The scripts run the same on Windows, macOS and Linux; CI (`.github/workflows/ci.yml`) runs the world half on all three.

## Version policy

`versions.lock` pins the Stardew Valley build, SMAPI, SVE, Content Patcher, FTM, the Archipelago tag
and the StardewArchipelago commit. A bump is a deliberate, validated change:

1. update `versions.lock`,
2. re-apply the patch series onto the new upstream,
3. run the compatibility checklist in [docs/compatibility.md](docs/compatibility.md),
4. only then move the pin.

SVE point releases are the ones that break us. When SVE ships, we stay on the pinned version until
someone re-validates; that is the entire point of the lock, and it is what upstream could not afford
to keep doing.

## Maintainership

Expectation: one named maintainer who can be found in the Archipelago Discord `#stardew-valley`
channel, with a re-validation turnaround measured in days after an SVE or Archipelago release, not
weeks. If that person stops, this repo should be archived rather than left to rot with a green README
— that failure mode is exactly why the upstream integration was disabled.

## License

BSD-3-Clause for this repository's own work; see [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md). The
patched upstream projects remain under their own licenses (Archipelago: MIT, StardewArchipelago:
BSD-3-Clause).
