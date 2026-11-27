"""
pick_s_rows.py - A2 Step 4 set-up: choose the 3 tickets used to measure S, at TYPICAL (median) length.

Why this exists: the brief says to measure S with "three different tickets of typical length", then send
one ticket every 2 x S so the top model is "idle about half the time, so no queue builds". The first S
rows from make_workload.py were 90-101 words, i.e. at the 25th percentile of our pool (the very bottom of
"typical"), while the workload's median is 174 words. Measuring S on such short tickets would set the
arrival rate too high: a pre-benchmark estimate from the A1 timings puts the top model ~81% busy, so a
queue would build and the p50 would depend on run length (the problem the brief warns about).

Rule used here: from the pool of our 1,000 rows minus the golden set, minus every ticket already used
for warm-up or the workload, take the 3 tickets whose word count is closest to the pool median
(ties broken by row number). This changes only a2/s_rows.csv; warm-up and workload rows are unchanged.

Run from the repo root, BEFORE measuring S:
    python a2/pick_s_rows.py golden_set/team20_rows_20000_20999.csv golden_set/golden_set_final.csv
"""
import sys

import pandas as pd

rows = pd.read_csv(sys.argv[1])
golden_rows = set(pd.read_csv(sys.argv[2])["row"])
pool = rows[~rows["row"].isin(golden_rows)].copy()
pool["narrative"] = pool["narrative"].str.replace(r"\s+", " ", regex=True).str.strip()   # same cleaning as make_workload.py
pool["words"] = pool["narrative"].str.split().str.len()
median = pool["words"].median()

used = set()
for f in ("a2/warmup_rows.csv", "a2/workload_rows.csv"):
    used |= set(pd.read_csv(f)["row"])
cand = pool[~pool["row"].isin(used)].assign(dist=lambda d: (d["words"] - median).abs())
s_rows = cand.sort_values(["dist", "row"]).head(3)

s_rows[["row", "narrative", "words"]].to_csv("a2/s_rows.csv", index=False)
print(f"Pool: {len(pool)} tickets, median {median:.0f} words "
      f"(p25 {pool['words'].quantile(.25):.0f}, p75 {pool['words'].quantile(.75):.0f})")
print(f"S rows: {s_rows['row'].tolist()} with {s_rows['words'].tolist()} words -> wrote a2/s_rows.csv")
