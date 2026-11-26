"""
tune_cascade.py — Assignment 2 cascade tuning (TUNING SET ONLY).

This script simulates a category-based cascade using saved Assignment 1 prediction
records. It does NOT call Ollama or the Flask service.

Rule:
  1. Run the small model first.
  2. If its valid PREDICTED category is in the acceptance list, accept that answer.
  3. Otherwise (including an invalid small-model response), escalate to the large model.

The true label is used only to evaluate simulated outcomes. It is never used to make
the accept/escalate decision.

Where this fits in Assignment 2: brief Step 2 ("Design the Cascade"), example method 1
(category-based). The brief says to choose the reliable categories "from the small model's
results on the tuning set only" and to "check how often a wrong answer slips through"; both are
printed below. Choose the strict and loose settings from this output for the selected model pair.
The per-ticket median latency and escalation fraction feed the Step 3 prediction record
(predictions_A2.md).

Run from the repository root:
    python a2/tune_cascade.py --small qwen2.5_3b --large qwen2.5_7b

Inputs:
    a2/tuning_set.csv
    results/accuracy/<model>_raw.csv

Outputs (for each small-model / large-model pairing):
    results/tuning_<small>_to_<large>.csv
        Overall simulation metrics for every k.
    results/tuning_<small>_to_<large>_precision.csv
        Small-model precision by PREDICTED category.
    results/tuning_<small>_to_<large>_k<k>_categories.csv
        Per-TRUE-category cascade accuracy and comparison with the large-model
        baseline, for every k.

IMPORTANT:
  - Only a2/tuning_set.csv is loaded. test_set.csv is never read.
  - Per-category 15-percentage-point checks in this script are TUNING-SET
    diagnostics only. Official pass/fail decisions must use the held-out test set.
  - Latencies are estimates based on individual A1 elapsed_s records. They are
    not measured live cascade latencies and exclude routing/queueing overhead.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd


REQUIRED_TUNE_COLUMNS = {"row", "final_label", "narrative"}
REQUIRED_RAW_COLUMNS = {"row", "status", "predicted", "elapsed_s"}
ACCURACY_TOLERANCE_PP = 15.0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Simulate category-based cascade settings using the tuning set only."
    )
    parser.add_argument(
        "--small",
        nargs="+",
        default=["qwen2.5_3b"],
        help="Small-model raw CSV file stem(s), without _raw.csv.",
    )
    parser.add_argument(
        "--large",
        default="qwen2.5_7b",
        help="Large-model raw CSV file stem, without _raw.csv.",
    )
    parser.add_argument("--tuning", default="a2/tuning_set.csv")
    parser.add_argument("--accuracy-dir", default="results/accuracy")
    parser.add_argument("--outdir", default="results")
    parser.add_argument(
        "--tolerance-pp",
        type=float,
        default=ACCURACY_TOLERANCE_PP,
        help="Tuning diagnostic tolerance in percentage points (default: 15).",
    )
    return parser.parse_args()


def require_columns(frame, required, source_name):
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{source_name} is missing required column(s): {', '.join(missing)}")


def load_tuning_set(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Tuning set not found: {path}")

    tune = pd.read_csv(path)
    require_columns(tune, REQUIRED_TUNE_COLUMNS, path)

    if tune.empty:
        raise ValueError("The tuning set is empty.")
    if tune["row"].isna().any():
        raise ValueError("The tuning set contains a missing row ID.")
    if tune["row"].duplicated().any():
        duplicates = tune.loc[tune["row"].duplicated(keep=False), "row"].tolist()
        raise ValueError(f"Duplicate row IDs in tuning set: {duplicates[:10]}")
    if tune["final_label"].isna().any():
        raise ValueError("The tuning set contains a missing final_label.")
    if tune["narrative"].isna().any():
        raise ValueError("The tuning set contains a missing narrative.")

    tune["final_label"] = tune["final_label"].astype(str).str.strip()
    if (tune["final_label"] == "").any():
        raise ValueError("The tuning set contains an empty final_label.")

    tune["words"] = tune["narrative"].astype(str).str.split().str.len()
    if (tune["words"] == 0).any():
        print("WARNING: one or more tuning tickets have an empty narrative.")

    return tune


def load_predictions(model, tune, accuracy_dir):
    path = os.path.join(accuracy_dir, f"{model}_raw.csv")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Prediction file not found for {model}: {path}")

    raw = pd.read_csv(path)
    require_columns(raw, REQUIRED_RAW_COLUMNS, path)

    if raw["row"].isna().any():
        raise ValueError(f"{path} contains a missing row ID.")

    # Duplicate records for a tuning ticket would make the merge ambiguous.
    tuning_ids = set(tune["row"])
    relevant = raw[raw["row"].isin(tuning_ids)].copy()
    if relevant["row"].duplicated().any():
        duplicates = relevant.loc[
            relevant["row"].duplicated(keep=False), "row"
        ].tolist()
        raise ValueError(
            f"{path} contains duplicate prediction records for tuning row(s): "
            f"{duplicates[:10]}"
        )

    missing_ids = tuning_ids - set(relevant["row"])
    if missing_ids:
        raise ValueError(
            f"{path} has no prediction record for {len(missing_ids)} tuning ticket(s): "
            f"{sorted(missing_ids, key=str)[:10]}"
        )

    relevant["status_num"] = pd.to_numeric(relevant["status"], errors="coerce")
    relevant["elapsed_s"] = pd.to_numeric(relevant["elapsed_s"], errors="coerce")

    if relevant["elapsed_s"].isna().any():
        bad = relevant.loc[relevant["elapsed_s"].isna(), "row"].tolist()
        raise ValueError(f"{path} has missing/non-numeric elapsed_s for rows: {bad[:10]}")
    if (relevant["elapsed_s"] < 0).any():
        bad = relevant.loc[relevant["elapsed_s"] < 0, "row"].tolist()
        raise ValueError(f"{path} has negative elapsed_s for rows: {bad[:10]}")

    d = tune[["row", "final_label", "words"]].merge(
        relevant[["row", "status_num", "predicted", "elapsed_s"]],
        on="row",
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    if len(d) != len(tune) or not (d["_merge"] == "both").all():
        raise ValueError(f"{model}: prediction merge did not match every tuning ticket.")

    d = d.drop(columns="_merge")
    d["predicted"] = d["predicted"].astype("string").str.strip()

    # Only HTTP 201 with a non-empty category is treated as a valid prediction.
    known_categories = set(tune["final_label"].unique())
    valid = (
        (d["status_num"] == 201)
        & d["predicted"].notna()
        & (d["predicted"] != "")
        & d["predicted"].isin(known_categories)
    )
    d["pred"] = d["predicted"].where(valid, pd.NA)

    invalid_n = int((~valid).sum())
    if invalid_n:
        print(
            f"WARNING: {model} has {invalid_n}/{len(d)} invalid/no-answer tuning "
            "prediction(s); these count as wrong and small-model cases escalate."
        )

    return d


def pct(numerator, denominator):
    return (100.0 * numerator / denominator) if denominator else np.nan


def safe_mean(series):
    return float(series.mean()) if len(series) else np.nan


def safe_median(series):
    return float(series.median()) if len(series) else np.nan


def category_precision(df):
    """Reliability of each valid category predicted by the small model."""
    valid = df.dropna(subset=["small"]).copy()
    if valid.empty:
        return pd.DataFrame(
            columns=["predicted", "right", "wrong", "precision_%"]
        )

    valid["small_right"] = valid["small"].eq(valid["true"])
    precision = (
        valid.groupby("small", dropna=True)["small_right"]
        .agg(predicted="size", right="sum")
        .reset_index()
        .rename(columns={"small": "predicted_category"})
    )
    precision["wrong"] = precision["predicted"] - precision["right"]
    precision["precision_%"] = (
        100 * precision["right"] / precision["predicted"]
    )
    # Stable tie-breaks make acceptance lists reproducible.
    precision = precision.sort_values(
        ["precision_%", "predicted", "predicted_category"],
        ascending=[False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    return precision


def category_results_for_setting(df, final, accept_mask, k, tolerance_pp):
    """Compare simulated cascade and large-model baseline by TRUE category."""
    result = pd.DataFrame(
        {
            "true_category": df["true"],
            "baseline_correct": df["large"].eq(df["true"]),
            "cascade_correct": final.eq(df["true"]),
            "accepted_by_small": accept_mask,
            "escalated_to_large": ~accept_mask,
        }
    )

    summary = (
        result.groupby("true_category", dropna=False)
        .agg(
            tickets=("true_category", "size"),
            baseline_right=("baseline_correct", "sum"),
            cascade_right=("cascade_correct", "sum"),
            accepted_n=("accepted_by_small", "sum"),
            escalated_n=("escalated_to_large", "sum"),
        )
        .reset_index()
    )
    summary["baseline_acc_%"] = 100 * summary["baseline_right"] / summary["tickets"]
    summary["cascade_acc_%"] = 100 * summary["cascade_right"] / summary["tickets"]
    summary["accuracy_change_pp"] = (
        summary["cascade_acc_%"] - summary["baseline_acc_%"]
    )
    summary["tuning_floor_%"] = summary["baseline_acc_%"] - tolerance_pp
    summary["within_tuning_tolerance"] = (
        summary["cascade_acc_%"] >= summary["tuning_floor_%"] - 1e-9
    )
    summary.insert(0, "k", k)
    return summary


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    tune = load_tuning_set(args.tuning)
    n = len(tune)
    categories = sorted(tune["final_label"].unique().tolist())

    if n < 3:
        raise ValueError("At least three tuning tickets are needed for the ticket-length analysis.")
    if args.tolerance_pp < 0:
        raise ValueError("--tolerance-pp cannot be negative.")

    print("=" * 100)
    print("CASCADE TUNING - TUNING SET ONLY")   # ASCII only: Windows consoles mangle the em dash
    print("=" * 100)
    print(f"Tuning file: {args.tuning}")
    print(f"Tuning tickets: {n}")
    print(f"True categories present: {len(categories)}")
    print("The test set is not loaded or used by this script.\n")

    large = load_predictions(args.large, tune, args.accuracy_dir)
    large_right = int(large["pred"].eq(large["final_label"]).sum())
    large_mean = safe_mean(large["elapsed_s"])
    large_median = safe_median(large["elapsed_s"])

    print(
        f"LARGE model {args.large}: {large_right}/{n} = "
        f"{pct(large_right, n):.1f}% correct; "
        f"mean {large_mean:.2f}s; median {large_median:.2f}s\n"
    )

    for small_model in args.small:
        small = load_predictions(small_model, tune, args.accuracy_dir)

        df = pd.DataFrame(
            {
                "true": small["final_label"],
                "small": small["pred"],
                "large": large["pred"],
                "s_s": small["elapsed_s"],
                "l_s": large["elapsed_s"],
                "words": small["words"],
            }
        )

        small_right = int(df["small"].eq(df["true"]).sum())
        small_mean = safe_mean(df["s_s"])
        small_median = safe_median(df["s_s"])
        break_even = (
            (large_mean - small_mean) / large_mean if large_mean > 0 else np.nan
        )

        print("=" * 100)
        print(
            f"SMALL model {small_model}: {small_right}/{n} = "
            f"{pct(small_right, n):.1f}% correct alone; "
            f"mean {small_mean:.2f}s; median {small_median:.2f}s"
        )
        if np.isfinite(break_even):
            print(
                f"Simplified break-even escalation fraction: "
                f"{100 * break_even:.1f}% "
                f"(cascade mean is theoretically below large-only mean when "
                f"escalation fraction is lower, assuming sequential inference).\n"
            )

        # 1. Predicted-category reliability.
        precision = category_precision(
            pd.DataFrame({"true": df["true"], "small": df["small"]})
        )
        print("1) Small-model reliability by PREDICTED category (tuning set)")
        if precision.empty:
            print("No valid small-model category predictions.\n")
            order = []
        else:
            print(
                precision[
                    ["predicted_category", "predicted", "right", "wrong", "precision_%"]
                ].round(2).to_string(index=False),
                "\n",
            )
            order = precision["predicted_category"].tolist()

        precision_path = os.path.join(
            args.outdir, f"tuning_{small_model}_to_{args.large}_precision.csv"
        )
        precision.to_csv(precision_path, index=False)

        # 2. Simulate every k from accepting no categories to accepting every
        # category observed in valid small-model predictions.
        print("2) Cascade simulation for each k")
        header = (
            f"{'k':>2} {'escalated':>12} {'overall acc':>12} "
            f"{'slipped':>8} {'accepted acc':>13} {'escalated acc':>14} "
            f"{'mean s':>9} {'median s':>10} {'simple mean':>12}"
        )
        print(header)

        summary_rows = []
        for k in range(len(order) + 1):
            accepted_categories = order[:k]
            accept_mask = df["small"].isin(accepted_categories)

            # Invalid small predictions are not in the acceptance list and escalate.
            final = df["small"].where(accept_mask, df["large"])

            cascade_right = int(final.eq(df["true"]).sum())
            cascade_wrong = n - cascade_right
            slipped = int(
                (accept_mask & ~df["small"].eq(df["true"])).sum()
            )

            accepted_n = int(accept_mask.sum())
            escalated_n = int((~accept_mask).sum())
            accepted_right = int(
                (accept_mask & final.eq(df["true"])).sum()
            )
            escalated_right = int(
                ((~accept_mask) & df["large"].eq(df["true"])).sum()
            )

            accepted_accuracy = pct(accepted_right, accepted_n)
            escalated_accuracy = pct(escalated_right, escalated_n)

            # Per-ticket simulated sequential latency: small model always runs;
            # large model time is added only for escalated tickets.
            simulated_latency = df["s_s"] + df["l_s"].where(~accept_mask, 0.0)
            per_ticket_mean = safe_mean(simulated_latency)
            per_ticket_median = safe_median(simulated_latency)

            # Retain the lecturer's simplified mean-latency estimate as a
            # comparable reference alongside the more detailed per-ticket estimate.
            simplified_mean = (
                small_mean + (escalated_n / n) * large_mean
            )

            escalation_pct = pct(escalated_n, n)
            overall_accuracy = pct(cascade_right, n)

            summary_rows.append(
                {
                    "k": k,
                    "accept": "; ".join(accepted_categories),
                    "accepted_categories_count": len(accepted_categories),
                    "accepted": accepted_n,
                    "accepted_pct": round(pct(accepted_n, n), 2),
                    "accepted_right": accepted_right,
                    "accepted_accuracy_pct": round(accepted_accuracy, 2)
                    if np.isfinite(accepted_accuracy) else np.nan,
                    "escalated": escalated_n,
                    "escalated_pct": round(escalation_pct, 2),
                    "escalated_right": escalated_right,
                    "escalated_accuracy_pct": round(escalated_accuracy, 2)
                    if np.isfinite(escalated_accuracy) else np.nan,
                    "cascade_right": cascade_right,
                    "cascade_wrong": cascade_wrong,
                    "cascade_acc_pct": round(overall_accuracy, 2),
                    "slipped": slipped,
                    "per_ticket_mean_s": round(per_ticket_mean, 4),
                    "per_ticket_median_s": round(per_ticket_median, 4),
                    "simplified_mean_s": round(simplified_mean, 4),
                    "large_only_mean_s": round(large_mean, 4),
                    "faster_than_large_only_estimate": bool(
                        per_ticket_mean < large_mean
                    ),
                }
            )

            print(
                f"{k:>2} {escalated_n:>5}/{n} {escalation_pct:>5.1f}% "
                f"{overall_accuracy:>7.1f}% {slipped:>8} "
                f"{accepted_accuracy:>12.1f}% "
                f"{escalated_accuracy:>13.1f}% "
                f"{per_ticket_mean:>9.2f} {per_ticket_median:>10.2f} "
                f"{simplified_mean:>12.2f}"
            )

            # 3. Per-TRUE-category analysis and tuning-only tolerance diagnostic.
            category_summary = category_results_for_setting(
                df, final, accept_mask, k, args.tolerance_pp
            )
            category_path = os.path.join(
                args.outdir,
                f"tuning_{small_model}_to_{args.large}_k{k}_categories.csv",
            )
            category_summary.to_csv(category_path, index=False)

        # Save the original k-table filename for compatibility.
        summary_path = os.path.join(
            args.outdir, f"tuning_{small_model}_to_{args.large}.csv"
        )
        summary_df = pd.DataFrame(summary_rows)
        summary_df.to_csv(summary_path, index=False)

        print("\n3) Per-category accuracy and change vs large-model baseline")
        for k in (4, 5, 6):
            if k >= len(summary_rows):
                continue
            accept_categories = order[:k]
            accept_mask = df["small"].isin(accept_categories)
            final = df["small"].where(accept_mask, df["large"])
            category_summary = category_results_for_setting(
                df, final, accept_mask, k, args.tolerance_pp
            )
            print(f"\n   k={k}: accepted {len(accept_categories)} predicted categories")
            print(
                category_summary[
                    [
                        "true_category",
                        "tickets",
                        "baseline_acc_%",
                        "cascade_acc_%",
                        "accuracy_change_pp",
                        "tuning_floor_%",
                        "within_tuning_tolerance",
                    ]
                ].round(2).to_string(index=False)
            )
            failures = category_summary[
                ~category_summary["within_tuning_tolerance"]
            ]
            if failures.empty:
                print("   Tuning diagnostic: all represented categories are within "
                      f"{args.tolerance_pp:.1f} pp of the tuning large-model baseline.")
            else:
                print("   Tuning diagnostic WARNING: category/categories below the "
                      f"{args.tolerance_pp:.1f} pp tuning-equivalent tolerance: "
                      + ", ".join(failures["true_category"].astype(str).tolist()))

        print("\n4) Ticket length vs small-model errors")
        # Rank first to make qcut robust when many tickets have the same word count.
        length_groups = pd.qcut(
            df["words"].rank(method="first"),
            q=3,
            labels=["short", "medium", "long"],
        )
        length_df = df.assign(length=length_groups)
        length_summary = (
            length_df.groupby("length", observed=True)
            .agg(
                tickets=("true", "count"),
                median_words=("words", "median"),
                small_wrong=("small", lambda s: int(
                    (~s.eq(length_df.loc[s.index, "true"])).sum()
                )),
            )
            .reset_index()
        )
        length_summary["error_%"] = (
            100 * length_summary["small_wrong"] / length_summary["tickets"]
        )
        print(length_summary.round(2).to_string(index=False))

        print("\n5) Saved outputs")
        print(f"   Overall k table:       {summary_path}")
        print(f"   Predicted-category:   {precision_path}")
        print(
            f"   Per-category tables:  "
            f"{os.path.join(args.outdir, f'tuning_{small_model}_to_{args.large}_k*_categories.csv')}"
        )
        print(
            "   Reminder: per-category tolerance results above are tuning diagnostics, "
            "not official test-set pass/fail results."
        )
        print(
            "   Reminder: per-ticket latency is estimated from A1 timings, not measured "
            "live cascade latency.\n"
        )


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, KeyError, pd.errors.ParserError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
