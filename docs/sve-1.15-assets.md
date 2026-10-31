# SVE 1.15.11 asset census (Phase 1, first pass)

Source: `SVE_Mod/Stardew Valley Expanded/[CP] Stardew Valley Expanded/content.json` and the FTM pack,
parsed with a lenient JSON5 reader (SVE uses trailing commas, so plain `json` rejects the file).

## Shape of the CP mod

| | |
|---|---|
| `Changes` | 86 |
| `Load` actions | 71 (maps, images, dialogue, assets) |
| `EditData` actions | 5 — all `Data/TriggerActions` |
| `Include` groups | 10 |
| map-related changes | 62 |
| `CustomLocations` | **71** |

The content.json is a skeleton: almost everything arrives through the 10 include groups, which is why
a naive read makes SVE look tiny.

## The 10 include groups

| Group | What it carries |
|---|---|
| Schedules | ~25 NPC schedule files (Apples, Peaches, Charlie, Claire, Gunther, Krobus, Lance, Magnus, Marlon, Martin, Morris, Scarlett, Susan) |
| Items | `BigCraftables`, `Objects`, `Weapons`, `Fences`, `Crops`, `Powers`, `CraftingRecipes`, `CookingRecipes`, `UniversalGiftTaste`, `Furniture`, `Machines` |
| Festivals | 12 (vanilla festivals + `JojaDay`, `CommunityDay`, `Nightmarket`, `Desertfestival`) |
| Shops | vanilla shop edits (17) **+ 25 SVE vendors**: AuroraLedger, SophiaLedger, Alesia/Isaac/Camilla/HighlandsDwarf/AdventurerLedger, Bear, six Junimo colours, Brooklyn, Zoey, Chloe×4, Jace, Axel×2, Lewis/Morris ledger, FurnitureCatalogue2 |
| Locations / Other | bundles, mail, FarmAnimals, fish, monsters, buildings, garbage cans, CJB warps, world map, sleep tiles, Galdora |
| NPCs (SVE) | victor, olivia, andy, **henchman**, susan, sophia, marlonfay, morgan, magnus, apples, claire, **camilla**, lance, adventurers, scarlett, gunther, martin, morris, **isaac**, **alesia**, **jolyne**, **jadu** |
| NPCs (vanilla edits) | 37 vanilla NPC files |
| Dialogue | 49 files, including **Hank**, **Treyvon**, **Jadu**, **Jolyne**, **HighLandsDwarf** |
| Events | Aurora, other, EnchantedGrove, SpecialOrder, GrandpasShed |

## The 71 custom locations

`Custom_*` maps, e.g. `Custom_AuroraVineyardRefurbished`, `Custom_GrandpasShed`, `Custom_TownEast`,
`Custom_AndyHouse`, `Custom_SusanHouse`, `Custom_OliviaCellar`, `Custom_SophiaHouse`,
`Custom_CrimsonBadlandsMap`, `Custom_GaldoranVoid`, `Custom_CastleVillage_DayEnd_WarpRoom`,
`Custom_MovieTheaterScreen_ClaireEvent`, plus warp rooms. These are the region/entrance surface.

## What this immediately tells us

- **The world's 317 SVE checks are thin against this.** 164 of them are friendsanity for ~14 SVE NPCs;
  SVE 1.15 names roughly 25 NPCs with dialogue and schedules, including several — Henchman, Hank,
  Treyvon, Jadu, Jolyne, Camilla — that the world has no concept of.
- **25 SVE vendors exist; the mod patches shops generically**, so vendor stock is probably wired but
  per-vendor check coverage is unknown. That is a Phase 2 question.
- **71 custom locations** versus the world's region list: any `Custom_*` map missing from the world is
  an entrance-randomizer hole, and those fails are silent.
- **1.15-only NPCs are confirmed present in data**, so the earlier "mod knows no 1.15 content" finding
  is really "the mod *need not* know them individually" — which is good news for maintainability and
  bad news for friendsanity coverage.

## Next in this phase

Follow each include group and count entries per data asset (objects, crops, cooking recipes, shops)
so the census becomes a list of names, not just files. Then Phase 2 can put one row per check against
it.
