#!/usr/bin/env python3
"""Parts you can leave on the tray.

UCLA's ingredient lists skip the assembly -- a Bruin Cheeseburger lists the patty and
the toppings but never the bun -- so there is nothing to subtract from the published
panel. Instead, price the common leave-behinds from USDA directly and attach them to the
items whose names imply them.  Writes data/removals.json.
"""
import json, sys
from pathlib import Path
from usda import load_usda, NUT
from overrides import find

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KEYS = [v[0] for v in NUT.values()]

# key -> (label, USDA phrase, grams, which item names offer it)
REMOVALS = {
    "bun":      ("the bun", "Interstate Brands Corp, Wonder Hamburger Rolls", 52,
                 r"burger|cheeseburger|hamburger|hot dog|sloppy"),
    "bread":    ("the bread", "Bread, white, commercially prepared", 56,
                 r"sandwich|melt|panini|press|cuban|havana|cheesesteak|\bsub\b|hoagie|toast|bagel"),
    "tortilla": ("the tortilla", "Tortillas, ready-to-bake or -fry, flour, refrigerated", 49,
                 r"burrito|quesadilla|wrap|taco\b"),
    "pita":     ("the pita", "Bread, pita, white, enriched", 60,
                 r"pita|gyro|shawarma|falafel"),
    "rice":     ("the rice", "Rice, white, long-grain, regular, cooked, enriched, without salt", 158,
                 r"\bbowl\b|fried rice|rice plate"),
    "fries":    ("the fries", "Potatoes, french fried, all types, salt added in processing, frozen, oven-heated", 85,
                 r"\bfries\b|combo|platter"),
}

def main():
    usda = load_usda(sys.argv[1])
    out = {}
    for key, (label, phrase, grams, pattern) in REMOVALS.items():
        fid = find(usda, phrase)
        if not fid:
            print(f"  !! no USDA match for {phrase}")
            continue
        f = usda[fid]
        vec = {k: round(f["n"].get(k, 0.0) / 100.0 * grams, 4) for k in KEYS}
        out[key] = {"label": label, "grams": grams, "usda": f["d"],
                    "match": pattern, "vec": vec}
        print(f"  {key:9} {label:14} {grams:3}g  {vec['kcal']:5.0f} kcal "
              f"C{vec['carb']:5.1f} P{vec['protein']:4.1f}   <- {f['d'][:44]}")
    (DATA / "removals.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"\nwrote data/removals.json: {len(out)} removals")

if __name__ == "__main__":
    main()
