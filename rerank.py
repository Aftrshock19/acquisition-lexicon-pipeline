#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

DEFAULT_INPUT = Path("spa-eng.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Renumber the first column of a CSV while preserving the header."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"CSV file to renumber (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional output path. Defaults to a new sibling file named <input>-renumbered.csv.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting an existing output file.",
    )
    return parser.parse_args()


def default_output_path(input_path: Path) -> Path:
    suffix = input_path.suffix or ".csv"
    return input_path.with_name(f"{input_path.stem}-renumbered{suffix}")


def same_path(left: Path, right: Path) -> bool:
    return left.resolve(strict=False) == right.resolve(strict=False)


def main() -> None:
    args = parse_args()
    input_path = args.input
    output_path = args.output or default_output_path(input_path)

    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")
    if same_path(input_path, output_path):
        raise SystemExit("Refusing to overwrite the input file. Choose a different output path.")
    if output_path.exists() and not args.force:
        raise SystemExit(
            f"Output file already exists: {output_path}. Use --force to overwrite it."
        )

    rows = []
    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise SystemExit(f"Input CSV is empty: {input_path}") from exc

        if not header:
            raise SystemExit(f"Input CSV has an empty header row: {input_path}")

        next_rank = 1
        for row in reader:
            if not row:
                continue
            row[0] = str(next_rank)
            rows.append(row)
            next_rank += 1

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"Wrote {output_path} with {len(rows)} renumbered rows.")


if __name__ == "__main__":
    main()
