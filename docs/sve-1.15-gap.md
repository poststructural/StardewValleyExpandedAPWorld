# SVE 1.15.11 vs pinned Stardew Valley world: gap list

Method: lenient JSON5 parse of the 1.15.11 CP `code/` tree (scan script: scratchpad `scan.py`; 12 files do not parse, none affect the lists below except Susan/Krobus/Monsters which were read by hand). World side: `data/locations.csv` (`content_packs` column), `content/mods/sve.py`, `strings/*`, `data/*`. Mod side: C# in `.cache/stardew_archipelago/StardewArchipelago`.

ID convention: every SVE object id is `FlashShifter.StardewValleyExpandedCP_<Name with spaces to underscores>` (written `~Name` below). Exceptions are noted. World display name = the object's internal `Name` field (NOT the i18n DisplayName), after the client's `SVENameMapper`.

## 0. Does the client map by display name, internal id, or table?

Both layers are name based; there is no AP-name to game-item-id table.
- AP location name to AP id: a shipped table, `StardewArchipelago/IdTables/stardew_valley_location_table.json` (+ `stardew_valley_item_table.json`), loaded by `Archipelago/StardewDatapackageCache.cs` (`LocationExists`, `GetLocationId`). It holds name, code, region, tags, content_packs. It has 4129 entries (331 SVE) vs world CSV 4051 (317 SVE). Any NEW world location must be added to the world CSV (`data/locations.csv`, ids; SVE ids sit in 56139-58247) AND regenerated into this JSON, else the client logs "Unrecognized ... Location".
- Game item to AP location name: computed at runtime from game data, by object `Name` (internal name, not DisplayName), via `Stardew/StardewItemManager.cs` (`_objectsByName`, built from Data/Objects) and `Stardew/NameMapping/*`. SVE internal-vs-world name differences are the six entries in `Stardew/NameMapping/SVENameMapper.cs` (Bearberrys to Bearberry, Big Conch to Conch, Dried Sand Dollar to Sand Dollar, Lucky Four Leaf Clover to Four Leaf Clover, Smelly Rafflesia to Rafflesia, Ancient Ferns Seed to Ancient Fern Seed). `Constants/Vanilla/NameAliases.cs` has NPC aliases (MarlonFay, GuntherSilvian, MorrisTod, ...).
- Generic by name (new rows need NO client code if the name equals the object `Name` or is in the mapper): shipsanity (`NightShippingBehaviors.cs`, "Shipsanity: "+name; unknown name only logs an error), fishsanity (`FishingInjections.cs`, "Fishsanity: "+Name), cropsanity harvest (`CropsanityInjections.cs`, "Harvest "+harvest item Name; forage "Forage "+Name), cooksanity (`CookingInjections.cs`, "Cook "+yield Name), craftsanity (`CraftingInjections.cs`, "Craft "+recipe id / yield Name), eatsanity (`EatInjections.cs`, "Eat "/"Drink "+Name via mapper), museumsanity (`MuseumInjections.cs`, "Museumsanity: "+Name), chefsanity friendship (`RecipeFriendshipInjections.cs` reads Data/CookingRecipes field 4 `f <npc> <hearts>`; generic), friendsanity (`Friends.cs` iterates Data/Characters; AP name = key unless aliased; hearts present = `LocationExists("Friendsanity: <name> N <3")`), story quests (`StoryQuestInjections.cs`, English title from Data/Quests).
- NOT generic (hard-coded SVE): special orders (`Constants/Modded/SpecialOrderNames.cs` maps order-name keys; `SpecialOrderInjections.cs:517` does `SpecialOrderNames.Mods[str1]` with NO ContainsKey, so any unlisted SVE order key throws; `Locations/CodeInjections/Modded/SVE/SVECutsceneInjections.cs` `sveEventSpecialOrders` maps event ids to order ids), shop checks (`Modded/SVE/BearShopStockModifier.cs`, `TemperedShopStockModifier.cs`, `GameModifications/Modded/JunimoShopStockModifier.cs`), Morris hearts release (`Modded/SVE/FriendshipReleaser.cs`), friends-not-met-immediately (`Constants/Modded/IgnoredModdedStrings.cs`), SVE entrance randomizer lists (`GameModifications/EntranceRandomizer/ModEntranceManager.cs`).

## 1. Counts

| Category | SVE 1.15 | World (SVE-tagged) | Missing | Client |
|---|---|---|---|---|
| Friendsanity NPCs (social-tab) | 15 (Andy, Apples, Claire, GuntherSilvian, SVE_Henchman, Lance, MarlonFay, Martin, Morgan, MorrisTod, Olivia, Scarlett, Sophia, Susan, Victor) + Wizard edit | 14 NPCs = 164 locs (Wizard override adds 4) | 1 NPC (Henchman) | one alias line |
| Fish (catchable objects) | 43 + Dulse Seaweed | 26 | 17 | generic |
| Crops (Data/Crops) | 12 (2 are Joja) | 6 | 4 (+3 fruit trees) | generic |
| Forageables / loot | ~21 | 15 forage + 6 loot, as logic and shipsanity only; 0 forage-check locations | n/a (no forage checks exist) | `Forage <Name>` hook exists, generic |
| Cooking recipes | 26 | 10 (cook + chefsanity) | 16 | generic |
| Crafting recipes | 12 | 3 | 9 | generic |
| Shippable objects | ~98 not yet in world, ~84 after removing key items and Joja items | 81 | ~84 | generic |
| Museum (Arch + Mineral) | 7 Arch + Galdoran Gem = 8 | 0 | 8 | generic |
| Special orders | 15 in Data/SpecialOrders + Krobus + event-added Clint3, Lewis2, Robin4 | 5 board + 6 story | 4 to 7 | code |
| Quests (Data/Quests) | 1 edit only (id 100); SVE "quests" are special orders | 6 STORY_QUEST | 0 | n/a |
| Shops/vendors | 84 Data/Shops edits; ~28 SVE shops | 3 Tempered + 2 Bear recipes + shop-sourced chefsanity | per-vendor purchase checks 0 | code |
| Custom locations | 57 Data/Locations Custom_ keys; 71 CustomLocations in content.json | 55 SVERegion names | ~35 unmatched (fuzzy) | entrance lists |

## 2. NPCs / friendsanity

SVE-defined Data/Characters (41 keys incl. adventurers). Only NPCs with a visible Social tab can have hearts:
- In world, correct: Claire (datable), Lance (datable), Olivia (datable, world calls her "Olivia"), Sophia (datable), Victor (datable), Andy, Apples, Gunther, Martin, Marlon, Morgan, Susan, Morris (non-datable, 10 hearts each). Scarlett: world says non-datable (10 hearts); 1.15 data has `CanBeRomanced: true`, so 4 more hearts (11-14) are possible and the datable flag in `villagers_data.py` is stale. Wizard already bachelor override. Gift tastes exist for all of these.
- MISSING: `SVE_Henchman` (Data/Characters key `SVE_Henchman`, male, adult, SocialTab AlwaysShown, CanSocialize true, not datable, has NPCGiftTastes entry). World name would be "Henchman" (needs `NameAliases.NPCNameAliases["SVE_Henchman"]="Henchman"`; also add to `IgnoredModdedStrings.FriendsNotMetImmediately` if he is gated). About 10 locations (+ 10 heart items).
- No friendship possible (SocialTab HiddenAlways, CanSocialize false, no gift tastes): Alesia, Isaac, Camilla, Jadu, Jolyne, HighlandsDwarf, HankSVE, Treyvon, Peaches, CharlieChicken, ScarlettFake, and the 11 adventurers (Sawyer, Gale, Brianna, Drake, Edmund, Gertrude, Brock, Cordelia, Freya, Cassandra, Emin).
- Data for hearts: `Friends.cs` also registers HiddenAlways NPCs but `ShuffledUpTo` returns 0 for them (no locations), so harmless.
- Note: Scarlett and Gunther visibility is event-gated (CanSocialize conditions), Morris is gated off after event 191393 (FriendshipReleaser handles his hearts after CC completion).

## 3. Fish (17 missing; all generic by name)

World has: Baby Lunaloo, Bonefish, Bull Trout, Butterfish, Clownfish, Daggerfish, Frog, Gemfish, Goldenfish, Grass Carp, King Salmon, Kittyfish, Lunaloo, Meteor Carp, Minnow, Puppyfish, Radioactive Bass, Seahorse, Shiny Lunaloo, Snatcher Worm, Starfish, Torpedo Trout, Undeadfish, Void Eel, Water Grub, Sea Sponge (26, all still exist in 1.15).

Missing (id `~Name`, spawn region per Data/Locations; all have Data/Fish rows and aquarium entries): Alligator (Custom_ForbiddenMaze, Custom_HenchmanBackyard), Arrowhead Shark (Custom_FableReef), Barred Knifejaw (FableReef + vanilla ocean), Blue Tang (FableReef + vanilla), Diamond Carp (Custom_DiamondCavern), Fiber Goby (Custom_Highlands), Gar (Custom_ForestWest), Goldfish (vanilla loc), Highlands Bass (Custom_Highlands), Ocean Sunfish (FableReef + vanilla), Razor Trout (vanilla loc; ExcludeFromShipping true), Shark (FableReef + vanilla), Swamp Crab (ForbiddenMaze, HenchmanBackyard), Tadpole (vanilla loc), Turretfish (FableReef), Viper Eel (FableReef), Wolf Snapper (Custom_ShearwaterBridge; also sold by Axel2/BlueJunimo vendors).
Also: Dulse Seaweed (Fish type, Category 0; world has forage logic but no shipsanity). World display name: object Name (e.g. "Wolf Snapper"). Needs world fish_data.py rows (season/location/difficulty) plus regions for ForbiddenMaze, HenchmanBackyard, DiamondCavern.

## 4. Crops / seeds

World: Salal Berry, Slime Berry, Monster Fruit, Monster Mushroom, Void Root, Ancient Fiber (seeds: Shrub, Slime, Stalk, Fungus, Void, Ancient Fern).
Missing crops (id `~Name`, seed `~Name_Seed`, harvest id): Cucumber (Spring), Butternut Squash (Summer), Sweet Potato (Fall), Gold Carrot (Spring/Summer/Fall); seeds sold in Pierre's shop (Cucumber_Seed, Butternut_Squash_Seed, Sweet_Potato_Seed) and desert trader (Gold_Carrot_Seed). Not randomizable: Joja Berry Starter, Joja Veggie Seeds (ExcludeFromShipping, Joja).
Fruit trees (Data/FruitTrees): ~Pear_Sapling, ~Nectarine_Sapling, ~Persimmon_Sapling (Pierre), ~Tree_Coin (odd entry; skip). Harvest items: Pear, Nectarine, Persimmon. Vanilla world has "Harvest Apple" style locations, so these would be "Harvest Pear" etc.; client path is `CropsanityInjections` (crop harvest generic, fruit-tree harvest also by item Name).
Seed unlock items: `GameModifications/SeedShopStockModifier.cs` filters all shops from Data/Shops generically.
Renamed (handled): Ancient Ferns Seed -> Ancient Fern Seed.

## 5. Forageables

SVE forage/loot objects: Ferngill Primrose, Goldenrod, Winter Star Rose, Thistle, Golden Ocean Flower (Flower); Bearberrys, Poison Mushroom, Red Baneberry, Dewdrop Berry (Fruit); Big Conch, Dried Sand Dollar, Shark Tooth (-23); Lucky Four Leaf Clover, Mushroom Colony, Smelly Rafflesia, Green Mushroom, Mega Purple Mushroom (Greens); Dulse Seaweed; Diamond Flower, Swamp Flower; Rusty Blade, Swirl Stone, Void Pebble, Void Shard, Void Soul, Sludge, Supernatural Goo, Swamp Essence, Gold Slime Egg, Magic Lamp (loot). World lists 15 SVEForage + 6 ModLoot, no forage check locations. Not in world at all: Shark Tooth, Mega Purple Mushroom, Diamond Flower, Swamp Flower, Sludge, Supernatural Goo, Swamp Essence, Gold Slime Egg, Magic Lamp (all appear in the shipsanity list below).

## 6. Cooking (16 missing, generic)

World has 10: Baked Berry Oatmeal, Big Bark Burger, Flower Cookie, Frog Legs, Glazed Butterfish, Mixed Berry Pie, Mushroom Berry Rice, Seaweed Salad, Void Delight, Void Salmon Sushi (all exist). Plus shop-only meals Grampleton Orange Chicken, Stamina Capsule, Sports Drink (objects exist, no recipe).
Missing recipes (recipe key = Name, id `~Name`), with 1.15 unlock field:
- friendship-unlocked `f <npc> 3`: Fish Dumpling (Olivia), Ramen (Victor), Baked Potato (GuntherSilvian), Grilled Cheese Sandwich (Martin), Pineapple Custard Crepe (Lance), Nectarine Fruit Bread (Claire), Glazed Pear (Morgan), Stuffed Persimmon (Andy), Cheese Charcuterie (Scarlett). These are chefsanity friendship checks and work generically.
- no unlock field (shop/other source; need a source per recipe): Birch Syrup, Candy (Gus shop), Chocolate Truffle Bar (Suki shop), Vegan Cone (Alex shop), Ice Cream Sundae (Alex/Luau shop), Prismatic Pop (Fair shop), Gingerbread Man.
Name clash risk: world already has vanilla/other-mod "Grilled Cheese" (TrashyMeal) vs SVE "Grilled Cheese Sandwich": use object Name.
Several ingredients depend on new items: Butter (new item from Butter Churner, a Farming 3 craft).

## 7. Crafting (9 missing, generic)

World: Haste Elixir, Hero Elixir, Armor Elixir (craft + "Recipe" shop locations). Stale risk: in 1.15 these three are unlocked by skill (Armor Elixir Combat 7, Haste Elixir Combat 8, Hero Elixir Combat 9); Alesia and Isaac vendors sell the elixirs and Tempered weapons, I found no recipe items in their shop files, so the "Haste/Hero/Armor Elixir Recipe" CRAFTSANITY_RECIPE locations at Alesia/Isaac shop (`Alesia Shop`, `Isaac Shop`) should be re-verified in game.
Missing (key = recipe Name): Seed Cookie (Foraging 3), Small Hardwood Fence (no unlock; result id ~Small_Hardwood_Fence_Tilesheet), Hedge Fence (Farming 6; ~Hedge_Fence_Tilesheet), Bombardier Elixir (Combat 9), Butter Churner (Farming 3, big craftable), Yarn Spooler (Farming 9, big craftable), Sun Totem (Foraging 9), Wind Totem (Foraging 9), Marsh Tonic (Combat 8; key is `{{modID}}_Marsh_Tonic`, so "Craft Marsh Tonic" may fail the recipe-id path and rely on the yield-Name fallback in `CraftingInjections.TryGetExistingCraftsanityLocationName`). Totem and Fence names may collide with vanilla ("Sun Totem" etc. do not exist in vanilla; check Rain Totem pattern).

## 8. Shipsanity (about 84 missing, generic)

World SVE shipsanity: 81 rows, all still valid in 1.15 (none removed/renamed other than the six mapper cases).
Not yet in world (excluding items flagged ExcludeFromShippingCollection or key items: Aurora Vineyard Property Deed, Golden Key, Lance's Schedule, Castle Village Outpost Vendor Schedule, Property Deed, Super Joja Cola, Super Starfruit, Joja Berry, Joja Berry Starter, Joja Veggie, Joja Veggie Seeds, Void Mayo Sandwich, Razor Trout, Mermaid's Bracelet):
- Fish 17 (section 3) + Dulse Seaweed
- Cooking 15: Candy, Vegan Cone, Ice Cream Sundae, Prismatic Pop, Chocolate Truffle Bar, Fish Dumpling, Gingerbread Man, Nectarine Fruit Bread, Ramen, Baked Potato, Grilled Cheese Sandwich, Pineapple Custard Crepe, Glazed Pear, Stuffed Persimmon, Cheese Charcuterie
- Crops/fruit 8: Cucumber, Butternut Squash, Sweet Potato, Gold Carrot, Pear, Nectarine, Persimmon, (Cucumber etc. seeds below)
- Seeds 4: Cucumber Seed, Butternut Squash Seed, Sweet Potato Seed, Gold Carrot Seed; Saplings 3: Pear, Nectarine, Persimmon Sapling; Tree Coin (skip)
- Crafting 9: Seed Cookie, Marsh Tonic, Bombardier Elixir, Wind Totem, Sun Totem, Birch Seed, Fir Cone, Small Hardwood Fence, Hedge Fence
- Animal/artisan 10: Honey Jar, Camel Wool, Butter, Yarn, Goose Mayonnaise, Goose Egg, Golden Goose Egg, Birch Water, Fir Wax, Birch Syrup
- Loot/misc 9: Shark Tooth, Sludge, Supernatural Goo, Swamp Essence, Gold Slime Egg, Magic Lamp, Diamond Flower, Swamp Flower, Mega Purple Mushroom, Money Bag
- Museum items shippable 8: Amber, Boomerang, Faded Button, Fossilized Apple, Old Coin, Rusty Shield, Stone of Yoba, Galdoran Gem
Known client skip list `IgnoredModdedStrings.Shipments` (Galmoran Gem etc., other mods). New names go through `_nameMapper`; add mapper entries only if the object Name differs from the desired world name.

## 9. Museum

SVE adds Arch objects: Amber, Boomerang, Faded Button, Fossilized Apple, Old Coin, Rusty Shield, Stone of Yoba; Mineral: Galdoran Gem (turns into Minerals only when config GaldoranGemMuseumMoveable true; skip). World `museum_data.py` has no SVE entries. 7 locations (+ any artifact items need museum_data rows with locations, e.g. Fossilized Apple). Client generic ("Museumsanity: "+Name).

## 10. Eatsanity

World has 273 eatsanity rows, 0 SVE. About 75 SVE edible objects (Edibility >= 0): all items in sections 3, 4, 6, 8 that are food, plus elixirs, wines, Sports Drink, Stamina Capsule, Grampleton Orange Chicken etc. Client generic via `EatInjections` and name mapper. World side needs rows plus the `eatsanity_item_is_included` path (no per-pack gating in CSV tags; content_packs column carries SVE).

## 11. Special orders / quests (needs client code)

1.15 Data/SpecialOrders keys and English names: HenchmanHouseRepaired (A Witch Offering), Lance (Monster Crops), LegendaryTrio (The Legendary Trio), MorrisTod2 (Townhouse Project), MorrisTod3 (Aurora Vineyard Purchase), Robin3 (Grandpa's Shed), Emily (name key `Emily_Name`, no string found), Andy (Andy's Cellar), Olivia (An Elegant Reception), Susan (Homemade Fertilizer), Sophia (Fairy Garden), MarlonFay (A Mysterious Venture), Clint2 (The Railroad Boulder), Apples (Aurora Vineyard), MarlonFay2 (Marlon's Boat). Krobus (Void Soul Retrieval) is defined in Krobus.json (not parseable by the scan). The event dictionary also lists Clint3, Lewis2, Robin4.
- World has: Andy's Cellar, A Mysterious Venture, An Elegant Reception, Fairy Garden, Homemade Fertilizer (board) and story: Marlon's Boat, The Railroad Boulder, Grandpa's Shed, Aurora Vineyard, Monster Crops, Void Soul Retrieval.
- Missing: A Witch Offering (HenchmanHouseRepaired), The Legendary Trio, Townhouse Project, Aurora Vineyard Purchase, plus Emily and Clint3/Lewis2/Robin4 if they are real orders. Client needs: `SpecialOrderNames.Mods` entries (keys `HenchmanHouseRepair_Name`, `LegendaryTrio_Name`, `MorrisTod2_Name`, `MorrisTod_Name3`, `Emily_Name`), `sveEventSpecialOrders` event ids if event-triggered, and possibly `IgnoredModdedStrings.SpecialOrders`. Until then a missing key throws at `SpecialOrderInjections.cs:517`.
- Data/Quests: only a single SVE edit (id "100"), so no extra story quests via the generic path.

## 12. Shops / vendors (code)

SVE-defined shops in Data/Shops (key `FlashShifter.StardewValleyExpandedCP_<name>`): AdventurerLedger (17 items), AlesiaVendor (6), AuroraLedger, AxelVendor1 (5), AxelVendor2 (11), BearVendor (11), Blue/Grey/Orange/Purple/Red JunimoVendor (11/11/48/5/29; Yellow not in this scan), BrooklynVendor (48), CamillaVendor (4), ChloeVendor1-4 (9/5/7/6), FurnitureCatalogue2, HighlandsDwarfShop (57), IsaacVendor (5), JaceVendor (47), LewisLedger, MorrisLedger, SophiaLedger (6). Portrait-only entries are Suki shop sub-edits. World models only logic sources for ~10 items. Client has bespoke modifiers for Bear, Tempered weapons, Junimo. New per-vendor purchase checks would need a ShopStockModifier per vendor. CookingRecipePurchase/CraftingRecipePurchase modifiers are generic (vanilla) and could cover recipes sold in SVE shops if the shop ids are registered.

## 13. Regions / custom locations

Data/Locations Custom_ keys (57): DayEnd_WarpRoom, Atlantis, DesertRailway, EnchantedGrove, FirstSlashGuestRoom, GrampletonCoast, GrampletonTrainStation, GrenvilleFalls, HighlandsCavernPrison(+Event), IridiumQuarry, JojaPetStore, SakuraVineyard(+Cellar, Cottage, DiningRoom), SpriteSpringCave, TreasureCave, Void, ZCCC_Entrance/FoodCourt/MainHall/Stage/VendorFloor/Courtyard, ZuzuCityStreet, HighlandsOutpost, CastleVillageOutpost, FirstSlashGuild, FirstSlashHallway, WizardBasement, SVESummit, AdventurerSummit, BlueMoonVineyard, ForbiddenMaze, HenchmanBackyard, HenchmanHouse, DinoIsland_South/North, CrimsonBadlands, FableReef, GrandpasShedGreenhouse, ForestWest, Garden, GrampletonSuburbs(+TrainStation, Outskirts), GoGoatRanch(+Interior), GrandpasShedOutside, Highlands, HighlandsCavern, DiamondCavern, JunimoWoods, MorrisProperty, ShearwaterBridge, SpriteSpring2.
Fuzzy match against the 55 `SVERegion` strings leaves 35 without an obvious counterpart (names may differ): the new-in-1.15 gameplay areas are Zuzu City (ZuzuCityStreet, ZCCC x6), Castle Village Outpost, Highlands Outpost, Henchman House/Backyard, Forbidden Maze, Diamond Cavern, Grenville Falls, Atlantis, Desert Railway, Iridium Quarry, Joja Pet Store, Treasure Cave, Sakura Vineyard x4, GoGoat Ranch x2, Dino Island x2, Morris Property, Garden, Grampleton Coast and Train Station. Silent hole: entrance randomizer and region_data need these before fish/forage there are in logic.

## 14. Removed / renamed since the world was built

- Nothing the world references has been removed: all 26 fish, 15 forage, 10 recipes, 8 elixir/wine/drink items, Tempered Galaxy Dagger/Sword/Hammer (exist in Weapons.json), and every SVE shipsanity row still resolve.
- Renamed internally (world name differs from object Name; mapper covers): Bearberry, Conch, Sand Dollar, Four Leaf Clover, Rafflesia, Ancient Fern Seed.
- Stale data: Scarlett datable flag (world False, 1.15 True); Haste/Hero/Armor Elixir recipe-shop locations (1.15 unlocks them by Combat level); the SVE census doc `docs/sve-1.15-assets.md` says 25 vendors (counted 28 shop keys; includes sub-edits).

## 15. Largest opportunities (estimated new locations)

1. Eatsanity of SVE foods/forage/fish: about 75 (needs the player to enable eatsanity; client generic).
2. Shipsanity: about 84 (client generic; mostly just CSV rows plus content classes).
3. Cooksanity + chefsanity + shipsanity-of-dishes: 16 recipes x 2 = 32 (9 are friendship-unlocked; generic).
4. Fishsanity for 17 new fish (plus 17 shipsanity counted above): 17, needs fish_data and new regions.
5. Friendsanity: Henchman 10 + Scarlett datable extension 4 = 14; then craftsanity 9, museumsanity 8, cropsanity 4-7, special orders 4-7 (code).
