#!/usr/bin/env python3
"""Nutrition for venues UCLA publishes nothing for -- the food trucks.

Neither UCLA nor the Nom app carries a nutrition panel for a truck, and the vendors
do not publish one either.  What the vendors do publish is a plain-English description
of what is in each item ("all beef frank ... fried in canola oil with their house's
signature dough"), so each item is written out here as a composition in grams, every
part resolved against USDA SR Legacy, and the nutrient vector summed from that.

These are reconstructions.  They are flagged estimated end to end, unlike the hall
items where the macros and 19 nutrients are UCLA's own published figures.
"""
import json, sys
from pathlib import Path
from usda import load_usda, NUT
from overrides import find

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KEYS = [v[0] for v in NUT.values()]

def main():
    usda = load_usda(sys.argv[1])
    spec = json.loads((DATA / "manual_venues.json").read_text())
    out = {"venues": [], "items": {}}
    nid = 0
    unresolved = []

    for v in spec["venues"]:
        rows = []
        for it in v["items"]:
            nid += 1
            rid = "m%d" % nid
            vec = {k: 0.0 for k in KEYS}
            grams = 0
            for phrase, g in it["parts"]:
                fid = find(usda, phrase)
                if not fid:
                    unresolved.append(phrase)
                    continue
                f = usda[fid]
                got = f["d"]
                if got.lower()[:len(phrase)] != phrase.lower():
                    print(f"  ~ {phrase[:44]:44} -> {got[:50]}")
                for k in KEYS:
                    vec[k] += f["n"].get(k, 0.0) / 100.0 * g
                grams += g
            out["items"][rid] = {
                "n": it["name"],
                "s": it.get("serving", ""),
                "g": grams,
                "vec": {k: round(x, 4) for k, x in vec.items()},
                "desc": it.get("desc", ""),
            }
            rows.append([v.get("station", "Truck"), rid])
            print(f"  {v['name']:16} {it['name'][:26]:26} {grams:4}g  "
                  f"{vec['kcal']:5.0f} kcal  P{vec['protein']:4.0f} F{vec['fat']:4.0f} C{vec['carb']:4.0f}")
        out["venues"].append({"k": v["key"], "n": v["name"], "kind": v["kind"],
                              "note": v.get("note", ""), "rows": rows})

    (DATA / "manual_items.json").write_text(json.dumps(out, ensure_ascii=False))
    if unresolved:
        print("\nUNRESOLVED (fix the phrase in manual_venues.json):", unresolved)
    print(f"\nwrote data/manual_items.json: {len(out['items'])} items across "
          f"{len(out['venues'])} venue(s)")

if __name__ == "__main__":
    main()
