import csv
import argparse
from pathlib import Path

def clean_merged_csv(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        required = {
            "rank",
            "lemma",
            "translation",
            "pos",
            "sentence",
            "english_sentence",
        }
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                "merged.csv must contain: "
                "rank, lemma, translation, pos, sentence, english_sentence"
            )

        rows = [
            row for row in reader
            if (row.get("translation") or "").strip()
            and (row.get("sentence") or "").strip() != "SKIP"
        ]

    with output_path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(
            outfile,
            fieldnames=[
                "rank",
                "lemma",
                "translation",
                "pos",
                "sentence",
                "english_sentence",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    clean_merged_csv(Path(args.input), Path(args.output))

if __name__ == "__main__":
    main()