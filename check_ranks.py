#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

DEFAULT_INPUT = Path("spa-eng-renumbered.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that CSV ranks are consecutive and increase by exactly 1."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"CSV file to verify (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="Expected first rank value (default: 1).",
    )
    return parser.parse_args()


def rank_column_index(header: list[str]) -> int:
    for index, name in enumerate(header):
        if name.strip().lower() == "rank":
            return index
    return 0


def main() -> None:
    args = parse_args()
    input_path = args.input

    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise SystemExit(f"Input CSV is empty: {input_path}") from exc

        if not header:
            raise SystemExit(f"Input CSV has an empty header row: {input_path}")

        column_index = rank_column_index(header)
        expected_rank = args.start
        checked_rows = 0

        for row_number, row in enumerate(reader, start=2):
            if not row:
                continue
            if column_index >= len(row):
                raise SystemExit(
                    f"Row {row_number} is missing the rank column at index {column_index}."
                )

            raw_rank = row[column_index].strip()
            if not raw_rank:
                raise SystemExit(f"Row {row_number} has a blank rank value.")
            if not raw_rank.isdigit():
                raise SystemExit(f"Row {row_number} has a non-integer rank: {raw_rank!r}.")

            actual_rank = int(raw_rank)
            if actual_rank != expected_rank:
                raise SystemExit(
                    f"Row {row_number} has rank {actual_rank}, expected {expected_rank}."
                )

            checked_rows += 1
            expected_rank += 1

    print(
        f"OK: {checked_rows} rows verified in {input_path}. "
        f"Ranks run consecutively from {args.start} to {expected_rank - 1}."
    )


if __name__ == "__main__":
    main()
