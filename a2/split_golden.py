"""
split_golden.py - A2 Step 1: split the frozen golden set into a tuning set and a test set.

Brief: "Sort your golden-set tickets by row number. Odd rows are your tuning set.
Even rows are your test set."

Our reading (stated on slide 1): sort the 185 golden tickets by the dataset `row` number, then
number them 1, 2, 3, ... in that sorted order. Odd POSITIONS (1st, 3rd, 5th, ...) -> tuning set.
Even POSITIONS (2nd, 4th, 6th, ...) -> test set. The golden_id is ignored, and so is whether the
`row` value itself is odd or even.

Usage (from the repo root):
    python a2/split_golden.py golden_set/golden_set_final.csv
Outputs:
    a2/tuning_set.csv, a2/test_set.csv   (same columns as the golden set)
"""
import sys

import pandas as pd

golden = pd.read_csv(sys.argv[1]).sort_values("row").reset_index(drop=True)
assert golden["row"].is_unique, "row numbers must be unique"

position = golden.index + 1                      # 1-based position in the sorted order
tuning = golden[position % 2 == 1]               # 1st, 3rd, 5th, ...
test = golden[position % 2 == 0]                 # 2nd, 4th, 6th, ...
assert len(tuning) + len(test) == len(golden) and not set(tuning["row"]) & set(test["row"])

tuning.to_csv("a2/tuning_set.csv", index=False)
test.to_csv("a2/test_set.csv", index=False)

print(f"Golden set: {len(golden)} tickets -> tuning {len(tuning)} (odd positions), test {len(test)} (even positions)\n")
counts = pd.DataFrame({"tuning": tuning["final_label"].value_counts(),
                       "test": test["final_label"].value_counts()}).fillna(0).astype(int)
counts.loc["TOTAL"] = counts.sum()
print(counts.to_string())
small = counts.drop("TOTAL")[counts.drop("TOTAL")["test"] < 10].index.tolist()
if small:
    print(f"\nCategories with < 10 test tickets (per-category limit is a weak test here): {small}")
else:
    print("\nEvery category has at least 10 test tickets.")
print(f"\nFirst tuning row numbers: {tuning['row'].head(4).tolist()} | first test row numbers: {test['row'].head(4).tolist()}")
