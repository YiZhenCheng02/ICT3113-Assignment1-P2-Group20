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
import time
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


# Skip golden-set rows: the golden set must stay unseen until the accuracy test
try:
    golden_rows = {r["row"] for r in csv.DictReader(open(args.golden, encoding="utf-8"))}
except FileNotFoundError:
    golden_rows = set()

print(call("GET", "/health")[1])
sent = 0
for row in csv.DictReader(open(args.rows_csv, encoding="utf-8")):
    if row["row"] in golden_rows:
        continue
    status, body, ms = call("POST", "/tickets", row["narrative"].encode("utf-8"),
                            {"Content-Type": "text/plain; charset=utf-8", "X-Ticket-Ref": row["row"]})
    print(f"row {row['row']}: HTTP {status} -> {body['category']:<26} ({ms:,.0f} ms)")
    sent += 1
    if sent >= args.n:
        break

print("search 'credit':", call("GET", "/search?" + urllib.parse.urlencode({"q": "credit"}))[1]["count"], "results")
print("stats:", call("GET", "/stats")[1])
