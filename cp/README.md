# Content packs

`[CP] StardewAP - SVE Gates` is the only Content Patcher pack this project ships. It needs Stardew Valley Expanded
(`FlashShifter.StardewValleyExpandedCP`) and the Archipelago mod. It contains no SVE assets, text or maps, only
property edits.

- Four `EditData` patches on `Data/SpecialOrders`: point each of the four donation objectives of the `Robin3`
  (Grandpa's Shed) order at a drop box named `apGSDrop` on `Custom_GrandpasShedOutside`. SVE's own drop box is inside
  the ruins, which become unreachable once the shed is repaired, and Archipelago can repair the shed at any time.
- One `EditMap` patch on `Maps/Custom_GrandpasShedOutside`: adds the `Action DropBox apGSDrop` property to two existing
  wall tiles of the shed front at (20,16) and (21,16), so the donation menu opens when you use them. No tiles are added.

Event gating (Aurora Vineyard, Morgan, Scarlett, the Nexus runes and so on) is done in the mod's code
(`SVEEventGates.cs`), not here. If the pack is missing, the mod logs a warning and Grandpa's Shed still works
through the ruins until the shed is repaired.
