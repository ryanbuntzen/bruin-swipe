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

State is saved to `localStorage`, so ticks survive a refresh and never leave the device.

## Running it

One HTML file, no build step and no dependencies beyond two Google Fonts. Open
`index.html`, or serve the directory with `python3 -m http.server`.

## Data

Hand-compiled from UCLA Dining's published nutrition, then converted into eyeball
portions. Menus rotate, so the "PICK: red meat of the day" rows are estimates for
whatever is out that day rather than a specific dish.
