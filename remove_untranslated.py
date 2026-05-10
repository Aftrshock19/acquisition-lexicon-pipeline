#!/usr/bin/env python3
import argparse
import csv


def is_translated(row: dict) -> bool:
    translated_flag = (row.get("translated_flag") or "").strip().upper()
    lemma_translated = (row.get("lemma_translated") or "").strip()

    if translated_flag == "TRUE":
        return True

    if lemma_translated and not lemma_translated.startswith("[UNTRANSLATED]"):
        return True

    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove rows that were not translated."
    )
    parser.add_argument("--input", required=True, help="Input CSV")
    parser.add_argument("--output", required=True, help="Output CSV")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise ValueError("Input CSV has no headers.")

        rows = [row for row in reader if is_translated(row)]
        fieldnames = reader.fieldnames

    with open(args.output, "w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Kept {len(rows)} translated rows.")
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()