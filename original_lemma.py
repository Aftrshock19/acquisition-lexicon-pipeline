import csv
import argparse
from pathlib import Path

FIRST_CSV_REQUIRED = {"lemma", "rank", "translation", "original_lemma", "pos"}
SECOND_CSV_REQUIRED = {
    "rank",
    "lemma",
    "translation",
    "pos",
    "sentence",
    "english_sentence",
}

OUTPUT_FIELDS = [
    "rank",
    "lemma",
    "original_lemma",
    "translation",
    "pos",
    "sentence",
    "english_sentence",
]


def load_original_lemmas(path: Path) -> dict[str, str]:
    lemma_to_original: dict[str, str] = {}

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames or not FIRST_CSV_REQUIRED.issubset(reader.fieldnames):
            raise ValueError(
                "First CSV must contain: lemma, rank, translation, original_lemma, pos"
            )

        for row in reader:
            lemma = (row.get("lemma") or "").strip()
            original_lemma = (row.get("original_lemma") or "").strip()

            if not lemma:
                continue

            if lemma not in lemma_to_original:
                lemma_to_original[lemma] = original_lemma
            elif not lemma_to_original[lemma] and original_lemma:
                lemma_to_original[lemma] = original_lemma

    return lemma_to_original


def add_original_lemma(
    first_csv_path: Path,
    second_csv_path: Path,
    output_path: Path,
) -> None:
    lemma_to_original = load_original_lemmas(first_csv_path)

    with second_csv_path.open("r", encoding="utf-8", newline="") as infile, \
         output_path.open("w", encoding="utf-8", newline="") as outfile:

        reader = csv.DictReader(infile)

        if not reader.fieldnames or not SECOND_CSV_REQUIRED.issubset(reader.fieldnames):
            raise ValueError(
                "Second CSV must contain: rank, lemma, translation, pos, sentence, english_sentence"
            )

        writer = csv.DictWriter(outfile, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()

        for row in reader:
            lemma = (row.get("lemma") or "").strip()
            original_lemma = lemma_to_original.get(lemma, "")

            writer.writerow({
                "rank": row.get("rank", ""),
                "lemma": row.get("lemma", ""),
                "original_lemma": original_lemma,
                "translation": row.get("translation", ""),
                "pos": row.get("pos", ""),
                "sentence": row.get("sentence", ""),
                "english_sentence": row.get("english_sentence", ""),
            })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-csv", required=True, help="CSV with original_lemma column")
    parser.add_argument("--second-csv", required=True, help="Merged CSV to enrich")
    parser.add_argument("--output", required=True, help="Output CSV path")
    args = parser.parse_args()

    add_original_lemma(
        Path(args.first_csv),
        Path(args.second_csv),
        Path(args.output),
    )


if __name__ == "__main__":
    main()