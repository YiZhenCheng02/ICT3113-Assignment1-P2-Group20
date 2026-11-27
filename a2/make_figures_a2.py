#!/usr/bin/env python3
"""
make_figures_a2.py - slide-ready A2 figures (Assignment 2 measured results).

Run from the repo root:   python3 a2/make_figures_a2.py
Output:                   results/figures/fig_tradeoff_a2.png, fig_pred_vs_outcome_a2.png
Inputs (read-only):       results/a2/speed_summary.csv, results/score_*.json, a2/limits.json

Figure 1 (accuracy vs latency): one point per configuration - the four single models and the two
cascade settings - measured p50 latency (median of the 3 runs) against test-set accuracy, with the
brief's overall accuracy limit. Filled circle = passes every limit; diamond = fails at least one
per-category limit.

Figure 2 (prediction vs outcome): the frozen Step-3 predictions (a2/predictions_A2.md, made for the
originally-planned llama3.2:3b -> llama3.1:8b pair) against what was measured (qwen2.5:3b ->
qwen2.5:7b, the only pair that passed the memory check). The prediction model explicitly ignored
CPU/memory contention between the two resident models - which is what the memory check exposed.
"""
import csv
import json
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SPEED_CSV = "results/a2/speed_summary.csv"
LIMITS = "a2/limits.json"
OUT = "results/figures"

COLOR = {"llama3.1:8b": "#B5420E", "qwen2.5:7b": "#1F4E79",
         "qwen2.5:3b": "#4C9BE8", "llama3.2:3b": "#F28E2B"}
CASCADE_COLOR = "#3E8E5A"
GOOD, HEAD = "#d9f2d9", "#1f4e79"

# Frozen Step-3 predictions (a2/predictions_A2.md, llama3.2:3b -> llama3.1:8b pair):
# top alone ~10.5 s p50; cascade strict (k=5) ~9.2 s; cascade loose (k=6) ~5.9 s.
PREDICTED = {"Top model alone": 10.5, "Cascade strict": 9.2, "Cascade loose": 5.9}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def p50_by_config():
    """Median p50_ms across the 3 runs per configuration."""
    runs = {}
    with open(SPEED_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            cfg = r["run"].rsplit("_run", 1)[0]
            runs.setdefault(cfg, []).append(float(r["p50_ms"]))
    return {c: statistics.median(v) / 1000 for c, v in runs.items()}


def fig_tradeoff():
    limits = load_json(LIMITS)
    limit = limits["overall_limit_pct"]
    p50 = p50_by_config()

    single = {"llama3.1:8b": "single_llama3_1_8b", "qwen2.5:7b": "single_qwen2_5_7b",
              "qwen2.5:3b": "single_qwen2_5_3b", "llama3.2:3b": "single_llama3_2_3b"}
    cascade = {"Cascade strict (k=4)": "cascade_s1", "Cascade loose (k=5)": "cascade_s2"}

    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    ax.axhspan(limit, 100, color=GOOD, alpha=0.55, zorder=0)
    ax.axhline(limit, color=HEAD, lw=1.6, ls="--", zorder=1)
    ax.text(2.35, limit + 0.35, f"overall accuracy limit {limit:.1f}%",
            color=HEAD, fontsize=9, va="bottom")

    def point(name, cfg, acc, color, passes_cats):
        x, y = p50[cfg], acc
        ax.scatter(x, y, s=130, zorder=3, color=color,
                   marker="o" if passes_cats else "D",
                   edgecolor="black" if passes_cats else "#B00020",
                   linewidth=0.8 if passes_cats else 1.6)

    for model, cfg in single.items():
        s = load_json(f"results/score_{model.replace(':', '_')}-alone.json")
        acc = s["overall_pct"]
        cats_ok = s["passes_limits"]
        point(model, cfg, acc, COLOR[model], cats_ok)
        if model == "llama3.1:8b":       # crowded top-right: label to the LEFT
            ax.annotate(f"{model}\n{acc:.1f}%, p50 {p50[cfg]:.1f} s", (p50[cfg], acc),
                        textcoords="offset points", xytext=(-10, 2), fontsize=8.5, ha="right")
        else:
            ax.annotate(f"{model}\n{acc:.1f}%, p50 {p50[cfg]:.1f} s", (p50[cfg], acc),
                        textcoords="offset points", xytext=(9, -6), fontsize=8.5)

    for name, cfg in cascade.items():
        letter = cfg[-1]
        s = load_json(f"results/score_acc_cascade-s{letter}_test.json")
        acc = s["overall_pct"]
        fails = [c for c, v in s["category_pass"].items() if not v["pass"]]
        point(name, cfg, acc, CASCADE_COLOR, not fails)
        ax.annotate(f"{name}\n{acc:.1f}%, p50 {p50[cfg]:.1f} s", (p50[cfg], acc),
                    textcoords="offset points", xytext=(10, -2), fontsize=8.5,
                    color=CASCADE_COLOR, ha="left")

    ax.text(2.25, 93.6, "diamond = fails a per-category floor:\n"
            "Credit card & Money transfer - by 1 ticket each\n"
            "(cascade settings and qwen2.5:7b; llama3.1:8b passes all)",
            fontsize=8, color="dimgray", va="top")

    ax.set_xlabel("Measured p50 latency under load (s) - median of 3 JMeter runs, 29 tickets each")
    ax.set_ylabel("Test-set accuracy (%)")
    ax.set_title("A2: accuracy vs measured latency", fontsize=12)
    ax.set_xlim(2.0, 9.5)
    ax.set_ylim(70, 96)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig_tradeoff_a2.png", dpi=160)
    print(f"saved {OUT}/fig_tradeoff_a2.png")


def fig_pred_vs_outcome():
    p50 = p50_by_config()
    measured = {"Top model alone": p50["single_llama3_1_8b"],
                "Cascade strict": p50["cascade_s1"], "Cascade loose": p50["cascade_s2"]}

    labels = list(PREDICTED.keys())
    x = range(len(labels))
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    ax.bar([i - 0.19 for i in x], [PREDICTED[l] for l in labels], width=0.36,
           color="#c9c9c9", edgecolor="black", linewidth=0.6,
           label="Predicted (frozen record: llama3.2:3b \u2192 llama3.1:8b pair)")
    ax.bar([i + 0.19 for i in x], [measured[l] for l in labels], width=0.36,
           color=CASCADE_COLOR, edgecolor="black", linewidth=0.6,
           label="Measured (qwen2.5:3b \u2192 qwen2.5:7b pair, under load)")
    for i, l in enumerate(labels):
        ax.text(i - 0.19, PREDICTED[l] + 0.12, f"{PREDICTED[l]:.1f}", ha="center", fontsize=9)
        ax.text(i + 0.19, measured[l] + 0.12, f"{measured[l]:.1f}", ha="center", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("p50 latency (s)")
    ax.set_title("Prediction vs outcome: model pair changed and contention was ignored")
    ax.legend(fontsize=8.5)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig_pred_vs_outcome_a2.png", dpi=160)
    print(f"saved {OUT}/fig_pred_vs_outcome_a2.png")


if __name__ == "__main__":
    import os
    os.makedirs(OUT, exist_ok=True)
    fig_tradeoff()
    fig_pred_vs_outcome()
