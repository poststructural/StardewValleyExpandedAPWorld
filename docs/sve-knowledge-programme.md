# SVE knowledge programme

What it would take to stop guessing about SVE and have the integration rest on a complete, checkable
picture. Written after the first end-to-end session; the first phase is already done.

## Why this is worth doing

Right now the integration works *by inspection*: we know SVE 1.15 loads, checks generate, items
arrive, and nothing throws. We do **not** know:

- which of the 317 SVE locations the world defines still have a live trigger in 1.15,
- which SVE content added since 1.14.46 is silently unrandomized,
- which of the mod's Harmony targets point at members that still exist versus members that were
  renamed (a missing Harmony target usually fails silently, by design of `HarmonyMethod` lookups),
- which hard-coded event ids, special orders and map names in the mod still match SVE's data.

Every one of those is answerable offline, from the artifacts we already hold. That is the whole point
of this document.

## What we already hold

| Artifact | Where | Size |
|---|---|---|
| SVE 1.15.11 code, decompiled | `_analysis/sve-1.15.11` (gitignored) | 44 files, 7,194 lines |
| SVE 1.15.11 CP content | `SVE_Mod/.../[CP] Stardew Valley Expanded` | content.json + assets + code |
| SVE 1.15.11 FTM spawn data | `SVE_Mod/.../[FTM] Stardew Valley Expanded` | content.json |
| SVE 1.14.31 patched code (Witchybun) | `Witchybun-.../Stardew Valley Expanded` | 157 KB dll, decompilable |
| AP world SVE data | `.cache/archipelago/worlds/stardew_valley` | 317 locations, 55 items |
| AP mod SVE surface | `.cache/stardew_archipelago` | 8 dedicated files, ~1,100 lines |

**Do not commit the decompiled tree.** SVE is closed-source; the decompilation is for analysis only.
`_analysis/` is gitignored. Derived facts (tables, counts, name lists) are fine to publish; verbatim
SVE source is not.

## Phase 0 — completed tonight

- Decompiled SVE 1.15.11 (44 files / 7,194 lines). Largest units: `ModEntry` (1,048),
  `CustomCauldronEffects` (877), `ItemMigrator` (502), `SpaceUtility` (403),
  `HarmonyPatch_FarmComputerLocations` (278), `DisableShadowAttacks` (269), `CustomBackgrounds` (268).
- Counted the world's SVE model: **317 locations** (friendsanity 164, shipsanity 81, fishsanity 26,
  cooking 10, quest 6, harvest 6, craft 3, tempered-weapon 3, void 2, haste 1) and **55 items**.
- Located the mod's SVE surface: `SVEUnlockManager` (179), `SVECutsceneInjections` (177),
  `JunimoShopStockModifier` (255), `TemperedShopStockModifier` (141), `BearShopStockModifier` (114),
  `SVENameMapper` (49), `FriendshipReleaser` (36), plus the registrations in `ModLocationPatcher` /
  `ModCodeInjectionInitializer`.

## Phase 1 — asset census

Enumerate everything SVE 1.15.11 actually defines, as machine-readable data:

- CP `content.json` (lenient parse — SVE uses trailing commas) → every `EditData` target field:
  `Data/Objects`, `Data/Crops`, `Data/Fishing`, `Data/CookingRecipes`, `Data/CraftingRecipes`,
  `Data/Buildings`, `Data/Festivals`, `Data/mail`, `Data/SpecialOrders`, `Data/Events/*`, `Data/Locations`.
- Every map the mod loads (from CP map patches + `Maps/` targets) → the region list SVE expects.
- FTM spawn tables → forage/ore/monster tables per location, which is what ER and monstersanity key on.
- Output: `_analysis/sve-1.15-assets.json` + `docs/sve-1.15-assets.md` (counts and top-level lists).

Yields: the authoritative list of what exists, which every later phase compares against.

## Phase 2 — the check inventory

For each of the 317 SVE locations, produce a row:

| location | category | AP item | trigger in game | trigger exists in 1.15? | notes |

Derivation: location name → category from the CSV prefix; trigger from the world's rules
(`rules.py`, `mods/logic/sve_logic.py`) and the mod's matching injection; existence from Phase 1's
asset census plus the decompiled assembly.

Yields: `docs/sve-check-matrix.md`, the single most valuable artifact for the project — it turns
"some checks may be broken" into a list of specific rows, each provable.

## Phase 3 — patch-surface verification

The mod's SVE code reaches into game members by name. Enumerate every `AccessTools.Method` /
`AccessTools.Property` / `AccessTools.Field` target across the SVE files, then check each against the
1.15.11 types:

- resolve the type and member in the decompiled tree (or via `MetadataLoadContext` on the DLL),
- mark `exists` / `renamed` / `gone`,
- for `gone`, find the nearest match by signature so the fix is a one-line edit.

Yields: `docs/sve-harmony-targets.md`. This is the phase that catches the failures that produce no
exception — Harmony's `AccessTools` returning null is silently tolerated in several call sites.

## Phase 4 — 1.14 → 1.15 delta

We lack vanilla 1.14.46, but Witchybun's `1.14.31-archipelago` dll is a 1.14 build: decompile it and
diff against 1.15.11. The diff is large but mechanical, and it answers "what did 1.15 actually change
that we depend on" rather than "what does the changelog say".

Focus the diff on: public/protected type and member signatures (the Harmony surface), event ids,
special-order names, map names, item ids.

Yields: `docs/sve-1.14-to-1.15-delta.md`, plus the exact list of members the old integration used that
no longer exist.

## Phase 5 — event and quest graph

SVE drives a lot of content through events and special orders, and the mod hard-codes ids
(`AURORA_EVENT 658059254`, `MORGAN_EVENT 658078924`, `RAILROAD_BOULDER_ID 8050108`,
`LANCE_CHEST_LOCATION "Quest: Monster Crops"`, …). Extract every such constant from the mod, then check
it against SVE's own data:

- `Data/Events/*` in the CP content,
- `Data/SpecialOrders`,
- the decompiled code that raises them.

Yields: `docs/sve-events-and-orders.md` — which ids are live, which are stale, and which quests have
no AP representation at all.

## Phase 6 — gap report and design decisions

Collapse phases 1–5 into a decision document: for every piece of SVE 1.15 content, one of

- already randomized (with the check name),
- randomized but mis-gated (fix this),
- not randomized, worth adding (effort estimate),
- deliberately out of scope (and why).

That is the document a maintainer reads before touching the version pin.

## Phase 7 — automated regression

Turn the above into tests:

- generate one seed per sanity option and assert the location count matches the check matrix,
- a smoke script that boots the testbed, connects, fires a scripted set of checks, and asserts the
  server received them,
- run it before every pin bump, per `docs/compatibility.md`.

## Order of work

1 and 3 first: they are pure enumeration and they unblock everything else. 2 needs both. 4 is the
biggest single effort and is only worth doing once 1–3 tell us where to look. 5 and 6 are analysis
over data we will already have. 7 last, and it is what makes the result durable.

Phases 1 and 3 are mechanical and can run unattended; 2, 5 and 6 need judgement about what a check
*should* mean, which is where the maintainer earns their name.
