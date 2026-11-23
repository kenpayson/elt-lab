"""
EXTRACT + LOAD  (the "E" and "L" in ELT -- the part Fivetran used to do for you)

Pulls NYC 311 service requests from the free NYC Open Data (Socrata) API for a
date window, lands each page as a raw JSON file, then loads those files into
DuckDB *unchanged* (every column as text). Typing and cleaning happen later in
dbt -- that's what makes this ELT instead of ETL.

Run:  python extract_load.py --days 7
      python extract_load.py --start 2026-11-01 --end 2026-11-08
      python extract_load.py --days 7 --force     # reload a window already loaded
"""

import argparse
import json
import os
import shutil
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import requests

API_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"  # NYC 311, 2010-present
PAGE_SIZE = 5000
PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = PROJECT_DIR / "warehouse.duckdb"
LANDING_DIR = PROJECT_DIR / "data" / "raw" / "nyc_311"

# Columns we keep from the source. All land as VARCHAR -- raw means raw.
COLUMNS = [
    "unique_key", "created_date", "closed_date", "agency", "agency_name",
    "complaint_type", "descriptor", "status", "resolution_description",
    "borough", "incident_zip", "latitude", "longitude",
]


def api_headers():
    # Optional: a free Socrata app token raises your rate limit.
    token = os.environ.get("SOCRATA_APP_TOKEN")
    return {"X-App-Token": token} if token else {}


def where_clause(start: date, end: date) -> str:
    # Window is [start, end): includes start day, excludes end day.
    return f"created_date >= '{start}T00:00:00' AND created_date < '{end}T00:00:00'"


def source_count(start: date, end: date) -> int:
    """Ask the API how many rows exist in the window (used to reconcile later)."""
    params = {"$select": "count(*) AS n", "$where": where_clause(start, end)}
    r = requests.get(API_URL, params=params, headers=api_headers(), timeout=60)
    r.raise_for_status()
    return int(r.json()[0]["n"])


def extract(start: date, end: date, batch_dir: Path) -> int:
    """Page through the API and write each page to its own JSON file."""
    batch_dir.mkdir(parents=True, exist_ok=True)
    offset, page, total = 0, 1, 0
    while True:
        params = {
            "$select": ",".join(COLUMNS),
            "$where": where_clause(start, end),
            "$order": "created_date, unique_key",  # stable order so paging is reliable
            "$limit": PAGE_SIZE,
            "$offset": offset,
        }
        r = requests.get(API_URL, params=params, headers=api_headers(), timeout=120)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        (batch_dir / f"page_{page:05d}.json").write_text(json.dumps(rows))
        total += len(rows)
        print(f"  page {page}: {len(rows)} rows (running total {total})")
        # Don't treat a short page as the end -- the API can return short pages
        # mid-stream. Only an empty page means we're done.
        offset += len(rows)
        page += 1
    return total


def extract_day(day: date, batch_dir: Path, attempts: int = 3, wait_s: int = 60) -> int:
    """Extract ONE day, reconciling against the source count. Retry if it doesn't match.

    Why per day: the API can serve row queries from an older copy of the data
    than count queries (during NYC's daily refresh). Small windows make a
    mismatch cheap to retry and easy to pinpoint.
    """
    nxt = day + timedelta(days=1)
    day_dir = batch_dir / f"day={day}"
    for attempt in range(1, attempts + 1):
        if day_dir.exists():
            shutil.rmtree(day_dir)  # discard the previous failed attempt's pages
        before = source_count(day, nxt)
        got = extract(day, nxt, day_dir) if before else 0
        after = source_count(day, nxt)
        if before == after == got:
            print(f"  {day}: {got} rows, reconciled")
            return got
        print(f"  {day}: attempt {attempt} mismatch (before={before}, extracted={got}, after={after})")
        if attempt < attempts:
            print(f"  waiting {wait_s}s and retrying {day}...")
            time.sleep(wait_s)
    raise RuntimeError(f"{day} did not reconcile after {attempts} attempts")


def ensure_tables(con):
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    cols = ",\n  ".join(f"{c} VARCHAR" for c in COLUMNS)
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS raw.nyc_311_requests (
          {cols},
          _batch_id VARCHAR,
          _loaded_at TIMESTAMP
        )""")
    # One row per load attempt: our audit trail.
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.load_log (
          batch_id VARCHAR,
          window_start DATE,
          window_end DATE,
          source_count BIGINT,
          extracted_count BIGINT,
          loaded_count BIGINT,
          status VARCHAR,
          started_at TIMESTAMP,
          finished_at TIMESTAMP,
          message VARCHAR
        )""")


def already_loaded(con, start: date, end: date) -> bool:
    row = con.execute(
        "SELECT count(*) FROM raw.load_log WHERE window_start=? AND window_end=? AND status='SUCCESS'",
        [start, end],
    ).fetchone()
    return row[0] > 0


def load(con, batch_dir: Path, batch_id: str, loaded_at: datetime) -> int:
    """Let the warehouse read the landed files directly -- classic ELT 'L'."""
    col_types = "{" + ", ".join(f"'{c}': 'VARCHAR'" for c in COLUMNS) + "}"
    glob = str(batch_dir / "*" / "*.json").replace("'", "''")  # day=*/page_*.json
    col_list = ", ".join(COLUMNS)
    con.execute(f"""
        INSERT INTO raw.nyc_311_requests
        SELECT {col_list}, ? AS _batch_id, ? AS _loaded_at
        FROM read_json('{glob}', format='array', columns={col_types})
    """, [batch_id, loaded_at])
    return con.execute(
        "SELECT count(*) FROM raw.nyc_311_requests WHERE _batch_id=?", [batch_id]
    ).fetchone()[0]


def main():
    p = argparse.ArgumentParser(description="Extract NYC 311 and load raw into DuckDB")
    p.add_argument("--days", type=int, default=7, help="days back from today (default 7)")
    p.add_argument("--start", help="YYYY-MM-DD (overrides --days)")
    p.add_argument("--end", help="YYYY-MM-DD, exclusive (default today)")
    p.add_argument("--force", action="store_true", help="reload even if window already loaded")
    a = p.parse_args()

    end = date.fromisoformat(a.end) if a.end else date.today()
    start = date.fromisoformat(a.start) if a.start else end - timedelta(days=a.days)
    if start >= end:
        sys.exit("start must be before end")

    con = duckdb.connect(str(DB_PATH))
    ensure_tables(con)

    if already_loaded(con, start, end) and not a.force:
        print(f"Window {start} -> {end} already loaded successfully. Skipping (use --force to reload).")
        return

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    started = datetime.now(timezone.utc).replace(tzinfo=None)
    batch_dir = LANDING_DIR / batch_id
    print(f"Batch {batch_id}: window {start} -> {end} (end exclusive)")

    src_n = ext_n = loaded_n = None
    try:
        src_n = ext_n = 0
        day = start
        while day < end:  # one day at a time, each reconciled on its own
            n = extract_day(day, batch_dir)
            src_n += n
            ext_n += n
            day += timedelta(days=1)
        print(f"All days reconciled: {ext_n} rows. Loading...")
        loaded_n = load(con, batch_dir, batch_id, started) if ext_n else 0

        # Reconciliation: did everything we expected actually arrive?
        if not (src_n == ext_n == loaded_n):
            raise RuntimeError(f"count mismatch: source={src_n} extracted={ext_n} loaded={loaded_n}")
        status, msg = "SUCCESS", None
        print(f"Loaded {loaded_n} rows into raw.nyc_311_requests. Counts reconcile.")
    except Exception as e:  # record the failure, then fail loudly
        status, msg = "FAILED", str(e)[:500]
        print(f"FAILED: {msg}", file=sys.stderr)
    finally:
        con.execute(
            "INSERT INTO raw.load_log VALUES (?,?,?,?,?,?,?,?,?,?)",
            [batch_id, start, end, src_n, ext_n, loaded_n, status,
             started, datetime.now(timezone.utc).replace(tzinfo=None), msg],
        )
        con.close()

    if status != "SUCCESS":
        sys.exit(1)


if __name__ == "__main__":
    main()
