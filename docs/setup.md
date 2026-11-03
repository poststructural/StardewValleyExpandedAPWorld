# Setup: Stardew Valley Expanded in Archipelago

This release supports one exact combination. Other versions may load, but they are untested.

| You need | Version |
|---|---|
| Stardew Valley | 1.6.15 |
| SMAPI | 4.5.2 |
| Stardew Valley Expanded | 1.15.11 (with its Content Patcher 2.9.1 and Farm Type Manager 1.26.1) |
| Archipelago | 0.6.8 |

Download from the [release page](https://github.com/poststructural/StardewValleyExpandedAPWorld/releases):

- `stardew_valley.apworld`: the Stardew Valley world with SVE switched on and the extra SVE checks
- `StardewValleyExpandedAP-<version>.zip`: the client mod (a build of StardewArchipelago with our SVE
  fixes) and our small Content Patcher pack. The same zip works on Windows and Mac.
- `SHA256SUMS.txt`, if you want to check the downloads

## 1. Install the world (whoever generates the game)

The file replaces Archipelago's built-in Stardew Valley world, so back up the original first.

**Windows:** go to `C:\ProgramData\Archipelago\lib\worlds\`. Rename `stardew_valley.apworld` to
`stardew_valley.apworld.bak`, then copy the new `stardew_valley.apworld` in.

**Mac (and Linux):** Archipelago runs from source. In your Archipelago folder, open `worlds/`. Move the
`stardew_valley` folder (or `stardew_valley.apworld`) somewhere safe, then copy the new
`stardew_valley.apworld` in.

To go back to stock Stardew Valley, restore the backup.

## 2. Install the mods (every Stardew Valley player)

1. Install SMAPI and Stardew Valley Expanded as usual, and check that SVE runs on its own.
2. Remove any existing `StardewArchipelago` folder from your `Mods` folder. If you have
   `[CP] StardewAP - SVE Patch` from the old SVE integration, remove that too.
3. Unzip `StardewValleyExpandedAP-<version>.zip`. Copy everything inside its `Mods/` folder into your
   game's `Mods` folder:
   - **Windows (Steam):** `C:\Program Files (x86)\Steam\steamapps\common\Stardew Valley\Mods`
   - **Mac (Steam):** `~/Library/Application Support/Steam/steamapps/common/Stardew Valley/Contents/MacOS/Mods`
     (in Finder, use Go → Go to Folder and paste the path)
4. You should now have `Mods/StardewArchipelago` and `Mods/[CP] StardewAP - SVE Gates`. Both are
   required: the client refuses to connect to an SVE game without the gates pack.

## 3. Your player yaml

```yaml
name: YourName
game: Stardew Valley
requires:
  version: 0.6.8
Stardew Valley:
  mods: [Stardew Valley Expanded]
  # turn these up for the extra SVE checks
  shipsanity: everything
  fishsanity: all
  friendsanity: all_with_marriage
  cropsanity: enabled
  cooksanity: all
  chefsanity: ["Queen of Sauce", "Purchases", "Friendship", "Skills"]
  craftsanity: all
  museumsanity: all
  eatsanity: ["Cooking", "Crops", "Fish", "Artisan", "Shop", "Poisonous"]
```

New SVE checks only appear when the matching option is on, so a default yaml is the same size as before.

## 4. Play

Start a new save from the title screen with the Archipelago fields filled in, the same as any
Stardew Valley Archipelago game. Items arrive **by mail**, so check your mailbox.

## Troubleshooting

- **"Please downgrade to a compatible mod version"**: the world and mod come from different
  releases. Install both from the same release.
- **The client says a required content pack is missing**: copy `[CP] StardewAP - SVE Gates` into
  `Mods`.
- **Logs**: the SMAPI log is at `%APPDATA%\StardewValley\ErrorLogs\SMAPI-latest.txt` (Windows) or
  `~/.config/StardewValley/ErrorLogs/SMAPI-latest.txt` (Mac). Attach it when you report a problem.
