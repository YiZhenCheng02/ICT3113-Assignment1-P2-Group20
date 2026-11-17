"""
tune_cascade.py - A2 Step 2: choose the cascade's two settings from the TUNING set only.

Rule being tuned (category-based, example method 1 in the brief):
    the SMALL model classifies the ticket first. If its PREDICTED category is in the accept list,
    return it; otherwise ESCALATE to the LARGE model, whose answer is final.
(The true category is unknown when a ticket arrives, so the rule can only use the predicted one.)

Data: the A1 prediction records (results/accuracy/<model>_raw.csv), restricted to the 93 tuning
tickets in a2/tuning_set.csv. No test ticket is used here. This reuse is valid only because A1 and A2
run on the same environment (same digest, prompt, Ollama version, machine).

Counting rules: a ticket with no valid answer (status != 201) is WRONG for a single model, and when it
is the small model's answer it is never accepted (it escalates).

Prints, for each small model:
  1. When the small model predicts category X, how often is it right?  (reliability of each category)
  2. Simulation: accept the k most reliable categories, k = 0..7: escalation, cascade accuracy, wrong
     answers that slip through, and an ESTIMATED mean latency = small mean + escalation x large mean.
     (Latencies come from the A1 accuracy runs, one ticket at a time: a rough guide only.)
  3. Method 4 check: is the small model's error rate higher on long tickets? (short/medium/long thirds)

Usage (from the repo root):
    python a2/tune_cascade.py                                   # both 3B models vs llama3.1_8b
    python a2/tune_cascade.py --small qwen2.5_3b --large llama3.1_8b
Writes results/tuning_<small>_to_<large>.csv (the k table).
"""
import argparse
import os

import pandas as pd

p = argparse.ArgumentParser()
p.add_argument("--small", nargs="+", default=["qwen2.5_3b", "llama3.2_3b"], help="small model file stem(s)")
p.add_argument("--large", default="llama3.1_8b", help="large model file stem")
p.add_argument("--outdir", default="results")
a = p.parse_args()
os.makedirs(a.outdir, exist_ok=True)

tune = pd.read_csv("a2/tuning_set.csv")
tune["words"] = tune["narrative"].str.split().str.len()
n = len(tune)


def load(model):
    raw = pd.read_csv(f"results/accuracy/{model}_raw.csv")
    d = tune[["row", "final_label", "words"]].merge(raw[["row", "status", "predicted", "elapsed_s"]], on="row", how="left")
    assert len(d) == n, f"{model}: merge changed the number of tuning rows"
    d["pred"] = d["predicted"].where(d["status"] == 201)       # NaN = invalid / no answer
    return d


L = load(a.large)
l_right = int((L["pred"] == L["final_label"]).sum())
l_ms = L["elapsed_s"].mean()
print(f"Tuning tickets: {n}")
print(f"LARGE model {a.large}: {l_right}/{n} = {100 * l_right / n:.1f}% correct, mean {l_ms:.2f} s per ticket\n")

for sm in a.small:
    S = load(sm)
    df = pd.DataFrame({"true": S["final_label"], "small": S["pred"], "large": L["pred"],
                       "s_s": S["elapsed_s"], "l_s": L["elapsed_s"], "words": S["words"]})
    s_right = int((df["small"] == df["true"]).sum())
    s_ms = df["s_s"].mean()
    print("=" * 100)
    print(f"SMALL model {sm}: {s_right}/{n} = {100 * s_right / n:.1f}% correct alone, mean {s_ms:.2f} s per ticket")
    print(f"Break-even: the cascade only beats {a.large} alone if it escalates fewer than "
          f"{100 * (l_ms - s_ms) / l_ms:.0f}% of tickets  (({l_ms:.2f} - {s_ms:.2f}) / {l_ms:.2f})\n")

    # 1. reliability of each PREDICTED category
    df["small_right"] = df["small"] == df["true"]
    prec = df.dropna(subset=["small"]).groupby("small")["small_right"].agg(predicted="count", right="sum")
    prec["precision_%"] = 100 * prec["right"] / prec["predicted"]
    prec = prec.sort_values(["precision_%", "predicted"], ascending=[False, False])
    print("1) When the SMALL model predicts this category, how often is it right? (tuning set)")
    print(prec.astype({"predicted": int, "right": int}).round(1).to_string(), "\n")

    # 2. simulate accepting the k most reliable categories
    print("2) Simulation: accept the k most reliable categories (the rest escalate)")
    print(f"{'k':>2}  {'accept list':<78}{'escalated':>12}{'cascade acc':>15}{'slipped':>9}{'est. mean':>11}")
    order = prec.index.tolist()
    rows = []
    for k in range(len(order) + 1):
        accept = order[:k]
        acc_mask = df["small"].isin(accept)
        final = df["small"].where(acc_mask, df["large"])
        right = int((final == df["true"]).sum())
        slipped = int((acc_mask & (df["small"] != df["true"])).sum())   # wrong small answers we accepted
        esc_n = int((~acc_mask).sum())
        est = s_ms + (esc_n / n) * l_ms
        rows.append({"k": k, "accept": "; ".join(accept), "escalated": esc_n, "escalated_pct": round(100 * esc_n / n, 1),
                     "cascade_right": right, "cascade_acc_pct": round(100 * right / n, 1),
                     "slipped": slipped, "est_mean_s": round(est, 2)})
        print(f"{k:>2}  {', '.join(accept) or '(none: escalate everything)':<78}"
              f"{esc_n:>5}/{n} {100 * esc_n / n:>3.0f}%{right:>6}/{n} {100 * right / n:>4.1f}%{slipped:>9}{est:>9.2f} s")
    out = os.path.join(a.outdir, f"tuning_{sm}_to_{a.large}.csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\n   Large model alone: {l_right}/{n} = {100 * l_right / n:.1f}%, mean {l_ms:.2f} s. "
          f"A row only helps if 'est. mean' is clearly below {l_ms:.2f} s.  (saved {out})\n")

    # 3. method 4: ticket length vs small-model errors
    df["length"] = pd.qcut(df["words"].rank(method="first"), 3, labels=["short", "medium", "long"])
    ln = df.groupby("length", observed=True).agg(tickets=("true", "count"), median_words=("words", "median"),
                                                  small_wrong=("small_right", lambda s: int((~s).sum())))
    ln["error_%"] = (100 * ln["small_wrong"] / ln["tickets"]).round(1)
    print("3) Method 4 check: small-model errors by ticket length (thirds of the tuning set)")
    print(ln.to_string(), "\n")
