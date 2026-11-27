"""
make_workload.py - A2 Step 4 set-up: fixed ticket lists for the speed test, from rows OUTSIDE the golden set.

Writes (commit all of them before the first speed run):
  a2/warmup_rows.csv     3 fixed warm-up tickets (same 3 before every run)
  a2/s_rows.csv          3 DIFFERENT typical-length tickets for measuring S
  a2/workload_rows.csv   the speed-test workload: typical + long tickets, fixed order (for JMeter's CSV Data Set)
  a2/workload_row_numbers.txt   just the row numbers (supporting file for the submission)

Usage:
  python a2/make_workload.py golden_set/team20_rows_20000_20999.csv golden_set/golden_set_final.csv --n 60
--n should be comfortably more than the tickets in one run (rate x run length, about 30). JMeter
reads the file from the top for every run, so every configuration gets the same tickets in the same order.
Newlines inside narratives are replaced by spaces so each ticket is one CSV line for JMeter.
"""
import argparse
import pandas as pd

p = argparse.ArgumentParser()
p.add_argument("team_rows")
p.add_argument("golden")
p.add_argument("--n", type=int, default=60)
p.add_argument("--seed", type=int, default=20)
a = p.parse_args()

rows = pd.read_csv(a.team_rows)
golden_rows = set(pd.read_csv(a.golden)["row"])
pool = rows[~rows["row"].isin(golden_rows)].copy()
pool["narrative"] = pool["narrative"].str.replace(r"\s+", " ", regex=True).str.strip()
pool["words"] = pool["narrative"].str.split().str.len()
q25, q50, q75, q90 = pool["words"].quantile([.25, .5, .75, .9])

typical = pool[(pool.words >= q25) & (pool.words <= q75)].sample(frac=1, random_state=a.seed)
long_ = pool[pool.words >= q90].sample(frac=1, random_state=a.seed)

warm = typical.iloc[:3]
s_rows = typical.iloc[3:6]
n_long = round(a.n * 0.25)                                   # ~25% long tickets, ~75% typical
work = pd.concat([typical.iloc[6:6 + a.n - n_long], long_.iloc[:n_long]]).sample(frac=1, random_state=a.seed)

for df, name in [(warm, "warmup_rows"), (s_rows, "s_rows"), (work, "workload_rows")]:
    df[["row", "narrative", "words"]].to_csv(f"a2/{name}.csv", index=False)
open("a2/workload_row_numbers.txt", "w").write("\n".join(map(str, work["row"])) + "\n")

print(f"Pool outside golden set: {len(pool)} rows; word quartiles p25={q25:.0f} p50={q50:.0f} p75={q75:.0f} p90={q90:.0f}")
print(f"Warm-up rows: {warm.row.tolist()} | S rows: {s_rows.row.tolist()} (words {s_rows.words.tolist()})")
print(f"Workload: {len(work)} tickets ({len(work) - n_long} typical, {n_long} long >= p90), "
      f"median {work.words.median():.0f} words, max {work.words.max()}")
