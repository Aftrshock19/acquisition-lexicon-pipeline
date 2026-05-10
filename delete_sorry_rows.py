#!/usr/bin/env python3
"""
delete_sorry_rows.py

Removes rows where definitions is empty AND english_definition contains "I'm sorry".
Reads spa-eng-final-fixed2.csv, writes spa-eng-final-fixed2.csv (in-place).
"""

import csv
from pathlib import Path

INPUT = "spa-eng-final-fixed2.csv"

rows_kept = []
rows_deleted = 0

with open(INPUT, newline="") as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        defn = row[4] if len(row) > 4 else ""
        eng  = row[5] if len(row) > 5 else ""
        if not defn.strip() and "I'm sorry" in eng:
            rows_deleted += 1
        else:
            rows_kept.append(row)

with open(INPUT, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(rows_kept)

print(f"Deleted {rows_deleted} rows. Kept {len(rows_kept)}. Saved to {INPUT}")
