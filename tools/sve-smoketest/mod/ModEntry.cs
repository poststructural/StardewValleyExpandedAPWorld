// Test-only SMAPI mod: creates a new Archipelago save from the title screen, then fires one location check per path
// through the game mechanics that StardewArchipelago hooks. Results go to the JSON file named in smoke.json.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Microsoft.Xna.Framework;
using Newtonsoft.Json;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
using StardewValley.Locations;
using StardewValley.Buildings;
using StardewValley.Menus;
using StardewValley.Network;
using StardewValley.SpecialOrders;

namespace APSmokeTest
{
    public class SmokeConfig
    {
        public string Server { get; set; } = "127.0.0.1:38290";
        public string Slot { get; set; } = "APSmoke";
        public string FarmName { get; set; } = "APSmoke";
        public string ResultPath { get; set; }
        public string FlagDir { get; set; }
        /// <summary>single (default), host (create save with a cabin, open to LAN co-op) or farmhand (join the host over LAN).</summary>
        public string Role { get; set; } = "single";
        public string JoinAddress { get; set; } = "127.0.0.1";
        /// <summary>Role host: load this existing APSmoke save as a co-op host instead of creating a new farm.</summary>
        public string LoadSave { get; set; }
    }

    public class PathResult
    {
        public string Path { get; set; }
        public bool Attempted { get; set; }
        public List<string> ExpectedLocations { get; set; } = new();
        public string Detail { get; set; }
        public string Error { get; set; }
    }

    public class ModEntry : Mod
    {
        private SmokeConfig _cfg;
        private enum Stage { Title, Creating, WaitWorld, Actions, WaitProceed, Sleeping, Day2, Done, HostOpen, HostWait, HostLoad, HostLoadWait, FhJoin, FhPick, FhWaitWorld, Script }
        private Stage _stage = Stage.Title;
        private int _tick, _stageTick, _actionIndex;
        private readonly List<PathResult> _results = new();
        private readonly Dictionary<string, object> _extra = new();
        private List<(string name, Func<PathResult> run)> _actions;

        public override void Entry(IModHelper helper)
        {
            var envPath = Environment.GetEnvironmentVariable("APSMOKE_CONFIG"); // lets two instances of one install use different configs
            _cfg = (!string.IsNullOrEmpty(envPath) ? JsonConvert.DeserializeObject<SmokeConfig>(File.ReadAllText(envPath)) : helper.Data.ReadJsonFile<SmokeConfig>("smoke.json")) ?? throw new Exception("smoke.json missing");
            helper.Events.GameLoop.UpdateTicked += OnTick;
            helper.Events.GameLoop.DayStarted += (_, _) => Monitor.Log($"[APSmoke] DayStarted day={Game1.dayOfMonth}", LogLevel.Info);
            helper.Events.GameLoop.DayEnding += (_, _) => Monitor.Log("[APSmoke] DayEnding", LogLevel.Info);
        }

        private void Say(string m) => Monitor.Log("[APSmoke] " + m, LogLevel.Info);
        private void SetStage(Stage s) { _stage = s; _stageTick = 0; Say("stage -> " + s); }

        private void OnTick(object sender, UpdateTickedEventArgs e)
        {
            _tick++; _stageTick++;
            try
            {
                if (Game1.options != null) Game1.options.pauseWhenOutOfFocus = false; // the test game runs unattended and unfocused
                switch (_stage)
                {
                    case Stage.Title: DoTitle(); break;
                    case Stage.Creating: DoCreating(); break;
                    case Stage.WaitWorld: DoWaitWorld(); break;
                    case Stage.Actions: DoActions(); break;
                    case Stage.WaitProceed: DoWaitProceed(); break;
                    case Stage.Sleeping: DoSleeping(); break;
                    case Stage.Day2: DoDay2(); break;
                    case Stage.HostOpen: DoHostOpen(); break;
                    case Stage.HostWait: DoHostWait(); break;
                    case Stage.FhJoin: DoFhJoin(); break;
                    case Stage.FhPick: DoFhPick(); break;
                    case Stage.FhWaitWorld: DoFhWaitWorld(); break;
                    case Stage.HostLoad: DoHostLoad(); break;
                    case Stage.HostLoadWait: DoHostLoadWait(); break;
                    case Stage.Script: DoScript(); break;
                }
            }
            catch (Exception ex)
            {
                Monitor.Log("[APSmoke] harness failure in stage " + _stage + ": " + ex, LogLevel.Error);
                _extra["harnessFailure"] = ex.ToString();
                WriteResults(false);
                SetStage(Stage.Done);
                Game1.quit = true;
            }
        }

        // ---------------------------------------------------------------- title / new game
        private void DoTitle()
        {
            if (Game1.activeClickableMenu is not TitleMenu || TitleMenu.subMenu != null || _tick < 360) return;
            if (_cfg.Role == "farmhand") { SetStage(Stage.FhJoin); return; }
            if (_cfg.Role == "host" && !string.IsNullOrEmpty(_cfg.LoadSave)) { SetStage(Stage.HostLoad); return; }
            // A co-op host uses the real Co-op > Host New Farm menu (one starting cabin by default), like a player would.
            var source = _cfg.Role == "host" ? CharacterCustomization.Source.HostNewFarm : CharacterCustomization.Source.NewGame;
            Say("opening new-game menu, source " + source);
            TitleMenu.subMenu = new CharacterCustomization(source, _cfg.Role == "host");
            SetStage(Stage.Creating);
        }

        private void DoCreating()
        {
            var sub = TitleMenu.subMenu;
            if (sub == null || sub.GetType().Name != "CharacterCustomizationArchipelago")
            {
                if (_stageTick % 120 == 0)
                {
                    var info = HarmonyLib.Harmony.GetPatchInfo(HarmonyLib.AccessTools.Method(typeof(TitleMenu), nameof(TitleMenu.update)));
                    Say($"waiting for AP menu: sub={sub?.GetType().FullName} active={Game1.activeClickableMenu?.GetType().Name} update-postfix owners={string.Join(",", info?.Postfixes.Select(x => x.owner) ?? new string[0])}");
                }
                if (_stageTick > 1200) throw new Exception("AP character menu never replaced the vanilla one; sub=" + sub?.GetType().FullName);
                return;
            }
            if (_stageTick < 30) return;
            var t = sub.GetType();
            void SetBox(string field, string text) => Helper.Reflection.GetField<TextBox>(sub, field, false).GetValue().Text = text;
            Game1.player.Name = "Smoke";
            Game1.player.farmName.Value = _cfg.FarmName;
            Game1.player.favoriteThing.Value = "Tests";
            SetBox("nameBox", "Smoke");
            SetBox("farmnameBox", _cfg.FarmName);
            SetBox("favThingBox", "Tests");
            ((TextBox)t.GetField("IpAddressTextBox").GetValue(sub)).Text = _cfg.Server;
            ((TextBox)t.GetField("SlotNameTextBox").GetValue(sub)).Text = _cfg.Slot;
            ((TextBox)t.GetField("PasswordTextBox").GetValue(sub)).Text = "";
            Helper.Reflection.GetField<bool>(sub, "skipIntro").SetValue(true);
            Say($"filled AP fields server={_cfg.Server} slot={_cfg.Slot} farm={_cfg.FarmName}; clicking OK");
            Helper.Reflection.GetMethod(sub, "optionButtonClick").Invoke("OK");
            SetStage(Stage.WaitWorld);
        }

        private void DoWaitWorld()
        {
            if (_stageTick > 60 * 90) throw new Exception("world never became ready after OK (connection failed?)");
            if (!Context.IsWorldReady || Game1.eventUp) return;
            if (Game1.activeClickableMenu != null)
            {
                if (_stageTick % 60 == 0) { Say("closing menu " + Game1.activeClickableMenu.GetType().Name); Game1.activeClickableMenu.exitThisMenu(false); }
                return;
            }
            if (_stageTick < 300) return; // let the client finish connecting and initializing
            Say($"world ready: save={Constants.SaveFolderName} day={Game1.dayOfMonth} loc={Game1.player.currentLocation?.Name}");
            _extra["saveFolder"] = Constants.SaveFolderName;
            if (!Constants.SaveFolderName.StartsWith("APSmoke")) throw new Exception("refusing to run in a non-APSmoke save: " + Constants.SaveFolderName);
            if (_cfg.Role == "host") { SetStage(Stage.HostOpen); return; }
            BuildActions();
            SetStage(Stage.Actions);
        }

        // ---------------------------------------------------------------- helpers
        private string IdByName(string name)
        {
            var hits = Game1.objectData.Where(kv => kv.Value.Name == name).Select(kv => kv.Key).ToList();
            if (hits.Count == 0) throw new Exception($"no object named '{name}' in Data/Objects");
            return hits.OrderBy(h => h.All(char.IsDigit) ? 1 : 0).First(); // prefer mod (non-numeric) ids
        }

        private PathResult Run(string path, Func<PathResult, string> body, params string[] expected)
        {
            var r = new PathResult { Path = path, Attempted = true, ExpectedLocations = expected.ToList() };
            try { r.Detail = body(r); }
            catch (Exception ex) { r.Error = ex.Message; Monitor.Log($"[APSmoke] path {path} failed: {ex}", LogLevel.Warn); }
            return r;
        }

        private void BuildActions()
        {
            var museumNames = new[] { "Amber", "Boomerang", "Faded Button", "Fossilized Apple", "Old Coin", "Rusty Shield", "Stone of Yoba" };
            _actions = new()
            {
                ("shipsanity-stage", () => Run("shipsanity", _ =>
                {
                    var bin = Game1.getFarm().getShippingBin(Game1.player);
                    var ids = new[] { "Cucumber", "Fish Dumpling", "Ferngill Primrose" }.Select(IdByName).ToList();
                    foreach (var id in ids) bin.Add(ItemRegistry.Create("(O)" + id, 1));
                    return "staged in shipping bin (ships at day end): " + string.Join(",", ids);
                }, "Shipsanity: Cucumber", "Shipsanity: Fish Dumpling", "Shipsanity: Ferngill Primrose")),
                ("fishsanity", () => Run("fishsanity", _ =>
                {
                    var gar = IdByName("Gar"); var bone = IdByName("Bonefish");
                    var a = Game1.player.caughtFish("(O)" + gar, 20); var b = Game1.player.caughtFish("(O)" + bone, 20); // the game passes qualified ids
                    return $"Farmer.caughtFish gar={gar}({a}) bonefish={bone}({b})";
                }, "Fishsanity: Gar", "Fishsanity: Bonefish")),
                ("cooksanity", () => Run("cooksanity", _ =>
                {
                    var a = IdByName("Fish Dumpling"); var b = IdByName("Void Delight");
                    Game1.player.cookedRecipe(a); Game1.player.cookedRecipe(b);
                    return $"Farmer.cookedRecipe {a},{b}";
                }, "Cook Fish Dumpling", "Cook Void Delight")),
                ("eatsanity", () => Run("eatsanity", _ =>
                {
                    var done = new List<string>();
                    foreach (var n in new[] { "Fish Dumpling", "Void Delight" })
                    {
                        var item = ItemRegistry.Create("(O)" + IdByName(n), 1);
                        Game1.player.itemToEat = item; Game1.player.mostRecentlyGrabbedItem = item;
                        Game1.player.doneEating();
                        done.Add(n);
                    }
                    return "Farmer.doneEating for " + string.Join(",", done);
                }, "Eat Fish Dumpling", "Eat Void Delight")),
                ("craftsanity", () => Run("craftsanity", _ =>
                {
                    var names = new[] { "Butter Churner", "Hedge Fence", "Haste Elixir" };
                    foreach (var n in names)
                    {
                        if (!CraftingRecipe.craftingRecipes.ContainsKey(n)) throw new Exception("no crafting recipe '" + n + "'");
                        Game1.player.craftingRecipes[n] = 1; // what CraftingPage does after a craft
                    }
                    Game1.stats.checkForCraftingAchievements();
                    return "crafted " + string.Join(",", names);
                }, "Craft Butter Churner", "Craft Hedge Fence", "Craft Haste Elixir")),
                ("friendsanity", () => Run("friendsanity", _ =>
                {
                    var d = new List<string>();
                    foreach (var n in new[] { "Henchman", "Sophia" })
                    {
                        var npc = Game1.getCharacterFromName(n) ?? throw new Exception("NPC not found: " + n);
                        if (!Game1.player.friendshipData.ContainsKey(n)) Game1.player.friendshipData.Add(n, new Friendship());
                        Game1.player.changeFriendship(300, npc);
                        d.Add($"{n}:{Game1.player.getFriendshipHeartLevelForNPC(n)}hearts");
                    }
                    return string.Join(" ", d);
                }, "Friendsanity: Henchman 1 <3", "Friendsanity: Sophia 1 <3")),
                ("museumsanity", () => Run("museumsanity", _ =>
                {
                    var museum = Game1.getLocationFromName("ArchaeologyHouse") as LibraryMuseum ?? throw new Exception("no museum");
                    int y = 2;
                    foreach (var n in museumNames) museum.museumPieces.Add(new Vector2(3, y++), IdByName(n));
                    museum.getRewardsForPlayer(Game1.player);
                    return "donated " + string.Join(",", museumNames);
                }, museumNames.Select(n => "Museumsanity: " + n).ToArray())),
                ("special-order", () => Run("special-order", _ =>
                {
                    var order = SpecialOrder.GetSpecialOrder("Robin3", null) ?? throw new Exception("GetSpecialOrder(Robin3) returned null");
                    Game1.player.team.specialOrders.Add(order);
                    foreach (var o in order.objectives) { o.SetCount(o.GetMaxCount()); (o as StardewValley.SpecialOrders.Objectives.DonateObjective)?.Confirm(); } // Confirm() is what closing the drop-box menu does
                    order.CheckCompletion();
                    var objs = string.Join(";", order.objectives.Select(o => $"{o.GetType().Name} {o.GetCount()}/{o.GetMaxCount()} complete={o.IsComplete()}"));
                    return $"Robin3 questName='{order.questName.Value}' state={order.questState.Value} objectives=[{objs}] inTeamList={Game1.player.team.specialOrders.Contains(order)}";
                }, "Quest: Grandpa's Shed")),
                ("gating", () => Run("gating", _ =>
                {
                    var farm = Game1.getFarm();
                    string Q(string id) => farm.checkEventPrecondition(id, false);
                    var before = (Q("77759254"), Q("5978924"));
                    Game1.player.mailReceived.Add("apAuroraVineyard"); Game1.player.mailReceived.Add("apMorganSchooling");
                    var after = (Q("77759254"), Q("5978924"));
                    Game1.player.mailReceived.Remove("apAuroraVineyard"); Game1.player.mailReceived.Remove("apMorganSchooling");
                    _extra["gating"] = new { before = new { e77759254 = before.Item1, e5978924 = before.Item2 }, after = new { e77759254 = after.Item1, e5978924 = after.Item2 } };
                    var ok = before.Item1 == "-1" && before.Item2 == "-1" && after.Item1 == "77759254" && after.Item2 == "5978924";
                    if (!ok) throw new Exception($"gate mismatch before={before} after={after}");
                    return $"before={before} after={after}";
                })),
            };
        }

        private void DoActions()
        {
            if (_stageTick % 45 != 0) return;
            if (_actionIndex >= _actions.Count)
            {
                WriteResults(false);
                File.WriteAllText(Path.Combine(_cfg.FlagDir, "ready.flag"), "ready");
                Say("all actions fired; waiting for harness to send items (proceed.flag)");
                SetStage(Stage.WaitProceed);
                return;
            }
            var (name, run) = _actions[_actionIndex++];
            Say("action " + name);
            _results.Add(run());
        }

        private void DoWaitProceed()
        {
            if (!File.Exists(Path.Combine(_cfg.FlagDir, "proceed.flag"))) return;
            if (_stageTick < 120) return;
            Game1.warpFarmer("FarmHouse", 9, 9, false);
            Say("sleeping");
            SetStage(Stage.Sleeping);
        }

        private void DoSleeping()
        {
            if (Game1.activeClickableMenu is ShippingMenu sm)
            {
                if (_stageTick % 30 == 0)
                {
                    try { sm.receiveLeftClick(sm.okButton.bounds.Center.X, sm.okButton.bounds.Center.Y); } catch { }
                }
                return;
            }
            if (Game1.activeClickableMenu != null && _stageTick % 60 == 0) { Game1.activeClickableMenu.exitThisMenu(false); return; }
            if (Game1.dayOfMonth >= 2 && Context.IsWorldReady && Game1.activeClickableMenu == null && !Game1.fadeToBlack && _stageTick > 240)
            {
                SetStage(Stage.Day2);
                return;
            }
            if (_stageTick == 200 && Game1.dayOfMonth == 1 && Game1.player.currentLocation?.Name == "FarmHouse")
            {
                Say("startSleep");
                Helper.Reflection.GetMethod(Game1.player.currentLocation, "startSleep").Invoke();
            }
            if (_stageTick == 1800 && Game1.dayOfMonth == 1) { Say("startSleep did not advance the day; forcing NewDay"); Game1.NewDay(0f); }
            if (_stageTick > 60 * 240) throw new Exception("day never advanced");
        }

        private void DoDay2()
        {
            if (_stageTick < 300) return; // let day-start item/mail processing settle
            var p = Game1.player;
            _extra["day2"] = new
            {
                day = Game1.dayOfMonth,
                mailbox = p.mailbox.ToList(),
                mailForTomorrow = p.mailForTomorrow.ToList(),
                mailReceivedAp = p.mailReceived.Where(m => m.StartsWith("ap", StringComparison.OrdinalIgnoreCase)).ToList(),
                hasAuroraFlag = p.mailReceived.Contains("apAuroraVineyard"),
                hasMorganFlag = p.mailReceived.Contains("apMorganSchooling"),
                cookingRecipes = p.cookingRecipes.Keys.Where(k => k.Contains("Dumpling") || k.Contains("Ramen") || k.Contains("Nectarine") || k.Contains("Cheese")).ToList(),
                craftingRecipesLearned = p.craftingRecipes.Keys.Where(k => k.Contains("Hardwood") || k.Contains("Hedge")).ToList(),
            };
            WriteResults(true);
            SetStage(Stage.Done);
            Game1.quit = true;
        }

        // ---------------------------------------------------------------- co-op: host
        private void Flag(string name) { File.WriteAllText(Path.Combine(_cfg.FlagDir, name), "1"); Say("flag " + name); }
        private bool HasFlag(string name) => File.Exists(Path.Combine(_cfg.FlagDir, name));

        private void DoHostLoad()
        {
            if (!_cfg.LoadSave.StartsWith("APSmoke")) throw new Exception("refusing to load a non-APSmoke save: " + _cfg.LoadSave);
            Say("loading save " + _cfg.LoadSave + " as a co-op host");
            Game1.multiplayerMode = 2;      // what CoopMenu's host-file slot does
            SaveGame.Load(_cfg.LoadSave);
            Game1.exitActiveMenu();
            SetStage(Stage.HostLoadWait);
        }

        private void DoHostLoadWait()
        {
            if (_stageTick > 60 * 120) throw new Exception("reloaded host world never became ready");
            if (!Context.IsWorldReady) return;
            if (Game1.activeClickableMenu != null && _stageTick % 60 == 0) Game1.activeClickableMenu.exitThisMenu(false);
            if (_stageTick < 600) return;   // let the client reconnect and initialise
            if (Game1.server == null) { if (_stageTick % 300 == 0) Say("waiting for the LAN server"); return; }
            Say($"reloaded world ready: save={Constants.SaveFolderName} day={Game1.dayOfMonth}");
            Flag("host.ready.flag");
            SetStage(Stage.Script);
        }

        private void DoHostOpen()
        {
            if (_stageTick < 120) return;
            var farm = Game1.getFarm();
            var cabin = farm.buildings.Select(b => b.indoors.Value).OfType<Cabin>().FirstOrDefault() ?? throw new Exception("no cabin on the farm (the Host New Farm menu's cabins did not apply)");
            var fh = cabin.owner;
            fh.isCustomized.Value = true;   // skip the farmhand character creator
            fh.Name = "Hand";
            fh.farmName.Value = _cfg.FarmName;
            fh.favoriteThing.Value = "Tests";
            _extra["cabins"] = farm.buildings.Count(b => b.indoors.Value is Cabin);
            Say($"cabin ready for farmhand '{fh.Name}' (multiplayerMode={Game1.multiplayerMode}, cabins={_extra["cabins"]})");
            Game1.multiplayerMode = 2;      // already 2 from the Host New Farm menu; the game starts the LAN server itself
            SetStage(Stage.HostWait);
        }

        private void DoHostWait()
        {
            if (_stageTick % 60 == 0 && Game1.activeClickableMenu != null && Game1.activeClickableMenu is not ShippingMenu) Game1.activeClickableMenu.exitThisMenu(false);
            if (Game1.server != null && _stageTick > 120) { Flag("host.ready.flag"); SetStage(Stage.Script); }
            if (_stageTick > 60 * 300) throw new Exception("host timed out waiting for the LAN server");
        }

        // ---------------------------------------------------------------- co-op: farmhand
        private void DoFhJoin()
        {
            Say("joining " + _cfg.JoinAddress + " over LAN");
            TitleMenu.subMenu = new FarmhandMenu(Helper.Reflection.GetField<Multiplayer>(typeof(Game1), "multiplayer").GetValue().InitClient(new LidgrenClient(_cfg.JoinAddress)));
            SetStage(Stage.FhPick);
        }

        private void DoFhPick()
        {
            if (TitleMenu.subMenu is not FarmhandMenu fm) { if (_stageTick > 120) throw new Exception("farmhand menu vanished: " + TitleMenu.subMenu?.GetType().Name); return; }
            if (_stageTick > 60 * 90) throw new Exception("no farmhand slot appeared");
            var slots = fm.MenuSlots.OfType<FarmhandMenu.FarmhandSlot>().Where(sl => !sl.BelongsToAnotherPlayer()).ToList();
            var slot = slots.FirstOrDefault(sl => sl.Farmer.Name == "Hand") ?? slots.FirstOrDefault();
            if (slot == null) return;
            Say("activating farmhand slot " + slot.Farmer.Name);
            slot.Activate();
            SetStage(Stage.FhWaitWorld);
        }

        private void DoFhWaitWorld()
        {
            if (_stageTick > 60 * 120) throw new Exception("farmhand world never became ready");
            if (Game1.activeClickableMenu is CharacterCustomization) throw new Exception("farmhand got the character creator (cabin not pre-customized)");
            if (!Context.IsWorldReady) return;
            if (Game1.activeClickableMenu != null && _stageTick % 60 == 0) Game1.activeClickableMenu.exitThisMenu(false);
            if (_stageTick < 300) return;
            Say($"farmhand world ready: IsMainPlayer={Context.IsMainPlayer} IsMultiplayer={Context.IsMultiplayer} player={Game1.player.Name}");
            Flag("farmhand.ready.flag");
            SetStage(Stage.Script);
        }

        // ---------------------------------------------------------------- co-op: scripted steps (both roles)
        // The harness writes step.json {"N":n,"Action":"..","Tag":".."}; each game runs it once and writes <role>.done.<n>.
        private class Step { public int N { get; set; } public string Action { get; set; } public string Tag { get; set; } }
        private int _lastStep;
        private Step _step;
        private int _stepTick;

        private void DoScript()
        {
            if (_stageTick > 60 * 3600) throw new Exception("script timed out");
            if (_step == null)
            {
                var path = Path.Combine(_cfg.FlagDir, "step.json");
                if (_tick % 30 != 0 || !File.Exists(path)) return;
                Step s;
                try { s = JsonConvert.DeserializeObject<Step>(File.ReadAllText(path)); } catch { return; }
                if (s == null || s.N <= _lastStep) return;
                _step = s; _stepTick = 0;
                Say($"step {s.N}: {s.Action} {s.Tag}");
            }
            _stepTick++;
            bool done = _step.Action switch
            {
                "snap" => StepSnap(_step.Tag),
                "prep" => StepPrep(),
                "mail" => StepMail(),
                "sleep" => StepSleep(),
                "fire" => StepFire(),
                "quit" => StepQuit(),
                _ => throw new Exception("unknown step " + _step.Action),
            };
            if (!done || _step == null) return;
            File.WriteAllText(Path.Combine(_cfg.FlagDir, $"{_cfg.Role}.done.{_step.N}"), "1");
            Say($"step {_step.N} done");
            _lastStep = _step.N; _step = null;
        }

        private static object ApStatic(string typeName, string method)
        {
            var t = HarmonyLib.AccessTools.TypeByName(typeName) ?? throw new Exception("type not found: " + typeName);
            return HarmonyLib.AccessTools.Method(t, method).Invoke(null, null);
        }

        private bool StepSnap(string tag)
        {
            if (_stepTick < 60) return false;
            var p = Game1.player;
            var modEntry = HarmonyLib.AccessTools.TypeByName("StardewArchipelago.ModEntry");
            var instance = HarmonyLib.AccessTools.Field(modEntry, "Instance").GetValue(null);
            var itemManager = HarmonyLib.AccessTools.Field(modEntry, "_itemManager").GetValue(instance);
            var processed = itemManager == null ? -1 : ((System.Collections.ICollection)HarmonyLib.AccessTools.Method(itemManager.GetType(), "GetAllItemsAlreadyProcessed").Invoke(itemManager, null)).Count;
            var apFriend = (Dictionary<string, int>)ApStatic("StardewArchipelago.Locations.CodeInjections.Vanilla.Relationship.FriendshipInjections", "GetArchipelagoFriendshipPoints");
            var apXp = (Dictionary<int, int>)ApStatic("StardewArchipelago.Locations.CodeInjections.Vanilla.SkillInjections", "GetArchipelagoExperience");
            var farm = Game1.getFarm();
            var snap = new
            {
                role = _cfg.Role, tag, day = Game1.dayOfMonth, isMain = Context.IsMainPlayer, player = p.Name, id = p.UniqueMultiplayerID,
                save = Constants.SaveFolderName,
                money = p.Money,
                maxItems = p.MaxItems,
                cursor = p.modData.TryGetValue("KaitoKid.StardewArchipelago/ItemsAppliedUpTo", out var c) ? c : null,
                processedItems = processed,
                knowsFishDumpling = p.cookingRecipes.Keys.Any(k => k.Contains("Fish Dumpling")),
                apFriendAbigail = apFriend.TryGetValue("Abigail", out var fa) ? fa : 0,
                apXpFishing = apXp.TryGetValue(1, out var xf) ? xf : 0,
                mailbox = p.mailbox.ToList(),
                mailForTomorrow = p.mailForTomorrow.ToList(),
                apLettersReceived = p.mailReceived.Where(m => m.Contains("|")).ToList(),
                buildings = farm.buildings.Select(b => b.buildingType.Value).OrderBy(x => x).ToList(),
                pets = Game1.locations.Sum(l => l.characters.OfType<StardewValley.Characters.Pet>().Count()) + farm.buildings.Where(b => b.indoors.Value != null).Sum(b => b.indoors.Value.characters.OfType<StardewValley.Characters.Pet>().Count()),
                farmers = Game1.getOnlineFarmers().Select(f => f.Name).ToList(),
            };
            File.WriteAllText(Path.Combine(_cfg.FlagDir, $"{_cfg.Role}.snap.{tag}.json"), JsonConvert.SerializeObject(snap, Formatting.Indented));
            Say("snapshot " + tag + ": " + JsonConvert.SerializeObject(snap));
            return true;
        }

        private bool StepPrep()
        {
            // Meet Abigail so "Friendship Bonus" has someone to raise (it raises every NPC in friendshipData).
            if (!Game1.player.friendshipData.ContainsKey("Abigail")) Game1.player.friendshipData.Add("Abigail", new Friendship());
            return true;
        }

        private bool StepMail()
        {
            if (_stepTick % 40 != 0) return false;
            if (Game1.activeClickableMenu != null) { Game1.activeClickableMenu.exitThisMenu(false); return false; } // closing a LetterViewerMenu applies its action
            if (Game1.dialogueUp) { Game1.dialogueUp = false; Game1.currentSpeaker = null; } // a closed hold-up message can leave the flag set
            if (_stepTick % 600 == 0) Say($"mail: mailbox={Game1.mailbox.Count} freeze={Game1.player.freezePause} canMove={Game1.player.canMove} eventUp={Game1.eventUp}");
            if (Game1.player.freezePause > 0 || Game1.eventUp) return false;
            if (Game1.mailbox.Count == 0) return _stepTick > 160;
            Say("opening letter " + Game1.mailbox[0]);
            Game1.currentLocation.mailbox();
            return false;
        }

        private int _sleepStartDay, _sleepSettled;
        private bool StepSleep()
        {
            if (_stepTick == 1)
            {
                _sleepStartDay = Game1.dayOfMonth;
                _sleepSettled = 0;
                var home = Utility.getHomeOfFarmer(Game1.player);
                var bed = home.GetPlayerBedSpot();
                Game1.warpFarmer(home.NameOrUniqueName, bed.X, bed.Y, false);
                Say("warped to bed in " + home.NameOrUniqueName);
                return false;
            }
            var menu = Game1.activeClickableMenu;
            if (menu is ShippingMenu sm)
            {
                if (_stepTick % 30 == 0) { try { sm.receiveLeftClick(sm.okButton.bounds.Center.X, sm.okButton.bounds.Center.Y); } catch { } }
                return false;
            }
            var waitMenu = menu is ReadyCheckDialog || menu is SaveGameMenu;
            if (menu != null && !waitMenu && _stepTick % 60 == 0) { Say("closing " + menu.GetType().Name); menu.exitThisMenu(false); return false; }
            if (Game1.dayOfMonth != _sleepStartDay)
            {
                if (Context.IsWorldReady && menu == null && !Game1.fadeToBlack && !Game1.eventUp) _sleepSettled++;
                return _sleepSettled > 420;
            }
            if (_stepTick == 240)
            {
                Say($"startSleep in {Game1.player.currentLocation?.Name}");
                Helper.Reflection.GetMethod(Game1.player.currentLocation, "startSleep").Invoke();
            }
            if (_stepTick > 60 * 300) throw new Exception("day never advanced");
            return false;
        }

        private bool StepFire()
        {
            var fired = new List<string>();
            if (_cfg.Role == "farmhand")
            {
                var gar = IdByName("Gar");
                fired.Add($"caughtFish {gar}={Game1.player.caughtFish("(O)" + gar, 20)}");
                var dumpling = IdByName("Fish Dumpling");
                Game1.player.cookedRecipe(dumpling); fired.Add("cookedRecipe " + dumpling);
                if (!CraftingRecipe.craftingRecipes.ContainsKey("Hedge Fence")) throw new Exception("no crafting recipe 'Hedge Fence'");
                Game1.player.craftingRecipes["Hedge Fence"] = 1; Game1.stats.checkForCraftingAchievements(); fired.Add("crafted Hedge Fence");
                var bin = Game1.getFarm().getShippingBin(Game1.player);
                bin.Add(ItemRegistry.Create("(O)" + IdByName("Cucumber"), 1)); fired.Add($"shipped Cucumber (bin has {bin.Count}, separateWallets={Game1.player.team.useSeparateWallets.Value})");
                Game1.player.gainExperience(1, 100); fired.Add("gainExperience fishing 100");
            }
            else
            {
                var bone = IdByName("Bonefish");
                fired.Add($"caughtFish {bone}={Game1.player.caughtFish("(O)" + bone, 20)}");
                var vd = IdByName("Void Delight");
                Game1.player.cookedRecipe(vd); fired.Add("cookedRecipe " + vd);
            }
            Say($"{_cfg.Role} fired: " + string.Join("; ", fired));
            return true;
        }

        private bool StepQuit()
        {
            File.WriteAllText(Path.Combine(_cfg.FlagDir, $"{_cfg.Role}.done.{_step.N}"), "1");
            WriteResults(true);
            _step = null;
            SetStage(Stage.Done);
            Game1.quit = true;
            return true;
        }

        private void WriteResults(bool final)
        {
            var obj = new { final, harnessVersion = 1, results = _results, extra = _extra };
            File.WriteAllText(_cfg.ResultPath, JsonConvert.SerializeObject(obj, Formatting.Indented));
            Say("wrote results (final=" + final + ")");
        }
    }
}
