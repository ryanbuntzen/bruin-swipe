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
    "bruin-plate": "Bruin Plate",
}
AYCE = {"De Neve Dining", "Covel Dining", "Feast at Rieber", "Bruin Plate"}
VENUE_NAME = {
    "De Neve Dining": "De Neve", "Covel Dining": "Epicuria at Covel",
    "Feast at Rieber": "Feast at Rieber", "Bruin Plate": "Bruin Plate",
    "rendezvous": "Rendezvous", "bruin-cafe": "Bruin Café", "cafe-1919": "Café 1919",
    "the-drey": "The Drey", "the-study-at-hedrick": "The Study at Hedrick",
    "epicuria-at-ackerman": "Epicuria at Ackerman", "bruin-bowl": "Bruin Bowl",
}

# How a portion actually looks on a tray. UCLA publishes "3.29oz", which tells you
# nothing in line, so each item carries the unit it is naturally counted in and the app
# turns weight x servings into "5 eggs" or "3 scoops = 1 cup".
# (unit grams, singular, plural, style)  -- style drives the hint the app appends.
PORTION = [
    (r"\bhard cooked egg|\bfried egg|poached egg",      50,  "egg", "eggs", "count"),
    (r"scrambled egg|omelet|egg white|^egg\b",           47,  "egg", "eggs", "worth"),
    (r"\bturkey bacon",                                  13,  "strip", "strips", "count"),
    (r"\bbacon\b",                                       15,  "strip", "strips", "count"),
    (r"sausage|link|chorizo|hot ?dog|frank",              28,  "link", "links", "count"),
    (r"\bmilk\b|juice|spritzer|\bwater\b|kombucha|tea", 240, "glass", "glasses", "count"),
    (r"yogurt|cottage cheese",                           113, "ladle", "ladles", "halfcup"),
    (r"sliced .*cheese|cheese.*slice|swiss|provolone|american cheese", 28, "slice", "slices", "count"),
    (r"\bham\b|roast beef|pastrami|salami|prosciutto|deli|sliced turkey",
                                                           28,  "slice", "slices", "count"),
    (r"grape",                                             5,  "grape", "grapes", "handful"),
    (r"cantaloupe|watermelon|honeydew|\bmelon",           14,  "cube", "cubes", "cup"),
    (r"pineapple",                                        15,  "chunk", "chunks", "cup"),
    (r"\bbanana\b|\bapple\b|\borange\b|\bkiwi\b|\bpear\b|\bpeach\b", 0, "medium", "medium", "whole"),
    (r"breast|thigh|drumstick|\bwing|chop\b|tenderloin|fillet|filet|steak|tri.?tip|\bribs?\b|patty|cutlet|fillet",
                                                            0,  "piece", "pieces", "piece"),
    (r"\bfries\b|tater tot",                             5.3, "fry", "fries", "basket"),
    (r"\brice\b|quinoa|grain|couscous|farro",            79,  "scoop", "scoops", "rice"),
    (r"burger|sandwich|wrap|burrito|taco\b|calzone|panini|roll\b|bowl\b|plate\b|platter",
                                                            0,  "", "", "whole"),
    (r"bar\b|salad bar|yogurt bar",                       0,  "", "", "whole"),
]

def portion_for(name, grams):
    import re as _r
    for pat, unit, sing, plur, style in PORTION:
        if _r.search(pat, name, _r.I):
            if style in ("whole", "piece"):      # counted as-is, no unit weight needed
                return [0, sing, plur, style]
            if not grams or not unit:
                return None
            return [unit, sing, plur, style]
    if grams:
        return [120, "scoop", "scoops", "plain"]     # a serving spoon of something hot
    return None


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
            if "sproul" in w["venue"].lower():
                continue        # UCLA's menu site still lists Sproul, but it doesn't serve
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

    # UCLA never itemises hall drinks, but the milk is there (seen at De Neve, and
    # reportedly Bruin Plate). Borrow The Study's milk panels and add them to every meal.
    # Whole milk has no UCLA panel at all, so it comes from manual_items.json (USDA).
    HALL_MILK = {
        "De Neve Dining": [["Beverages", "6570"], ["Beverages", "6569"], ["Beverages", "m-whole-milk"]],
        "Bruin Plate":    [["Beverages", "6570"], ["Beverages", "6569"]],   # lowfat, nonfat
    }
    for v in venues:
        for ms in v["menu"].values() if v["k"] in HALL_MILK else []:
            for rows in ms.values():
                rows.extend(r for r in HALL_MILK[v["k"]] if r not in rows)
    for ms in next(v for v in venues if v["k"] == "De Neve Dining")["menu"].values():
        if "Breakfast" in ms and ["Beverages", "6568"] not in ms["Breakfast"]:
            ms["Breakfast"].append(["Beverages", "6568"])     # orange juice, The Study's panel

    # A hall's yogurt bar is out at every meal, but UCLA only lists it at some of them
    # (De Neve skips it at breakfast), so copy a day's yogurt-bar rows to its other meals.
    def yog(r):
        n = items.get(r[1], {}).get("name", "")
        return "yogurt bar" in (r[0] + " " + n).lower() and \
               "frozen" not in n.lower()
    for v in venues:
        if v["kind"] != "ayce":
            continue
        for ms in v["menu"].values():
            bar = [r for rows in ms.values() for r in rows if yog(r)]
            bar = [r for i, r in enumerate(bar) if r not in bar[:i]]
            for rows in ms.values():
                if bar and not any(yog(r) for r in rows):
                    rows.extend(bar)

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
        # Some UCLA "servings" are batch yields, not portions -- a 907 g salad bar, a
        # 12 kg pork tenderloin. Anything this large is a recipe size; flag it so the
        # app can warn rather than silently logging a whole hotel pan.
        if (v.get("grams") or 0) > 600:
            rec["batch"] = True
        pf = portion_for(v["name"], v.get("grams"))
        if pf:
            rec["p"] = pf
        if v.get("build_groups"):
            rec["b"] = [[c["id"] for c in g if c["id"] in items] for g in v["build_groups"]]
        if v.get("tags"):
            rec["t"] = [t for t in v["tags"] if t not in ("low-carbon", "high-carbon")]
        if v.get("allergens"):
            # UCLA appends its whole legal disclaimer to the allergen list, and that
            # boilerplate names foods ("hamburger buns, pizza dough, baked goods"),
            # which poisons any text matching done against this field. Keep the real
            # tokens only.
            al = []
            for entry in v["allergens"]:
                if "*" in entry or entry.lower().startswith(("if you", "please")):
                    break                      # the disclaimer starts here
                for a in entry.split(","):     # real allergens arrive comma-packed
                    a = a.strip(" ,.")
                    if a and len(a) <= 20 and a.lower() != "none":
                        al.append(a)
            if al:
                rec["a"] = al
        out[rid] = rec

    # venues UCLA publishes nothing for (the trucks), reconstructed in manual_venues.py
    mp = DATA / "manual_items.json"
    if mp.exists():
        man = json.loads(mp.read_text())
        for rid, it in man["items"].items():
            v = it["vec"]
            out[rid] = {
                "n": it["n"], "s": it.get("s", ""), "g": it.get("g"),
                "v": [round_sig(v.get(k, 0.0)) for k in ORDER],
                "src": "reconstructed",
            }
            if it.get("desc"):
                out[rid]["d"] = it["desc"]
        for v in man["venues"]:
            venues.append({"k": v["k"], "n": v["n"], "kind": v["kind"],
                           "note": v.get("note", ""),
                           "menu": {"standing": {"All day": v["rows"]}}})

    # every yogurt bar has squeezable honey; UCLA lists it at none of them
    if "m-honey" in out:
        for rec in out.values():
            if rec["n"] == "Yogurt Bar" and rec.get("b") and "m-honey" not in rec["b"][-1]:
                rec["b"][-1].append("m-honey")
        for v in venues:
            for ms in v["menu"].values():
                for rows in ms.values():
                    if any(r[0] == "Yogurt Bar" for r in rows) and ["Yogurt Bar", "m-honey"] not in rows:
                        rows.append(["Yogurt Bar", "m-honey"])

    # Cooked rice is 100-130 kcal per 100 g and dry rice about 360, so a "rice" panel above
    # ~280 was worked out from the dry rice that went into the scoop. Scale the whole panel
    # to cooked rice of the same kind (USDA: glutinous 97, brown 112, white 130).
    for rid, rec in out.items():
        n = rec["n"].lower()
        if "rice" not in n or not rec.get("v") or not rec.get("g") or \
           any(w in n for w in ("fried", "pudding", "bowl", "beans", "cereal", "cake")):
            continue
        dens = rec["v"][0] / rec["g"] * 100
        if dens < 280:
            continue
        ref = 97 if "sticky" in n or "glutinous" in n else 112 if "brown" in n else 130
        k = ref / dens
        rec["v"] = [round_sig(x * k) for x in rec["v"]]
        rec["note"] = (f"UCLA's panel works out to {dens:.0f} kcal per 100 g, which only dry rice "
                       f"reaches (cooked is about {ref}), so it was calculated from the uncooked rice. "
                       f"Scaled to cooked rice of the same weight.")

    # parts you can leave on the tray, attached to the items whose names imply them
    rp = DATA / "removals.json"
    removals = {}
    if rp.exists():
        import re as _re
        spec = json.loads(rp.read_text())
        for key, r in spec.items():
            removals[key] = {"label": r["label"],
                             "v": [round_sig(r["vec"].get(k, 0.0)) for k in ORDER]}
        for rid, rec in out.items():
            if rec.get("src") == "reconstructed":
                continue
            keys = [k for k, r in spec.items() if _re.search(r["match"], rec["n"], _re.I)]
            if keys:
                rec["rm"] = keys

    # real service windows from dining.ucla.edu/hours/
    hp = DATA / "hours.json"
    if hp.exists():
        hours = json.loads(hp.read_text())
        alias = {"Epicuria at Covel": "Epicuria at Covel", "De Neve": "De Neve Dining",
                 "Smile Hotdog": "Food Trucks", "Perro 1-10 Tacos": "Food Trucks"}
        missing = []
        for v in venues:
            name = alias.get(v["n"], v["n"])
            got = {d: day[name] for d, day in hours.items() if name in day and day[name]}
            if got:
                v["hours"] = got
            else:
                missing.append(v["n"])
        if missing:
            print("  no published hours for: " + ", ".join(missing))

    payload = {
        "nutrients": ORDER,
        "measured": len(MEASURED),
        "dates": sorted({w["date"] for v in items.values() for w in v.get("where", [])
                         if w["date"] != "standing"}),
        "venues": venues,
        "removals": removals,
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
