import csv
import argparse
from pathlib import Path


def load_sentences(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"rank", "sentence", "english_sentence"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                f"{path} must contain these columns: rank, sentence, english_sentence"
            )

        data = {}
        for row in reader:
            rank = (row.get("rank") or "").strip()
            if rank:
                data[rank] = {
                    "sentence": row.get("sentence", ""),
                    "english_sentence": row.get("english_sentence", ""),
                }
        return data


def merge_csvs(lemma_path: Path, sentences_path: Path, output_path: Path) -> None:
    sentences_by_rank = load_sentences(sentences_path)

    with lemma_path.open("r", encoding="utf-8", newline="") as lemma_file, \
         output_path.open("w", encoding="utf-8", newline="") as out_file:

        lemma_reader = csv.DictReader(lemma_file)
        required = {"lemma", "rank", "translation", "pos"}
        if not lemma_reader.fieldnames or not required.issubset(lemma_reader.fieldnames):
            raise ValueError(
                f"{lemma_path} must contain these columns: lemma, rank, translation, pos"
            )

        fieldnames = ["rank", "lemma", "translation", "pos", "sentence", "english_sentence"]
        writer = csv.DictWriter(out_file, fieldnames=fieldnames)
        writer.writeheader()

        for row in lemma_reader:
            rank = (row.get("rank") or "").strip()
            if not rank:
                continue
            if rank not in sentences_by_rank:
                continue

            writer.writerow({
                "rank": rank,
                "lemma": row.get("lemma", ""),
                "translation": row.get("translation", ""),
                "pos": row.get("pos", ""),
                "sentence": sentences_by_rank[rank]["sentence"],
                "english_sentence": sentences_by_rank[rank]["english_sentence"],
            })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lemma-csv", required=True, help="Path to lemma_translation.csv")
    parser.add_argument("--sentences-csv", required=True, help="Path to final_sentences_en.csv")
    parser.add_argument("--output", required=True, help="Path to merged output CSV")
    args = parser.parse_args()

    merge_csvs(
        Path(args.lemma_csv),
        Path(args.sentences_csv),
        Path(args.output),
    )


if __name__ == "__main__":
    main()