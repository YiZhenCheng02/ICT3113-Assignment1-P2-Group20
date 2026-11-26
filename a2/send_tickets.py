"""
send_tickets.py - send tickets to the triage service ONE AT A TIME (not a load test).

Used for:
  * accuracy runs   (A2 Step 4): every test-set (or tuning-set) ticket through POST /tickets
  * warm-up         (each speed run): the 3 fixed warm-up tickets
  * measuring S     (Step 4 set-up): 3 different typical tickets to the top model, take the middle time

Where this fits in Assignment 2: Step 4 accuracy test ("Run every test-set ticket through
POST /tickets, once per configuration"), the fixed warm-up before every speed run, and the S
measurement in the speed-test set-up. It is NOT the load test: JMeter does that (open loop).
--limit N sends only the first N tickets (used for the Step 2 memory check).

Each ticket is sent with header X-Ticket-Ref = its golden_id (or row), so the service log can be matched
back to the golden label. A copy of every answer is also written to a CSV as a second record.

Usage:
    python a2/send_tickets.py a2/test_set.csv     --out results/acc_cascade-strict_test.csv
    python a2/send_tickets.py a2/warmup_rows.csv  --out results/warmup.csv
    python a2/send_tickets.py a2/s_rows.csv       --out results/S_measurement.csv --median
Options:
    --url http://localhost:8000   (default)
The input CSV needs a 'narrative' column and a 'golden_id' or 'row' column.
"""
import argparse
import csv
import json
import statistics
import time
import urllib.request

p = argparse.ArgumentParser()
p.add_argument("csv_in")
p.add_argument("--out", required=True)
p.add_argument("--url", default="http://localhost:8000")
p.add_argument("--limit", type=int, help="only send the first N tickets (e.g. for the memory check)")
p.add_argument("--median", action="store_true", help="print the middle of the elapsed times (for S)")
a = p.parse_args()

rows = list(csv.DictReader(open(a.csv_in, encoding="utf-8")))
if a.limit:
    rows = rows[:a.limit]
results = []
for i, r in enumerate(rows, 1):
    ref = r.get("golden_id") or r.get("row")
    req = urllib.request.Request(a.url + "/tickets", data=r["narrative"].encode("utf-8"), method="POST",
                                 headers={"Content-Type": "text/plain; charset=utf-8", "X-Ticket-Ref": str(ref)})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            body = json.loads(resp.read())
            status, cat = resp.status, body.get("category")
    except Exception as e:                       # keep going, but record the failure
        status, cat = "ERROR", f"{type(e).__name__}: {e}"
    ms = (time.perf_counter() - t0) * 1000
    results.append({"ref": ref, "row": r.get("row"), "category": cat, "status": status, "elapsed_ms": round(ms)})
    print(f"[{i}/{len(rows)}] {ref}: {cat}  ({ms / 1000:.1f} s)")

with open(a.out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=results[0].keys())
    w.writeheader()
    w.writerows(results)
print(f"\nSaved {a.out}")

if a.median:
    times = [x["elapsed_ms"] / 1000 for x in results]
    S = statistics.median(times)
    gap = 2 * S
    run_min = max(5, round(S))
    timeout_s = max(300, round(10 * S))
    print(f"\nTimes (s): {[round(t, 1) for t in times]}  ->  S = middle = {S:.1f} s")
    print(f"Arrival rate: 1 ticket every {gap:.1f} s = {60 / gap:.2f} tickets/min")
    print(f"Run length: {run_min} min (S minutes, min 5)  -> ~{run_min * 60 / gap:.0f} tickets per run")
    print(f"JMeter response timeout: {timeout_s} s (10 x S, min 300 s); "
          f"schedule pause: at least {-(-(timeout_s + 60) // 60)} min (timeout + at least 1 min)")
