# Spike 01 — Does SVE 1.15.11 load without a rebuilt DLL?

**Date:** 2026-10-31
**Question:** the 1.14 integration shipped a rebuilt SVE code DLL (`1.14.31-archipelago-1`) because
SVE 1.14.46 could not load on SDV 1.6.9+. Does SVE 1.15.11 need the same treatment on SDV 1.6.15?

**Answer: No.** SVE 1.15.11 loads natively, patches the game, and runs its content packs with
zero warnings and zero errors.

## Environment

| Component | Version |
|---|---|
| Stardew Valley | 1.6.15 build 24356 (copy of `Stardew Valley_backup`) |
| SMAPI | 4.5.2 (manual install from `SVE_Mod\Dependencies\SMAPI 4.5.2 installer\internal\windows\install.dat`) |
| Stardew Valley Expanded | 1.15.11 (Code + `[CP]` + `[FTM]`) |
| Content Patcher | 2.9.1 |
| Farm Type Manager | 1.26.1 |
| Testbed | `_testbed\sdv-sve` (disposable copy; Steam install untouched) |

## Method

1. `robocopy` the pristine 1.6.15 backup to `_testbed\sdv-sve`.
2. Unzip `install.dat` into the game folder; copy `Stardew Valley.deps.json` →
   `StardewModdingAPI.deps.json` (the documented manual install; avoids the interactive installer).
3. Stage into `Mods\`: `Stardew Valley Expanded Code`, `[CP] Stardew Valley Expanded`,
   `[FTM] Stardew Valley Expanded`, `ContentPatcher`, `FarmTypeManager`.
4. Write `steam_appid.txt` = `413150` so the copy does not fight Steam for the app id.
5. Launch `StardewModdingAPI.exe` with stdout redirected, let it run ~55 s, terminate, read
   `%APPDATA%\StardewValley\ErrorLogs\SMAPI-latest.txt`.

## Evidence (archived at `_testbed\logs\SMAPI-latest-spike1.txt`)

```
[SMAPI] SMAPI 4.5.2 with Stardew Valley 1.6.15 build 24356 on Windows 11
[SMAPI] Loaded 5 mods:
[SMAPI]    Content Patcher 2.9.1 by Pathoschild
[SMAPI]    Farm Type Manager (FTM) 1.26.1 by Esca
[SMAPI]    Save Backup 4.5.2
[SMAPI]    Stardew Valley Expanded 1.15.11 by FlashShifter, Esca, and kittycatcasey | Adds coded elements to the game
[SMAPI]    Console Commands 4.5.2
[SMAPI] Loaded 2 content packs:
[SMAPI]    Stardew Valley Expanded 1.15.11 by FlashShifter [Content Patcher]
[SMAPI]    Stardew Valley Expanded Farm Type Manager 1.15.11 by FlashShifter [FTM]
[SMAPI]    Patched game code
[Stardew Valley Expanded] Installation check completed. Everything seems fine!
[SMAPI] Mods loaded and ready!
```

Log severity counts for the run: **TRACE 120, DEBUG 5, INFO 21, WARN 0, ERROR 0, ALERT 0**.
Content Patcher was observed editing `Data/Objects`, `Data/Crops`, `Data/BigCraftables`,
`Data/Locations`, `Strings/StringsFromCSFiles` for the SVE pack, and the game reached Galaxy auth
success (title screen initialised).

## Implications

1. **The decompile-and-rebuild tail is gone.** We do not have to maintain a patched SVE DLL for
   game compatibility. That removes the single largest recurring cost from the project and the
   reason the integration was dropped ("becoming too unstable and unmaintained").
2. **The integration becomes ordinary Harmony + Content Patcher work**, which is maintainable
   against SVE point releases as long as type/member names hold.
3. **The remaining unknown moves to Reflection/Harmony compatibility**: do the AP mod's SVE
   patches (`AddSVEModInjections`, `SVECutsceneInjections`, `PatchSVEShops`, `SVENameMapper`,
   `JunimoShopStockModifier`, `SVEUnlockManager`) still bind to members that exist in 1.15.11?
   That is spike 02 and it needs a built mod + a generated slot.
4. Witchybun's `[CP] StardewAP - SVE Patch` 2.1.2 (5 small JSON files: event requirement edits,
   Grandpa's Shed map + special order) is ordinary Content Patcher content and remains portable;
   it must be re-checked against 1.15 whether those hooks still exist.

## Reproduce

```
robocopy "<integration>\Stardew Valley_backup" "<integration>\_testbed\sdv-sve" /MIR
# unzip install.dat -> testbed, copy deps.json
# stage Mods\, write steam_appid.txt
Start-Process "<testbed>\StardewModdingAPI.exe" -WorkingDirectory "<testbed>"
# ~55 s, then read %APPDATA%\StardewValley\ErrorLogs\SMAPI-latest.txt
```

## Notes for later

- `git` in this environment needs `-c http.sslBackend=openssl`; the default schannel backend fails
  with `SEC_E_NO_CREDENTIALS`. Relevant for any CI that clones during a build.
- The farm-map packs (`Frontier Farm`, `Grandpa's Farm`, `Immersive Farm 2 Remastered`,
  `GrampletonFields`) were deliberately not staged for this spike; they are separate content packs
  and will matter for region/entrance mapping, not for DLL loading.
