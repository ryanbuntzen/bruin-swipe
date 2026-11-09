#!/usr/bin/env python3
"""Turn UCLA's ingredient strings into a list of leaf food names.

UCLA writes sub-recipes with commas inside brackets — "Breaded Chicken: [ a, b, c ]" —
but concatenates top-level ingredients with no separator at all:
"White Rice Long Grain Parboiled Tomato Sauce Water Canola Oil Garlic Clove Peeled".
So build a vocabulary from every comma-delimited name that appears inside brackets
anywhere in the corpus, then greedily longest-match the unpunctuated runs against it.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def strip_parens(s):
    """Drop manufacturer and allergen parentheticals, innermost first."""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\([^()]*\)", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def clean(n):
    """Keep UCLA's own Title-Case ingredient names; drop manufacturer additive lists,
    which UCLA pastes in upper case (RIBOFLAVIN, THIAMIN MONONITRATE, ...)."""
    n = n.strip(" .;:*")
    if not (2 < len(n) < 60) or "(" in n or ")" in n:
        return None
    letters = [c for c in n if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.7:
        return None
    return n

def bracket_names(raw):
    """Comma-delimited leaf names living inside [ ... ] groups."""
    out = []
    for grp in re.findall(r"\[([^\[\]]*)\]", raw):
        for part in strip_parens(grp).split(","):
            n = clean(part)
            if n:
                out.append(n)
    return out

def build_vocab(items):
    from collections import Counter
    c = Counter()
    for v in items.values():
        for n in bracket_names(v.get("ingredients_raw") or ""):
            c[n] += 1
    # every recipe name is also a plausible ingredient (sub-recipes are recipes)
    for v in items.values():
        n = clean(v["name"])
        if n:
            c[n] += 1
    # names stay known after their dish rotates off the menu: "Cheddar Cheese" is what
    # lets "Cheddar Cheese Mild Sliced" parse, whether or not it's a recipe this week
    vp = ROOT / "data" / "vocab.json"
    if vp.exists():
        for n, _ in json.loads(vp.read_text()):
            c.setdefault(n, 0)
    return c

# A bought-in product that says it isn't what it names: "Vegan Chorizo (WATER, SOY FLOUR, ...)".
# Its name would match the real thing, so its own ingredient list is used instead.
IMITATION = re.compile(r"vegan|vegetarian|veggie|plant|substitute|imitation|meatless|"
                       r"unreal|beyond|impossible|dairy.?free|non.?dairy|egg.?free", re.I)
ALLERGENS = re.compile(r"[A-Za-z, ]*(Dairy|Soy|Gluten|Wheat|Eggs?|Sesame|Fish|Shellfish|Tree Nuts?|Peanuts?|Alcohol)[A-Za-z, ]*")
ADDITIVE = re.compile(r"\bcolor\b|vitamin|flavor|extract|acid|sodium |phosphate|gum$|enzymes?|culture", re.I)

def greedy(run, vocab_sorted):
    """Longest-match a run with no separators against the vocabulary -> [(name, start)].
    An unknown head word is dropped and matching carries on."""
    out, pos = [], 0
    while pos < len(run):
        rest = run[pos:]
        hit = next((v for v in vocab_sorted if len(v) <= len(rest) and rest[:len(v)].lower() == v.lower()), None)
        if hit:
            out.append((hit, pos))
            pos += len(hit)
        else:
            sp = rest.find(" ")
            if sp < 0:
                break
            pos += sp + 1
        while pos < len(run) and run[pos] == " ":
            pos += 1
    return out

def split_top(s):
    """Split on commas that aren't inside ( ) or [ ]."""
    out, depth, cur = [], 0, ""
    for ch in s:
        depth += {"(": 1, ")": -1, "[": 1, "]": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    return out + [cur]

def products(outside):
    """-> (name, [paren groups]) for each top-level "Name (...) (...)"."""
    i, start = 0, 0
    while i < len(outside):
        if outside[i] != "(":
            i += 1
            continue
        name, groups = outside[start:i], []
        while i < len(outside) and outside[i] == "(":
            depth, j = 0, i
            while j < len(outside):
                depth += {"(": 1, ")": -1}.get(outside[j], 0)
                if depth == 0:
                    break
                j += 1
            groups.append(outside[i + 1:j])
            i = j + 1
            while i < len(outside) and outside[i] == " ":
                i += 1
        yield name, groups
        start = i

def list_items(group):
    out = []
    for part in split_top(group):
        part = re.sub(r"(?i)contains (less than )?2%.*?of:?", " ", part)
        part = strip_parens(re.sub(r"\[[^\]]*\]", " ", part)).replace("&amp;", "&").split(".")[0]
        n = clean(part.title())
        if n and not ADDITIVE.search(n):
            out.append(n)
    return out

def imitations(outside, vocab_sorted):
    """-> [(name the vocabulary matched, or None; the product's own list)]"""
    out = []
    for name, groups in products(outside):
        name = strip_parens(name).strip(" ,:").split(":")[-1].strip()
        lists = [g for g in groups if g.count(",") >= 2]
        quals = " ".join(g for g in groups if g.count(",") < 2 and not ALLERGENS.fullmatch(g.strip()))
        if not lists:
            continue
        hits = greedy(name, vocab_sorted)
        # the product is the text after the previous ingredient; if the last match runs to
        # the end of the name, that match is the product's name
        last_is_product = hits and hits[-1][1] + len(hits[-1][0]) >= len(name)
        prev = hits[-2] if last_is_product and len(hits) > 1 else (hits[-1] if hits and not last_is_product else None)
        product = name[prev[1] + len(prev[0]):] if prev else name
        if IMITATION.search(product + " " + quals):
            out.append((hits[-1][0] if last_is_product else None, list_items(lists[0])))
    return out

def parse(raw, vocab_sorted, vocab_set):
    """-> (leaf names in menu order with duplicates kept, the ones taken from a product's own list)."""
    if not raw:
        return [], []
    leaves = []
    # sub-recipe groups: take their children, drop the wrapper (its mass is the sum)
    for grp in re.findall(r"\[([^\[\]]*)\]", raw):
        for part in strip_parens(grp).split(","):
            n = clean(part)
            if n:
                leaves.append(n)
    # whatever sits outside brackets, minus the "Wrapper:" labels
    outside = re.sub(r"\[[^\[\]]*\]", " ", raw)
    swaps = imitations(outside, vocab_sorted)
    outside = re.sub(r"[A-Za-z0-9 '\"/&%.-]{2,40}:", " ", outside)
    outside = strip_parens(outside)
    for run in re.split(r"[,;]", outside):
        leaves += [h for h, _ in greedy(run.strip(), vocab_sorted)]
    from_lists = []
    for old, new in swaps:
        if old in leaves:
            leaves.remove(old)
        from_lists += new
    leaves = [l for l in (clean(x) for x in leaves) if l]
    return leaves + from_lists, from_lists

def main():
    items = json.loads((ROOT / "data" / "ucla_raw.json").read_text())["items"]
    vocab = build_vocab(items)
    vs = sorted(vocab, key=len, reverse=True)
    vset = set(v.lower() for v in vocab)
    print(f"vocabulary: {len(vocab)} distinct ingredient names")
    cov = []
    for v in items.values():
        raw = v.get("ingredients_raw")
        if not raw:
            continue
        v["ingredients"], v["list_leaves"] = parse(raw, vs, vset)
        for n in v["list_leaves"]:          # new names need a USDA match too
            vocab[n] += 1
        cov.append(len(v["ingredients"]))
    print(f"parsed {len(cov)} items, median {sorted(cov)[len(cov)//2]} leaves, "
          f"{sum(1 for c in cov if c == 0)} with none")
    (ROOT / "data" / "vocab.json").write_text(json.dumps(vocab.most_common(), ensure_ascii=False))
    (ROOT / "data" / "ucla_parsed.json").write_text(json.dumps(items, ensure_ascii=False))
    for n, c in vocab.most_common(25):
        print(f"  {c:5} {n}")

if __name__ == "__main__":
    main()
