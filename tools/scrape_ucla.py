#!/usr/bin/env python3
"""Scrape UCLA Dining: every menu item's full nutrition panel, ingredient list and
where it shows up (venue / meal / station / which days).

Writes data/ucla_raw.json.  Re-run whenever the menus roll over.
"""
import json, re, sys, urllib.request, concurrent.futures as cf
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ucla_raw.json"

# Residential halls keep a rotating menu published on the at-a-glance page.
HALL_SLUG = {
    "De Neve Dining": "de-neve-dining",
    "Covel Dining": "covel-dining-2",
    "Feast at Rieber": "spice-kitchen",
    "Bruin Plate": "bruin-plate",
}
# Quick-service venues publish one standing menu on their own page.
QUICK = ["rendezvous", "bruin-cafe", "bruin-bowl", "cafe-1919", "the-drey",
         "the-study-at-hedrick", "epicuria-at-ackerman", "to-go-lunches"]

UA = {"User-Agent": "bruin-swipe/1.0 (personal nutrition tracker)"}

def get(url, tries=3, required=True):
    """Fetch a page.  A missing venue page is normal (some halls have none), so a 404
    comes back empty instead of killing the run; anything else still raises."""
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=45).read().decode("utf8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"  404 {url}", file=sys.stderr)
                return ""
            if n == tries - 1:
                if required:
                    raise
                return ""
        except Exception:
            if n == tries - 1:
                if required:
                    raise
                return ""
    return ""

# ---------------------------------------------------------------- menu structure

def menu_dates(html):
    return re.findall(r"<option value='(\d{4}-\d\d-\d\d)'>", html)

def parse_at_a_glance(html, date, out):
    """at-a-glance page: h2 meal -> h3 hall -> h4 station -> li items"""
    meals = [(m.start(), m.group(1).title()) for m in re.finditer(r"<h2>([A-Z]+) MENU FOR", html)]
    meals.append((len(html), None))
    for i in range(len(meals) - 1):
        seg, meal = html[meals[i][0]:meals[i + 1][0]], meals[i][1]
        halls = [(m.start(), m.group(1).strip()) for m in re.finditer(r"<h3>([^<]+)</h3>", seg)]
        halls.append((len(seg), None))
        for j in range(len(halls) - 1):
            hseg, hall = seg[halls[j][0]:halls[j + 1][0]], halls[j][1]
            for sm in re.finditer(r"<h4>([^<]+)</h4>(.*?)</ul>", hseg, re.S):
                station = sm.group(1).strip()
                for rid, name in re.findall(r"recipe=(\d+)['\"]>([^<]+)<", sm.group(2)):
                    out.append((rid, name.strip(), hall, meal, station, date))

def parse_venue_page(html, venue, out, date="standing"):
    """venue page: section id '<meal>-<Station>' -> recipe-card h3 names"""
    secs = re.findall(
        r"meal-station' id='([^']+)'>(.*?)(?=<div class='force-left-full-width meal-station'|</main>)",
        html, re.S)
    for sec, body in secs:
        meal, _, station = sec.partition("-")
        station = station.replace("-", " ").strip() or meal
        for card in re.finditer(r"<h3>([^<]+)</h3>(.*?)(?=<section class='recipe-card|</main>)", body, re.S):
            name = card.group(1).strip()
            rid = re.search(r"recipe=(\d+)", card.group(2))
            if rid:
                out.append((rid.group(1), name, venue, meal.title(), station, date))

# ---------------------------------------------------------------- nutrition panel

NUTRIENTS = [
    ("kcal",    r"single-calories'><span>Calories</span>([\d.]+)</p>", None),
    ("fat",     r"<span>Total Fat</span>([\d.]+)g", "g"),
    ("satfat",  r"<span>Saturated Fat</span>([\d.]+)g", "g"),
    ("transfat", r"<span>Trans Fat</span>([\d.]+)g", "g"),
    ("chol",    r"<span>Cholesterol</span>([\d.]+)mg", "mg"),
    ("sodium",  r"<span>Sodium</span>([\d.]+)mg", "mg"),
    ("carb",    r"<span>Total Carbohydrate</span>([\d.]+)g", "g"),
    ("fiber",   r"<span>Dietary Fiber</span>([\d.]+)g", "g"),
    ("sugar",   r"<span>Sugars</span>([\d.]+)g", "g"),
    ("addsugar", r"<span>Includes Added Sugars</span>([\d.]+)g", "g"),
    ("protein", r"<span>Protein</span>([\d.]+)g", "g"),
    ("calcium", r"<span>Calcium</span>([\d.]+)mg", "mg"),
    ("iron",    r"<span>Iron</span>([\d.]+)mg", "mg"),
    ("potassium", r"<span>Potassium</span>([\d.]+)mg", "mg"),
    ("vit_a",   r"<span>Vitamin A</span>([\d.]+)µg", "ug"),
    ("vit_b6",  r"<span>Vitamin B6</span>([\d.]+)mg", "mg"),
    ("vit_b12", r"<span>Vitamin B12</span>([\d.]+)µg", "ug"),
    ("vit_c",   r"<span>Vitamin C</span>([\d.]+)mg", "mg"),
    ("vit_d",   r"<span>Vitamin D</span>([\d.]+)µg", "ug"),
]

def oz_to_g(s):
    m = re.match(r"([\d.]+)\s*oz", s or "", re.I)
    return round(float(m.group(1)) * 28.3495, 1) if m else None

def scrape_item(rid):
    try:
        html = get(f"https://dining.ucla.edu/menu-item/?recipe={rid}")
    except Exception as e:
        return rid, {"error": str(e)}
    d = {}
    m = re.search(r"Serving Size:</strong>\s*([^<]+)<", html)
    if m:
        d["serving"] = m.group(1).strip()
        g = oz_to_g(d["serving"])
        if g:
            d["grams"] = g
    for key, pat, _unit in NUTRIENTS:
        m = re.search(pat, html)
        if m:
            d[key] = float(m.group(1))
    m = re.search(r'id="ingredient_list".*?>(.*?)Allergens\*', html, re.S)
    if m:
        txt = re.sub(r"<[^>]+>", " ", m.group(1))
        txt = txt.replace("Ingredients:", " ")
        d["ingredients_raw"] = re.sub(r"\s+", " ", txt).strip()[:2000]
    m = re.search(r"Allergens\*:</strong>(.*?)</div>", html, re.S)
    if m:
        d["allergens"] = [a.strip() for a in re.sub(r"<[^>]+>", "|", m.group(1)).split("|") if a.strip()]
    d["tags"] = sorted(set(re.findall(r"allergens/([a-z-]+)\.(?:svg|png)", html)))

    # Build-your-own items carry no nutrition of their own; they publish a component
    # picker instead.  Each component is a recipe in its own right, so capture the ids
    # and the accordion groups they sit in and price the build up from those.
    i = html.find("single-complex-ingredients")
    if i > -1:
        seg = html[i:html.find("single-complex-nutrition", i) if "single-complex-nutrition" in html[i:] else i + 40000]
        groups = []
        for block in re.split(r'<div class="complex-ingredient-group">', seg)[1:]:
            comps = [{"id": r, "name": n.strip()} for r, n in re.findall(
                r'single-ingredient-link" href="/menu-item/\?recipe=(\d+)">([^<]+)<', block)]
            if comps:
                groups.append(comps)
        if groups:
            d["build_groups"] = groups
    return rid, d

# ---------------------------------------------------------------- main

def main():
    placements = []
    print("fetching at-a-glance week ...", file=sys.stderr)
    first = get("https://dining.ucla.edu/menus-at-a-glance")
    dates = menu_dates(first) or []
    pages = {}
    with cf.ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(get, f"https://dining.ucla.edu/menus-at-a-glance?date={d}"): d for d in dates}
        for f in cf.as_completed(futs):
            pages[futs[f]] = f.result()
    for d, html in pages.items():
        parse_at_a_glance(html, d, placements)
    print(f"  {len(dates)} days, {len(placements)} placements", file=sys.stderr)

    # a hall missing from at-a-glance (Bruin Plate) still dates its own page with ?date=
    seen = {p[2] for p in placements}
    dated = [s for h, s in HALL_SLUG.items() if h not in seen]
    for slug in dated:
        with cf.ThreadPoolExecutor(8) as ex:
            got = dict(zip(dates, ex.map(lambda d: get(f"https://dining.ucla.edu/{slug}/?date={d}"), dates)))
        before = len(placements)
        for d, html in got.items():
            parse_venue_page(html, slug, placements, d)
        print(f"  {slug}: {len(placements) - before} over {len(dates)} days", file=sys.stderr)

    print("fetching venue standing menus ...", file=sys.stderr)
    slugs = sorted(QUICK)   # halls are dated above; their own pages repeat that menu undated
    with cf.ThreadPoolExecutor(8) as ex:
        vpages = dict(zip(slugs, ex.map(lambda s: get(f"https://dining.ucla.edu/{s}/", required=False), slugs)))
    for slug, html in vpages.items():
        before = len(placements)
        parse_venue_page(html, slug, placements)
        print(f"  {slug}: {len(placements) - before}", file=sys.stderr)

    # best name per recipe id: prefer a real name over the venue pages' "See Meal Details"
    names, where = {}, defaultdict(list)
    for rid, name, venue, meal, station, date in placements:
        if not name.lower().startswith("see meal"):
            names.setdefault(rid, name)
        where[rid].append({"venue": venue, "meal": meal, "station": station, "date": date})

    ids = sorted(names)
    print(f"scraping {len(ids)} nutrition panels ...", file=sys.stderr)
    items = {}
    with cf.ThreadPoolExecutor(14) as ex:
        for n, (rid, d) in enumerate(ex.map(scrape_item, ids), 1):
            if n % 200 == 0:
                print(f"  {n}/{len(ids)}", file=sys.stderr)
            d["name"] = names[rid]
            d["where"] = where[rid]
            items[rid] = d

    # components of build-your-own items are recipes too, and most never appear on a
    # menu station, so pull whatever the first pass referenced but did not fetch.
    for depth in range(3):
        extra = {c["id"]: c["name"]
                 for v in items.values()
                 for grp in v.get("build_groups", [])
                 for c in grp
                 if c["id"] not in items}
        if not extra:
            break
        print(f"  component pass {depth + 1}: {len(extra)} more", file=sys.stderr)
        with cf.ThreadPoolExecutor(14) as ex:
            for rid, d in ex.map(scrape_item, sorted(extra)):
                d["name"] = extra[rid]
                d["where"] = []
                d["component_only"] = True
                items[rid] = d

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"dates": dates, "items": items}, ensure_ascii=False))
    ok = sum(1 for v in items.values() if "kcal" in v)
    ing = sum(1 for v in items.values() if v.get("ingredients_raw"))
    print(f"\nwrote {OUT.relative_to(ROOT)}: {len(items)} items, {ok} with calories, {ing} with ingredients",
          file=sys.stderr)

if __name__ == "__main__":
    main()
