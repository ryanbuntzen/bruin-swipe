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
    "Epicuria at Covel": "Covel Dining",      # the at-a-glance page renamed it (Nov 2026)
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
    # first: a sandwich is one sandwich, not the slices of ham inside it
    (r"burger|sandwich|wrap|burrito|taco\b|calzone|panini|roll\b|bowl\b|plate\b|platter|croissant\b.*(ham|egg)|\bbox\b|hot ?dog|banh mi|stromboli|flatbread",
                                                            0,  "", "", "whole"),
    (r"\bhard cooked egg|\bfried egg|poached egg",      50,  "egg", "eggs", "count"),
    (r"scrambled egg|omelet|egg white|^egg\b",           47,  "egg", "eggs", "worth"),
    (r"\bturkey bacon",                                  13,  "strip", "strips", "count"),
    (r"\bbacon\b",                                       15,  "strip", "strips", "count"),
    (r"sausage|link|chorizo|hot ?dog|frank",              28,  "link", "links", "count"),
    (r"\bmilk\b|juice|spritzer|\bwater\b|kombucha|\bteas?\b", 240, "glass", "glasses", "count"),
    (r"yogurt|cottage cheese",                           113, "ladle", "ladles", "halfcup"),
    (r"sliced .*cheese|cheese.*slice|swiss|provolone|american cheese", 28, "slice", "slices", "count"),
    (r"\bham\b|roast beef|pastrami|salami|prosciutto|\bdeli\b|sliced turkey",
                                                           28,  "slice", "slices", "count"),
    (r"grape",                                             5,  "grape", "grapes", "handful"),
    (r"cantaloupe|watermelon|honeydew|\bmelon",           14,  "cube", "cubes", "cup"),
    (r"pineapple",                                        15,  "chunk", "chunks", "cup"),
    (r"\bbanana\b|\bapple\b|\borange\b|\bkiwi\b|\bpear\b|\bpeach\b", 0, "medium", "medium", "whole"),
    (r"breast|thigh|drumstick|\bwing|chop\b|tenderloin|fillet|filet|steak|tri.?tip|\bribs?\b|patty|cutlet|fillet",
                                                            0,  "piece", "pieces", "piece"),
    (r"\bfries\b|tater tot",                             5.3, "fry", "fries", "basket"),
    (r"\brice\b|quinoa|grain|couscous|farro",            79,  "scoop", "scoops", "rice"),
    (r"bar\b|salad bar|yogurt bar",                       0,  "", "", "whole"),
]

def portion_for(name, grams):
    import re as _r
    # a dish that only mentions an egg or a sausage (soup, stew, "x, y and polenta") is
    # served by the spoon, not counted in eggs or links
    if _r.search(r"soup|stew|chili|curry|polenta|casserole|pasta|,|\band\b", name, _r.I) and \
       not _r.search(PORTION[0][0], name, _r.I):
        return [120, "scoop", "scoops", "plain"] if grams else None
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


# UCLA's own names, tidied: menu numbers, weekday prefixes, typos, and one wrap UCLA
# calls just "Bacon" (crispy chicken, bacon, ranch and blue cheese in a tortilla)
RENAME = {"10046": "Chicken Bacon Ranch Wrap", "Honey Nut Cherrios": "Honey Nut Cheerios",
          "Speical K Berry": "Special K Berry", "Vegetarian Fettucine": "Vegetarian Fettuccine",
          "7200": "Salted Pretzel", "8008": "Jalapeño Pretzel", "8007": "Pepperoni Pretzel",
          "5907": "Pepperoni Pizzette", "6540": "Caesar Salad", "634": "Chicken Caesar Salad"}
def clean_name(rid, n):
    n = RENAME.get(rid) or RENAME.get(n) or n
    n = re.sub(r"^Smoothie #\d+:\s*(.+)$", r"\1 Smoothie", n)                 # Smoothie #15: Chocolate Banana
    n = re.sub(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) - (.+)$", r"\2 (\1 only)", n)  # Café 1919's daily special
    return n

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
            if "kcal" in v and not v["kcal"] and v.get("grams", 0) < 5:
                continue        # theme-night banners ("Northeast", "Brunch"): 3 g of water, not food
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
        if "kcal" not in v and not v.get("build_groups") or "kcal" in v and not v["kcal"] and v.get("grams", 0) < 5:
            continue
        rec = {"n": clean_name(rid, v["name"])}
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
        pf = portion_for(rec["n"], v.get("grams"))
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
            for _, rid in v["rows"]:
                out[rid]["e"] = 1            # a truck item is estimated end to end
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

    # Cooked rice is 100-130 kcal per 100 g and dry rice about 360. Plain rice (rice, water,
    # salt, garlic or saffron) that comes out denser than cooked rice of its kind -- by more
    # than a quarter -- was worked out from rice that wasn't fully cooked; anything above ~280,
    # oil or not, from the dry rice itself. Keep UCLA's weight, scale the whole panel to
    # cooked rice of the same kind (USDA: glutinous 97, brown 112, white 130).
    PLAIN = re.compile(r"rice|water|salt|garlic|saffron|bay leaf", re.I)
    for rid, rec in out.items():
        n = rec["n"].lower()
        if "rice" not in n or not rec.get("v") or not rec.get("g") or \
           any(w in n for w in ("fried", "pudding", "bowl", "beans", "cereal", "cake")):
            continue
        ing = items.get(rid, {}).get("ingredients") or []
        plain = bool(ing) and all(PLAIN.search(x) for x in ing)
        low = " ".join(ing).lower() + " " + n
        ref = 97 if "sticky" in low and "calrose" not in low or "glutinous" in low else \
              112 if "brown" in low else 130
        dens = rec["v"][0] / rec["g"] * 100
        if dens < (ref * 1.25 if plain else 280):
            continue
        k = ref / dens
        rec["v"] = [round_sig(x * k) for x in rec["v"]]
        rec["note"] = (f"UCLA's panel works out to {dens:.0f} kcal per 100 g; cooked rice of this kind "
                       f"is about {ref}, so it was calculated from uncooked or part-cooked rice. "
                       f"Scaled to cooked rice of the same weight.")

    # Servings UCLA publishes for something other than what you're handed: the panel is
    # replaced with the item rebuilt from its own recipe card (manual_venues.json extras,
    # keyed "fix-<id>"), and the note says what UCLA's number was.
    EST = "UCLA's numbers for this were impossible, so these are estimates."
    FIX = {
        "8197": "UCLA's number is the whole plate with rice. This is the wrap alone, estimated.",
        "2031": EST, "6527": EST, "6553": EST, "7056": EST, "7361": EST, "7362": EST, "7225": EST,
        "5611": EST, "1627": EST, "1631": EST, "5610": EST, "1643": EST, "1642": EST,
    }
    # Servings UCLA weighs as several of what you're handed. The per-gram panel is fine;
    # the serving is cut down to one piece, so a serving in the app is what's on the plate.
    PIECE = {
        "Hawaiian BBQ Chicken": (85, "1 piece (about 3 oz)", [0, "piece", "pieces", "piece"],
            "UCLA lists one serving as {g:.0f} g / {k} kcal -- about four of the 3 oz pieces "
            "Rieber actually serves. Same recipe per gram, sized to one piece."),
        "Japanese Karaage Popcorn Chicken": (72, "about 6 pieces", [12, "piece", "pieces", "count"],
            "UCLA lists one serving as {g:.0f} g / {k} kcal, but what's handed out is 5-6 small "
            "pieces (~12 g each). Same recipe per gram, sized to 6 pieces -- and UCLA's recipe "
            "counts a lot of spicy mayo, which is most of the fat."),
    }
    for rec in out.values():
        if rec["n"] in PIECE and rec.get("g"):
            g, serving, p, note = PIECE[rec["n"]]
            rec["note"] = note.format(g=rec["g"], k=round(rec["v"][0]))
            rec["v"] = [round_sig(x * g / rec["g"]) for x in rec["v"]]
            rec.update({"g": g, "s": serving, "p": p})

    # The same pattern, everywhere else: a hall hands out one portion, while some of UCLA's
    # "servings" are several. The yardstick is the FDA's reference amount for one portion
    # (21 CFR 101.12): 85 g of cooked meat or fish, about 130 g of it on the bone, 140 g
    # for a sandwich-type item. A hall item more than twice that (three times for a
    # sandwich, so a real burger is left alone) is cut to one portion; the panel per gram
    # stays UCLA's. Mixed dishes -- pasta, bowls, stews and so on -- have no clean
    # yardstick and are left as published.
    hall_ids = {r[1] for v in venues if v["kind"] == "ayce" for ms in v["menu"].values()
                for rows in ms.values() for r in rows}
    other_ids = {r[1] for v in venues if v["kind"] != "ayce" for ms in v["menu"].values()
                 for rows in ms.values() for r in rows}
    # a takeout item is bought whole -- a smoothie is one smoothie, not "5 scoops"
    for rid in other_ids - hall_ids:
        rec = out.get(rid)
        if rec and rec.get("p"):                # "1 medium" is only for a piece of fruit
            fruit = re.fullmatch(r"(fuji |granny smith |pink lady )?(apple|banana|oranges?|pear|peach|kiwi)", rec["n"], re.I)
            rec["p"] = [0, "medium", "medium", "whole"] if fruit else [0, "", "", "whole"]
    # the filling of a build-your-own is one portion too -- a sandwich gets 3 oz of
    # carnitas, not the 17 oz pan UCLA's recipe card is written for
    comp_ids = {c for rec in out.values() for g in rec.get("b", []) for c in g}
    MIXED_DISH = re.compile(r"sandwich|bao|burger|wrap|burrito|taco|torta|hot ?dog|corn ?dog|panini|\bsub\b|"
                            r"slider|quesadilla|flatbread|pizza|calzone|bowl|salad|soup|pasta|fettuccine|"
                            r"alfredo|lasagna|rice|noodle|ramen|nachos|chilaquiles|polenta|marinara|pancake|"
                            r"benedict|egg roll|dumpling|\bbun\b|\bbar\b|stew|curry|chili|casserole|pot pie|"
                            r"\bmac\b|loco moco|omelet|scramble|hash|sukiyaki|vegan|tofu|plant|beyond", re.I)
    MEAT = re.compile(r"chicken|pork|beef|steak|lamb|turkey|salmon|fish|cod|tilapia|shrimp|\bribs?\b|"
                      r"drumstick|thigh|wings?|katsu|tenderloin|brisket|carnitas", re.I)
    BONE = re.compile(r"\bribs?\b|drumstick|wings?|bone.?in", re.I)
    HAND = re.compile(r"sandwich|\bbao\b|burger|wrap|burrito|torta|panini|\bsub\b|quesadilla", re.I)
    for rid, rec in out.items():
        if (rid not in hall_ids and rid not in comp_ids) or rid in other_ids or rec.get("note") or not rec.get("g") or not rec.get("v"):
            continue
        n = rec["n"]
        if HAND.search(n):
            ref, over, what, dense = 140, 3, "a sandwich-type item", 180
        elif MEAT.search(n) and not MIXED_DISH.search(n):
            ref, over, what = (130, 2, "meat on the bone") if BONE.search(n) else (85, 2, "cooked meat or fish")
            dense = 130
        else:
            continue
        # too light per gram to be the meat or the sandwich: mostly sauce, or the weight is the
        # wrong number -- either way, scaling by weight would make it worse
        if rec["g"] <= ref * over or rec["v"][0] / rec["g"] * 100 < dense:
            continue
        rec["note"] = (f"UCLA lists one serving as {rec['g']:.0f} g / {round(rec['v'][0])} kcal -- several "
                       f"portions; a plate or a build gets one. Sized to one standard portion of {what} "
                       f"({ref} g, the FDA reference amount), same recipe per gram.")
        rec["v"] = [round_sig(x * ref / rec["g"]) for x in rec["v"]]
        rec.update({"g": ref, "s": f"1 portion ({ref} g)", "p": [0, "portion", "portions", "piece"]})
        rec.pop("batch", None)

    # Impossible UCLA panels. Almost all are recipes that count several times the "Olive Oil
    # Blend" that goes in: protein and carbs look right, the fat does not. Fixed below, in order:
    # a hand rebuild (FIX), the same dish elsewhere per gram, or the extra oil taken back out.
    BROKEN = {"2457", "3057", "3052", "321", "480"}   # caught by eye, under the automatic limits
    FATTY = re.compile(r"oil|butter|\bnuts?\b|almond|peanut|pecan|walnut|cashew|seed|chip|mayo|aioli|dressing|"
                       r"vinaigrette|fried garlic|fried shallot|bacon|chocolate|cookie|praline|granola|spread|pesto|tahini|ghee|lard|chicharr", re.I)
    OILY_OK = re.compile(r"cheese|cream|sausage|chorizo|salami|pepperoni|avocado|olive|coconut|fudge|"
                         r"ganache|frosting|nutella|pork belly|popcorn|sauce", re.I)
    def impossible(rid, rec):
        if rid in BROKEN:
            return True
        if not rec.get("v") or not rec.get("g") or rec.get("note") or FATTY.search(rec["n"]):
            return False
        # pure fat is 900 kcal per 100 g; over ~35% of the weight as fat is oil, not a dish
        return rec["v"][0] / rec["g"] * 100 > 600 or \
               rec["v"][2] > 0.35 * rec["g"] and not OILY_OK.search(rec["n"])
    by_name = defaultdict(list)
    for rid, rec in out.items():
        by_name[rec["n"]].append(rid)
    I_FAT = [ORDER.index(k) for k in ("fat", "satfat", "mufa", "pufa", "omega3_ala", "omega6", "vit_e", "vit_k")]
    bad = [rid for rid, rec in out.items() if rid not in FIX and impossible(rid, rec)]
    for rid in bad:
        rec = out[rid]
        twin = {"480": "9205"}.get(rid) or next((t for t in by_name[rec["n"]] if t != rid and t not in bad
                                                and out[t].get("g") and out[t].get("v")), None)
        if twin:                                   # the same dish at another venue, per gram
            rec["v"] = [round_sig(x * rec["g"] / out[twin]["g"]) for x in out[twin]["v"]]
        elif rec["v"][2] > 0.10 * rec["g"]:        # take the extra oil out: fat down to 10% of the weight
            k = 0.10 * rec["g"] / rec["v"][2]
            v = list(rec["v"])
            v[0] -= 9 * v[2] * (1 - k)
            for i in I_FAT:
                v[i] *= k
            rec["v"] = [round_sig(x) for x in v]
        else:
            rec["note"] = "UCLA's numbers for this are broken. Left out of suggested plates."
            rec["bad"] = 1
            continue
        rec["note"], rec["e"] = EST, 1
    # Bruin Plate's eggs: same 3.29 oz scoop as De Neve's, whose panel is fine
    for rid, twin in {"506": "6542", "989": "9742"}.items():
        if rid in out and twin in out and abs(out[rid]["g"] - out[twin]["g"]) < 2:
            out[rid]["note"] = "UCLA's numbers for this were broken, so it uses De Neve's (same scoop)."
            out[rid]["v"] = list(out[twin]["v"])
            out[rid].pop("e", None)
    for rid, rec in out.items():                   # custom recipes UCLA posts nothing for
        if rec.get("v") is not None and not rec["v"][0] and "Custom Recipe" in (items.get(rid, {}).get("ingredients_raw") or ""):
            rec["note"], rec["bad"] = "UCLA doesn't post nutrition for this one.", 1

    for rid, note in FIX.items():
        fix = out.pop("fix-" + rid, None)
        if rid in out and fix:
            rec = out[rid]
            rec["note"] = note
            rec.update({"v": fix["v"], "g": fix["g"], "s": fix["s"], "src": "recipe", "e": 1})
    if "2031" in out:
        out["2031"]["p"] = [20, "link", "links", "count"]     # cooked link, so 1 serving reads "2 links"

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
            ing = " ".join(items.get(rid, {}).get("ingredients") or []).lower()
            if "naan" in ing:                  # a naan wrap has no tortilla to take off
                keys = [k for k in keys if k != "tortilla"]
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
