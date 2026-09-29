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
const consts = ["DAY_START_HOUR", "DV", "UNIT", "LABEL", "SECTIONS", "MAJOR", "CHASE"]
  .map(n => src.match(new RegExp(`\\nvar ${n} =[\\s\\S]*?\\n\\};?\\n|\\nvar ${n} =[^\\n]*\\n`))[0]).join("\n");
const fns = ["dayKey", "zero", "vecOf", "sumVecs", "get", "fmt", "isEstimated", "targets",
             "hasRule", "scoreItem"].map(n => grab(n)).join("\n");

const db = JSON.parse(readFileSync(new URL("../data/foods.json", import.meta.url), "utf8"));
let PROFILE = { goal: 3100, diets: [], rules: [], log: {} };

const sandbox = `
${consts}
var D = DB, NUT = D.nutrients, MEASURED = D.measured;
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

console.log("all logic checks passed");
