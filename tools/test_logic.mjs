// Pulls the pure functions out of index.html and runs them against the real data file.
// node tools/test_logic.mjs
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const src = html.match(/<script>([\s\S]*)<\/script>/)[1];

// take the constant block plus the functions that touch no DOM
function grab(name, kind = "function") {
  const re = kind === "function"
    ? new RegExp(`\\nfunction ${name}\\([\\s\\S]*?\\n\\}`, "m")
    : new RegExp(`\\nvar ${name} = [\\s\\S]*?;\\n`, "m");
  const m = src.match(re);
  assert.ok(m, `could not extract ${name}`);
  return m[0];
}
const consts = ["DAY_START_HOUR", "OWNER", "DV", "UNIT", "LABEL", "SECTIONS", "MAJOR", "CHASE"]
  .map(n => src.match(new RegExp(`\\nvar ${n} =[\\s\\S]*?\\n\\};?\\n|\\nvar ${n} =[^\\n]*\\n`))[0]).join("\n");
const fns = ["dayKey", "zero", "vecOf", "sumVecs", "get", "fmt", "isEstimated", "targets",
             "hasRule", "isOwner", "scoreItem"].map(n => grab(n)).join("\n");

const db = JSON.parse(readFileSync(new URL("../data/foods.json", import.meta.url), "utf8"));
let PROFILE = { name: "ryanbuntzen", goal: 3100, diets: [], rules: [], log: {} };

const sandbox = `
${consts}
var D = DB, NUT = D.nutrients, MEASURED = D.measured;
var who = PROFILE.name;
function me(){ return PROFILE; }
${fns}
RESULT = { dayKey, vecOf, sumVecs, get, fmt, targets, scoreItem, isEstimated, zero };
`;
let RESULT;
const DB = db;
RESULT = new Function("DB", "PROFILE", sandbox + "\nreturn RESULT;")(DB, PROFILE);
const { vecOf, sumVecs, get, targets, scoreItem, dayKey } = RESULT;

const byName = n => Object.entries(db.items).find(([, v]) => v.n === n);

// 1. a plain item's vector is UCLA's own panel, untouched
{
  const [id, it] = byName("Fried Eggs");
  const v = vecOf({ id, q: 1 });
  assert.equal(v[0], it.v[0], "kcal passed through");
  assert.equal(get(v, "protein"), it.v[db.nutrients.indexOf("protein")]);
  // 5 eggs is 5x one serving
  assert.equal(vecOf({ id, q: 5 })[0], it.v[0] * 5, "quantity scales");
}

// 2. a build totals its chosen components and nothing else
{
  const [id, it] = byName("Build-Your-Own Burrito");
  assert.ok(it.b && it.b.length, "burrito is a builder");
  const comps = {};
  const picked = it.b.flat().slice(0, 3);
  picked.forEach(c => { comps[c] = 1; });
  const v = vecOf({ id, q: 1, comps });
  const want = picked.reduce((a, c) => a + (db.items[c].v?.[0] || 0), 0);
  assert.ok(Math.abs(v[0] - want) < 0.01, `build kcal ${v[0]} vs ${want}`);
  // doubling one component moves the total by exactly that component
  comps[picked[0]] = 2;
  const v2 = vecOf({ id, q: 1, comps });
  assert.ok(Math.abs(v2[0] - v[0] - db.items[picked[0]].v[0]) < 0.01, "component qty scales");
}

// 3. a day rolls over at 05:00, not midnight
{
  const at = h => { const d = new Date(2026, 8, 29, h, 30); return dayKey(d); };
  assert.equal(at(4), "2026-09-28", "4:30am still counts as the night before");
  assert.equal(at(5), "2026-09-29", "5:30am is the new day");
  assert.equal(at(23), "2026-09-29");
}

// 4. targets scale with the calorie goal only when the rule is on, and ceilings never move
//    (the rule is owner-gated, so this also proves the gate opens for the owner)
{
  PROFILE.rules = [];
  const plain = targets();
  assert.equal(plain.protein, 50);
  PROFILE.rules = ["scale"];
  const scaled = targets();
  assert.ok(Math.abs(scaled.protein - 50 * 3100 / 2000) < 1e-9, "protein scales 1.55x");
  assert.equal(scaled.sodium, 2300, "sodium ceiling does not scale");
  assert.equal(scaled.satfat, 20, "saturated fat ceiling does not scale");
  assert.equal(scaled.kcal, 3100);

  // ... and stays shut for anyone else, even with the rule ticked
  const other = new Function("DB", "PROFILE", sandbox + "\nreturn RESULT;")(
    DB, { name: "someone else", goal: 3100, diets: [], rules: ["scale"], log: {} });
  assert.equal(other.targets().protein, 50, "target scaling is owner-only");

  PROFILE.rules = [];
}

// 5. every stored vector is the right length and free of NaN
{
  let bad = 0;
  for (const [, it] of Object.entries(db.items)) {
    if (!it.v) continue;
    if (it.v.length !== db.nutrients.length || it.v.some(x => typeof x !== "number" || Number.isNaN(x))) bad++;
  }
  assert.equal(bad, 0, `${bad} items with a malformed nutrient vector`);
}

// 6. the recommender scores finite, and ranks a gap-filler above an empty one
{
  const gl = [{ k: "vit_c", frac: 0.1, missing: 80, target: 90 },
              { k: "calcium", frac: 0.2, missing: 900, target: 1300 }];
  const [, orange] = byName("Orange Juice") || [];
  let finite = true, n = 0;
  for (const [, it] of Object.entries(db.items)) {
    if (!it.v) continue;
    const s = scoreItem(it, gl);
    if (!Number.isFinite(s) || s < 0) finite = false;
    n++;
  }
  assert.ok(finite, "all scores finite and non-negative");
  assert.ok(n > 800, "scored the corpus");
  if (orange) assert.ok(scoreItem(orange, gl) > 0, "vitamin C item scores on a vitamin C gap");
}

// 7. sums add up across a logged day
{
  const [a] = byName("Fried Eggs"), [b] = byName("Sticky Rice");
  const tot = sumVecs([{ id: a, q: 2 }, { id: b, q: 1 }]);
  assert.ok(Math.abs(tot[0] - (db.items[a].v[0] * 2 + db.items[b].v[0])) < 0.01, "day total adds up");
}

// 8. the meal-of-day clock: 4pm is dinner, 2am is the late counter
{
  const fnSrc = n => src.match(new RegExp(`\\nfunction ${n}\\([\\s\\S]*?\\n\\}`))[0];
  const Real = Date;
  const at = h => new Function("Real", "H", `var DAY_START_HOUR = 5;
    function Date(){ return new Real(2026, 8, 29, Math.floor(H), Math.round((H % 1) * 60)); }
    ${fnSrc("mealAt")} ${fnSrc("currentMeal")} ${fnSrc("mealMatchesNow")}
    return { currentMeal, mealMatchesNow };`)(Real, h);
  assert.equal(at(8).currentMeal(), "Breakfast");
  assert.equal(at(12).currentMeal(), "Lunch");
  assert.equal(at(16.45).currentMeal(), "Dinner", "4:27pm is not breakfast");
  assert.equal(at(22).currentMeal(), "Late");
  assert.equal(at(2).currentMeal(), "Late", "2am belongs to the night before");
  assert.equal(at(16.45).mealMatchesNow("Breakfast"), false);
  assert.equal(at(16.45).mealMatchesNow("Dinner"), true);
}

// 9. slot targets count real units, not UCLA servings
{
  const fnSrc = n => src.match(new RegExp(`\\nfunction ${n}\\([\\s\\S]*?\\n\\}`))[0];
  const M = new Function(`${["cups","portionText","unitsPerServing","servingsForUnits"].map(fnSrc).join("\n")}
    return { portionText, unitsPerServing, servingsForUnits };`)();
  const eggs = byName("Scrambled Eggs")[1];
  // one UCLA serving of scrambled eggs is already about two eggs, so asking for five
  // must not hand back five servings
  assert.equal(M.unitsPerServing(eggs), 2);
  const q = M.servingsForUnits(eggs, 5);
  assert.ok(q <= 3, `five eggs should be at most 3 servings, got ${q}`);
  assert.ok(!/\b(9|10|11|12)\b/.test(M.portionText(eggs, q)), "no ten-egg plates");
  // and counting is per serving then multiplied, so it does not drift
  const fried = byName("Fried Eggs")[1];
  const per = M.unitsPerServing(fried);
  assert.equal(M.portionText(fried, 5), (per * 5) + " eggs");
}

// 10. published service hours beat the clock heuristic
{
  const fnSrc = n => src.match(new RegExp(`\\nfunction ${n}\\([\\s\\S]*?\\n\\}`))[0];
  const Real = Date;
  const at = h => new Function("Real", "H", `var DAY_START_HOUR = 5;
    function Date(){ return new Real(2026, 8, 29, Math.floor(H), Math.round((H % 1) * 60)); }
    Date.now = function(){ return new Real(2026, 8, 29, Math.floor(H), Math.round((H % 1) * 60)).getTime(); };
    ${["dayKey","currentMeal","mealMatchesNow","nowMins","clock","windowsFor",
       "mealWindow","servingNow","venueStatus"].map(fnSrc).join("\n")}
    return { venueStatus, servingNow };`)(Real, h);
  const deneve = db.venues.find(v => v.n === "De Neve");
  assert.ok(deneve.hours, "De Neve has published hours");

  // the clock alone calls 4:27pm dinner; the hall does not open until five
  assert.equal(at(16.45).servingNow(deneve, "Dinner"), false, "dinner is not served at 4:27");
  assert.match(at(16.45).venueStatus(deneve), /Closed .*Dinner at 5pm/);
  assert.equal(at(17.5).servingNow(deneve, "Dinner"), true);
  assert.match(at(17.5).venueStatus(deneve), /Dinner now/);
  assert.match(at(20.9).venueStatus(deneve), /closes in \d+ min/);
  assert.equal(at(8).servingNow(deneve, "Breakfast"), true);
}

// 11. leaving the bun behind comes off the total, and scales with servings
{
  const [id, it] = byName("Bruin Cheeseburger");
  assert.ok((it.rm || []).includes("bun"), "the burger offers to skip its bun");
  const whole = vecOf({ id, q: 1 });
  const naked = vecOf({ id, q: 1, skip: ["bun"] });
  const bun = db.removals.bun.v[0];
  assert.ok(Math.abs((whole[0] - naked[0]) - bun) < 0.01, "one bun comes off");
  assert.ok(naked[0] < whole[0] && naked[0] > 0, "and the patty is still there");
  const two = vecOf({ id, q: 2, skip: ["bun"] });
  assert.ok(Math.abs(two[0] - naked[0] * 2) < 0.01, "two burgers, two buns");
  // carbs should drop more than protein does
  const ci = db.nutrients.indexOf("carb"), pi = db.nutrients.indexOf("protein");
  assert.ok(whole[ci] - naked[ci] > whole[pi] - naked[pi], "a bun is mostly carbohydrate");
}

// 12. the allowlist diet: staples survive, and the things it exists to exclude do not
{
  const i = src.indexOf("var DIETS = ["), j = src.indexOf("/i}];", i) + 5;
  const DIETS = new Function(src.slice(i, j) + "\nreturn DIETS;")();
  const dbk = src.slice(src.indexOf("var DIET_BY_KEY"),
                        src.indexOf("DIETS.forEach(function(d){ DIET_BY_KEY[d.k] = d; });") + 52);
  const bs = src.match(/\nfunction blocked\([\s\S]*?\n\}/)[0];
  const blocked = new Function("DIETS", "PROFILE",
    'var who = "ryanbuntzen", OWNER = "ryanbuntzen", OWNER_DIETS = ["animalfruit"];\n'
    + 'function isOwner(n){return (n||"").trim().toLowerCase()===OWNER;}\n'
    + dbk + "\nfunction me(){return PROFILE;}" + bs + "\nreturn blocked;")(
      DIETS, { diets: [] });          // nothing ticked: it applies on its own
  const find = n => Object.values(db.items).find(v => v.n === n);

  for (const n of ["Fried Eggs", "Scrambled Eggs", "Sticky Rice", "Bruin Cheeseburger",
                   "Bruin Burger", "Pork Sausage", "Bacon", "Cantaloupe", "Banana",
                   "Lowfat Milk", "Low Fat Greek Yogurt", "Sweet Potato Fries",
                   "Grilled Rosemary Chicken Breast", "Orange Juice",
                   // the bread, the veg and the sauce come off a meat dish; smoothies and coconut are in
                   "Bruin Fresh Smoothie", "Shredded Coconut", "Cheesesteak", "Ham & Swiss Sandwich",
                   "Daube Beef Provençal", "Beef and Broccoli", "Whole Wheat Sourdough Bread"]) {
    const it = find(n);
    if (it) assert.equal(blocked(it), false, `${n} should be on the diet`);
  }
  for (const n of ["Almond Butter", "Peanut Butter", "Chocolate Peanut Butter",
                   "Garlicky Green Beans", "Oatmeal", "Chicken Tortilla Soup",
                   "Cheese Pizza", "Banana Walnut Muffin",
                   // a meat dish is still out when the rest can't be picked off, or the meat isn't meat
                   "Chicken Noodle Soup", "Chicken & Sundried Tomato Pizza", "Pepperoni and Cheese Calzone", "Vegan Chicken Caesar Sandwich",
                   'Roasted Garden "Salmon" Sandwich', "Wheat Berry"]) {
    const it = find(n);
    if (it) assert.equal(blocked(it), true, `${n} should be off the diet`);
  }
  // and the diet is owner-only: same items, a different name, nothing hidden
  const notOwner = new Function("DIETS", "PROFILE",
    'var who = "someone", OWNER = "ryanbuntzen", OWNER_DIETS = ["animalfruit"];\n'
    + 'function isOwner(n){return (n||"").trim().toLowerCase()===OWNER;}\n'
    + dbk + "\nfunction me(){return PROFILE;}" + bs + "\nreturn blocked;")(
      DIETS, { diets: ["animalfruit"] });   // even ticked, it must not apply
  assert.equal(notOwner(find("Almond Butter")), false, "the allowlist diet is owner-only");
}

// 13. the swipe budget: a 19 Regular with 4 left on Saturday gets 2 today, not 3
{
  const pick = n => src.match(new RegExp(`\\nfunction ${n}\\([\\s\\S]*?\\n\\}`))[0];
  const plan = src.slice(src.indexOf("var PLANS = ["), src.indexOf("function keyDate"));
  const body = ["dayKey", "keyDate", "addDays", "weekdayOf", "planOf", "mealsOn", "swipesOn", "budget"]
    .map(pick).join("\n");
  const at = (d, h) => new Date(2026, 9, d, h).getTime();      // Oct 2026: the 3rd is a Saturday
  function run(profile, nowD, nowH) {
    const RealDate = Date;
    class FakeDate extends RealDate {
      constructor(...a) { super(...(a.length ? a : [at(nowD, nowH)])); }
      static now() { return at(nowD, nowH); }
    }
    return new Function("PROFILE", "Date", "var DAY_START_HOUR = 5;\n" + plan + body +
      "\nfunction me(){ return PROFILE; }\nreturn budget();")(profile, FakeDate);
  }
  // 15 swipes Mon 9/28 - Fri 10/2, three meals planned every day
  const swipes = [];
  for (let d = 28; d <= 32; d++) for (const h of [9, 13, 18]) if (swipes.length < 15)
    swipes.push(new Date(2026, 8, d, h).getTime());
  const b = run({plan: "19R", meals: [3, 3, 3, 3, 3, 3, 3], swipes}, 3, 10);
  assert.equal(b.left, 4, "19 minus 15");
  assert.equal(b.today, 2, "4 left over Sat+Sun is 2 a day");
  // a new week resets the count
  assert.equal(run({plan: "19R", meals: [3, 3, 3, 3, 3, 3, 3], swipes}, 5, 10).left, 19, "Monday resets");
  // a Premier pot counts down from what was typed in, and plans 2-meal days lightly
  const p = run({plan: "19P", meals: [2, 2, 2, 2, 2, 2, 2], planEnd: "2026-12-11",
                 left: {n: 150, at: at(1, 8)}, swipes: [at(1, 12), at(2, 12)]}, 3, 10);
  assert.equal(p.left, 148, "typed count minus swipes since");
  assert.equal(p.today, 2, "plenty left: the plan's own meals");
}

console.log("all logic checks passed");
