#!/usr/bin/env python3
"""
analyse.py - post-hoc analysis of the load test and accuracy results.

Reads:
  results/jtl/<tag>.jtl          JMeter CSV (timeStamp ms, elapsed ms, label, responseCode)
  logs/requests.jsonl            service request log (one JSON per line)
  results/accuracy/<model>_raw.csv

Writes:
  results/summary/report.md
  results/summary/r1r2_perrun.csv
  results/summary/r3_perrun.csv
  results/summary/r4_perrun.csv
  results/summary/accuracy.csv
  results/summary/reconciliation.csv
  results/summary/r3_latency_over_time.png

Percentiles use the NEAREST-RANK method: value at position ceil(p*n) in the sorted list.
"""
import collections
import csv
import json
import math
import os
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
JTL_DIR = os.path.join(BASE, "..", "results", "jtl")
LOG_PATH = os.path.join(BASE, "..", "logs", "requests.jsonl")
ACC_DIR = os.path.join(BASE, "..", "results", "accuracy")
OUT_DIR = os.path.join(BASE, "..", "results", "summary")

CATEGORIES = [
    "Credit reporting", "Debt collection", "Mortgage", "Credit card",
    "Bank account or service", "Consumer loan", "Money transfer or service",
]

MODELS = [
    {"slug": "qwen2-5-3b",  "acc": "qwen2.5_3b",  "short": "qwen3b", "size": "3b"},
    {"slug": "llama3-2-3b", "acc": "llama3.2_3b", "short": "llama3b", "size": "3b"},
    {"slug": "qwen2-5-7b",  "acc": "qwen2.5_7b",  "short": "qwen7b", "size": "7b"},
    {"slug": "llama3-1-8b", "acc": "llama3.1_8b", "short": "llama8b", "size": "8b"},
]

RUNS = (1, 2, 3)
CUT_MS = 360000  # R3/R4 run duration (6 min)


def nearest_rank(sorted_vals, p):
    n = len(sorted_vals)
    if n == 0:
        return None
    k = max(1, math.ceil(p * n))
    return sorted_vals[k - 1]


def read_jtl(path):
    samples = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                ts = int(float(r["timeStamp"]))
            except (KeyError, ValueError, TypeError):
                ts = 0
            try:
                el = int(float(r["elapsed"]))
            except (KeyError, ValueError, TypeError):
                el = 0
            samples.append({
                "timeStamp": ts,
                "elapsed": el,
                "label": (r.get("label") or "").strip(),
                "code": (r.get("responseCode") or "").strip(),
            })
    return samples


def load_service_log():
    lines = []
    with open(LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return lines


def service_log_for_tag(log_lines, tag):
    by_status = collections.Counter()
    invalid = 0
    for e in log_lines:
        ref = e.get("ref") or ""
        if e.get("method") == "POST" and ref.startswith(tag + "-"):
            st = e.get("status")
            by_status[st] += 1
            err = (e.get("error") or "").lower()
            if "invalid" in err:
                invalid += 1
    return by_status, invalid


def classify_run(samples):
    groups = collections.Counter()
    for s in samples:
        code = s["code"]
        if code == "201":
            groups["success"] += 1
        elif code == "502":
            groups["invalid_output"] += 1
        elif code.startswith("Non HTTP"):
            groups["unfinished"] += 1
        else:
            groups["infra_error"] += 1
    return groups


def elapsed_seconds(samples, label, ok_codes):
    vals = [s["elapsed"] / 1000.0 for s in samples
            if s["label"] == label and s["code"] in ok_codes]
    vals.sort()
    return vals


def mmm(vals, nd=1):
    if not vals or all(v is None for v in vals):
        return "-"
    v = [x for x in vals if x is not None]
    if not v:
        return "-"
    return f"{sum(v)/len(v):.{nd}f} ({min(v):.{nd}f}-{max(v):.{nd}f})"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    log_lines = load_service_log()

    # ---------------- Clock skew (R1/R2 POST: JMeter vs service log) ----------------
    # Match the 4 POST /tickets 201 samples per run to the 4 service-log POST 201 lines
    # k-th to k-th in time order. skew = log epoch_ms - JMeter timeStamp (both request starts).
    skews = []          # seconds: log epoch_ms - JMeter timeStamp (pure clock skew)
    el_minus_lat = []   # JMeter elapsed - log latency_ms (should be << 1 s)
    for m in MODELS:
        for k in RUNS:
            tag = f"r1r2_{m['slug']}_run{k}"
            samples = read_jtl(os.path.join(JTL_DIR, tag + ".jtl"))
            jm = sorted((s["timeStamp"], s["elapsed"]) for s in samples
                        if s["label"] == "POST /tickets" and s["code"] == "201")
            sv = sorted((e["epoch_ms"], e.get("latency_ms") or 0.0) for e in log_lines
                        if e.get("method") == "POST" and e.get("status") == 201
                        and (e.get("ref") or "").startswith(tag + "-"))
            for (ts, el), (ep, lm) in zip(jm, sv):
                skews.append((ep - ts) / 1000.0)
                el_minus_lat.append((el - lm) / 1000.0)
    skews.sort()
    skew_s = statistics.median(skews)
    el_minus_lat.sort()

    # ---------------- R1/R2 ----------------
    r1r2_rows = []
    r1r2 = {}
    r1r2_pooled = {}
    for m in MODELS:
        r1r2[m["short"]] = {"POST /tickets": collections.defaultdict(list),
                            "GET /search": collections.defaultdict(list)}
        pooled = {"POST /tickets": [], "GET /search": []}
        for k in RUNS:
            tag = f"r1r2_{m['slug']}_run{k}"
            samples = read_jtl(os.path.join(JTL_DIR, tag + ".jtl"))
            for label in ("POST /tickets", "GET /search"):
                ok = elapsed_seconds(samples, label, ("201",) if "POST" in label else ("200",))
                n = len(ok)
                all_s = [s for s in samples if s["label"] == label]
                total = len(all_s)
                infra = total - n
                p50 = nearest_rank(ok, 0.50)
                p95 = nearest_rank(ok, 0.95)
                p99 = nearest_rank(ok, 0.99)
                achieved = n / 0.25
                err_rate = (infra / total) if total else 0.0
                r1r2[m["short"]][label]["n"].append(n)
                r1r2[m["short"]][label]["p50"].append(p50)
                r1r2[m["short"]][label]["p95"].append(p95)
                r1r2[m["short"]][label]["p99"].append(p99)
                r1r2[m["short"]][label]["achieved"].append(achieved)
                r1r2[m["short"]][label]["error_rate"].append(err_rate)
                pooled[label].extend(ok)
                r1r2_rows.append([m["short"], k, label, n,
                                  "" if p50 is None else f"{p50:.3f}",
                                  "" if p95 is None else f"{p95:.3f}",
                                  "" if p99 is None else f"{p99:.3f}",
                                  f"{achieved:.1f}", f"{err_rate:.4f}", 0])
        for label in ("POST /tickets", "GET /search"):
            p = sorted(pooled[label])
            r1r2_pooled.setdefault(m["short"], {})[label] = {
                "p50": nearest_rank(p, 0.50),
                "p95": nearest_rank(p, 0.95),
                "p99": nearest_rank(p, 0.99),
                "n": len(p),
            }

    # ---------------- R3 / R4 ----------------
    r3_rows, r4_rows = [], []
    r3 = collections.defaultdict(lambda: collections.defaultdict(list))
    r4 = collections.defaultdict(lambda: collections.defaultdict(list))
    r3_get_pooled = []
    recon = []   # (tag, jm_201, svc_201, extra, after_cut)
    for m in MODELS:
        for kind, store, csvrows in (("r3", r3, r3_rows), ("r4", r4, r4_rows)):
            for k in RUNS:
                tag = f"{kind}_{m['slug']}_run{k}"
                samples = read_jtl(os.path.join(JTL_DIR, tag + ".jtl"))
                svc, inv = service_log_for_tag(log_lines, tag)
                t0 = min((s["timeStamp"] for s in samples), default=0)
                posts = [s for s in samples if s["label"] == "POST /tickets"]
                groups = classify_run(posts)
                jmeter_502 = groups.get("invalid_output", 0)
                invalid = min(jmeter_502, inv)
                infra = groups.get("infra_error", 0) + (jmeter_502 - invalid)
                success = groups.get("success", 0)
                unfinished = groups.get("unfinished", 0)
                sent = success + invalid + infra + unfinished
                ok = elapsed_seconds(samples, "POST /tickets", ("201",))
                p50 = nearest_rank(ok, 0.50)
                p95 = nearest_rank(ok, 0.95)
                p99 = nearest_rank(ok, 0.99)
                succ_in_window = sum(
                    1 for s in samples
                    if s["label"] == "POST /tickets" and s["code"] == "201"
                    and t0 + 180000 <= s["timeStamp"] + s["elapsed"] <= t0 + CUT_MS
                )
                achieved = succ_in_window * 20
                denom = sent - unfinished
                err_rate = (infra / denom) if denom else 0.0
                valid = achieved < 2070
                store[m["short"]]["sent"].append(sent)
                store[m["short"]]["success"].append(success)
                store[m["short"]]["invalid"].append(invalid)
                store[m["short"]]["infra"].append(infra)
                store[m["short"]]["unfinished"].append(unfinished)
                store[m["short"]]["achieved"].append(achieved)
                store[m["short"]]["p50"].append(p50)
                store[m["short"]]["p95"].append(p95)
                store[m["short"]]["p99"].append(p99)
                store[m["short"]]["error_rate"].append(err_rate)
                store[m["short"]]["valid"].append(valid)
                csvrows.append([m["short"], k, sent, success, invalid, infra, unfinished,
                                f"{achieved:.1f}",
                                "" if p50 is None else f"{p50:.3f}",
                                "" if p95 is None else f"{p95:.3f}",
                                "" if p99 is None else f"{p99:.3f}",
                                f"{err_rate:.4f}", str(valid)])
                if kind == "r3":
                    r3_get_pooled.extend(elapsed_seconds(samples, "GET /search", ("200",)))
                # reconciliation: server-side completion time, corrected for clock skew
                cut = t0 + CUT_MS
                completions = sorted(
                    e["epoch_ms"] + (e.get("latency_ms") or 0.0) - skew_s * 1000
                    for e in log_lines
                    if e.get("method") == "POST" and e.get("status") == 201
                    and (e.get("ref") or "").startswith(tag + "-")
                )
                jm_201 = sum(1 for s in posts if s["code"] == "201")
                before_cut = sum(1 for c in completions if c <= cut)
                after_cut = len(completions) - before_cut
                status = "RECONCILED" if abs(before_cut - jm_201) <= 2 else "MISMATCH"
                recon.append([tag, jm_201, len(completions), before_cut, after_cut, status])

    # ---------------- Accuracy ----------------
    acc = {}
    for m in MODELS:
        raw = list(csv.DictReader(open(os.path.join(ACC_DIR, m["acc"] + "_raw.csv"))))
        correct = 0
        invalid = 0
        gold = {c: 0 for c in CATEGORIES}
        pred = {c: 0 for c in CATEGORIES}
        matrix = {c: {d: 0 for d in CATEGORIES} for c in CATEGORIES}
        for r in raw:
            g = r["final_label"]
            p = r["predicted"]
            if g in gold:
                gold[g] += 1
            if r["status"] == "201" and p in pred:
                pred[p] += 1
                if g in matrix:
                    matrix[g][p] += 1
                if p == g:
                    correct += 1
            else:
                invalid += 1
        recall = {c: (matrix[c][c] / gold[c] if gold[c] else 0.0) for c in CATEGORIES}
        precision = {c: (matrix[c][c] / pred[c] if pred[c] else 0.0) for c in CATEGORIES}
        acc[m["short"]] = {
            "accuracy": correct / len(raw) if raw else 0.0,
            "correct": correct, "n": len(raw), "invalid": invalid,
            "recall": recall, "precision": precision,
            "gold": gold, "pred": pred, "matrix": matrix,
        }

    # ---------------- Build report ----------------
    L = []
    L.append("# Load test analysis")
    L.append("")
    L.append("Percentiles: **nearest-rank** (value at position ceil(p*n) in the sorted list).")
    L.append("Times in seconds unless stated. R3/R4 runs are 360 s (6 min); "
             "'unfinished' = non-HTTP/SocketException POSTs aborted at the run cut "
             "(their recorded end times all fall within ~0.2 s of T0+360000 ms).")
    L.append("")

    # R1
    L.append("## R1 - POST latency (targets: p50<=10, p95<=30, p99<=60 s)")
    L.append("")
    L.append("Each run sent exactly 4 POST arrivals (rate 16/h; JMeter rounds rate x duration down), "
             "so the pooled sample is n=12 POST per model.")
    L.append("")
    L.append("| model | pooled n | pooled p50 | pooled p95 | pooled p99 | per-run p50 | per-run p95 | per-run p99 | achieved/h | PASS/FAIL |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for m in MODELS:
        s = m["short"]
        pl = r1r2_pooled[s]["POST /tickets"]
        p50, p95, p99 = pl["p50"], pl["p95"], pl["p99"]
        ok = p50 <= 10 and p95 <= 30 and p99 <= 60
        L.append(f"| {s} | {pl['n']} | {p50:.3f} | {p95:.3f} | {p99:.3f} | {mmm(r1r2[s]['POST /tickets']['p50'],3)} | "
                 f"{mmm(r1r2[s]['POST /tickets']['p95'],3)} | {mmm(r1r2[s]['POST /tickets']['p99'],3)} | "
                 f"{mmm(r1r2[s]['POST /tickets']['achieved'])} | {'PASS' if ok else 'FAIL'} |")
    L.append("")

    # R2
    L.append("## R2 - GET latency (targets: p50<=1, p95<=5, p99<=10 s)")
    L.append("")
    L.append("Each run sent exactly 7 GET arrivals (rate 28/h), so the pooled sample is n=21 GET per model.")
    L.append("")
    L.append("| model | pooled n | pooled p50 | pooled p95 | pooled p99 | per-run p50 | per-run p95 | per-run p99 | achieved/h | PASS/FAIL |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for m in MODELS:
        s = m["short"]
        pl = r1r2_pooled[s]["GET /search"]
        p50, p95, p99 = pl["p50"], pl["p95"], pl["p99"]
        ok = p50 <= 1 and p95 <= 5 and p99 <= 10
        L.append(f"| {s} | {pl['n']} | {p50:.3f} | {p95:.3f} | {p99:.3f} | {mmm(r1r2[s]['GET /search']['p50'],3)} | "
                 f"{mmm(r1r2[s]['GET /search']['p95'],3)} | {mmm(r1r2[s]['GET /search']['p99'],3)} | "
                 f"{mmm(r1r2[s]['GET /search']['achieved'])} | {'PASS' if ok else 'FAIL'} |")
    L.append("")

    # R3
    L.append("## R3 - sustained POST (target: achieved >= 32/h)")
    L.append("")
    L.append("| model | sent | success | invalid | infra | unfinished | achieved/h | p50 | p95 | p99 | error rate | PASS/FAIL |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    r3_mean_achieved = {}
    for m in MODELS:
        s = m["short"]
        ach = sum(r3[s]["achieved"]) / 3
        r3_mean_achieved[s] = ach
        ok = ach >= 32
        L.append(f"| {s} | {mmm(r3[s]['sent'],0)} | {mmm(r3[s]['success'],0)} | {mmm(r3[s]['invalid'],0)} | "
                 f"{mmm(r3[s]['infra'],0)} | {mmm(r3[s]['unfinished'],0)} | {mmm(r3[s]['achieved'])} | "
                 f"{mmm(r3[s]['p50'],3)} | {mmm(r3[s]['p95'],3)} | {mmm(r3[s]['p99'],3)} | "
                 f"{mmm(r3[s]['error_rate'],4)} | {'PASS' if ok else 'FAIL'} |")
    L.append("")
    r3_get_sorted = sorted(r3_get_pooled)
    L.append(f"R3 GET pooled p50 (all models): {nearest_rank(r3_get_sorted, 0.50):.3f} s (n={len(r3_get_sorted)})")
    L.append("")

    # R4
    L.append("## R4 - sustained POST (target: achieved >= 19/h)")
    L.append("")
    L.append("| model | sent | success | invalid | infra | unfinished | achieved/h | p50 | p95 | p99 | error rate | PASS/FAIL |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    r4_mean_achieved = {}
    for m in MODELS:
        s = m["short"]
        ach = sum(r4[s]["achieved"]) / 3
        r4_mean_achieved[s] = ach
        ok = ach >= 19
        L.append(f"| {s} | {mmm(r4[s]['sent'],0)} | {mmm(r4[s]['success'],0)} | {mmm(r4[s]['invalid'],0)} | "
                 f"{mmm(r4[s]['infra'],0)} | {mmm(r4[s]['unfinished'],0)} | {mmm(r4[s]['achieved'])} | "
                 f"{mmm(r4[s]['p50'],3)} | {mmm(r4[s]['p95'],3)} | {mmm(r4[s]['p99'],3)} | "
                 f"{mmm(r4[s]['error_rate'],4)} | {'PASS' if ok else 'FAIL'} |")
    L.append("")
    L.append("| model | R4/R3 ratio | headroom (R3 mean / 19) |")
    L.append("|---|---|---|")
    for m in MODELS:
        s = m["short"]
        ratio = (r4_mean_achieved[s] / r3_mean_achieved[s]) if r3_mean_achieved[s] else float('nan')
        hd = r3_mean_achieved[s] / 19.0
        L.append(f"| {s} | {ratio:.3f} | {hd:.2f} |")
    L.append("")

    # R5
    L.append("## R5 - accuracy (pass if overall>=75%, every category recall>=70% and precision>=70%, invalid<=1)")
    L.append("")
    L.append("| model | accuracy | min recall | min precision | invalid | PASS/FAIL |")
    L.append("|---|---|---|---|---|---|")
    for m in MODELS:
        s = m["short"]
        a = acc[s]
        mr = min(a["recall"].values())
        mp = min(a["precision"].values())
        ok = a["accuracy"] >= 0.75 and mr >= 0.70 and mp >= 0.70 and a["invalid"] <= 1
        L.append(f"| {s} | {a['accuracy']*100:.2f}% | {mr*100:.1f}% | {mp*100:.1f}% | {a['invalid']} | {'PASS' if ok else 'FAIL'} |")
    L.append("")
    L.append("Per-category recall / precision (values below 70% marked with `*`):")
    L.append("")
    for m in MODELS:
        s = m["short"]
        a = acc[s]
        L.append(f"**{s}** (accuracy {a['accuracy']*100:.2f}%):")
        L.append("")
        L.append("| category | recall | precision |")
        L.append("|---|---|---|")
        for c in CATEGORIES:
            r = a["recall"][c] * 100
            p = a["precision"][c] * 100
            rs = f"{r:.1f}%*" if r < 70 else f"{r:.1f}%"
            ps = f"{p:.1f}%*" if p < 70 else f"{p:.1f}%"
            L.append(f"| {c} | {rs} | {ps} |")
        L.append("")
    L.append("Failed conditions per model:")
    L.append("")
    for m in MODELS:
        s = m["short"]
        a = acc[s]
        fails = []
        if a["accuracy"] < 0.75:
            fails.append(f"overall accuracy {a['accuracy']*100:.2f}% < 75%")
        low_recall = [c for c in CATEGORIES if a["recall"][c] < 0.70]
        low_prec = [c for c in CATEGORIES if a["precision"][c] < 0.70]
        if low_recall:
            fails.append("recall<70%: " + ", ".join(low_recall))
        if low_prec:
            fails.append("precision<70%: " + ", ".join(low_prec))
        if a["invalid"] > 1:
            fails.append(f"invalid={a['invalid']} > 1")
        if not fails:
            L.append(f"- {s}: PASS")
        else:
            L.append(f"- {s}: FAIL — " + "; ".join(fails))
    L.append("")

    # Prediction checks
    preds = []
    for m in MODELS:
        ratios = []
        for e in log_lines:
            ref = e.get("ref") or ""
            if e.get("method") == "POST" and e.get("status") == 201 and ref.startswith(f"r1r2_{m['slug']}"):
                if e.get("latency_ms") and e.get("model_ms"):
                    ratios.append(e["model_ms"] / e["latency_ms"])
        if ratios:
            rs = sorted(ratios)
            med = rs[len(rs)//2]
            mn = min(rs)
            preds.append((f"P1 {m['short']}: median & min model_ms/latency >= 0.90",
                          f"median={med:.3f} min={mn:.3f}", "CORRECT" if mn >= 0.90 else "WRONG"))
        else:
            preds.append((f"P1 {m['short']}", "no data", "WRONG"))
    for m in MODELS:
        s = m["short"]
        p50p = r1r2_pooled[s]["POST /tickets"]["p50"]
        p95p = r1r2_pooled[s]["POST /tickets"]["p95"]
        preds.append((f"P2 {s}: pooled POST p95 <= 2 * pooled p50",
                      f"p95={p95p:.3f} 2*p50={2*p50p:.3f}",
                      "CORRECT" if p95p <= 2 * p50p else "WRONG"))
    for m in MODELS:
        s = m["short"]
        g95 = r1r2_pooled[s]["GET /search"]["p95"]
        preds.append((f"P3 {s}: pooled GET p95 < 0.5 s",
                      f"p95={g95:.3f}", "CORRECT" if g95 < 0.5 else "WRONG"))
    p4_target = {"qwen3b": 1500, "llama3b": 1440, "qwen7b": 800, "llama8b": 750}
    for m in MODELS:
        s = m["short"]
        v = r3_mean_achieved[s]
        tgt = p4_target[s]
        ok = abs(v - tgt) / tgt <= 0.20
        preds.append((f"P4 {s}: R3 mean within +-20% of {tgt}", f"measured={v:.0f}",
                      "CORRECT" if ok else "WRONG"))
    both3b = all(r3_mean_achieved[s] >= 1.6 * r3_mean_achieved[x]
                 for s in ("qwen3b", "llama3b") for x in ("qwen7b", "llama8b"))
    preds.append(("P4: both 3B >= 1.6x both 7-8B", "see R3 achieved", "CORRECT" if both3b else "WRONG"))
    for m in MODELS:
        s = m["short"]
        ratio = r4_mean_achieved[s] / r3_mean_achieved[s] if r3_mean_achieved[s] else float('nan')
        ok = 0.60 <= ratio <= 0.85
        preds.append((f"P5 {s}: R4/R3 ratio in 0.60-0.85", f"ratio={ratio:.3f}",
                      "CORRECT" if ok else "WRONG"))
    n504 = n502b = 0
    for e in log_lines:
        ref = e.get("ref") or ""
        if e.get("method") == "POST" and (ref.startswith("r3_") or ref.startswith("r4_")):
            if e.get("status") == 504:
                n504 += 1
            if e.get("status") == 502 and "backend" in (e.get("error") or "").lower():
                n502b += 1
    preds.append(("P6: zero 504 & zero backend-unavailable 502 in R3/R4",
                  f"504={n504} backend502={n502b}", "CORRECT" if (n504 == 0 and n502b == 0) else "WRONG"))
    for m in MODELS:
        s = m["short"]
        sent = sum(r3[s]["sent"]) / 3
        unf = sum(r3[s]["unfinished"]) / 3
        target_unf = 80 if m["size"] == "3b" else 150
        ok_sent = abs(sent - 230) / 230 <= 0.20
        ok_unf = abs(unf - target_unf) / target_unf <= 0.20
        preds.append((f"P7 {s}: sent~230 & unfinished~{target_unf} (+-20%)",
                      f"sent={sent:.0f} unfinished={unf:.0f}",
                      "CORRECT" if (ok_sent and ok_unf) else "WRONG"))
    preds.append(("P8: R3 GET pooled p50 > 30 s",
                  f"p50={nearest_rank(r3_get_sorted,0.50):.3f} s",
                  "CORRECT" if nearest_rank(r3_get_sorted, 0.50) > 30 else "WRONG"))
    lat_range = {"qwen3b": (1.9, 3.1), "llama3b": (1.9, 3.1), "qwen7b": (3.4, 5.6), "llama8b": (3.8, 6.3)}
    for m in MODELS:
        s = m["short"]
        v = r1r2_pooled[s]["POST /tickets"]["p50"]
        lo, hi = lat_range[s]
        preds.append((f"Latency {s}: pooled R1 POST p50 in {lo}-{hi} s",
                      f"p50={v:.3f}", "CORRECT" if lo <= v <= hi else "WRONG"))
    acc_range = {"qwen3b": (68, 72), "llama3b": (63, 67), "qwen7b": (75, 79), "llama8b": (73, 77)}
    for m in MODELS:
        s = m["short"]
        v = acc[s]["accuracy"] * 100
        lo, hi = acc_range[s]
        preds.append((f"Accuracy {s}: in {lo}-{hi}%", f"{v:.2f}%", "CORRECT" if lo <= v <= hi else "WRONG"))

    h1_lowest = 0
    h1_all70 = True
    for m in MODELS:
        a = acc[m["short"]]
        prec = a["precision"]
        if min(prec, key=prec.get) == "Credit reporting":
            h1_lowest += 1
        if prec["Credit reporting"] >= 0.70:
            h1_all70 = False
    preds.append(("H1: Credit reporting lowest precision (>=3/4) and <70% all",
                  f"lowest_in={h1_lowest}/4 all_lt70={h1_all70}",
                  "CORRECT" if (h1_lowest >= 3 and h1_all70) else "WRONG"))
    h2_largest = 0
    h2_recall = 0
    for m in MODELS:
        a = acc[m["short"]]
        mat = a["matrix"]
        best = 0; best_pair = None
        for c1 in CATEGORIES:
            if c1 == "Credit reporting":
                continue
            for c2 in CATEGORIES:
                if c1 == c2 or c2 == "Credit reporting":
                    continue
                if mat[c1][c2] > best:
                    best = mat[c1][c2]; best_pair = (c1, c2)
        if best_pair in (("Bank account or service", "Money transfer or service"),
                         ("Money transfer or service", "Bank account or service")):
            h2_largest += 1
        if m["size"] == "3b":
            if a["recall"]["Bank account or service"] < 0.70 or a["recall"]["Money transfer or service"] < 0.70:
                h2_recall += 1
    preds.append(("H2: Bank<->Money largest non-credit confusion (>=3/4); both 3B recall<70% in one",
                  f"largest={h2_largest}/4 recall_ok={h2_recall}/2",
                  "CORRECT" if (h2_largest >= 3 and h2_recall >= 2) else "WRONG"))
    h3 = sum(1 for m in MODELS if max(acc[m["short"]]["recall"], key=acc[m["short"]]["recall"].get) == "Mortgage")
    preds.append(("H3: Mortgage highest recall (>=3/4)", f"mortgage_highest={h3}/4",
                  "CORRECT" if h3 >= 3 else "WRONG"))

    L.append("## Prediction checks")
    L.append("")
    L.append("| prediction | measured | verdict |")
    L.append("|---|---|---|")
    for name, measured, verdict in preds:
        L.append(f"| {name} | {measured} | {verdict} |")
    L.append("")

    # Clock skew
    L.append("## Clock skew (JMeter vs service log)")
    L.append("")
    L.append("Matched the 4 POST 201 samples per R1/R2 run to the 4 service-log POST 201 lines, "
             "k-th to k-th in time order (48 pairs). skew = log epoch_ms - JMeter timeStamp "
             "(both are request-start times).")
    L.append("")
    L.append("| metric | value |")
    L.append("|---|---|")
    L.append(f"| matched pairs | {len(skews)} |")
    L.append(f"| median skew (Computer 1 ahead of Computer 2) | {skew_s:+.3f} s |")
    L.append(f"| min / max skew | {min(skews):+.3f} / {max(skews):+.3f} s |")
    L.append(f"| JMeter elapsed - log latency_ms (median / max) | "
             f"{statistics.median(el_minus_lat):.3f} / {max(el_minus_lat):.3f} s |")
    L.append("")

    # Reconciliation
    L.append("## Reconciliation (JMeter POST vs service-log POST per run)")
    L.append("")
    L.append("R1/R2: JMeter and the service log both record exactly 4 POST 201 per run (12 runs), "
             "so they reconcile directly.")
    L.append("")
    L.append("R3/R4: requests still being processed when JMeter ended its schedule at T0+360 s "
             "were aborted by the client (SocketException = unfinished). The service finished "
             "some of them after the cut, before the containers were stopped ~30 s later; "
             "these are the extra 201s in the service log. Server completion time = "
             "epoch_ms + latency_ms - skew. A run reconciles when the server-side 201s completed "
             "at or before the cut equal JMeter's 201 count (+-2 for network delay at the boundary).")
    L.append("")
    L.append("| run | JMeter 201 | log 201 total | log 201 before cut | log 201 after cut | result |")
    L.append("|---|---|---|---|---|---|")
    recon_csv = []
    for tag, jm, sv, before, after, status in recon:
        L.append(f"| {tag} | {jm} | {sv} | {before} | {after} | {status} |")
        recon_csv.append([tag, jm, sv, before, after, status])
    L.append("")

    report = "\n".join(L) + "\n"

    with open(os.path.join(OUT_DIR, "report.md"), "w") as f:
        f.write(report)

    # CSVs
    def write_csv(name, header, rows):
        with open(os.path.join(OUT_DIR, name), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    write_csv("r1r2_perrun.csv",
              ["model", "run", "kind", "n", "p50_s", "p95_s", "p99_s", "achieved_per_hour", "error_rate", "invalid"],
              r1r2_rows)
    write_csv("r3_perrun.csv",
              ["model", "run", "sent", "success", "invalid", "infra_error", "unfinished",
               "achieved_per_hour", "p50_s", "p95_s", "p99_s", "error_rate", "valid"],
              r3_rows)
    write_csv("r4_perrun.csv",
              ["model", "run", "sent", "success", "invalid", "infra_error", "unfinished",
               "achieved_per_hour", "p50_s", "p95_s", "p99_s", "error_rate", "valid"],
              r4_rows)
    write_csv("reconciliation.csv",
              ["run", "jmeter_201", "log_201_total", "log_201_before_cut", "log_201_after_cut", "result"], recon_csv)

    acc_rows = []
    for m in MODELS:
        a = acc[m["short"]]
        acc_rows.append([m["short"], f"{a['accuracy']*100:.2f}", a["correct"], a["n"], a["invalid"],
                         min(a["recall"].values()), min(a["precision"].values())])
    write_csv("accuracy.csv", ["model", "accuracy_pct", "correct", "n", "invalid", "min_recall", "min_precision"], acc_rows)

    # ---------------- PNG: R3 latency over time ----------------
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    bucket_notes = []
    for i, m in enumerate(MODELS):
        s = m["short"]
        ax = axes[i]
        buckets = collections.defaultdict(list)
        latest_start = 0.0
        for k, color in zip(RUNS, ("tab:blue", "tab:orange", "tab:green")):
            tag = f"r3_{m['slug']}_run{k}"
            samples = read_jtl(os.path.join(JTL_DIR, tag + ".jtl"))
            t0 = min((smp["timeStamp"] for smp in samples), default=0)
            xs, ys = [], []
            for smp in samples:
                if smp["label"] == "POST /tickets" and smp["code"] == "201":
                    x = (smp["timeStamp"] - t0) / 1000.0
                    y = smp["elapsed"] / 1000.0
                    xs.append(x); ys.append(y)
                    buckets[int(x // 60)].append(y)
                    latest_start = max(latest_start, x)
            ax.scatter(xs, ys, s=12, alpha=0.7, color=color, label=f"run{k}")
        ax.set_title(s)
        ax.set_xlabel("seconds since T0 (request start)")
        ax.set_ylabel("POST latency (s)")
        ax.legend()
        bucket_notes.append((s, buckets, latest_start))
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "r3_latency_over_time.png"))
    plt.close(fig)

    print("R3 median POST latency (s) of completed requests, grouped by start minute (3 runs pooled)")
    for s, buckets, latest in bucket_notes:
        parts = []
        for b in range(6):
            v = sorted(buckets.get(b, []))
            med = nearest_rank(v, 0.5)
            parts.append(f"{b*60}-{(b+1)*60}s: " + (f"{med:.1f} (n={len(v)})" if med is not None else "none"))
        print(f"  {s}: " + " | ".join(parts))
        print(f"  {s}: latest request start that still completed = {latest:.0f} s after T0")

    print(report, end="")


if __name__ == "__main__":
    main()
