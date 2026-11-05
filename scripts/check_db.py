#!/usr/bin/env python3
"""Preflight for the Instagram run: is <db_dir> a usable copy of today's Ripple data?

usage: python3 -I check_db.py <db_dir> <YYYY-MM-DD> [--fix]

Checks (prints one JSON line {ok, problems[], fixed[]}; exit 0 only if ok):
  - every *.json parses;
  - days/<date>.json exists, its "date" is <date>, it has >= 3 items, each with id, rank, title, summary;
  - config/catalog.json has companies; config/status.json has state "done" and date <date>;
  - calendar/ahead.json exists (warning only if missing).
--fix rewrites {"id","data",...} wrappers to plain data fields (the shape ig_cards.py's page stub expects).
"""
import json, os, sys, glob
db, day = sys.argv[1], sys.argv[2]
fix = "--fix" in sys.argv
problems, fixed, warn = [], [], []
def load(rel):
    f = os.path.join(db, rel)
    if not os.path.exists(f): return None
    return json.load(open(f, encoding="utf8"))
for f in glob.glob(os.path.join(db, "**", "*.json"), recursive=True):
    try: d = json.load(open(f, encoding="utf8"))
    except Exception as ex:
        problems.append(f"{os.path.relpath(f, db)}: not valid JSON ({ex})"); continue
    if isinstance(d, dict) and isinstance(d.get("data"), dict) and set(d) <= {"id", "data", "version", "updatedAt"}:
        if fix:
            json.dump(d["data"], open(f, "w", encoding="utf8"), ensure_ascii=False); fixed.append(os.path.relpath(f, db))
        else:
            warn.append(f"{os.path.relpath(f, db)}: wrapped doc (run with --fix)")
dd = load(f"days/{day}.json")
if dd is None: problems.append(f"days/{day}.json missing")
else:
    dd = dd.get("data", dd)
    if dd.get("date") != day: problems.append(f"days/{day}.json has date {dd.get('date')}")
    items = dd.get("items", [])
    if len(items) < 3: problems.append(f"days/{day}.json has only {len(items)} items")
    for it in items:
        miss = [k for k in ("id", "rank", "title", "summary") if not it.get(k)]
        if miss: problems.append(f"item {it.get('id')}: missing {miss}"); break
    if not dd.get("snapshot"): warn.append("no snapshot (cover strip will be thin)")
cat = load("config/catalog.json")
if not cat or not (cat.get("data", cat)).get("companies"): problems.append("config/catalog.json missing or has no companies")
st = load("config/status.json")
if not st: problems.append("config/status.json missing")
else:
    st = st.get("data", st)
    if st.get("state") != "done" or st.get("date") != day: problems.append(f"config/status not done for {day} ({st.get('state')}, {st.get('date')})")
if load("calendar/ahead.json") is None: warn.append("calendar/ahead.json missing (no upcoming-event lines)")
print(json.dumps({"ok": not problems, "problems": problems, "fixed": fixed, "warnings": warn}, ensure_ascii=False))
sys.exit(0 if not problems else 1)
