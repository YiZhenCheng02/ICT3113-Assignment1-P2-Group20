"""
summarize_jtl.py — summarise A2 JMeter .jtl results (one line per run).

Reads results/a2/jtl/*.jtl (JMeter CSV format: timeStamp,label,responseCode,success,elapsed,...)
and prints, per run: samples, error count by HTTP code, and latency percentiles (p50/p95).
Tags encode the configuration: single_<model>_run<k> / cascade_s<1|2>_run<k>.

Usage:
    python a2/summarize_jtl.py
    python a2/summarize_jtl.py --jtl-dir results/a2/jtl --out results/a2/speed_summary.csv
"""

import argparse
import csv
import glob
import json
import os
import statistics


def parse_args():
    p = argparse.ArgumentParser(description="Summarise A2 .jtl files.")
    p.add_argument("--jtl-dir", default="results/a2/jtl")
    p.add_argument("--out", default="results/a2/speed_summary.csv")
    return p.parse_args()


def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f, c = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def summarise(path):
    elapsed, codes = [], {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                elapsed.append(int(row["elapsed"]))
                code = str(row.get("responseCode", ""))
            except (KeyError, ValueError):
                continue
            codes[code] = codes.get(code, 0) + 1
    elapsed.sort()
    n = len(elapsed)
    ok = codes.get("201", 0)
    return {
        "samples": n,
        "http_201": ok,
        "errors": n - ok,
        "codes": json.dumps(codes, sort_keys=True),
        "p50_ms": round(pct(elapsed, 50), 0) if n else None,
        "p95_ms": round(pct(elapsed, 95), 0) if n else None,
        "min_ms": elapsed[0] if n else None,
        "max_ms": elapsed[-1] if n else None,
        "mean_ms": round(statistics.mean(elapsed), 0) if n else None,
    }


def main():
    args = parse_args()
    files = sorted(glob.glob(os.path.join(args.jtl_dir, "*.jtl")))
    if not files:
        print(f"No .jtl files in {args.jtl_dir}")
        return

    rows = []
    for path in files:
        tag = os.path.splitext(os.path.basename(path))[0]
        s = summarise(path)
        s = {"run": tag, **s}
        rows.append(s)

    width = max(len(r["run"]) for r in rows) + 1
    print(f"{'run':<{width}} {'n':>4} {'201':>4} {'err':>4}  {'p50 s':>6} {'p95 s':>6} {'mean s':>7} {'max s':>7}  codes")
    for r in rows:
        f = lambda v: f"{v / 1000:.2f}" if v is not None else "-"
        print(f"{r['run']:<{width}} {r['samples']:>4} {r['http_201']:>4} {r['errors']:>4}  "
              f"{f(r['p50_ms']):>6} {f(r['p95_ms']):>6} {f(r['mean_ms']):>7} {f(r['max_ms']):>7}  {r['codes']}")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
