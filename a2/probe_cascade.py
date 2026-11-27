"""
probe_cascade.py — A2 stability gate for the cascade pair on the fixed 7.4 GB limit.

Sends N escalation-prone tickets (tuning set rows whose saved A1 small-model prediction is NOT
in the service's active accept list, so the service must escalate them) through POST /tickets,
then reads the service log to verify each one was genuinely escalated to the large model and
answered with HTTP 201.

Exit code 0 = all probes escalated + 201 (cascade judged stable enough to benchmark).
Exit code 1 = at least one probe failed (OOM-kill territory -> do NOT benchmark the cascade).

Usage:
    python a2/probe_cascade.py --n 10 --tag gate
    python a2/probe_cascade.py --n 3 --tag warmup-check
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

TUNING_CSV = "a2/tuning_set.csv"
SMALL_RAW = "results/accuracy/{small}_raw.csv"
LOG_PATH = "logs/requests.jsonl"


def parse_args():
    p = argparse.ArgumentParser(description="Cascade stability gate (escalation probes).")
    p.add_argument("--n", type=int, default=10, help="number of probes (default 10)")
    p.add_argument("--tag", default="probe", help="ref prefix for the probes")
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--small", default="qwen2.5_3b", help="small-model raw CSV stem for escalation picks")
    return p.parse_args()


def active_accept_list(url):
    with urllib.request.urlopen(url + "/health", timeout=30) as r:
        h = json.loads(r.read())
    return h["accept_categories"], h.get("cascade_setting"), h.get("small_model"), h.get("large_model")


def pick_escalators(n, accept, small):
    """Tuning rows whose saved small-model prediction is outside the accept list."""
    with open(TUNING_CSV, encoding="utf-8") as f:
        tuning = {r["row"]: r for r in csv.DictReader(f)}
    with open(SMALL_RAW.format(small=small), encoding="utf-8") as f:
        raw = csv.DictReader(f)
        picks = [{**tuning[r["row"]], "small_prediction": r["predicted"].strip(),
                  "small_elapsed_s": r["elapsed_s"]}
                 for r in raw if r["row"] in tuning and r["status"] == "201"
                 and r["predicted"].strip() not in accept]
    picks.sort(key=lambda r: float(r["small_elapsed_s"]), reverse=True)   # longest first: hardest cases
    return picks[:n]


def send(url, narrative, ref):
    req = urllib.request.Request(url + "/tickets", data=narrative.encode("utf-8"), method="POST",
                                 headers={"Content-Type": "text/plain; charset=utf-8",
                                          "X-Ticket-Ref": ref})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        return e.code, time.perf_counter() - t0


def log_facts(ref):
    """Newest service-log line for this ref: (escalated, final_model, status, category)."""
    facts = None
    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("path") == "/tickets" and e.get("method") == "POST" and e.get("ref") == ref:
                facts = e
    if not facts:
        return None
    return (bool(facts.get("escalated")), facts.get("final_model"), facts.get("status"),
            facts.get("category"))


def main():
    args = parse_args()
    accept, setting, small_srv, large_srv = active_accept_list(args.url)
    print(f"Service: cascade_setting={setting} small={small_srv} large={large_srv}")
    print(f"Accept list ({len(accept)}): {accept}\n")
    if not accept:
        print("ERROR: service is not in cascade mode (empty accept list).")
        sys.exit(1)

    picks = pick_escalators(args.n, set(accept), args.small)
    if len(picks) < args.n:
        print(f"ERROR: only {len(picks)} escalator rows available (wanted {args.n}).")
        sys.exit(1)

    os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
    results = []
    for i, r in enumerate(picks, 1):
        ref = f"{args.tag}-{r['row']}"
        status, secs = send(args.url, tuning_narrative(r), ref)
        facts = log_facts(ref)
        esc = facts[0] if facts else None
        final = facts[1] if facts else None
        ok = status == 201 and esc is True and final == large_srv
        results.append(ok)
        print(f"[{i:>2}/{args.n}] row={r['row']} -> HTTP {status} in {secs:5.1f}s | "
              f"escalated={esc} final={final} | {'OK' if ok else 'FAIL'}")

    n_ok = sum(results)
    print(f"\nGATE RESULT: {n_ok}/{len(results)} probes escalated and answered 201 "
          f"-> {'STABLE - benchmark the cascade' if n_ok == len(results) else 'UNSTABLE - do not benchmark'}")
    sys.exit(0 if n_ok == len(results) else 1)


def tuning_narrative(row):
    return row["narrative"]


if __name__ == "__main__":
    main()
