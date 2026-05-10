import csv
import argparse
from pathlib import Path

FIELDNAMES = [
    "rank",
    "lemma",
    "translation",
    "pos",
    "sentence",
    "english_sentence",
]

def renumber_ranks(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)

        if not reader.fieldnames or not set(FIELDNAMES).issubset(reader.fieldnames):
            raise ValueError(
                "CSV must contain: rank, lemma, translation, pos, sentence, english_sentence"
            )

        rows = list(reader)

    for i, row in enumerate(rows, start=1):
        row["rank"] = str(i)

    with output_path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    renumber_ranks(Path(args.input), Path(args.output))

if __name__ == "__main__":
    main()