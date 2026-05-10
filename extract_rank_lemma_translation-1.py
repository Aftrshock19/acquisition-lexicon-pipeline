#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reduce a CSV to rank, lemma, and translation columns."
    )
    parser.add_argument(
        "input_csv",
        nargs="?",
        default="spa-eng.csv",
        help="Path to the source CSV file.",
    )
    parser.add_argument(
        "output_csv",
        nargs="?",
        default="spa-eng-rank-lemma-translation.csv",
        help="Path to the reduced CSV file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)

    with input_path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        if reader.fieldnames is None:
            raise ValueError("Input CSV is missing a header row.")

        required_columns = {"rank", "lemma", "translation"}
        missing = required_columns - set(reader.fieldnames)
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(f"Input CSV is missing required columns: {missing_list}")

        with output_path.open("w", encoding="utf-8", newline="") as outfile:
            writer = csv.DictWriter(
                outfile, fieldnames=["rank", "lemma", "translation"]
            )
            writer.writeheader()

            for row in reader:
                writer.writerow(
                    {
                        "rank": row["rank"],
                        "lemma": row["lemma"],
                        "translation": row["translation"],
                    }
                )


if __name__ == "__main__":
    main()
