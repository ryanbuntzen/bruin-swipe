# Bruin Swipe Card

Track what you eat at UCLA dining. Log an item and you get its full panel: calories,
macros and 39 micronutrients, for every item at every dining location on campus.

**Live:** https://ryanbuntzen.github.io/bruin-swipe/

## What it does

- **Logs the day.** Tap an item, pick how many servings, add it. The bar at the bottom runs
  your day's total against your calorie target, and tapping it opens the full panel, where you
  can also take things back off. The day rolls over at 5am instead of midnight, so a 2am plate
  counts against the night before. Each person keeps two weeks of history, stored on the device.
- **39 micronutrients.** UCLA publishes 19 of them per item. The other 20, including magnesium,
  zinc, selenium, copper, manganese, the B vitamins, E, K and the omega-3s, are worked out from
  the ingredient list instead. Anything worked out that way is marked `est`.
- **Every dining location**, not just the residential halls. Four all-you-can-eat halls on the
  first deck, then Rendezvous, Bruin Café, The Study at Hedrick, Café 1919, The Drey and
  Epicuria at Ackerman on the second. Swipe sideways to get between the two.
- **Build-your-own items** are priced up component by component from UCLA's own picker, so the
  Rendezvous burrito bar, the salad bars, the omelet bar, The Study's craft-your-own pizza and
  the Bruin Café toasted sandwiches all cost what you actually built.
- **Tells you what you are short on.** Once you have logged a meal it ranks the nutrients you
  are behind on, names the place that fixes them fastest, and flags the best items at whatever
  place you open.
- **Search** across all 1,285 items.
- **Per person.** Name, calorie target, and diet restrictions (vegetarian, no pork, no red meat,
  no dairy), which hide the items that match.

## Where the numbers come from

UCLA Dining publishes, per item: calories, protein, total, saturated and trans fat,
cholesterol, sodium, carbohydrate, fiber, sugars, added sugars, calcium, iron, potassium, and
vitamins A, B6, B12, C and D, plus the full ingredient list, the allergens and a serving weight.
All of that is used exactly as published and marked measured.

The remaining 20 are estimated:

1. Parse the ingredient list into leaf foods. UCLA comma-separates the ingredients inside
   sub-recipe brackets but runs the top-level ones together with no separator at all, so the
   parser builds a vocabulary from the bracketed names across the whole corpus, then
   longest-matches the unpunctuated runs against it.
2. Match each ingredient to [USDA FoodData Central SR Legacy](https://fdc.nal.usda.gov/download-datasets),
   which is 7,793 foods with complete nutrient vectors. Fuzzy matching, plus a hand-written
   override table covering the high-frequency names, since that is where most of the mass sits.
3. Solve for how many grams of each ingredient the serving holds. Non-negative least squares
   against the 18 nutrients UCLA does publish, with total mass pinned to the serving weight.
4. Read the missing nutrients off the fitted masses.

Median relative residual across 1,177 fitted items is 0.27. Simple recipes fit tightest: Fried
Eggs comes out as 99.7 g of egg and 6.3 g of canola oil at a 0.003 residual, which gives 293 mg
of choline, or two large eggs. Composite dishes whose bun or batter did not parse are where it
gets loose. Every item carries its own residual so you can see which is which.

**These are estimates, not label data.** Treat the `est` rows as good approximations.

## Rebuilding the data

Menus rotate weekly, so re-run the pipeline to refresh them:

```sh
python3 tools/scrape_ucla.py          # UCLA panels, ingredients, builders  -> data/ucla_raw.json
python3 tools/ingredients.py          # ingredient vocabulary + parse       -> data/vocab.json
curl -sLO https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip
unzip -o FoodData_Central_sr_legacy_food_json_2018-04.zip
python3 tools/usda.py   FoodData_Central_sr_legacy_food_json_2018-04.json   # -> data/ing_map.json
python3 tools/overrides.py FoodData_Central_sr_legacy_food_json_2018-04.json
python3 tools/estimate.py             # the fit for the missing micros
python3 tools/build_app_data.py       # -> data/foods.json, what the page loads
node tools/test_logic.mjs             # checks the maths against the bundle
```

Only `data/foods.json`, `data/ing_map.json` and `data/vocab.json` are committed. The
multi-megabyte intermediates can be regenerated and are gitignored.

## Running it

One HTML file plus one JSON file. No build step and no dependencies beyond two Google Fonts.
It fetches its data, so serve the directory rather than opening the file:

```sh
python3 -m http.server
```

State lives in `localStorage`. Nothing is sent anywhere and there are no accounts.

## Known gaps

- **Hall beverage lines aren't published.** No UCLA menu itemises hall drinks. Milk (De Neve,
  Bruin Plate), De Neve's breakfast orange juice and the yogurt bars' honey are added by hand in
  `build_app_data.py`; any other hall drink has to be logged through search.
- **Menus only publish a week ahead**, so the day picker covers the published window and falls
  back to the nearest day outside it.
- **Bruin Bowl, To-Go Lunches and the food trucks** publish no menu at all.
- **Brown Calrose rice** is listed at 105 kcal per 2 oz, which works out to 181 kcal per 100 g
  where cooked brown rice is about 123. The scoop looks to be weighed before cooking, so the
  brown-rice halls run roughly ±80 kcal a meal.
- **Sweet potato fries** are published at 0 kcal, which is broken data on UCLA's side.
