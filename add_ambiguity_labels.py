#!/usr/bin/env python3
"""
Append fixed ambiguity labels to translations for ser, estar, haber, and tener.

Usage:
  python3 add_ambiguity_labels.py
  python3 add_ambiguity_labels.py --input spa-eng.csv --output spa-eng-ambiguity-labels.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

DEFAULT_INPUT = Path("spa-eng.csv")
DEFAULT_OUTPUT = Path("spa-eng-ambiguity-labels.csv")

OUTPUT_COLUMNS = [
    "rank",
    "lemma",
    "original_lemma",
    "translation",
    "definitions",
    "english_definition",
    "pos",
    "tags",
    "sentence",
    "english_sentence",
]

REQUIRED_COLUMNS = set(OUTPUT_COLUMNS)

AMBIGUITY_LABELS = {
    "ser": "identity/essence/origin/time",
    "estar": "state/location/result",
    "haber": "auxiliary/existence",
    "tener": "possession/age/state/obligation",
}

FINAL_PARENTHETICAL_RE = re.compile(r"^(.*)\(([^()]*)\)\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append fixed ambiguity labels to translations for ser, estar, haber, and tener."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def output_fieldnames(input_fieldnames: list[str]) -> list[str]:
    missing = [column for column in REQUIRED_COLUMNS if column not in set(input_fieldnames)]
    if missing:
        raise SystemExit(f"Input CSV is missing required columns: {', '.join(missing)}")
    return list(OUTPUT_COLUMNS)


def add_ambiguity_label(translation: str, original_lemma: str) -> str:
    normalized_lemma = (original_lemma or "").strip().lower()
    label = AMBIGUITY_LABELS.get(normalized_lemma)
    if not label:
        return translation

    text = (translation or "").strip()
    match = FINAL_PARENTHETICAL_RE.match(text)
    if not match:
        if not text:
            return f"({label})"
        return f"{text} ({label})"

    base = match.group(1).rstrip()
    existing_content = match.group(2).strip()

    if label in existing_content:
        return text

    if existing_content:
        return f"{base} ({existing_content}; {label})"
    return f"{base} ({label})"


def rewrite_row(row: dict[str, str]) -> dict[str, str]:
    row = dict(row)
    row["translation"] = add_ambiguity_label(
        translation=row.get("translation", ""),
        original_lemma=row.get("original_lemma", ""),
    )
    return row


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    with input_path.open("r", newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise SystemExit("Input CSV has no header row.")
        fieldnames = output_fieldnames(list(reader.fieldnames))
        rows = [rewrite_row(row) for row in reader]

    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} rows to {output_path}.")


if __name__ == "__main__":
    main()
