# Bruin Swipe Card

A day tracker for UCLA dining. Log what you ate, get the full nutrient panel —
calories, macros and 39 micronutrients — for every item at every dining location.

**Live:** https://ryanbuntzen.github.io/bruin-swipe/

## What it does

- **Logs the day.** Tap an item, pick how many servings, add it. The bar at the bottom
  runs the day's total against your calorie target; tap it for the full panel and to
  remove things. **The day rolls over at 5am**, not midnight, so a 2am plate counts
  against the night before. Two weeks of history is kept per person, on the device.
- **39 micronutrients.** UCLA publishes 19 per item. The other 20 — magnesium, zinc,
  selenium, copper, manganese, the B vitamins, E, K, the omega-3s — are derived (see
  *Where the numbers come from*). Every derived value is marked `est`.
- **Every dining location**, not just the residential halls: five all-you-can-eat halls
  on the first deck, then Rendezvous, Bruin Café, The Study at Hedrick, Café 1919, The
  Drey and Epicuria at Ackerman on the second. Swipe sideways between the two.
- **Build-your-own items** are priced up component by component from UCLA's own picker —
  the Rendezvous burrito bar, the salad bars, the omelet bar, The Study's craft-your-own
  pizza, the Bruin Café toasted sandwiches.
- **Tells you what you're missing.** After your first meal it ranks the nutrients you're
  behind on, names the best place to fix it, and flags the best items at whatever place
  you actually open.
- **Search** across all 1,285 items.
- **Per person.** Name, calorie target, diet restrictions (vegetarian, no pork, no red
  meat, no dairy — matching items are hidden), and two optional rules: scale the nutrient
  targets to your calorie goal, and hold omega-3:6 between 1:1 and 1:2.

## Where the numbers come from

UCLA Dining publishes, per item: calories, protein, total/saturated/trans fat,
cholesterol, sodium, carbohydrate, fiber, sugars, added sugars, calcium, iron,
potassium, and vitamins A, B6, B12, C and D — plus the full ingredient list, allergens
and a serving weight. All of that is used as published and marked measured.

The remaining 20 nutrients are estimated the way a dietitian would back them out:

1. Parse the ingredient list into leaf foods. UCLA comma-separates ingredients inside
   sub-recipe brackets but concatenates top-level ones with no separator, so the parser
   builds a vocabulary from the bracketed names across the whole corpus and
   longest-matches the unpunctuated runs against it.
2. Match each ingredient to [USDA FoodData Central SR Legacy](https://fdc.nal.usda.gov/download-datasets)
   — 7,793 foods with complete nutrient vectors. Fuzzy matching, plus a curated override
   table covering the high-frequency names, which is where the mass is.
3. Solve for how many grams of each ingredient the serving holds: non-negative least
   squares against the 18 nutrients UCLA does publish, with total mass pinned to the
   serving weight.
4. Read the missing nutrients off the fitted masses.

Median relative residual across 1,177 fitted items is 0.27. It is tightest where the
recipe is simple — Fried Eggs resolves to 99.7 g egg + 6.3 g canola oil at a 0.003
residual, giving 293 mg choline, which is two large eggs — and loosest on composite
dishes whose bun or batter didn't parse. Each item carries its own residual.

**These are estimates, not label data.** Treat the `est` rows as good approximations.

## Rebuilding the data

Menus rotate weekly, so re-run the pipeline to refresh:

```sh
python3 tools/scrape_ucla.py          # UCLA panels, ingredients, builders  -> data/ucla_raw.json
python3 tools/ingredients.py          # ingredient vocabulary + parse       -> data/vocab.json
curl -sLO https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip
unzip -o FoodData_Central_sr_legacy_food_json_2018-04.zip
python3 tools/usda.py   FoodData_Central_sr_legacy_food_json_2018-04.json   # -> data/ing_map.json
python3 tools/overrides.py FoodData_Central_sr_legacy_food_json_2018-04.json
python3 tools/estimate.py             # NNLS fit for the missing micros
python3 tools/build_app_data.py       # -> data/foods.json, what the page loads
node tools/test_logic.mjs             # checks the maths against the bundle
```

Only `data/foods.json`, `data/ing_map.json` and `data/vocab.json` are committed; the
multi-megabyte intermediates are regenerable and gitignored.

## Running it

One HTML file plus one JSON file, no build step, no dependencies beyond two Google
Fonts. It fetches its data, so serve the directory rather than opening the file:

```sh
python3 -m http.server
```

State lives in `localStorage`. Nothing is sent anywhere and there are no accounts.

## Known gaps

- **Hall beverage lines aren't published.** No UCLA menu itemises the milk and juice
  dispensers at De Neve, Sproul, Epicuria or Feast — the only milk and orange juice
  entries in the whole dataset belong to The Study at Hedrick. Those numbers are real,
  but that the same drinks sit on a given hall's island is an assumption.
- **Menus only publish a week ahead**, so the day picker covers the published window and
  falls back to the nearest day outside it.
- **Bruin Bowl, To-Go Lunches and the food trucks** publish no menu at all.
- **Brown Calrose rice** is listed at 105 kcal per 2 oz, which works out to 181 kcal per
  100 g where cooked brown rice is about 123 — the scoop looks to be measured before
  cooking, so the brown-rice halls run roughly ±80 kcal a meal.
- **Sweet potato fries** are published at 0 kcal, which is broken data on UCLA's side.
