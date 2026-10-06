"""
compute_agreement.py

Calculates the inter-annotator agreement (Cohen's kappa) between our two
annotators for the golden test set, and lists out every ticket that we need
to discuss (disagreements + AMBIGUOUS ones) so we can resolve them as a team.

Usage:
    python compute_agreement.py G20_labels_annotatorA.xlsx G20_labels_annotatorB.xlsx

Requirements:
    pip install pandas openpyxl scikit-learn

Outputs:
    agreement_report.txt          -> kappa, raw agreement, confusion table, per-category agreement
    disagreements_to_resolve.xlsx -> tickets to go through during our resolution meeting

Note: AMBIGUOUS is counted as its own label when computing kappa. We did this
so the kappa reflects what the annotators actually picked, instead of
quietly dropping the tickets we were unsure about.
"""
import sys
import pandas as pd
from sklearn.metrics import cohen_kappa_score

# ---------------------------------------------------------------------------
# 1. Load both annotators' label sheets
# ---------------------------------------------------------------------------
# File paths come from the command line (A first, then B), so the same script
# works if we ever add a third annotator - we just run it on a different pair.
a_path, b_path = sys.argv[1], sys.argv[2]

def load_sheet(path):
    """Read one annotator's sheet and keep only the columns we need.
    """
    df = pd.read_excel(path)
    notes_col = next(c for c in df.columns if str(c).lower().startswith("notes"))
    df = df.rename(columns={notes_col: "notes"})
    return df[["golden_id", "row", "narrative", "label", "confidence", "notes"]]

a = load_sheet(a_path)
b = load_sheet(b_path)

# Join the two sheets on the ticket itself (ID + row + narrative), so A's label
# and B's label for the same ticket end up on the same row. The suffixes rename
# the overlapping columns to label_A / confidence_A / notes_A and
# label_B / confidence_B / notes_B. Because pandas keeps all of A's columns
# first and then B's, the output order is already what we want:
#   label_A, confidence_A, notes_A, label_B, confidence_B, notes_B
# Merging on all three fields also works as a sanity check: if someone edited a
# narrative or messed up a row by accident, that ticket won't match.
m = a.merge(b, on=["golden_id", "row", "narrative"], suffixes=("_A", "_B"))

# ---------------------------------------------------------------------------
# 2. Validation: make sure both annotators finished labelling
# ---------------------------------------------------------------------------
# A blank label would give us a kappa based on incomplete data, so stop early
# and show which tickets are still missing a label.
missing = m[m.label_A.isna() | m.label_B.isna()]
if len(missing):
    sys.exit(f"{len(missing)} tickets are unlabelled, e.g. {missing.golden_id.head().tolist()}; finish labelling first.")

# ---------------------------------------------------------------------------
# 3. Calculate agreement
# ---------------------------------------------------------------------------
n = len(m)

# agree is a True/False column: True where A and B picked the same label.
agree = (m.label_A == m.label_B)

# p_o (observed agreement) = fraction of tickets where we agreed.
# The mean of a True/False column is just the proportion of True values.
po = agree.mean()

# Cohen's kappa from sklearn. This is the number that goes on our slides.
kappa = cohen_kappa_score(m.label_A, m.label_B)

# Every label that either annotator used (including AMBIGUOUS if anyone used it).
labels = sorted(set(m.label_A) | set(m.label_B))

# p_e (chance agreement) = how often we'd agree just by luck.
# For each label: P(A picks it) x P(B picks it), then add them all up.
# We calculate this by hand so we can show the working in the report,
# since sklearn only gives us the final kappa.
pa, pb = m.label_A.value_counts(normalize=True), m.label_B.value_counts(normalize=True)
pe = sum(pa.get(l, 0) * pb.get(l, 0) for l in labels)

# ---------------------------------------------------------------------------
# 4. Build the agreement report
# ---------------------------------------------------------------------------
out = []
out.append(f"Tickets: {n}")
out.append(f"Raw agreement (p_o): {agree.sum()}/{n} = {po:.3f}")
out.append(f"Chance agreement (p_e): {pe:.3f}")
out.append(f"Cohen's kappa = (p_o - p_e) / (1 - p_e) = {kappa:.3f}")
# Landis & Koch scale, used to interpret what our kappa value means
out.append("Landis & Koch: <0.20 slight, 0.21-0.40 fair, 0.41-0.60 moderate, 0.61-0.80 substantial, >0.80 almost perfect\n")

# Confusion table between the two annotators. The diagonal is where we agreed;
# anything off the diagonal shows which pairs of categories we keep mixing up
# (e.g. Credit reporting vs Debt collection).
out.append("Confusion (rows = Annotator A, cols = Annotator B):")
out.append(pd.crosstab(m.label_A, m.label_B).to_string())

# Per-category agreement: out of all the tickets where at least one of us
# picked this category, how often did we BOTH pick it? A low score means
# that category's definition in the protocol probably needs to be clearer.
out.append("\nPer-category agreement (tickets where either annotator chose the category):")
for l in labels:
    either = (m.label_A == l) | (m.label_B == l)
    both = (m.label_A == l) & (m.label_B == l)
    out.append(f"  {l:28s} {both.sum():3d}/{either.sum():3d} = {both.sum()/either.sum():.2f}")

# Print to the terminal and also save to a file so we can commit it to the
# repo as evidence.
report = "\n".join(out)
print(report)
open("agreement_report.txt", "w").write(report)

# ---------------------------------------------------------------------------
# 5. Count AMBIGUOUS tickets
# ---------------------------------------------------------------------------
# True if at least one annotator marked the ticket AMBIGUOUS
# (protocol Rule 7: not enough info, so don't guess).
amb = (m.label_A == "AMBIGUOUS") | (m.label_B == "AMBIGUOUS")
out_amb = f"\nTickets marked AMBIGUOUS by at least one annotator: {amb.sum()}"
print(out_amb)
# Append ("a") instead of overwrite ("w") so the main report above is kept.
open("agreement_report.txt", "a").write(out_amb + "\n")

# ---------------------------------------------------------------------------
# 6. Export the tickets we need to discuss
# ---------------------------------------------------------------------------
# Every disagreement AND every AMBIGUOUS ticket goes into the resolution sheet.
# That includes tickets where BOTH of us picked AMBIGUOUS: technically we
# "agree", but AMBIGUOUS can't be a final golden label, so we still need to
# decide on a real category or remove the ticket.
d = m[(~agree) | amb].copy()

# Tag why each ticket is on the list, so it's clear during the meeting.
d["reason_for_discussion"] = ["AMBIGUOUS" if x else "disagreement" for x in amb[(~agree) | amb]]

# Empty columns that we fill in during the resolution meeting. This sheet is
# our evidence that each disagreement was actually discussed and resolved.
d["final_label (category or REMOVE)"] = ""
d["resolution_reason"] = ""
d["protocol_change (rule id / none)"] = ""   # e.g. "added Rule 10" if the protocol was missing something
# No "agreed_by" column: the resolution is done by the same annotators (A and B),
# so it would just be the same names on every row.

d.to_excel("disagreements_to_resolve.xlsx", index=False)
print(f"\n{len(d)} tickets (disagreements + AMBIGUOUS) written to disagreements_to_resolve.xlsx")