#!/usr/bin/env python3
"""Hand-picked USDA targets for the UCLA ingredient names the fuzzy matcher gets wrong.

Written as search phrases, not ids, so the intent stays readable and the script
resolves each one against SR Legacy and prints what it picked.  Patterns are matched
against the UCLA ingredient name case-insensitively, longest pattern first.
Only the high-frequency names are worth curating; spices in trace amounts can stay fuzzy.
"""
import json, re, sys
from pathlib import Path
from usda import load_usda, norm

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

ZERO = "__zero__"        # nutritionally nil: plain water, ice

OVERRIDES = [
    (r"^water$|^ice$|^water\b.*\bfilter", ZERO),
    (r"granulated sugar|^sugar$|cane sugar", "Sugars, granulated"),
    (r"brown sugar", "Sugars, brown"),
    (r"powdered sugar|confectioner", "Sugars, powdered"),
    (r"onion.*(diced|julienne|sliced|whole|peeled|chopped)|^yellow onion|^red onion|^white onion",
     "Onions, raw"),
    (r"green onion|scallion", "Onions, spring or scallions (includes tops and bulb), raw"),
    (r"tomato.*(diced|crushed|roma|san marzano|whole peeled|canned)", "Tomatoes, red, ripe, canned, packed in tomato juice"),
    (r"^tomato \d|^tomato$|tomato.*fresh", "Tomatoes, red, ripe, raw, year round average"),
    (r"tomato paste", "Tomato products, canned, paste, without salt added"),
    (r"tomato sauce", "Tomato products, canned, sauce"),
    (r"white vinegar|distilled vinegar|vinegar rice|rice vinegar", "Vinegar, distilled"),
    (r"dried oregano|oregano leaf|italian seasoning", "Spices, oregano, dried"),
    (r"yeast", "Leavening agents, yeast, baker's, active dry"),
    (r"high.?gluten|bread flour", "Wheat flour, white, bread, enriched"),
    (r"all.?purpose flour|^ap flour", "Wheat flour, white, all-purpose, enriched, bleached"),
    (r"egg liquid|egg shell large|whole egg", "Egg, whole, raw, fresh"),
    (r"egg white", "Egg, white, raw, fresh"),
    (r"unsalted butter|butter unsalted", "Butter, without salt"),
    (r"^butter\b", "Butter, salted"),
    (r"mustard dijon|prepared mustard", "Mustard, prepared, yellow"),
    (r"mustard powder|mustard seed|ground mustard", "Spices, mustard seed, ground"),
    (r"ketchup|catsup", "Catsup"),
    (r"corn starch|cornstarch", "Cornstarch"),
    (r"red bell pepper|roasted red pepper|^bell pepper", "Peppers, sweet, red, raw"),
    (r"green bell pepper", "Peppers, sweet, green, raw"),
    (r"^avocado", "Avocados, raw, California"),
    (r"whole milk|milk whole", "Milk, whole, 3.25% milkfat, with added vitamin D"),
    (r"2% milk|milk 2%|reduced fat milk", "Milk, reduced fat, fluid, 2% milkfat, with added vitamin A and vitamin D"),
    (r"nonfat milk|skim milk", "Milk, nonfat, fluid, with added vitamin A and vitamin D (fat free or skim)"),
    (r"buttermilk", "Milk, buttermilk, fluid, cultured, lowfat"),
    (r"grape ?seed oil", "Oil, grapeseed"),
    (r"shortening", "Shortening, vegetable, household, composite"),
    (r"oats rolled|rolled oats|^oats", "Cereals, oats, regular and quick, not fortified, dry"),
    (r"turkey breast", "Turkey breast, sliced, prepackaged"),
    (r"black forest ham|^ham\b", "Ham, sliced, pre-packaged, deli meat (96%FF, water added)"),
    (r"mayonnaise", "Salad dressing, mayonnaise, regular"),
    (r"orange juice", "Orange juice, raw"),
    (r"lowfat greek yogurt|greek yogurt.*(plain|lowfat)", "Yogurt, Greek, plain, lowfat"),
    (r"cinnamon stick", "Spices, cinnamon, ground"),
    (r"peppercorn|whole black pepper", "Spices, pepper, black"),
    (r"ranch dressing", "Salad dressing, ranch dressing, regular"),
    (r"sour cream", "Cream, sour, cultured"),
    (r"heavy.*cream|whipping cream", "Cream, fluid, heavy whipping"),
    (r"olive oil", "Oil, olive, salad or cooking"),
    (r"sesame oil", "Oil, sesame, salad or cooking"),
    (r"soy sauce|tamari|kikoman", "Soy sauce made from soy and wheat (shoyu)"),
    (r"chipotle|guajillo|chile pod|ancho", "Peppers, ancho, dried"),
    (r"refried beans", "Beans, refried, canned, traditional style"),
    (r"black beans", "Beans, black, mature seeds, cooked, boiled, without salt"),
    (r"pinto beans", "Beans, pinto, mature seeds, cooked, boiled, without salt"),
    (r"garbanzo|chickpea", "Chickpeas (garbanzo beans, bengal gram), mature seeds, cooked, boiled, without salt"),
    (r"^white rice|rice calrose|long grain parboiled|jasmine rice|sticky rice",
     "Rice, white, long-grain, regular, cooked, enriched, without salt"),
    (r"brown rice", "Rice, brown, long-grain, cooked"),
    (r"ground beef|beef ground", "Beef, ground, 85% lean meat / 15% fat, raw"),
    (r"beef flap|sirloin|tri.?tip|flank", "Beef, loin, top sirloin steak, boneless, lean only, raw"),
    (r"chicken breast", "Chicken, broilers or fryers, breast, meat only, raw"),
    (r"chicken thigh", "Chicken, broilers or fryers, thigh, meat only, raw"),
    (r"shredded cheese|cheddar", "Cheese, cheddar"),
    (r"mozzarella", "Cheese, mozzarella, whole milk"),
    (r"parmesan", "Cheese, parmesan, grated"),
    (r"swiss cheese", "Cheese, swiss"),
    (r"cream cheese", "Cheese, cream"),
    (r"iceberg lettuce", "Lettuce, iceberg (includes crisphead types), raw"),
    (r"romaine", "Lettuce, cos or romaine, raw"),
    (r"^spinach", "Spinach, raw"),
    (r"cilantro|coriander leaves", "Coriander (cilantro) leaves, raw"),
    (r"lime juice", "Lime juice, raw"),
    (r"lemon juice", "Lemon juice, raw"),
    (r"^honey", "Honey"),
    (r"canola oil|salad oil|vegetable oil", "Oil, canola"),
    (r"^salt$|kosher salt|sea salt|table salt", "Salt, table"),
    (r"^corn\b", "Corn, sweet, yellow, raw"),
    (r"pico de gallo|salsa", "Sauce, salsa, ready-to-serve"),
    (r"guacamole", "Avocados, raw, California"),
    (r"flour tortilla|tortilla flour", "Tortillas, ready-to-bake or -fry, flour, refrigerated"),
    (r"corn tortilla|tortilla corn", "Tortillas, ready-to-bake or -fry, corn"),
]

def find(usda, phrase):
    """Exact description, then a prefix match (SR suffixes many names with
    "(Includes foods for USDA's Food Distribution Program)"), then token overlap."""
    low = phrase.lower()
    for fid, f in usda.items():
        if f["d"].lower() == low:
            return fid
    pref = sorted((f["d"], fid) for fid, f in usda.items() if f["d"].lower().startswith(low))
    if pref:
        return pref[0][1]
    want = set(norm(phrase))
    best, sc = None, 0
    for fid, f in usda.items():
        toks = set(norm(f["d"]))
        if not toks:
            continue
        s = len(want & toks) / max(len(want | toks), 1)
        if s > sc:
            best, sc = fid, s
    return best

def main():
    src = sys.argv[1]
    usda = load_usda(src)
    ing_map = json.loads((DATA / "ing_map.json").read_text())
    vocab = dict(json.loads((DATA / "vocab.json").read_text()))

    resolved = {}
    print(f"{'pattern':44} -> USDA pick")
    for pat, phrase in OVERRIDES:
        if phrase == ZERO:
            resolved[pat] = ZERO
            print(f"  {pat[:42]:42} -> (zero: no nutrients)")
            continue
        fid = find(usda, phrase)
        resolved[pat] = fid
        mark = "" if fid and usda[fid]["d"].lower() == phrase.lower() else "  ~approx"
        print(f"  {pat[:42]:42} -> {usda[fid]['d'][:56] if fid else 'NOT FOUND':56}{mark}")

    # apply, longest pattern first so specific rules beat general ones
    order = sorted(resolved, key=len, reverse=True)
    hits = 0
    for name in list(vocab):
        for pat in order:
            if re.search(pat, name, re.I):
                fid = resolved[pat]
                ing_map[name] = {
                    "fdc": fid,
                    "score": 1.0,
                    "desc": "(water / no nutrients)" if fid == ZERO else usda[fid]["d"],
                    "count": vocab[name],
                    "curated": True,
                }
                hits += 1
                break
    (DATA / "ing_map.json").write_text(json.dumps(ing_map, ensure_ascii=False, indent=0))

    # how much of the corpus mass do curated names cover?
    tot = sum(vocab.values())
    cur = sum(v["count"] for v in ing_map.values() if v.get("curated"))
    print(f"\ncurated {hits} ingredient names, {cur}/{tot} ({cur/tot*100:.0f}%) of all ingredient mentions")

if __name__ == "__main__":
    main()
