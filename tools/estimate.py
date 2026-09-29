#!/usr/bin/env python3
"""Fill in the ~20 micronutrients UCLA does not publish.

UCLA gives 18 usable nutrients per item plus the ingredient list and the serving weight.
USDA gives a full nutrient vector per ingredient.  So solve for how many grams of each
ingredient the serving holds, by fitting the published 18 -- non-negative least squares
on the ingredient mass vector, with total mass pinned to the serving weight -- then read
the missing nutrients straight off the fitted ingredient masses.

Everything UCLA published is passed through untouched and marked measured; only the
remainder is marked estimated, with a confidence from the fit residual.
"""
import json
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

FIT = ["kcal", "protein", "fat", "satfat", "transfat", "chol", "sodium", "carb",
       "fiber", "sugar", "calcium", "iron", "potassium", "vit_a", "vit_b6",
       "vit_b12", "vit_c", "vit_d"]
EST = ["magnesium", "phosphorus", "zinc", "copper", "manganese", "selenium",
       "vit_e", "vit_k", "thiamin", "riboflavin", "niacin", "folate",
       "pantothenic", "choline", "mufa", "pufa",
       "omega3_ala", "omega3_epa", "omega3_dha", "omega6"]
# typical serving magnitudes, used to put every nutrient on comparable footing in the fit
SCALE = {"kcal": 500, "protein": 25, "fat": 25, "satfat": 8, "transfat": 0.5,
         "chol": 100, "sodium": 600, "carb": 50, "fiber": 5, "sugar": 10,
         "calcium": 200, "iron": 3, "potassium": 400, "vit_a": 150,
         "vit_b6": 0.4, "vit_b12": 1.0, "vit_c": 20, "vit_d": 2.0}

def nnls(A, b, iters=200):
    """Lawson-Hanson active set NNLS.  Small problems (<=40 columns), so this is plenty."""
    m, n = A.shape
    P = np.zeros(n, bool)
    x = np.zeros(n)
    w = A.T @ (b - A @ x)
    for _ in range(iters):
        if P.all() or (w[~P] <= 1e-10).all():
            break
        j = np.argmax(np.where(P, -np.inf, w))
        P[j] = True
        for _ in range(60):
            s = np.zeros(n)
            s[P] = np.linalg.lstsq(A[:, P], b, rcond=None)[0]
            if (s[P] > 0).all():
                break
            neg = P & (s <= 0)
            alpha = np.min(x[neg] / (x[neg] - s[neg] + 1e-15))
            x = x + alpha * (s - x)
            P &= ~(np.abs(x) < 1e-11)
        else:
            break
        x = s
        w = A.T @ (b - A @ x)
    return np.clip(x, 0, None)

def main():
    items = json.loads((DATA / "ucla_parsed.json").read_text())
    usda = json.loads((DATA / "usda.json").read_text())
    imap = json.loads((DATA / "ing_map.json").read_text())

    fit_scale = np.array([SCALE[k] for k in FIT])
    stats = {"fitted": 0, "no_ingredients": 0, "no_panel": 0, "resid": []}

    for rid, v in items.items():
        if "kcal" not in v:
            continue
        have = {k: v.get(k, 0.0) for k in FIT}
        grams = v.get("grams")
        names = v.get("ingredients") or []
        picks, cols = [], []
        for n in names:
            m = imap.get(n)
            if not m:
                continue
            if m["fdc"] == "__zero__":
                picks.append((n, None))
                cols.append(np.zeros(len(FIT)))
                continue
            f = usda.get(m["fdc"])
            if not f:
                continue
            picks.append((n, m["fdc"]))
            cols.append(np.array([f["n"].get(k, 0.0) for k in FIT]) / 100.0)  # per gram
        if not picks or not grams:
            stats["no_ingredients" if not picks else "no_panel"] += 1
            v["micro_source"] = "none"
            continue

        A = np.array(cols).T                      # 18 x k, per gram
        b = np.array([have[k] for k in FIT])
        # scale rows so a milligram of iron matters as much as a calorie
        As, bs = A / fit_scale[:, None], b / fit_scale
        # pin total mass to the serving weight, weighted so it is a strong constraint
        w_mass = 3.0
        As = np.vstack([As, np.ones((1, A.shape[1])) * w_mass / max(grams, 1)])
        bs = np.append(bs, w_mass)

        x = nnls(As, bs)
        if x.sum() <= 0:
            v["micro_source"] = "none"
            continue
        # rescale masses so they really do add up to the serving weight
        x = x * (grams / x.sum())

        pred = A @ x
        denom = np.where(b > 0, b, 1.0)
        rel = np.abs(pred - b) / denom
        resid = float(np.median(rel[b > 0])) if (b > 0).any() else 1.0
        stats["resid"].append(resid)
        stats["fitted"] += 1

        est = {}
        for k in EST:
            tot = 0.0
            for (name, fid), g in zip(picks, x):
                if fid and fid in usda:
                    tot += usda[fid]["n"].get(k, 0.0) / 100.0 * g
            est[k] = round(tot, 4)
        v["est"] = est
        v["micro_source"] = "ingredient-fit"
        v["fit_residual"] = round(resid, 3)
        v["fit_masses"] = [[n, round(float(g), 1)] for (n, _f), g in zip(picks, x) if g > 0.05]

    (DATA / "ucla_full.json").write_text(json.dumps(items, ensure_ascii=False))
    r = sorted(stats["resid"])
    print(f"fitted {stats['fitted']} items; no usable ingredients {stats['no_ingredients']}")
    if r:
        print(f"median relative residual {r[len(r)//2]:.2f}, "
              f"p25 {r[len(r)//4]:.2f}, p75 {r[3*len(r)//4]:.2f}")
        print(f"{sum(1 for x in r if x < .25)} items fit within 25%")

if __name__ == "__main__":
    main()
