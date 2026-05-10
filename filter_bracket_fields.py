#!/usr/bin/env python3
"""
filter_bracket_fields.py

Extract fields from `stg_words_spa.csv` that contain parentheses.

The output CSV contains one row per matching field with:
  row_number,lemma,value

By default the script scans every column in `stg_words_spa.csv`. Use --columns
to limit the search to specific fields.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

INPUT_CSV = Path("stg_words_spa.csv")
PAREN_RE = re.compile(r"\([^()]*\)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Save only fields from stg_words_spa.csv that contain parentheses."
    )
    parser.add_argument(
        "--output",
        default="stg_words_spa_parentheses_fields.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--columns",
        nargs="+",
        help="Optional list of column names to clean. Defaults to all columns.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = INPUT_CSV
    output_path = Path(args.output)

    with input_path.open("r", newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise SystemExit("Input CSV has no header row.")

        columns = args.columns or fieldnames
        missing = [column for column in columns if column not in fieldnames]
        if missing:
            raise SystemExit(f"Unknown columns: {', '.join(missing)}")

        matches: list[dict[str, str]] = []

        for row_number, row in enumerate(reader, start=2):
            for column in columns:
                value = row.get(column)
                if value is None or not PAREN_RE.search(value):
                    continue
                matches.append(
                    {
                        "row_number": str(row_number),
                        "lemma": row.get("lemma", ""),
                        "value": value,
                    }
                )

    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=["row_number", "lemma", "value"])
        writer.writeheader()
        writer.writerows(matches)

    print(f"Saved {len(matches)} matching fields from {input_path} to {output_path}.")


if __name__ == "__main__":
    main()
