#!/usr/bin/env python3
"""
make_figures.py - slide-ready PNG tables and charts from the raw test results.

Run from the repo root:   python3 loadtest/make_figures.py
Output:                   results/figures/*.png
Inputs (read-only):       results/jtl/*.jtl, logs/requests.jsonl, results/accuracy/*_raw.csv
Same definitions as loadtest/analyse.py: nearest-rank percentiles, 6-minute cut,
R3/R4 throughput = POST 201s completed in the final 3 minutes x 20.
"""
import collections
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analyse import (read_jtl, load_service_log, nearest_rank,
                     MODELS, RUNS, JTL_DIR, ACC_DIR, CATEGORIES, CUT_MS)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "figures")
NAME = {"qwen3b": "qwen2.5:3b", "llama3b": "llama3.2:3b",
        "qwen7b": "qwen2.5:7b", "llama8b": "llama3.1:8b"}
COLOR = {"qwen3b": "#4C9BE8", "llama3b": "#F28E2B", "qwen7b": "#1F4E79", "llama8b": "#B5420E"}
SHORT = {"Credit reporting": "Credit\nreporting", "Debt collection": "Debt\ncollection",
         "Mortgage": "Mortgage", "Credit card": "Credit\ncard",
         "Bank account or service": "Bank\naccount", "Consumer loan": "Consumer\nloan",
         "Money transfer or service": "Money\ntransfer", "INVALID/FAILED": "Invalid/\nfailed"}
GOOD, BAD, HEAD, PLAIN = "#d9f2d9", "#f8d0d0", "#1f4e79", "white"

# Committed predictions (predictions.md)
PRED_LAT = {"qwen3b": (2.5, 1.9, 3.1), "llama3b": (2.5, 1.9, 3.1),
            "qwen7b": (4.5, 3.4, 5.6), "llama8b": (5.0, 3.8, 6.3)}
PRED_ACC = {"qwen3b": (70, 68, 72), "llama3b": (65, 63, 67),
            "qwen7b": (77, 75, 79), "llama8b": (75, 73, 77)}
PRED_R3 = {"qwen3b": 1500, "llama3b": 1440, "qwen7b": 800, "llama8b": 750}


def mean(v):
    return sum(v) / len(v)


def mmm(v, nd=0):
    return f"{mean(v):,.{nd}f} ({min(v):,.{nd}f}–{max(v):,.{nd}f})"


def save_table(fname, header, rows, colors=None, widths=None, fontsize=10):
    ncols = len(header)
    widths = widths or [1.5] * ncols
    height = 0.42 * len(rows) + 0.75
    fig = plt.figure(figsize=(sum(widths), height))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    tbl = ax.table(cellText=rows, colLabels=header, cellLoc="center",
                   cellColours=colors or [[PLAIN] * ncols for _ in rows],
                   colWidths=[w / sum(widths) for w in widths], bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(fontsize)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#999999")
        if r == 0:
            cell.set_facecolor(HEAD)
            cell.set_text_props(color="white", weight="bold")
    fig.savefig(os.path.join(OUT, fname), dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------- loaders ----------------
def load_r1r2():
    out = {}
    for m in MODELS:
        d = {"POST": [], "GET": [], "run_p50": [], "total": 0, "bad": 0}
        for k in RUNS:
            smp = read_jtl(os.path.join(JTL_DIR, f"r1r2_{m['slug']}_run{k}.jtl"))
            post = sorted(x["elapsed"] / 1000 for x in smp
                          if x["label"] == "POST /tickets" and x["code"] == "201")
            get = sorted(x["elapsed"] / 1000 for x in smp
                         if x["label"] == "GET /search" and x["code"] == "200")
            d["POST"] += post
            d["GET"] += get
            d["run_p50"].append(nearest_rank(post, 0.5))
            d["total"] += len(smp)
            d["bad"] += sum(1 for x in smp if x["code"] not in ("200", "201"))
        d["POST"].sort()
        d["GET"].sort()
        out[m["short"]] = d
    return out


def load_sat(kind):
    out = {}
    for m in MODELS:
        d = collections.defaultdict(list)
        for k in RUNS:
            smp = read_jtl(os.path.join(JTL_DIR, f"{kind}_{m['slug']}_run{k}.jtl"))
            t0 = min(x["timeStamp"] for x in smp)
            posts = [x for x in smp if x["label"] == "POST /tickets"]
            ok = sorted(x["elapsed"] / 1000 for x in posts if x["code"] == "201")
            win = sum(1 for x in posts if x["code"] == "201"
                      and t0 + 180000 <= x["timeStamp"] + x["elapsed"] <= t0 + CUT_MS)
            unf = sum(1 for x in posts if x["code"].startswith("Non HTTP"))
            err = sum(1 for x in posts if x["code"] != "201" and not x["code"].startswith("Non HTTP"))
            d["thr"].append(win * 20)
            d["p50"].append(nearest_rank(ok, 0.50))
            d["p95"].append(nearest_rank(ok, 0.95))
            d["p99"].append(nearest_rank(ok, 0.99))
            d["unf"].append(unf)
            d["sent"].append(len(posts))
            d["err"].append(err / (len(posts) - unf) if len(posts) > unf else 0.0)
            d["codes"] += [x["code"] for x in posts]
            d["get"] += [x["elapsed"] / 1000 for x in smp
                         if x["label"] == "GET /search" and x["code"] == "200"]
            d["pts"] += [((x["timeStamp"] - t0) / 1000, x["elapsed"] / 1000)
                         for x in posts if x["code"] == "201"]
        out[m["short"]] = d
    return out


def load_acc():
    out = {}
    for m in MODELS:
        with open(os.path.join(ACC_DIR, m["acc"] + "_raw.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        mat = {g: collections.Counter() for g in CATEGORIES}
        for r in rows:
            p = r["predicted"] if (r["status"] == "201" and r["predicted"] in CATEGORIES) else "INVALID/FAILED"
            mat[r["final_label"]][p] += 1
        gold = {c: sum(mat[c].values()) for c in CATEGORIES}
        pred = {c: sum(mat[g][c] for g in CATEGORIES) for c in CATEGORIES}
        out[m["short"]] = {
            "mat": mat, "gold": gold,
            "acc": sum(mat[c][c] for c in CATEGORIES) / len(rows),
            "rec": {c: mat[c][c] / gold[c] if gold[c] else 0.0 for c in CATEGORIES},
            "prec": {c: mat[c][c] / pred[c] if pred[c] else 0.0 for c in CATEGORIES},
            "inv": sum(mat[g]["INVALID/FAILED"] for g in CATEGORIES),
        }
    return out


# ---------------- figures ----------------
def fig_r1r2(r):
    header = ["Model", "POST p50 / p95 / p99 (s)\npooled 3 runs", "POST p50 per run\n(min–max, s)",
              "GET p50 / p95 / p99 (s)\npooled 3 runs", "n\nPOST / GET", "Error\nrate", "R1", "R2"]
    rows, cols = [], []
    for m in MODELS:
        s, d = m["short"], r[m["short"]]
        P = [nearest_rank(d["POST"], p) for p in (0.5, 0.95, 0.99)]
        G = [nearest_rank(d["GET"], p) for p in (0.5, 0.95, 0.99)]
        r1 = P[0] <= 10 and P[1] <= 30 and P[2] <= 60
        r2 = G[0] <= 1 and G[1] <= 5 and G[2] <= 10
        rows.append([NAME[s], " / ".join(f"{x:.1f}" for x in P),
                     f"{min(d['run_p50']):.2f}–{max(d['run_p50']):.2f}",
                     " / ".join(f"{x:.2f}" for x in G),
                     f"{len(d['POST'])} / {len(d['GET'])}",
                     f"{100 * d['bad'] / d['total']:.0f}%",
                     "PASS" if r1 else "FAIL", "PASS" if r2 else "FAIL"])
        cols.append([PLAIN] * 6 + [GOOD if r1 else BAD, GOOD if r2 else BAD])
    save_table("fig_r1r2_load.png", header, rows, cols, [1.4, 2.1, 1.7, 2.1, 1.2, 0.8, 0.7, 0.7])


def fig_r3r4(r3, r4):
    header = ["Model", "R3 throughput /h\nmean (min–max)", "R4 long tickets /h\nmean (min–max)",
              "R3 POST p50 / p95 / p99 (s)\nmean of 3 runs", "Unfinished\nper run", "Error rate\nR3 / R4",
              "Headroom\nR3 ÷ peak 19", "R3", "R4"]
    rows, cols = [], []
    for m in MODELS:
        s = m["short"]
        a, b = r3[s], r4[s]
        p3 = mean(a["thr"]) >= 32
        p4 = mean(b["thr"]) >= 19
        rows.append([NAME[s], mmm(a["thr"]), mmm(b["thr"]),
                     f"{mean(a['p50']):.0f} / {mean(a['p95']):.0f} / {mean(a['p99']):.0f}",
                     f"{mean(a['unf']):.0f} of {mean(a['sent']):.0f}",
                     f"{100 * max(a['err']):.0f}% / {100 * max(b['err']):.0f}%",
                     f"{mean(a['thr']) / 19:.0f}×",
                     "PASS" if p3 else "FAIL", "PASS" if p4 else "FAIL"])
        cols.append([PLAIN] * 7 + [GOOD if p3 else BAD, GOOD if p4 else BAD])
    save_table("fig_r3r4_stress.png", header, rows, cols, [1.3, 1.9, 1.9, 2.2, 1.2, 1.2, 1.3, 0.7, 0.7])


def fig_latency(r3):
    fig, ax = plt.subplots(figsize=(7, 4))
    latest = 0.0
    for m in MODELS:
        s = m["short"]
        xs, ys = zip(*r3[s]["pts"])
        latest = max(latest, max(xs))
        ax.scatter(xs, ys, s=8, alpha=0.6, color=COLOR[s], label=NAME[s])
    ax.axvspan(latest, 360, color="grey", alpha=0.15)
    ax.text(latest + 5, ax.get_ylim()[1] * 0.85,
            f"Arrivals after {latest:.0f} s\nnever completed\n(still queued at cut)", fontsize=8)
    ax.set_xlim(0, 360)
    ax.set_xlabel("Request arrival time (s since start of run)")
    ax.set_ylabel("POST /tickets latency (s)")
    ax.set_title("Stress test (R3, 2,300 tickets/h): latency grows without bound",
                 fontsize=11, weight="bold")
    ax.grid(alpha=0.3)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_r3_latency_growth.png"), dpi=200)
    plt.close(fig)


def r5_fails(a):
    n = int(a["acc"] < 0.75) + int(a["inv"] > 1)
    n += sum(1 for c in CATEGORIES if a["rec"][c] < 0.70)
    n += sum(1 for c in CATEGORIES if a["prec"][c] < 0.70)
    return n


def fig_accuracy(acc):
    header = ["Category (golden n)\nrecall / precision %"] + [NAME[m["short"]] for m in MODELS]
    rows, cols = [], []
    for c in CATEGORIES:
        row, col = [f"{c} ({acc['qwen3b']['gold'][c]})"], [PLAIN]
        for m in MODELS:
            a = acc[m["short"]]
            row.append(f"{a['rec'][c] * 100:.0f} / {a['prec'][c] * 100:.0f}")
            col.append(BAD if (a["rec"][c] < 0.70 or a["prec"][c] < 0.70) else PLAIN)
        rows.append(row)
        cols.append(col)
    rows.append(["Overall accuracy (target ≥ 75%)"] + [f"{acc[m['short']]['acc'] * 100:.1f}%" for m in MODELS])
    cols.append([PLAIN] + [GOOD if acc[m["short"]]["acc"] >= 0.75 else BAD for m in MODELS])
    rows.append(["Invalid outputs (target ≤ 1)"] + [str(acc[m["short"]]["inv"]) for m in MODELS])
    cols.append([PLAIN] + [GOOD if acc[m["short"]]["inv"] <= 1 else BAD for m in MODELS])
    r5 = []
    for m in MODELS:
        n = r5_fails(acc[m["short"]])
        r5.append("PASS" if n == 0 else f"FAIL ({n} condition{'s' if n > 1 else ''})")
    rows.append(["R5 result"] + r5)
    cols.append([PLAIN] + [GOOD if x == "PASS" else BAD for x in r5])
    save_table("fig_accuracy_table.png", header, rows, cols, [2.9, 1.6, 1.6, 1.6, 1.6])


def draw_cm(ax, a, title):
    cols = CATEGORIES + (["INVALID/FAILED"] if a["inv"] else [])
    data = [[a["mat"][g][p] for p in cols] for g in CATEGORIES]
    vmax = max(max(r) for r in data)
    ax.imshow(data, cmap="Blues", vmin=0, vmax=vmax)
    for i, row in enumerate(data):
        for j, v in enumerate(row):
            if v:
                ax.text(j, i, str(v), ha="center", va="center", fontsize=8,
                        color="white" if v > vmax * 0.6 else "black",
                        weight="bold" if i == j else "normal")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([SHORT[c] for c in cols], fontsize=7)
    ax.set_yticks(range(len(CATEGORIES)))
    ax.set_yticklabels([SHORT[c] for c in CATEGORIES], fontsize=7)
    ax.set_xlabel("Predicted", fontsize=8)
    ax.set_ylabel("Golden label", fontsize=8)
    ax.set_title(title, fontsize=10, weight="bold")


def fig_confusion(acc):
    fig, axes = plt.subplots(2, 2, figsize=(11, 10))
    for ax, m in zip(axes.flatten(), MODELS):
        a = acc[m["short"]]
        draw_cm(ax, a, f"{NAME[m['short']]}  (accuracy {a['acc'] * 100:.1f}%)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_confusion_all.png"), dpi=200)
    plt.close(fig)
    for m in MODELS:
        a = acc[m["short"]]
        fig, ax = plt.subplots(figsize=(6, 5.5))
        draw_cm(ax, a, f"{NAME[m['short']]}  (accuracy {a['acc'] * 100:.1f}%)")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, f"fig_confusion_{m['acc']}.png"), dpi=200)
        plt.close(fig)


def fig_tradeoff(acc, r3):
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for m in MODELS:
        s = m["short"]
        x, y = acc[s]["acc"] * 100, mean(r3[s]["thr"])
        ax.scatter(x, y, s=90, color=COLOR[s], zorder=3)
        ax.annotate(NAME[s], (x, y), xytext=(7, 6), textcoords="offset points", fontsize=9)
    ax.axvline(75, ls="--", color="grey")
    ax.text(75.4, 60, "R5 overall target 75%", rotation=90, fontsize=8, color="grey", va="bottom")
    ax.axhline(32, ls=":", color="grey")
    ax.text(65.5, 60, "R3 target 32/h", fontsize=8, color="grey")
    ax.set_xlim(65, 95)
    ax.set_ylim(0, 1700)
    ax.set_xlabel("Overall accuracy on golden set (%)")
    ax.set_ylabel("Max throughput, R3 (tickets/h)")
    ax.set_title("Accuracy vs speed: all pass R1–R4; none pass R5", fontsize=11, weight="bold")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_tradeoff.png"), dpi=200)
    plt.close(fig)


def fig_pred_models(r12, r3, r4, acc):
    header = ["Model", "R1 p50 latency (s)\npredicted → measured", "Accuracy (%)\npredicted → measured",
              "R3 throughput (/h)\npredicted → measured", "R4 ÷ R3\npredicted → measured"]
    rows, cols = [], []
    for m in MODELS:
        s = m["short"]
        lat = nearest_rank(r12[s]["POST"], 0.5)
        lp, llo, lhi = PRED_LAT[s]
        ac = acc[s]["acc"] * 100
        ap, alo, ahi = PRED_ACC[s]
        thr = mean(r3[s]["thr"])
        tp = PRED_R3[s]
        ratio = mean(r4[s]["thr"]) / thr
        ok = [llo <= lat <= lhi, alo <= ac <= ahi, abs(thr - tp) / tp <= 0.20, 0.60 <= ratio <= 0.85]
        rows.append([NAME[s],
                     f"{lp} ({llo}–{lhi}) → {lat:.1f}",
                     f"{ap} ({alo}–{ahi}) → {ac:.1f}",
                     f"{tp:,} ±20% → {thr:,.0f}",
                     f"0.60–0.85 → {ratio:.2f}"])
        cols.append([PLAIN] + [GOOD if o else BAD for o in ok])
    save_table("fig_predictions_models.png", header, rows, cols, [1.3, 2.4, 2.4, 2.4, 2.0])


def fig_pred_other(r12, r3, r4, acc):
    logs = load_service_log()
    ratios = [e["model_ms"] / e["latency_ms"] for e in logs
              if e.get("method") == "POST" and e.get("status") == 201
              and (e.get("ref") or "").startswith("r1r2_")
              and e.get("model_ms") and e.get("latency_ms")]
    p2 = max(nearest_rank(r12[m["short"]]["POST"], 0.95) / nearest_rank(r12[m["short"]]["POST"], 0.5)
             for m in MODELS)
    p3 = max(nearest_rank(r12[m["short"]]["GET"], 0.95) for m in MODELS)
    n_err = sum(1 for d in (r3, r4) for m in MODELS
                for c in d[m["short"]]["codes"] if c in ("502", "504"))
    unf = {m["short"]: mean(r3[m["short"]]["unf"]) for m in MODELS}
    p7 = all(abs(unf[s] - (80 if s in ("qwen3b", "llama3b") else 150)) /
             (80 if s in ("qwen3b", "llama3b") else 150) <= 0.20 for s in unf)
    get_all = sorted(g for m in MODELS for g in r3[m["short"]]["get"])
    p8 = nearest_rank(get_all, 0.5)

    h1_low = sum(1 for m in MODELS
                 if min(acc[m["short"]]["prec"], key=acc[m["short"]]["prec"].get) == "Credit reporting")
    cr_prec = [acc[m["short"]]["prec"]["Credit reporting"] * 100 for m in MODELS]
    h2 = 0
    for m in MODELS:
        mat = acc[m["short"]]["mat"]
        pairs = {}
        for i, a_ in enumerate(CATEGORIES):
            for b_ in CATEGORIES[i + 1:]:
                if "Credit reporting" not in (a_, b_):
                    pairs[(a_, b_)] = mat[a_][b_] + mat[b_][a_]
        if set(max(pairs, key=pairs.get)) == {"Bank account or service", "Money transfer or service"}:
            h2 += 1
    h3 = sum(1 for m in MODELS
             if acc[m["short"]]["rec"]["Mortgage"] == max(acc[m["short"]]["rec"].values()))
    mort = [acc[m["short"]]["rec"]["Mortgage"] * 100 for m in MODELS]

    rows = [
        ["P1", "Ollama ≥ 90% of POST time at peak load", f"min {min(ratios) * 100:.1f}%", min(ratios) >= 0.90],
        ["P2", "Peak POST p95 ≤ 2 × p50", f"max p95/p50 = {p2:.2f}", p2 <= 2],
        ["P3", "Peak search p95 < 0.5 s", f"max {p3:.2f} s", p3 < 0.5],
        ["P6", "No 504 / backend 502 under overload", f"{n_err} errors", n_err == 0],
        ["P7", "Unfinished ≈ 80 (3B) / 150 (7–8B), ±20%",
         " / ".join(f"{unf[m['short']]:.0f}" for m in MODELS), p7],
        ["P8", "Search p50 > 30 s under overload", f"{p8:.0f} s", p8 > 30],
        ["H1", "Credit reporting lowest precision, < 70%",
         f"lowest in {h1_low}/4; {min(cr_prec):.0f}–{max(cr_prec):.0f}%",
         h1_low >= 3 and max(cr_prec) < 70],
        ["H2", "Bank ↔ Money transfer largest non-credit confusion", f"{h2}/4 models", h2 >= 3],
        ["H3", "Mortgage highest recall", f"{h3}/4 models ({min(mort):.0f}–{max(mort):.0f}%)", h3 >= 3],
    ]
    cols = [[PLAIN, PLAIN, PLAIN, GOOD if ok else BAD] for *_, ok in rows]
    rows = [[a, b, c, "CORRECT" if ok else "WRONG"] for a, b, c, ok in rows]
    save_table("fig_predictions_other.png", ["ID", "Prediction", "Measured", "Verdict"],
               rows, cols, [0.6, 4.2, 3.0, 1.1])


def main():
    os.makedirs(OUT, exist_ok=True)
    r12, r3, r4, acc = load_r1r2(), load_sat("r3"), load_sat("r4"), load_acc()
    fig_r1r2(r12)
    fig_r3r4(r3, r4)
    fig_latency(r3)
    fig_accuracy(acc)
    fig_confusion(acc)
    fig_tradeoff(acc, r3)
    fig_pred_models(r12, r3, r4, acc)
    fig_pred_other(r12, r3, r4, acc)
    for f in sorted(os.listdir(OUT)):
        print("wrote results/figures/" + f)


if __name__ == "__main__":
    main()