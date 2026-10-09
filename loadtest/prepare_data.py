"""
prepare_data.py - build the load-test input files from the team's rows CSV.

Reads golden_set/team20_rows_20000_20999.csv (columns: row, source_label, narrative),
skips empty narratives, and writes (deterministic, random seed 42):

  loadtest/data/pool.tsv         all rows shuffled, no header
  loadtest/data/long.tsv         only rows whose narrative is longer than 1227 chars
  loadtest/data/search_terms.txt 200 random alphabetic words (>=5 letters, no "xx")

Each .tsv line is two TAB-separated columns: row and the JSON-escaped narrative
(json.dumps(narrative)[1:-1] -> no surrounding quotes, single line, no raw tabs).
"""
import csv
import json
import os
import random
import re

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "..", "golden_set", "team20_rows_20000_20999.csv")
OUT = os.path.join(BASE, "data")

random.seed(42)


def enc(narrative):
    """JSON-escape the narrative and drop the surrounding double quotes."""
    return json.dumps(narrative, ensure_ascii=False)[1:-1]


rows = []
skipped_empty = 0
with open(SRC, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        narrative = (r.get("narrative") or "").strip()
        if not narrative:
            skipped_empty += 1
            continue
        rows.append((r["row"], narrative))

os.makedirs(OUT, exist_ok=True)

# a. pool.tsv: all rows shuffled, no header
shuffled = list(rows)
random.shuffle(shuffled)
with open(os.path.join(OUT, "pool.tsv"), "w", encoding="utf-8") as f:
    for row, narrative in shuffled:
        f.write(f"{row}\t{enc(narrative)}\n")

# b. long.tsv: only rows with narrative longer than 1227 chars
longs = [(row, narrative) for row, narrative in rows if len(narrative) > 1227]
with open(os.path.join(OUT, "long.tsv"), "w", encoding="utf-8") as f:
    for row, narrative in longs:
        f.write(f"{row}\t{enc(narrative)}\n")

# c. search_terms.txt: 200 random words drawn from the narratives
words = set()
for _, narrative in rows:
    for w in re.findall(r"[A-Za-z]+", narrative):
        wl = w.lower()
        if len(wl) >= 5 and "xx" not in wl:
            words.add(wl)
words = sorted(words)
random.shuffle(words)
terms = words[:200]
with open(os.path.join(OUT, "search_terms.txt"), "w", encoding="utf-8") as f:
    for t in terms:
        f.write(t + "\n")

print(f"team rows read: {len(rows)}")
print(f"empty narratives skipped: {skipped_empty}")
print(f"pool.tsv rows: {len(shuffled)}")
print(f"long.tsv rows (narrative > 1227 chars): {len(longs)}")
print(f"search terms: {len(terms)}")
