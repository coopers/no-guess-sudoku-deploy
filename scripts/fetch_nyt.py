#!/usr/bin/env python3
"""Fetch today's NYT sudoku (easy/medium/hard) and store it in puzzles/nyt.json.

The NYT sudoku page embeds all three difficulties as `window.gameData`.
We keep a rolling 30-day archive keyed by print date so the site can offer
recent days too. Run daily by .github/workflows/nyt.yml.
"""
import json, re, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.nytimes.com/puzzles/sudoku/easy"
OUT = Path(__file__).resolve().parent.parent / "puzzles" / "nyt.json"
KEEP_DAYS = 30

req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (no-guess-sudoku fetcher)"})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
m = re.search(r"window\.gameData\s*=\s*(\{.*?\})\s*</script>", html, re.S)
if not m:
    sys.exit("gameData not found on NYT page")
data = json.loads(m.group(1))

day = {}
date = None
for level in ("easy", "medium", "hard"):
    v = data[level]
    date = date or v["print_date"]
    puzzle = "".join(str(x) for x in v["puzzle_data"]["puzzle"])
    if len(puzzle) != 81:
        sys.exit(f"{level}: unexpected puzzle length {len(puzzle)}")
    day[level] = puzzle

store = {"updated": None, "days": {}}
if OUT.exists():
    store = json.loads(OUT.read_text())
store["days"][date] = day
store["days"] = dict(sorted(store["days"].items())[-KEEP_DAYS:])
store["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
OUT.write_text(json.dumps(store, indent=1) + "\n")
print(f"stored {date}: " + ", ".join(f"{k}={v}" for k, v in day.items()))
