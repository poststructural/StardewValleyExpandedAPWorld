# Notices

This repository contains **patches and build scripts only**. It does not redistribute Stardew Valley,
Stardew Valley Expanded, SMAPI, Content Patcher, Farm Type Manager, Archipelago or the
StardewArchipelago mod. Players obtain those from their own sources.

## Upstream projects

| Project | License | Author |
|---|---|---|
| [Archipelago](https://github.com/ArchipelagoMW/Archipelago) — `worlds/stardew_valley` | MIT | Archipelago contributors, incl. `agilbert1412` (Stardew world maintainer) |
| [StardewArchipelago](https://github.com/agilbert1412/StardewArchipelago) — the mod | BSD-3-Clause | Alex Gilbert (`agilbert1412`) |
| [SMAPI](https://github.com/Pathoschild/SMAPI) | LGPL-3.0 | Pathoschild |
| [Content Patcher](https://github.com/Pathoschild/StardewMods) | LGPL-3.0 | Pathoschild |
| [Farm Type Manager](https://www.nexusmods.com/stardewvalley/mods/3231) | — | Esca |

Patch files in `patches/` are derivative works of the first two projects and carry their licenses.
BSD-3-Clause requires retaining the copyright notice and disclaimer for redistributed binaries; built
mod artifacts must ship `LICENSE.md` from StardewArchipelago alongside the DLL.

## Prior art

The original SVE integration (2023–2025) was written by **Witchybun**, with the SVE content-pack
patches published under `StardewAP - SVE Patch`. That work is the reference implementation this
project reconciles against SVE 1.15: the event-requirement edits, the Grandpa's Shed map/special-order
fixes, and the shop/cutscene injection points all originate there. Their 1.14 code patch is kept
locally as reference only and is **not** redistributed here — spike 01 established that SVE 1.15.11
does not need a rebuilt code DLL.

## Stardew Valley Expanded

SVE is closed-source and is **not** redistributed, decompiled, or shipped in modified form by this
project. No SVE assembly is included in any release artifact. Players install SVE themselves from
Nexus; this project only patches Archipelago's world and the StardewArchipelago mod.

## Trademarks

Stardew Valley is a trademark of ConcernedApe LLC. Archipelago is a community project. This project is
unaffiliated with and unendorsed by either.
