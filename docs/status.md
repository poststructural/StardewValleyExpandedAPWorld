# Status

Last updated: 2026-10-31, after the first end-to-end session on the SVE testbed.

## Proven working

| Layer | Evidence |
|---|---|
| SVE 1.15.11 loads on SDV 1.6.15 / SMAPI 4.5.2 with no rebuilt DLL | [spike-01](spike-01-sve-loads-natively.md): WARN 0, ERROR 0 |
| Generator accepts SVE and produces SVE content | [spike-02](spike-02-world-enable.md): upstream rejects the same player file; patched world gives 492 locations vs 472 vanilla, with SVE regions and quest checks |
| Client connects and the version gate passes | `StardewArchipelago version '8.1.12' connected to a multiworld generated with APWorld version '8.1.12'` |
| Save loads with SVE active, all Harmony targets bind | WARN 5, ERROR 0 — the five are missing post-7.4.25 slot-data keys, not SVE |
| Shop replacement runs | `StardewArchipelago edited Data/Shops` ×12 on day rollover |
| A full day cycle completes | `DayStarted`, FTM respawn, second day in the same session, no exceptions |
| An SVE item can be delivered | `!getitem Grandpa's Shed` → `Cheat console: sending "Grandpa's Shed"` → no error from the unlock manager |

## Bugs found and fixed

| # | Bug | Fix |
|---|---|---|
| 1 | World built without `compatible_version`/`version` → registers as 0.0.0, `requires.game` rejects it | `build_world.py` injects container fields from `versions.lock` |
| 2 | Packaging dropped subdirectories / deleted the staged tree | robocopy instead of `Copy-Item "dir\*"`; `-Filter` instead of `-Include` |
| 3 | Patch files written as UTF-16 by PowerShell redirection | regenerate with raw byte redirection |
| 4 | World/mod version drift → "Please downgrade to a compatible mod version" | `world_version` stamped from the paired mod manifest |
| 5 | `VillagerUnlockManager` throws `ArgumentException` on duplicate arrival name once SVE adds Marlon/Gunther/Morris | `patches/mod/0002` skips duplicates |
| 6 | Item receipt was silent — `_itemManager?.ReceiveAllNewItems()` looks identical whether the event never fired or the manager was missing | `patches/mod/0003` logs which of the two happened |

## Item delivery: verified

`!getitem Iridium Fireplace` → server sends `ReceivedItems` at index 7 → client logs
`Received-items event fired (item manager: ready)` → the item appears **as a letter**, before sleeping.

That last part matters for testing: nearly every AP item for Stardew is delivered through the mail
system (`APItemManager.ProcessItem` → `ProcessItemAsLetter` → `SendToPlayer`), not the inventory.
"Checked my bag and nothing was there" is the expected observation, not a failure. Test via the
mailbox, or via the save file, never the inventory.

## Known gaps

- **SVE location checks are unverified.** The default-options seed only contains quest-gated SVE
  checks (`Quest: Marlon's Boat`, `Quest: Grandpa's Shed`, `Quest: Aurora Vineyard`), which take hours
  to reach. Needs a purpose-built seed with friendsanity/shipsanity/cropsanity on.
- **The world's SVE model is still 1.14-shaped.** `Content/mod` mapping carries no knowledge of 1.15
  additions (Frontier Farm, Henchman, Scarlett, 12 new fish, 4 crops, ~26 recipes). Those are simply
  not randomized yet — the integration does not mis-handle them, it ignores them.
- **Five slot-data keys missing** because the world is 0.6.8's 7.4.25-era code paired with a `main`
  mod. Resolved either by moving the world pin to a matching line or by accepting the warnings.
- **`connect_override` half-applies** in 8.1.12 (announces the new host, dials the old one). Upstream
  issue, not ours; the save form works.

## Next

1. Purpose-built test seed (all sanities) → verify SVE check reporting end to end.
2. Inventory 1.15 content deltas against the world's SVE model and the mod's SVE patches; decide what
   to add and what to explicitly leave out.
3. Release plumbing: artifacts, checksums, install docs, and the version gate that tells players which
   SVE build is expected.
