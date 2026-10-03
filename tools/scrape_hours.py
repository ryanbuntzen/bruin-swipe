#!/usr/bin/env python3
"""UCLA publishes real service windows; use them instead of guessing at meal times.

dining.ucla.edu/hours/ carries one table per day for the coming week: a row per venue,
a column per meal period, each cell either a window or "Closed".  Writes data/hours.json
as {date: {venue: {meal: [open_minutes, close_minutes]}}}, minutes from midnight so the
app can compare against the clock without parsing anything.
"""
import json, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "hours.json"
UA = {"User-Agent": "bruin-swipe/1.0 (personal nutrition tracker)"}

def mins(t):
    m = re.match(r"(\d{1,2}):(\d{2})\s*([ap])\.?m", t.strip(), re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    if ap == "p" and h != 12:
        h += 12
    if ap == "a" and h == 12:
        h = 0
    return h * 60 + mi

def main():
    html = urllib.request.urlopen(
        urllib.request.Request("https://dining.ucla.edu/hours/", headers=UA),
        timeout=45).read().decode("utf8", "ignore")

    dates = [d for _, d in re.findall(r"<option value=\"(\d+)\"[^>]*>([^<]+)</option>", html)]
    panels = re.split(r'<div class="hours-day-panel"', html)[1:]
    out = {}
    from datetime import datetime
    for idx, panel in enumerate(panels):
        label = dates[idx] if idx < len(dates) else f"day{idx}"
        try:
            iso = datetime.strptime(label.split(", ", 1)[1], "%B %d, %Y").strftime("%Y-%m-%d")
        except Exception:
            iso = label
        heads = [re.sub(r"<[^>]+>", "", x).strip()
                 for x in re.findall(r"<th[^>]*>(.*?)</th>", panel, re.S)][1:]     # drop "Location"
        day = {}
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", panel, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if len(cells) < 2:
                continue
            venue = re.sub(r"<[^>]+>", "", cells[0]).strip()
            windows = {}
            for meal, cell in zip(heads, cells[1:]):
                txt = re.sub(r"<[^>]+>", " ", cell)
                txt = txt.replace("&nbsp;", " ").replace("–", "-").replace("—", "-")
                parts = txt.split("-")
                if len(parts) == 2:
                    a, b = mins(parts[0]), mins(parts[1])
                    if a is not None and b is not None:
                        windows[meal] = [a, b if b > a else b + 24 * 60]
            if venue:
                day[venue] = windows
        out[iso] = day

    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    first = sorted(out)[0]
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} days, {len(out[first])} venues")
    def hhmm(m): return f"{m // 60:02d}:{m % 60:02d}"
    for v, w in sorted(out[first].items())[:9]:
        print("  " + v[:26].ljust(26) +
              "  ".join(f"{k} {hhmm(a)}-{hhmm(b)}" for k, (a, b) in w.items()) or "  closed all day")

if __name__ == "__main__":
    main()
