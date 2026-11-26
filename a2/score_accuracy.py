"""
score_accuracy.py — score an A2 accuracy run against the golden labels and the brief's limits.

Joins a send_tickets.py results CSV (ref = golden_id or row) to the golden labels
(a2/test_set.csv or a2/tuning_set.csv), computes overall accuracy, per-category accuracy,
the confusion matrix, and — when the service log is available — the escalation fraction and
the accuracy of accepted vs escalated tickets. Pass/fail is checked against a2/limits.json
(top model overall limit, per-category floors).

Usage:
    python a2/score_accuracy.py results/acc_cascade-s1_test.csv --run-id acc-cascade-s1
    python a2/score_accuracy.py results/acc_single_test.csv --name llama3.1_8b-alone
Outputs:
    results/score_<name>.json  (+ console summary)
"""

import argparse
import json
import os
import sys
from collections import Counter

import pandas as pd

CATEGORY_ORDER = [
    "Bank account or service",
    "Consumer loan",
    "Credit card",
    "Credit reporting",
    "Debt collection",
    "Money transfer or service",
    "Mortgage",
]


def parse_args():
    p = argparse.ArgumentParser(description="Score an A2 accuracy run against golden labels.")
    p.add_argument("results_csv", help="CSV written by a2/send_tickets.py (ref,row,category,status,elapsed_ms)")
    p.add_argument("--golden", default="a2/test_set.csv", help="Golden labels CSV (default: a2/test_set.csv)")
    p.add_argument("--limits", default="a2/limits.json", help="Limits JSON (default: a2/limits.json)")
    p.add_argument("--log", default="logs/requests.jsonl", help="Service request log (JSONL)")
    p.add_argument("--run-id", default=None, help="Only use log lines with this run_id")
    p.add_argument("--name", default=None, help="Name for the output file (default: results file stem)")
    p.add_argument("--outdir", default="results")
    return p.parse_args()


def pct(n, d):
    return round(100.0 * n / d, 2) if d else None


def load_log_escalations(path, run_id):
    """ref -> {escalated, reason, final_model} from the newest matching log line per ref."""
    if not os.path.isfile(path):
        return {}
    esc = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("path") != "/tickets" or e.get("method") != "POST":
                continue
            if run_id and e.get("run_id") != run_id:
                continue
            ref = e.get("ref")
            if ref is not None:
                esc[str(ref)] = {
                    "escalated": bool(e.get("escalated", False)),
                    "reason": e.get("escalation_reason"),
                    "final_model": e.get("final_model"),
                    "category": e.get("category"),
                    "status": e.get("status"),
                }
    return esc


def main():
    args = parse_args()
    name = args.name or os.path.splitext(os.path.basename(args.results_csv))[0]

    res = pd.read_csv(args.results_csv)
    golden = pd.read_csv(args.golden)
    for col in ("golden_id", "row", "final_label"):
        if col not in golden.columns:
            raise ValueError(f"{args.golden} missing column: {col}")
    if "ref" not in res.columns or "category" not in res.columns:
        raise ValueError(f"{args.results_csv} must have 'ref' and 'category' columns")

    res["ref"] = res["ref"].astype(str)
    golden["golden_id"] = golden["golden_id"].astype(str)
    golden["row"] = golden["row"].astype(str)
    labels = {}
    for _, g in golden.iterrows():
        labels[g["golden_id"]] = g["final_label"]
        labels.setdefault(g["row"], g["final_label"])

    res["true"] = res["ref"].map(labels)
    unmatched = res[res["true"].isna()]
    if len(unmatched):
        print(f"WARNING: {len(unmatched)} result row(s) could not be matched to a golden label: "
              f"{unmatched['ref'].tolist()[:10]}")

    res["ok"] = res["category"].eq(res["true"])
    n = len(res)
    right = int(res["ok"].sum())
    errors = res[~res["ok"]]

    per_cat = (
        res.groupby("true", dropna=False)
        .agg(tickets=("true", "size"), right=("ok", "sum"))
        .reset_index()
        .rename(columns={"true": "category"})
    )
    per_cat["pct"] = 100 * per_cat["right"] / per_cat["tickets"]

    confusion = (
        res.groupby(["true", "category"], dropna=False).size().reset_index(name="n")
    )

    limits = {}
    if os.path.isfile(args.limits):
        with open(args.limits, encoding="utf-8") as f:
            lim = json.load(f)
        limits = {
            "overall_limit_pct": lim.get("overall_limit_pct"),
            "category_limit_pct": lim.get("category_limit_pct", {}),
            "top_model": lim.get("top_model"),
            "top_overall_pct": lim.get("top_overall_pct"),
        }

    esc_map = load_log_escalations(args.log, args.run_id)
    esc_stats = None
    if esc_map:
        res["escalated"] = res["ref"].map(lambda r: esc_map.get(r, {}).get("escalated"))
        known = res[res["escalated"].notna()]
        if len(known):
            acc = known[~known["escalated"].astype(bool)]
            esc = known[known["escalated"].astype(bool)]
            esc_stats = {
                "logged_tickets": int(len(known)),
                "escalated_n": int(len(esc)),
                "escalated_pct": pct(len(esc), len(known)),
                "accepted_n": int(len(acc)),
                "accepted_right": int(acc["ok"].sum()),
                "accepted_accuracy_pct": pct(int(acc["ok"].sum()), len(acc)),
                "escalated_right": int(esc["ok"].sum()),
                "escalated_accuracy_pct": pct(int(esc["ok"].sum()), len(esc)),
            }

    overall_pass = (
        limits.get("overall_limit_pct") is not None
        and pct(right, n) is not None
        and 100.0 * right / n >= limits["overall_limit_pct"]
    )
    cat_pass = {}
    floors = limits.get("category_limit_pct", {})
    for _, r in per_cat.iterrows():
        floor = floors.get(r["category"])
        cat_pass[r["category"]] = {
            "pct": round(r["pct"], 2),
            "floor_pct": floor,
            "pass": (floor is None) or (r["pct"] >= floor),
        }

    out = {
        "name": name,
        "source_results": args.results_csv,
        "golden": args.golden,
        "run_id": args.run_id,
        "n": n,
        "right": right,
        "overall_pct": pct(right, n),
        "overall_pass": overall_pass,
        "by_category": {
            r["category"]: {"right": int(r["right"]), "total": int(r["tickets"]), "pct": round(r["pct"], 2)}
            for _, r in per_cat.iterrows()
        },
        "category_pass": cat_pass,
        "all_category_pass": all(v["pass"] for v in cat_pass.values()) if cat_pass else None,
        "errors": {
            "http_or_other": int((~res["status"].astype(str).str.startswith("201")).sum()),
            "wrong_category": int((res["status"].astype(str).str.startswith("201") & ~res["ok"]).sum()),
            "detail": errors[["ref", "true", "category", "status"]].to_dict(orient="records"),
        },
        "escalation": esc_stats,
        "confusion_true_pred_n": confusion.to_dict(orient="records"),
        "limits_used": limits,
    }

    os.makedirs(args.outdir, exist_ok=True)
    out_path = os.path.join(args.outdir, f"score_{name}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"=== {name} ===")
    print(f"Overall: {right}/{n} = {out['overall_pct']}%  "
          f"(limit {limits.get('overall_limit_pct')}% -> {'PASS' if overall_pass else 'FAIL'})")
    print("\nPer category (floor = top-model test accuracy - 15pp):")
    for cat in CATEGORY_ORDER:
        row = next((r for r in per_cat.to_dict(orient='records') if r['category'] == cat), None)
        if row is None:
            continue
        cp = cat_pass.get(cat, {})
        floor = cp.get("floor_pct")
        verdict = "PASS" if cp.get("pass") else "FAIL"
        print(f"  {cat:<28} {int(row['right']):>2}/{int(row['tickets']):<2} = {row['pct']:>6.2f}%"
              f"  (floor {floor}%) -> {verdict}")
    if esc_stats:
        print(f"\nEscalated: {esc_stats['escalated_n']}/{esc_stats['logged_tickets']} = "
              f"{esc_stats['escalated_pct']}%  "
              f"(accepted acc {esc_stats['accepted_accuracy_pct']}%, "
              f"escalated acc {esc_stats['escalated_accuracy_pct']}%)")
    else:
        print("\nNOTE: no matching log lines found; escalation stats skipped "
              "(check --run-id and logs/requests.jsonl).")
    if out["errors"]["detail"]:
        print(f"\nErrors ({len(out['errors']['detail'])}):")
        for e in out["errors"]["detail"][:10]:
            print(f"  ref={e['ref']} true={e['true']} got={e['category']} status={e['status']}")
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, KeyError, pd.errors.ParserError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
