# SVE identifier check (Phase 3, first pass)

The mod's SVE integration barely touches SVE's *code*. It hooks vanilla game points and keys off SVE
**data identifiers** — event ids, mail flags, item ids, NPC names. That is good news for maintenance:
SVE recompiles mean little, but SVE renumbering means a lot, and a stale identifier fails **silently**
(`HasFlag`, `eventsSeen.Contains` and `mailReceived.Contains` all just return false).

Method: extract every string constant from the mod's SVE files, then search SVE 1.15.11's Content
Patcher data for each. Source of truth is the CP payload, not the changelog.

## Results

| Identifier | Used by mod as | Present in SVE 1.15.11? | Where |
|---|---|---|---|
| `658059254` | `AURORA_EVENT` — Aurora Vineyard intro | **NO** | 1.15 uses `746153081`–`746153087` (`code/OtherEvents/Aurora.json`) |
| `658078924` | `MORGAN_EVENT` — Morgan's schooling | **NO** | not found anywhere in 1.15 data |
| `Clint2Again` | railroad boulder mail flag | **NO** | not found |
| `8050108` | railroad boulder item id | yes | `code/OtherEvents/SpecialOrder.json` |
| `8050109` | iridium bomb item id | yes | `code/Locations/Summit.json`, `code/NPCs/Sandy.json`, +3 |
| `GuntherUnlocked` | museum unlock mail flag | yes | `code/Festivals/*.json` |
| `ShedRepaired` | Grandpa's Shed unlock | yes | `code/OtherEvents/GrandpasShed.json` |
| `RailroadBoulderRemoved` | iridium bomb unlock | yes | `code/OtherEvents/SpecialOrder.json` |
| `GaveVoidSouls` | void spirit peace | yes | `code/NPCs/Krobus.json` |
| `marlonsBoat` | Marlon's boat paddle | yes | `code/OtherEvents/SpecialOrder.json` |
| `apAuroraVineyard` | AP-gated Aurora flag | **NO** | exists only in Witchybun's `[CP] StardewAP - SVE Patch` |
| `apMorganSchooling` | AP-gated Morgan flag | **NO** | same |

## What this means

1. **Event ids were renumbered between 1.14 and 1.15.** The Aurora/Morgan unlock letters call
   `LetterEventSeenAttachment` with ids that no longer exist, so those two unlocks mark nothing as
   seen. Not a crash — a quiet no-op, exactly the failure mode this phase was written to find.
2. **Two AP-specific mail flags only ever existed in the CP patch, not in SVE.** `apAuroraVineyard`
   and `apMorganSchooling` are how the integration gates Aurora Vineyard and Morgan's schooling
   behind AP items. Without the CP patch ported to 1.15, those gates do nothing.
3. **Most of the SVE mail flags and both item ids survived 1.15.** The unlock surface that does not
   depend on event ids is intact — which matches the fact that `Grandpa's Shed` was delivered
   correctly during the live test.

## Consequence for the project

The CP patch is not optional polish; `apAuroraVineyard` / `apMorganSchooling` are load-bearing. Porting
`[CP] StardewAP - SVE Patch` 2.1.2 to 1.15 is now a Phase-1-level task, not a nice-to-have, and it is a
much smaller job than the code patch it was mistaken for: five JSON files, all of whose hooks still
exist except the renumbered events.

## Inconclusive

The special-order name scan (`Purify an Infested Lichtung`) returned nothing, but so did every other
special order, which means the scan itself is wrong rather than the data — `Data/SpecialOrders` entries
are not being collected by the current walker. Needs a corrected pass; treat the special-order row as
unknown, not missing.
