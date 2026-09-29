#!/usr/bin/env python3
"""USDA SR Legacy -> per-100g nutrient vectors, plus a UCLA-ingredient name matcher.

Run once with the SR Legacy JSON in place:
  curl -sLO https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip
  unzip -o FoodData_Central_sr_legacy_food_json_2018-04.zip
  python3 tools/usda.py path/to/FoodData_Central_sr_legacy_food_json_2018-04.json
"""
import json, re, sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# id -> (key, scale to the unit we store).  Everything per 100 g.
NUT = {
    1008: ("kcal", 1),      1003: ("protein", 1),   1004: ("fat", 1),
    1258: ("satfat", 1),    1257: ("transfat", 1),  1292: ("mufa", 1),
    1293: ("pufa", 1),      1005: ("carb", 1),      1079: ("fiber", 1),
    2000: ("sugar", 1),     1253: ("chol", 1),      1051: ("water", 1),
    1087: ("calcium", 1),   1089: ("iron", 1),      1090: ("magnesium", 1),
    1091: ("phosphorus", 1), 1092: ("potassium", 1), 1093: ("sodium", 1),
    1095: ("zinc", 1),      1098: ("copper", 1),    1101: ("manganese", 1),
    1103: ("selenium", 1),  1106: ("vit_a", 1),     1162: ("vit_c", 1),
    1114: ("vit_d", 1),     1109: ("vit_e", 1),     1185: ("vit_k", 1),
    1165: ("thiamin", 1),   1166: ("riboflavin", 1), 1167: ("niacin", 1),
    1175: ("vit_b6", 1),    1177: ("folate", 1),    1178: ("vit_b12", 1),
    1170: ("pantothenic", 1), 1180: ("choline", 1),
    1404: ("omega3_ala", 1), 1278: ("omega3_epa", 1), 1272: ("omega3_dha", 1),
    1316: ("omega6", 1),
}
KEYS = [v[0] for v in NUT.values()]

# UCLA writes prep and pack detail into ingredient names; none of it changes nutrition.
NOISE = re.compile(
    r"\b(sp|diced|sliced|chopped|shredded|minced|peeled|whole|fresh|frozen|raw|dry|dried|"
    r"bulk|bias|cut|large|medium|small|jumbo|grade|a|aa|iqf|rtu|rte|halal|kosher|"
    r"no\s*salt\s*added|low\s*sodium|reduced|gal|oz|lb|ct|pack|case|thawed|drained|"
    r"granulated|ground|table|grind|julienne|wedge|wedges|florets|strips|cubes|rings)\b",
    re.I)
SIZE = re.compile(r'\d+\s*(?:/\d+)?\s*(?:"|in\b|mm|cm|x\s*\d+)?')

def norm(name):
    s = name.lower()
    s = SIZE.sub(" ", s)
    s = re.sub(r"[^a-z ]", " ", s)
    s = NOISE.sub(" ", s)
    return [w for w in s.split() if len(w) > 2]

def load_usda(path):
    foods = json.loads(Path(path).read_text())["SRLegacyFoods"]
    out = {}
    for f in foods:
        vec = {}
        for n in f.get("foodNutrients", []):
            nid = n.get("nutrient", {}).get("id")
            if nid in NUT and n.get("amount") is not None:
                vec[NUT[nid][0]] = n["amount"]
        if "kcal" not in vec:
            continue
        out[str(f["fdcId"])] = {
            "d": f["description"],
            "cat": (f.get("foodCategory") or {}).get("description", ""),
            "n": vec,
        }
    return out

def index(usda):
    idx = {}
    for fid, f in usda.items():
        idx[fid] = set(norm(f["d"]))
    return idx

def match(name, usda, idx, prefer=()):
    want = set(norm(name))
    if not want:
        return None, 0.0
    best, score = None, 0.0
    for fid, toks in idx.items():
        if not toks:
            continue
        inter = len(want & toks)
        if not inter:
            continue
        # Jaccard-ish, but reward covering the UCLA name over matching a long USDA one
        s = inter / len(want) * 0.75 + inter / len(toks) * 0.25
        d = usda[fid]["d"].lower()
        if "raw" in d:
            s += 0.06          # prefer the unprepared form for a recipe ingredient
        if any(p in d for p in prefer):
            s += 0.10
        if "," not in d:
            s += 0.02          # short plain descriptions beat oddly-specific ones
        if s > score:
            best, score = fid, s
    return best, round(score, 3)

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if not src:
        sys.exit("usage: usda.py <SR legacy json>")
    print("loading USDA ...", file=sys.stderr)
    usda = load_usda(src)
    print(f"  {len(usda)} foods with energy", file=sys.stderr)
    (DATA / "usda.json").write_text(json.dumps(usda, ensure_ascii=False))

    vocab = json.loads((DATA / "vocab.json").read_text())
    idx = index(usda)
    print(f"matching {len(vocab)} ingredient names ...", file=sys.stderr)
    out = {}
    for i, (name, count) in enumerate(vocab, 1):
        if i % 200 == 0:
            print(f"  {i}/{len(vocab)}", file=sys.stderr)
        fid, sc = match(name, usda, idx)
        if fid:
            out[name] = {"fdc": fid, "score": sc, "desc": usda[fid]["d"], "count": count}
    (DATA / "ing_map.json").write_text(json.dumps(out, ensure_ascii=False, indent=0))
    good = sum(1 for v in out.values() if v["score"] >= 0.5)
    print(f"\nmatched {len(out)}/{len(vocab)}; {good} at score >= 0.5", file=sys.stderr)
    print("\ntop 40 ingredients by frequency:")
    for name, count in vocab[:40]:
        m = out.get(name)
        print(f"  {count:4}  {name[:34]:34} -> {m['desc'][:52] if m else '(no match)':52} {m['score'] if m else ''}")

if __name__ == "__main__":
    main()
