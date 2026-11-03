"""Dump a generated multiworld's Stardew locations: prints JSON {id: name} for slot 1 (run with the AP venv, cwd = AP checkout)."""
import json, sys, zipfile, zlib
sys.path.insert(0, ".")
import Utils  # noqa: E402


def load(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.endswith(".archipelago"))
        raw = z.read(name)
    return Utils.restricted_loads(zlib.decompress(raw[1:]))


if __name__ == "__main__":
    md = load(sys.argv[1])
    pkg = md["datapackage"]["Stardew Valley"]["location_name_to_id"]
    mine = md["locations"][1]  # slot 1 locations: {id: (item, player, flags)}
    out = {str(i): n for n, i in pkg.items() if i in mine}
    json.dump(out, open(sys.argv[2], "w"))
    print(len(out), "locations in slot 1")
