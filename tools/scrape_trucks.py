#!/usr/bin/env python3
"""UCLA's food truck schedule -> data/trucks.json: {truck name: [[spot, "Wed Nov 4", slot], ...]}.

The meal-swipe-exchange page holds one table per truck spot (Sproul, Rieber): a row per day,
a column per time slot, truck names separated by <br> in each cell.
"""
import json, re, html as H
from pathlib import Path
from scrape_ucla import get

ROOT = Path(__file__).resolve().parent.parent

def text(s):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s))).strip()

def main():
    page = get("https://dining.ucla.edu/meal-swipe-exchange/")
    out = {}
    for spot, table in re.findall(r"<h3[^>]*>([^<]+)</h3>\s*<figure[^>]*>(.*?)</table>", page, re.S):
        slots = [text(t) for t in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)][1:]
        for row in re.findall(r"<tr>(.*?)</tr>", table, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if not cells:
                continue
            day = text(cells[0]).replace("[", "").replace("]", "").replace("  ", " ")
            for slot, cell in zip(slots, cells[1:]):
                for name in re.split(r"<br\s*/?>", cell):
                    name = text(name)
                    if name and name.upper() != "CLOSED":
                        out.setdefault(name, []).append([text(spot), day, slot])
    if not out:
        raise SystemExit("no trucks found on the schedule page -- did its layout change?")
    (ROOT / "data" / "trucks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"wrote data/trucks.json: {len(out)} trucks")
    for n, s in out.items():
        print(f"  {n}: {', '.join(d for _, d, _ in s)}")

if __name__ == "__main__":
    main()
