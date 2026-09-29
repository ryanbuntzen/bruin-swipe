#!/usr/bin/env python3
"""Compact everything into data/foods.json for the app."""
import json, re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

MEASURED = ["kcal", "protein", "fat", "satfat", "transfat", "chol", "sodium", "carb",
            "fiber", "sugar", "addsugar", "calcium", "iron", "potassium",
            "vit_a", "vit_b6", "vit_b12", "vit_c", "vit_d"]
ESTIMATED = ["magnesium", "phosphorus", "zinc", "copper", "manganese", "selenium",
             "vit_e", "vit_k", "thiamin", "riboflavin", "niacin", "folate",
             "pantothenic", "choline", "mufa", "pufa",
             "omega3_ala", "omega3_epa", "omega3_dha", "omega6"]
ORDER = MEASURED + ESTIMATED

# the at-a-glance page and the venue pages name the same hall differently
CANON = {
    "de-neve-dining": "De Neve Dining",
    "spice-kitchen": "Feast at Rieber",
    "covel-dining-2": "Covel Dining",
    "sproul-dining": "Sproul Dining",
    "bruin-plate": "Bruin Plate",
}
AYCE = {"De Neve Dining", "Sproul Dining", "Covel Dining", "Feast at Rieber", "Bruin Plate"}
VENUE_NAME = {
    "De Neve Dining": "De Neve", "Sproul Dining": "Sproul", "Covel Dining": "Epicuria at Covel",
    "Feast at Rieber": "Feast at Rieber", "Bruin Plate": "Bruin Plate",
    "rendezvous": "Rendezvous", "bruin-cafe": "Bruin Café", "cafe-1919": "Café 1919",
    "the-drey": "The Drey", "the-study-at-hedrick": "The Study at Hedrick",
    "epicuria-at-ackerman": "Epicuria at Ackerman", "bruin-bowl": "Bruin Bowl",
}

def round_sig(x):
    if x is None:
        return 0
    if x == 0:
        return 0
    a = abs(x)
    return round(x, 3 if a < 1 else (2 if a < 10 else (1 if a < 100 else 0)))

def main():
    items = json.loads((DATA / "ucla_full.json").read_text())

    # ---- venues and their menus
    menus = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))   # venue>day>meal>station
    stations = defaultdict(lambda: defaultdict(set))
    for rid, v in items.items():
        for w in v.get("where", []):
            ven = CANON.get(w["venue"], w["venue"])
            day, meal, st = w["date"], w["meal"] or "All day", w["station"]
            menus[ven][day][meal].append([st, rid])
            stations[ven][meal].add(st)

    venues = []
    for ven, days in menus.items():
        kind = "ayce" if ven in AYCE else "pickup"
        venues.append({
            "k": ven,
            "n": VENUE_NAME.get(ven, ven.replace("-", " ").title()),
            "kind": kind,
            "menu": {d: {m: rows for m, rows in ms.items()} for d, ms in days.items()},
        })
    venues.sort(key=lambda v: (v["kind"] != "ayce", v["n"]))

    # ---- items
    out = {}
    for rid, v in items.items():
        if "kcal" not in v and not v.get("build_groups"):
            continue
        rec = {"n": v["name"]}
        if v.get("serving"):
            rec["s"] = v["serving"]
        if v.get("grams"):
            rec["g"] = v["grams"]
        if "kcal" in v:
            est = v.get("est") or {}
            rec["v"] = [round_sig(v.get(k, 0.0)) for k in MEASURED] + \
                       [round_sig(est.get(k, 0.0)) for k in ESTIMATED]
            rec["src"] = v.get("micro_source", "none")
            if v.get("fit_residual") is not None:
                rec["r"] = v["fit_residual"]
        if v.get("build_groups"):
            rec["b"] = [[c["id"] for c in g if c["id"] in items] for g in v["build_groups"]]
        if v.get("tags"):
            rec["t"] = [t for t in v["tags"] if t not in ("low-carbon", "high-carbon")]
        if v.get("allergens"):
            rec["a"] = v["allergens"]
        out[rid] = rec

    payload = {
        "nutrients": ORDER,
        "measured": len(MEASURED),
        "dates": sorted({w["date"] for v in items.values() for w in v.get("where", [])
                         if w["date"] != "standing"}),
        "venues": venues,
        "items": out,
    }
    p = DATA / "foods.json"
    p.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    kb = p.stat().st_size / 1024
    fitted = sum(1 for r in out.values() if r.get("src") == "ingredient-fit")
    builds = sum(1 for r in out.values() if "b" in r)
    print(f"data/foods.json  {kb:.0f} KB")
    print(f"  {len(out)} items, {fitted} with fitted micros, {builds} builders")
    print(f"  {len(venues)} venues: " + ", ".join(f"{v['n']}({v['kind'][0]})" for v in venues))
    print(f"  menu days: {payload['dates']}")

if __name__ == "__main__":
    main()
