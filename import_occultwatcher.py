"""
Occultation Ledger — Bulk Import Script
-----------------------------------------
Takes a CSV file you've exported from OccultWatcherCloud (or typed up
yourself) and uploads every row to your live API in one go, instead of
retyping each event by hand into the /docs page.

HOW TO USE
----------
1. pip install requests

2. Export your events from OccultWatcherCloud as a CSV (or build your own
   CSV / spreadsheet with the same idea — see COLUMN MAPPING below).

3. Save that file as "events_export.csv" next to this script (or pass a
   different filename as an argument, see bottom of this file).

4. Set API_URL below to your real Render URL.

5. Run:  python import_occultwatcher.py

   It will show you a preview of what it's about to upload first, ask you
   to confirm, then upload everything and skip anything that looks like a
   duplicate of what's already in your API.

COLUMN MAPPING — READ THIS PART
--------------------------------
Every export tool names its columns a bit differently, and I haven't seen
your actual OccultWatcherCloud export yet, so this script tries several
common header names automatically (see COLUMN_ALIASES below). If it can't
find a match for something, it'll tell you exactly which column it
couldn't figure out — at that point, either:
  (a) rename that column in your CSV to match one of the aliases listed, or
  (b) add your export's actual header name to the alias list yourself,
      right in the COLUMN_ALIASES dictionary below (it's plain text, no
      real "coding" needed — just add "your header name" inside the
      matching list).
"""

import csv
import sys
from datetime import datetime

import requests

# ---- fill this in ----
API_URL = "https://occultation-api.onrender.com"

# Recognized header name variants for each field we need.
# Add your export's actual column names here if they don't match already.
COLUMN_ALIASES = {
    "name": ["name", "star", "star name", "target", "event", "tycho", "object"],
    "type": ["type", "event type", "occultation type"],
    "starmag": ["starmag", "star mag", "star magnitude", "mag", "magnitude"],
    "objmag": ["objmag", "asteroid mag", "asteroid magnitude", "object mag", "obj mag"],
    "dur": ["dur", "duration", "duration (s)", "duration sec", "max duration"],
    "datetime": ["datetime", "date", "date time", "date/time (ut)", "event time", "time"],
    "moon": ["moon", "moon phase", "days from new moon", "moon illum"],
    "notes": ["notes", "comment", "comments", "remarks"],
}


def find_column(headers, field):
    lowered = {h.lower().strip(): h for h in headers}
    for alias in COLUMN_ALIASES[field]:
        if alias in lowered:
            return lowered[alias]
    return None


def guess_type(row_type_value, has_objmag):
    if row_type_value:
        v = row_type_value.strip().lower()
        if "lunar" in v or "moon" in v:
            return "lunar"
        if "aster" in v:
            return "asteroid"
    # fall back: if there's an asteroid magnitude, assume asteroid event
    return "asteroid" if has_objmag else "lunar"


def parse_float(value):
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def normalize_datetime(value):
    """Try a handful of common formats; fall back to returning as-is
    (the API expects ISO format like 2026-09-14T21:30)."""
    value = value.strip()
    formats = [
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%d %b %Y %H:%M",
        "%d-%m-%Y %H:%M",
        "%m/%d/%Y %H:%M",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            continue
    return value  # let the API validation catch it if it's truly unparseable


def load_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)
    return headers, rows


def build_events(headers, rows):
    col = {field: find_column(headers, field) for field in COLUMN_ALIASES}

    missing_required = [f for f in ("name", "starmag", "datetime") if col[f] is None]
    if missing_required:
        print("Could not find a column for:", ", ".join(missing_required))
        print("Your CSV's actual headers are:", headers)
        print("Add the matching header name to COLUMN_ALIASES in this script, then re-run.")
        sys.exit(1)

    events = []
    skipped = []
    for i, row in enumerate(rows, start=2):  # start=2: row 1 is the header line
        name = (row.get(col["name"]) or "").strip()
        starmag = parse_float(row.get(col["starmag"]))
        raw_dt = row.get(col["datetime"]) or ""

        if not name or starmag is None or not raw_dt.strip():
            skipped.append((i, "missing name, star magnitude, or datetime"))
            continue

        objmag = parse_float(row.get(col["objmag"])) if col["objmag"] else None
        ev = {
            "name": name,
            "type": guess_type(row.get(col["type"]) if col["type"] else None, objmag is not None),
            "starmag": starmag,
            "objmag": objmag,
            "dur": parse_float(row.get(col["dur"])) if col["dur"] else None,
            "datetime": normalize_datetime(raw_dt),
            "moon": parse_float(row.get(col["moon"])) if col["moon"] else None,
            "notes": (row.get(col["notes"]) or "").strip() if col["notes"] else None,
        }
        events.append(ev)
    return events, skipped


def already_exists(existing, ev):
    for e in existing:
        if e.get("name") == ev["name"] and e.get("datetime") == ev["datetime"]:
            return True
    return False


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "events_export.csv"

    try:
        headers, rows = load_csv(path)
    except FileNotFoundError:
        print(f"Couldn't find '{path}'. Put your exported CSV next to this script, "
              f"or run: python import_occultwatcher.py your_file.csv")
        sys.exit(1)

    events, skipped = build_events(headers, rows)

    print(f"\nParsed {len(events)} event(s) from '{path}'.")
    if skipped:
        print(f"Skipped {len(skipped)} row(s) with missing required data:")
        for row_num, reason in skipped:
            print(f"  - row {row_num}: {reason}")

    if not events:
        print("Nothing to upload.")
        return

    print("\nPreview of what will be uploaded:")
    for ev in events[:5]:
        print(f"  - {ev['name']}  |  {ev['type']}  |  star mag {ev['starmag']}  |  {ev['datetime']}")
    if len(events) > 5:
        print(f"  ...and {len(events) - 5} more.")

    confirm = input(f"\nUpload these {len(events)} event(s) to {API_URL}? [y/N] ").strip().lower()
    if confirm != "y":
        print("Cancelled — nothing was uploaded.")
        return

    try:
        existing = requests.get(f"{API_URL}/events", timeout=15).json()
    except requests.RequestException as e:
        print(f"Couldn't reach the API ({e}). Check API_URL and that your Render service is awake.")
        return

    uploaded, duplicates, failed = 0, 0, 0
    for ev in events:
        if already_exists(existing, ev):
            duplicates += 1
            continue
        resp = requests.post(f"{API_URL}/events", json=ev, timeout=15)
        if resp.status_code == 200:
            uploaded += 1
        else:
            failed += 1
            print(f"  [failed] {ev['name']}: {resp.status_code} {resp.text}")

    print(f"\nDone. Uploaded: {uploaded}   Already existed (skipped): {duplicates}   Failed: {failed}")


if __name__ == "__main__":
    main()
