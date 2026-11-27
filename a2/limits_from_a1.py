"""
limits_from_a1.py - A2 Step 1: accuracy limits, from the A1 prediction records (no new model run).

The brief allows reusing A1 prediction records for single models "as long as nothing has changed
(same digest, prompt, Ollama version and machine). Score only the test-set rows, and say in the
report that you did this."

What it does:
  1. Reads a2/test_set.csv (92 tickets) and results/accuracy/<model>_raw.csv for each A1 model.
  2. Keeps only the test rows. A ticket with no valid answer (status not 201, e.g. a 502 'invalid
     category') counts as WRONG, and the denominator stays the full 92.
  3. The top model = the model with the highest A1 accuracy on the FULL golden set (the brief:
     "your most accurate Assignment 1 model").
  4. Overall limit = top model's TEST accuracy - 10 points.
     Per-category limit = top model's accuracy in that category on the TEST set - 15 points.
  5. Prints every model against the limits (PASS/FAIL, with counts) and writes:
        a2/limits.json
        results/score_<model>-alone.json   (one per model, for the trade-off chart later)

Usage (from the repo root):
    python a2/limits_from_a1.py
"""
import json
import math
import os

import pandas as pd

MODELS = ["llama3.1_8b", "qwen2.5_7b", "llama3.2_3b", "qwen2.5_3b"]   # file stems in results/accuracy/
OVERALL_DROP, CATEGORY_DROP, SMALL_N = 10.0, 15.0, 10
EPS = 1e-9

test = pd.read_csv("a2/test_set.csv")
golden = pd.read_csv("golden_set/golden_set_final.csv")
test_rows = set(test["row"])


def load(model):
    raw = pd.read_csv(f"results/accuracy/{model}_raw.csv")
    assert raw["row"].is_unique, f"{model}: duplicate rows in raw file"
    # sanity: the A1 raw file must carry the same frozen labels as the golden set
    lab = golden.set_index("row")["final_label"]
    assert (raw.set_index("row")["final_label"] == lab.reindex(raw["row"]).values).all(), f"{model}: labels differ"
    return raw


raws = {m: load(m) for m in MODELS}

# 1) top model by A1 accuracy on the full golden set
full = {m: 100 * ((r["status"] == 201) & (r["predicted"] == r["final_label"])).sum() / len(r) for m, r in raws.items()}
top = max(full, key=full.get)
print("A1 accuracy on the FULL golden set (185):", {m: round(v, 1) for m, v in full.items()})
print(f"Top model = {top}\n")


def score(model):
    raw = raws[model]
    d = test[["row", "final_label"]].merge(raw[["row", "status", "predicted"]], on="row", how="left")
    assert len(d) == len(test), "merge changed the number of test rows"
    d["correct"] = (d["status"] == 201) & (d["predicted"] == d["final_label"])   # missing/invalid = wrong
    cat = d.groupby("final_label")["correct"].agg(right="sum", total="count")
    return d, int(d["correct"].sum()), len(d), cat


top_d, top_k, top_n, top_cat = score(top)
top_pct = 100 * top_k / top_n
cat_top_pct = 100 * top_cat["right"] / top_cat["total"]
limits = {
    "top_model": top, "top_overall_pct": top_pct, "top_right": top_k, "top_n": top_n,
    "overall_limit_pct": top_pct - OVERALL_DROP,
    "top_by_category": {c: {"right": int(r.right), "total": int(r.total), "pct": 100 * r.right / r.total}
                        for c, r in top_cat.iterrows()},
    "category_limit_pct": {c: cat_top_pct[c] - CATEGORY_DROP for c in top_cat.index},
    "source": "A1 prediction records (results/accuracy/*_raw.csv), test rows only (a2/test_set.csv)",
}
json.dump(limits, open("a2/limits.json", "w"), indent=2)

print(f"TOP MODEL {top} on the test set: {top_k}/{top_n} = {top_pct:.1f}%")
print(f"OVERALL LIMIT = {top_pct:.1f}% - {OVERALL_DROP:.0f} points = {top_pct - OVERALL_DROP:.1f}%  "
      f"(i.e. at least {math.ceil(limits['overall_limit_pct'] * top_n / 100 - EPS)} of {top_n} correct)\n")

os.makedirs("results", exist_ok=True)
for model in MODELS:
    d, k, n, cat = score(model)
    overall_ok = 100 * k / n >= limits["overall_limit_pct"] - EPS
    passes = overall_ok
    print(f"=== {model}{'  (TOP)' if model == top else ''}: {k}/{n} = {100 * k / n:.1f}%   "
          f"overall limit {limits['overall_limit_pct']:.1f}% -> {'PASS' if overall_ok else 'FAIL'}")
    print(f"    {'Category':<27}{'right/total':>12}{'acc':>8}{'limit':>8}   result")
    by_cat = {}
    for c, r in cat.iterrows():
        pct = 100 * r.right / r.total
        lim = limits["category_limit_pct"][c]
        ok = pct >= lim - EPS
        passes &= ok
        note = "  (small n: weak test)" if r.total < SMALL_N else ""
        print(f"    {c:<27}{int(r.right):>5}/{int(r.total):<6}{pct:>7.1f}%{lim:>7.1f}%   {'PASS' if ok else 'FAIL'}{note}")
        by_cat[c] = {"right": int(r.right), "total": int(r.total), "pct": round(pct, 2)}
    print(f"    PASSES BOTH LIMITS: {'YES' if passes else 'NO'}\n")
    json.dump({"name": f"{model}-alone", "source": "A1 records, test rows", "right": k, "n": n,
               "overall_pct": round(100 * k / n, 2), "by_category": by_cat, "passes_limits": bool(passes)},
              open(f"results/score_{model}-alone.json", "w"), indent=2)

print("Wrote a2/limits.json and results/score_<model>-alone.json")
print("Reminder for the report: single-model accuracy reuses A1 records (same digest, prompt, Ollama 0.40.0, machine).")
