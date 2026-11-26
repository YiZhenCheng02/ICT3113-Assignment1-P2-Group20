"""
predict_latency.py - A2 Step 3 (prediction record): estimate S and the speed-test latency of each configuration
BEFORE any Assignment 2 benchmark, so the predictions in a2/predictions_A2.md can be reproduced.

Inputs (all committed before any A2 test; no test-set result is used):
  * a2/tuning_set.csv + results/accuracy/<model>_raw.csv : A1 one-at-a-time timings of the 93 TUNING tickets.
    Fit elapsed_s = a + b x words per model (ticket length explains almost all of the time, r ~ 0.97).
  * a2/s_rows.csv       : the 3 tickets S will be measured on -> predicted S = median of their fitted times.
  * a2/workload_rows.csv: the fixed speed-test tickets, in JMeter order.
  * results/tuning_llama3.2_3b_to_llama3.1_8b.csv : escalation fraction of the strict (k=5) and loose (k=6) settings.

Speed-test rules from the brief: one ticket every 2 x S on average (random arrivals), run length S minutes (min 5).

Model (deliberately simple; stated on the predictions):
  * one server, first come first served: Ollama runs one generation at a time per model and the two cascade models
    share the same CPU, so the total work per ticket is what matters;
  * service time per ticket = fitted time for its length + a residual drawn from the tuning-set residuals;
  * cascade: small-model time for every ticket + large-model time for a random fraction f (the tuning escalation);
  * it IGNORES the CPU contention when a small and a large call overlap, so it likely UNDERESTIMATES the cascade.
Response time = waiting time + service time. Queueing is reduced at lower utilisation, not eliminated.

Run from the repo root (deterministic for a given --seed):
    python a2/predict_latency.py
"""
import argparse

import numpy as np
import pandas as pd

p = argparse.ArgumentParser()
p.add_argument("--s-rows", default="a2/s_rows.csv")
p.add_argument("--reps", type=int, default=4000, help="simulated runs per configuration")
p.add_argument("--seed", type=int, default=20)
a = p.parse_args()
rng = np.random.default_rng(a.seed)

tune = pd.read_csv("a2/tuning_set.csv")
tune["words"] = tune["narrative"].str.split().str.len()
work = pd.read_csv("a2/workload_rows.csv")
srows = pd.read_csv(a.s_rows)
k_table = pd.read_csv("results/tuning_llama3.2_3b_to_llama3.1_8b.csv").set_index("k")


def fit(model):
    """Linear fit of A1 elapsed time vs word count, TUNING tickets only."""
    raw = pd.read_csv(f"results/accuracy/{model}_raw.csv")
    d = tune[["row", "words"]].merge(raw[["row", "elapsed_s"]], on="row")
    b, c = np.polyfit(d["words"], d["elapsed_s"], 1)
    resid = (d["elapsed_s"] - (c + b * d["words"])).to_numpy()
    r = np.corrcoef(d["words"], d["elapsed_s"])[0, 1]
    print(f"{model}: elapsed ~= {c:.2f} s + {100 * b:.2f} s per 100 words  (r = {r:.3f}, n = {len(d)} tuning tickets)")
    return c, b, resid


large = fit("llama3.1_8b")
small = fit("llama3.2_3b")

S = float(np.median(large[0] + large[1] * srows["words"]))
gap = 2 * S
run_s = max(300, 60 * S)
print(f"\nS rows {srows['row'].tolist()} ({srows['words'].tolist()} words) -> predicted S = {S:.2f} s")
print(f"Arrival: one ticket every {gap:.1f} s ({60 / gap:.2f}/min, {3600 / gap:.0f}/hour); "
      f"run {run_s:.0f} s = {run_s / 60:.1f} min, ~{run_s / gap:.0f} tickets per run")
print(f"Workload words: median {work['words'].median():.0f}, mean {work['words'].mean():.0f}\n")


def service(model, words):
    c, b, resid = model
    base = c + b * words
    return np.maximum(base + rng.choice(resid, len(words)), 0.4 * base)   # floor keeps times positive


def simulate(f):
    """f = None -> top model alone; otherwise cascade with escalation fraction f."""
    run_p50, pooled, work_s = [], [], []
    for _ in range(a.reps):
        arrivals = []
        t = rng.exponential(gap)
        while t <= run_s:
            arrivals.append(t)
            t += rng.exponential(gap)
        words = work["words"].to_numpy()[: len(arrivals)]
        if f is None:
            svc = service(large, words)
        else:
            svc = service(small, words) + (rng.random(len(words)) < f) * service(large, words)
        free, lat = 0.0, []
        for arr, st in zip(arrivals, svc):
            start = max(arr, free)
            free = start + st
            lat.append(free - arr)                       # response time = waiting + service
        run_p50.append(np.median(lat))
        pooled.extend(lat)
        work_s.extend(svc)
    return (np.mean(run_p50), np.percentile(run_p50, [10, 90]), np.percentile(pooled, 95),
            np.mean(work_s) / gap)


configs = [("top model alone (llama3.1:8b)", None),
           (f"cascade strict (k=5, f={k_table.loc[5, 'escalated_pct']:.1f}%)", k_table.loc[5, "escalated_pct"] / 100),
           (f"cascade loose  (k=6, f={k_table.loc[6, 'escalated_pct']:.1f}%)", k_table.loc[6, "escalated_pct"] / 100)]
print(f"{'configuration':<36}{'p50 (mean of runs)':>20}{'single-run p50, 10-90%':>26}{'pooled p95':>12}{'utilisation':>13}")
for name, f in configs:
    p50, band, p95, util = simulate(f)
    print(f"{name:<36}{p50:>18.1f} s{band[0]:>15.1f} - {band[1]:.1f} s{p95:>10.1f} s{util:>12.0%}")
print(f"\n({a.reps} simulated runs per configuration, seed {a.seed}. Estimates only: no CPU contention modelled.)")
