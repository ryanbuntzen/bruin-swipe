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
    return c

def parse(raw, vocab_sorted, vocab_set):
    """-> list of leaf names, in menu order, duplicates kept."""
    if not raw:
        return []
    leaves = []
    # sub-recipe groups: take their children, drop the wrapper (its mass is the sum)
    for grp in re.findall(r"\[([^\[\]]*)\]", raw):
        for part in strip_parens(grp).split(","):
            n = clean(part)
            if n:
                leaves.append(n)
    # whatever sits outside brackets, minus the "Wrapper:" labels
    outside = re.sub(r"\[[^\[\]]*\]", " ", raw)
    outside = re.sub(r"[A-Za-z0-9 '\"/&%.-]{2,40}:", " ", outside)
    outside = strip_parens(outside)
    for run in re.split(r"[,;]", outside):
        run = run.strip()
        while run:
            hit = next((v for v in vocab_sorted
                        if len(v) <= len(run) and run[:len(v)].lower() == v.lower()), None)
            if hit:
                leaves.append(hit)
                run = run[len(hit):].strip()
            else:                      # unknown head word: drop it and carry on
                sp = run.find(" ")
                if sp < 0:
                    break
                run = run[sp + 1:].strip()
    return [l for l in (clean(x) for x in leaves) if l]

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
        v["ingredients"] = parse(raw, vs, vset)
        cov.append(len(v["ingredients"]))
    print(f"parsed {len(cov)} items, median {sorted(cov)[len(cov)//2]} leaves, "
          f"{sum(1 for c in cov if c == 0)} with none")
    (ROOT / "data" / "vocab.json").write_text(json.dumps(vocab.most_common(), ensure_ascii=False))
    (ROOT / "data" / "ucla_parsed.json").write_text(json.dumps(items, ensure_ascii=False))
    for n, c in vocab.most_common(25):
        print(f"  {c:5} {n}")

if __name__ == "__main__":
    main()
