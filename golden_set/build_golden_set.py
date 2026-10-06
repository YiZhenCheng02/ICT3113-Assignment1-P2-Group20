"""
build_golden_set.py

Builds our FINAL golden test set after the resolution meeting.

How the final label is decided for each ticket:
  - A and B agreed (and it wasn't AMBIGUOUS) -> use the agreed label
  - Ticket was in disagreements_to_resolve  -> use the final label we decided in the meeting
  - Final label is REMOVE                   -> ticket is dropped from the golden set

Usage:
    python build_golden_set.py G20_labels_annotatorA.xlsx G20_labels_annotatorB.xlsx disagreements_to_resolve.xlsx

Outputs:
    golden_set_final.csv    -> golden_id, row, narrative, final_label, label_source
    removed_tickets.csv     -> tickets we removed and why
    golden_set_summary.txt  -> counts per category (for Slide 6)
"""
import sys
import pandas as pd

CATEGORIES = [
    "Credit reporting", "Debt collection", "Mortgage", "Credit card",
    "Bank account or service", "Consumer loan", "Money transfer or service",
]

a_path, b_path, res_path = sys.argv[1], sys.argv[2], sys.argv[3]

# ---------------------------------------------------------------------------
# 1. Load the raw labels and the resolution sheet
# ---------------------------------------------------------------------------
cols = ["golden_id", "row", "narrative", "label"]
a = pd.read_excel(a_path)[cols]
b = pd.read_excel(b_path)[cols]
m = a.merge(b, on=["golden_id", "row", "narrative"], suffixes=("_A", "_B"))

res = pd.read_excel(res_path)
# The column header is long, so find it by its prefix instead of typing it out.
final_col = next(c for c in res.columns if str(c).startswith("final_label"))
res = res.rename(columns={final_col: "final_label"})
res["final_label"] = res["final_label"].astype(str).str.strip()   # removes stray spaces typed in Excel

# ---------------------------------------------------------------------------
# 2. Validation: check that the resolution sheet is properly filled in
# ---------------------------------------------------------------------------
# Every ticket we discussed needs a valid final label AND a written reason.
# If not, stop here, because a half-finished resolution would give us a wrong golden set.
problems = []
for r in res.itertuples():
    if r.final_label not in CATEGORIES + ["REMOVE"]:
        problems.append(f"{r.golden_id}: final_label '{r.final_label}' is not one of the 7 categories or REMOVE")
    if pd.isna(r.resolution_reason) or str(r.resolution_reason).strip() == "":
        problems.append(f"{r.golden_id}: resolution_reason is empty")
if problems:
    print("Fix these in disagreements_to_resolve.xlsx first:")
    print("\n".join("  - " + p for p in problems))
    sys.exit(1)

# Every ticket that A and B did NOT cleanly agree on should be in the resolution
# sheet. This catches the case where someone accidentally deleted a row from it.
needs_resolution = m[(m.label_A != m.label_B) | (m.label_A == "AMBIGUOUS") | (m.label_B == "AMBIGUOUS")]
missing = set(needs_resolution.golden_id) - set(res.golden_id)
if missing:
    sys.exit(f"These tickets need a resolution but are missing from the sheet: {sorted(missing)}")

# ---------------------------------------------------------------------------
# 3. Work out the final label for every ticket
# ---------------------------------------------------------------------------
resolved = dict(zip(res.golden_id, res.final_label))
m["final_label"] = [resolved.get(g, la) for g, la in zip(m.golden_id, m.label_A)]
# label_source records HOW we got each label. It's useful evidence for Slide 6.
m["label_source"] = ["resolved" if g in resolved else "agreed" for g in m.golden_id]

removed = m[m.final_label == "REMOVE"].merge(res[["golden_id", "resolution_reason"]], on="golden_id")
golden = m[m.final_label != "REMOVE"][["golden_id", "row", "narrative", "final_label", "label_source"]]

# The brief says the golden set must be 150 to 200 tickets.
if not 150 <= len(golden) <= 200:
    print(f"WARNING: golden set has {len(golden)} tickets; the brief requires 150-200!")

# ---------------------------------------------------------------------------
# 4. Save outputs
# ---------------------------------------------------------------------------
golden.to_csv("golden_set_final.csv", index=False)
removed[["golden_id", "row", "label_A", "label_B", "resolution_reason"]].to_csv("removed_tickets.csv", index=False)

summary = [
    f"Final golden set: {len(golden)} tickets ({len(removed)} removed out of {len(m)})",
    f"  agreed directly by A and B : {(golden.label_source == 'agreed').sum()}",
    f"  decided in resolution      : {(golden.label_source == 'resolved').sum()}",
    "\nTickets per category:",
    golden.final_label.value_counts().reindex(CATEGORIES, fill_value=0).to_string(),
]
print("\n".join(summary))
open("golden_set_summary.txt", "w").write("\n".join(summary) + "\n")