"""
run_accuracy.py <MODEL_NAME>

Send each of the 185 golden-set rows ONE AT A TIME to POST /tickets and record the
result, then compute per-category metrics and a confusion matrix.

Writes:
  results/accuracy/<model>_raw.csv      one row per ticket (model name, ':' -> '_')
  results/accuracy/<model>_summary.txt  accuracy, recall, precision, confusion matrix
"""
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(BASE, "..", "golden_set", "golden_set_final.csv")
OUT_DIR = os.path.join(BASE, "..", "results", "accuracy")
URL = "http://localhost:8000/tickets"

CATEGORIES = [
    "Credit reporting",
    "Debt collection",
    "Mortgage",
    "Credit card",
    "Bank account or service",
    "Consumer loan",
    "Money transfer or service",
]


def main():
    if len(sys.argv) != 2:
        print("usage: python loadtest/run_accuracy.py MODEL_NAME", file=sys.stderr)
        sys.exit(2)

    model = sys.argv[1]
    safe_model = model.replace(":", "_")
    os.makedirs(OUT_DIR, exist_ok=True)

    with open(GOLDEN, encoding="utf-8") as f:
        golden = list(csv.DictReader(f))

    records = []
    for r in golden:
        row, label, narrative = r["row"], r["final_label"], r["narrative"]
        payload = json.dumps(
            {"narrative": narrative, "ref": f"acc-{model}-{row}"}
        ).encode("utf-8")
        req = urllib.request.Request(
            URL, data=payload, method="POST",
            headers={"Content-Type": "application/json"},
        )
        t0 = time.perf_counter()
        status, predicted, error = None, None, ""
        try:
            with urllib.request.urlopen(req, timeout=900) as resp:
                status = resp.status
                body = json.loads(resp.read())
                predicted = body.get("category", "")
        except urllib.error.HTTPError as e:
            status = e.code
            try:
                body = json.loads(e.read())
                error = (body or {}).get("error", "")
            except (ValueError, OSError):
                error = ""
        except urllib.error.URLError as e:
            status = -1
            error = f"URLError: {e.reason}"
        elapsed = time.perf_counter() - t0
        records.append({
            "row": row, "final_label": label, "status": status,
            "predicted": predicted, "error": error,
            "elapsed_s": round(elapsed, 3),
        })

    # raw csv
    raw_path = os.path.join(OUT_DIR, f"{safe_model}_raw.csv")
    with open(raw_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row", "final_label", "status", "predicted", "error", "elapsed_s"])
        for rec in records:
            w.writerow([rec["row"], rec["final_label"], rec["status"],
                        rec["predicted"], rec["error"], rec["elapsed_s"]])

    # metrics
    idx = {c: i for i, c in enumerate(CATEGORIES)}
    n = len(records)
    gold_count = [0] * 7
    pred_count = [0] * 7
    matrix = [[0] * 7 for _ in range(7)]  # rows = golden, cols = predicted
    invalid = [0] * 7                    # rows = golden, "INVALID/FAILED" col
    invalid_output = 0
    correct = 0

    for rec in records:
        g = rec["final_label"]
        p = rec["predicted"]
        gi = idx.get(g, -1)
        if gi >= 0:
            gold_count[gi] += 1
        if rec["status"] == 201 and p in idx:
            pi = idx[p]
            pred_count[pi] += 1
            if gi >= 0:
                matrix[gi][pi] += 1
            if gi >= 0 and pi == gi:
                correct += 1
        else:
            if gi >= 0:
                invalid[gi] += 1
        if rec["status"] == 502 and rec["error"] == "model returned an invalid category":
            invalid_output += 1

    lines = []
    lines.append(f"model: {model}")
    lines.append(f"tickets: {n}")
    lines.append(f"correct: {correct}")
    lines.append(f"overall accuracy: {correct / n:.4f} ({correct}/{n})")
    lines.append(f"invalid output (502 'invalid category'): {invalid_output}")
    lines.append("")
    lines.append("category: recall (tp / golden), precision (tp / predicted)")
    for c in CATEGORIES:
        i = idx[c]
        tp = matrix[i][i]
        recall = (tp / gold_count[i]) if gold_count[i] else 0.0
        precision = (tp / pred_count[i]) if pred_count[i] else 0.0
        lines.append(
            f"{c:<24} recall={recall:.4f} ({tp}/{gold_count[i]})  "
            f"precision={precision:.4f} ({tp}/{pred_count[i]})"
        )
    lines.append("")
    lines.append("Confusion matrix (rows = golden label, columns = predicted):")
    header = "".join(f"{c[:20]:>21}" for c in CATEGORIES) + f"{'INVALID/FAILED':>16}"
    lines.append("golden\\predicted" + header)
    for i, c in enumerate(CATEGORIES):
        row_str = "".join(f"{matrix[i][j]:>21}" for j in range(7))
        lines.append(f"{c:<24}{row_str}{invalid[i]:>16}")

    summary_path = os.path.join(OUT_DIR, f"{safe_model}_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"wrote {raw_path}")
    print(f"wrote {summary_path}")
    print(f"accuracy: {correct}/{n} = {correct / n:.4f}")


if __name__ == "__main__":
    main()
