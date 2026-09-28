# Bruin Swipe Card

Calories and macros for every UCLA dining hall, written in the portions you actually
take rather than the ones the nutrition site lists.

**Live:** https://ryanbuntzen.github.io/bruin-swipe/

## Why

UCLA publishes nutrition per serving, but nobody eats a serving. The useful question at
the counter is "what does the thing in front of me cost me," so every item here carries
an eyeball portion — *5 eggs, ask for five, they plate it*; *3 scoops ≈ 1 cup*;
*≈ 22 grapes, one cupped handful* — with the macros for that amount, not for 4oz.

## What it does

- Six halls: De Neve, Sproul, Bruin Plate, Epicuria at Covel, Feast at Rieber, Rendezvous
- A day's worth of meals per hall, each hitting roughly 1,000 kcal and 50g protein
- Tap any item to tick it; a sticky bar tallies kcal, protein, fat and carbs
- A progress bar against a 3,200 kcal day, marked at 3,000
- Each hall is chipped with what it does and doesn't have — *eggs daily*, *no white rice*,
  *no breakfast* — because that's what decides where you walk
- Items fried in canola are flagged, and a "Weekend +" card covers two-meal days

## Per person

On first open it asks who's eating, a daily calorie target and any diet
restrictions. The progress bar runs against that target instead of a fixed one.

Several people can share a device: each gets their own target, diet and ticks,
and the chip in the header switches between them. Diets available are
vegetarian, no pork, no red meat and no dairy; matching items are hidden and the
meal totals recompute around them, with a count of what was hidden.

Diet tags are derived from each item's own name and station rather than
hand-tagged across 250 rows, so "Turkey Bacon" survives a no-pork filter but not
a vegetarian one. The rotating "red meat of the day" rows are tagged red meat,
which is always true, and never pork, which is only true some days.

State is saved to `localStorage`, so ticks survive a refresh and never leave the
device. Nothing is sent anywhere and there are no accounts.

## Running it

One HTML file, no build step and no dependencies beyond two Google Fonts. Open
`index.html`, or serve the directory with `python3 -m http.server`.

## Data

Hand-compiled from UCLA Dining's published nutrition, then converted into eyeball
portions. Menus rotate, so the "PICK: red meat of the day" rows are estimates for
whatever is out that day rather than a specific dish.
