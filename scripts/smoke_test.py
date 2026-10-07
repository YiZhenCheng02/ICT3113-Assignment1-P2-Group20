"""
smoke_test.py - quick check that the triage service works end to end.
Sends a few tickets from our team's rows (NOT from the golden set), then calls /search and /stats.

Usage:
    python scripts/smoke_test.py golden_set/team20_rows_20000_20999.csv
    python scripts/smoke_test.py golden_set/team20_rows_20000_20999.csv --url http://localhost:8000 --n 3

Uses only the Python standard library, so no pip install is needed.
"""
import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

p = argparse.ArgumentParser()
p.add_argument("rows_csv")
p.add_argument("--url", default="http://localhost:8000")
p.add_argument("--n", type=int, default=3)
p.add_argument("--golden", default="golden_set/golden_set_final.csv",
               help="golden set file, used only to SKIP those rows so the model doesn't see them early")
args = p.parse_args()


def call(method, path, body=None, headers=None):
    req = urllib.request.Request(args.url + path, data=body, method=method, headers=headers or {})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as r:
        return r.status, json.loads(r.read()), (time.perf_counter() - t0) * 1000


# Skip golden-set rows: the golden set must stay unseen until the accuracy test.
# Fail loudly (before sending any ticket) if the golden file is missing or has no "row" column.
try:
    with open(args.golden, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "row" not in reader.fieldnames:
            print(f"ERROR: golden set {args.golden!r} has no 'row' column; refusing to run.",
                  file=sys.stderr)
            sys.exit(1)
        golden_rows = {(r["row"] or "").strip() for r in reader}
except FileNotFoundError:
    print(f"ERROR: golden set file {args.golden!r} not found; refusing to run.", file=sys.stderr)
    sys.exit(1)

print(call("GET", "/health")[1])
posted_ok = 0
posted_failed = 0
for row in csv.DictReader(open(args.rows_csv, encoding="utf-8")):
    row_id = (row["row"] or "").strip()
    if row_id in golden_rows:
        continue
    # POST directly so we can time it and handle a 502 invalid-category response ourselves.
    req = urllib.request.Request(
        args.url + "/tickets",
        data=row["narrative"].encode("utf-8"),
        method="POST",
        headers={"Content-Type": "text/plain; charset=utf-8", "X-Ticket-Ref": row_id},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            status, body = r.status, json.loads(r.read())
        ms = (time.perf_counter() - t0) * 1000
        category = body.get("category", "?") if isinstance(body, dict) else "?"
        print(f"row {row_id}: HTTP {status} -> {str(category):<26} ({ms:,.0f} ms)")
        posted_ok += 1
    except urllib.error.HTTPError as e:
        ms = (time.perf_counter() - t0) * 1000
        try:
            payload = json.loads(e.read())
            message = payload.get("error", "") if isinstance(payload, dict) else ""
        except (ValueError, OSError):
            message = ""
        if not message:
            message = str(e.reason or "HTTP error")
        print(f"row {row_id}: HTTP {e.code} -> ERROR: {message} ({ms:,.0f} ms)")
        posted_failed += 1
    if posted_ok + posted_failed >= args.n:
        break

print(f"tickets posted: {posted_ok} succeeded, {posted_failed} failed")
print("search 'credit':", call("GET", "/search?" + urllib.parse.urlencode({"q": "credit"}))[1]["count"], "results")
print("stats:", call("GET", "/stats")[1])
