#!/usr/bin/env python3
"""
Detect Spanish imperative forms in a CSV and append bracket context to translation.

Usage:
  python3 add_imperative.py
  python3 add_imperative.py --input spa-eng.csv --output spa-eng-imperative.csv
  python3 add_imperative.py --allow-regular-tu
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

DEFAULT_INPUT = Path("spa-eng.csv")
DEFAULT_OUTPUT = Path("spa-eng-imperative.csv")

OUTPUT_FIELDNAMES = [
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

# (original_lemma, lemma) -> (relation, person, number, polarity, confidence, reason)
MANUAL_IMPERATIVE_MAP: dict[tuple[str, str], tuple[str, str, str, str, str, str]] = {
    ("decir", "di"):  ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("hacer", "haz"): ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("ir",    "ve"):  ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("poner", "pon"): ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("salir", "sal"): ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("ser",   "sé"):  ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("tener", "ten"): ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("venir", "ven"): ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("ser",   "sed"): ("imperative_form", "vosotros", "plural", "affirmative", "high", "manual_irregular_vosotros"),
    ("ir",    "id"):  ("imperative_form", "vosotros", "plural", "affirmative", "high", "manual_irregular_vosotros"),
}


def normalize_pos(pos: str) -> str:
    if not pos:
        return ""
    p = pos.strip().lower()
    return "v" if p in {"v", "verb"} else p


def has_brackets(text: str) -> bool:
    return bool(re.search(r"\([^()]*\)", text or ""))


def clean_translation(raw: str) -> str:
    if not raw:
        return ""
    cleaned = re.sub(r"\s*\([^()]*\)", "", raw).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    parts = [p.strip() for p in cleaned.split(";") if p.strip()]
    deduped: list[str] = []
    for p in parts:
        if p not in deduped:
            deduped.append(p)
    return "; ".join(deduped)


def infer_imperative_form(
    lemma: str,
    original_lemma: str,
    pos: str,
    allow_regular_tu: bool = False,
) -> tuple[str, str, str, str, str, str]:
    """
    Returns (relation, person, number, polarity, confidence, reason).
    """
    lemma = (lemma or "").strip().lower()
    original = (original_lemma or "").strip().lower()
    pos = normalize_pos(pos)

    if pos != "v":
        return ("unknown", "", "", "", "", "pos_not_supported")

    if not original.endswith(("ar", "er", "ir")):
        return ("unknown", "", "", "", "", "original_not_infinitive")

    manual = MANUAL_IMPERATIVE_MAP.get((original, lemma))
    if manual:
        return manual

    # Affirmative vosotros: drop final r, add d
    if lemma == original[:-1] + "d":
        return ("imperative_form", "vosotros", "plural", "affirmative", "high", "regular_vosotros_imperative")

    if allow_regular_tu:
        stem = original[:-2]
        ending = original[-2:]

        if ending == "ar" and lemma == stem + "a":
            return ("imperative_form", "tú", "singular", "affirmative", "low", "regular_tu_ar_ambiguous")
        if ending in {"er", "ir"} and lemma == stem + "e":
            return ("imperative_form", "tú", "singular", "affirmative", "low", "regular_tu_er_ir_ambiguous")

    return ("not_imperative_form", "", "", "", "", "no_match")


def append_imperative_context_if_safe(
    raw_translation: str,
    cleaned_translation: str,
    person: str,
    polarity: str,
) -> str:
    if not person:
        if has_brackets(raw_translation):
            return raw_translation.strip()
        return cleaned_translation

    imperative_part = f"{polarity} imperative {person}"

    # If the translation already has a bracket, append inside it
    m = re.search(r"\(([^()]*)\)\s*$", raw_translation.strip())
    if m:
        existing = m.group(1).strip()
        base = raw_translation[: m.start()].strip()
        if imperative_part in existing:
            return raw_translation.strip()
        inner = f"{existing}; {imperative_part}"
        return f"{base} ({inner})"

    suffix = f" ({imperative_part})"
    if cleaned_translation.endswith(suffix):
        return cleaned_translation
    return f"{cleaned_translation}{suffix}"


def build_tags(existing_tags: str, person: str, number: str, polarity: str) -> str:
    tags: list[str] = [t for t in existing_tags.split("|") if t] if existing_tags else []

    if person:
        if person == "tú":
            tags.append("tú")
        elif person == "vosotros":
            tags.append("vosotros")
        tags.append("2nd_person")
        tags.append(number)
        tags.append("imperative")
        if polarity:
            tags.append(polarity)

    seen: set[str] = set()
    deduped: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            deduped.append(tag)
    return "|".join(deduped)


def rewrite_row(row: dict[str, str], allow_regular_tu: bool) -> dict[str, str]:
    row = dict(row)
    lemma = row.get("lemma", "").strip()
    original_lemma = row.get("original_lemma", "").strip()
    pos = row.get("pos", "").strip()
    raw_translation = row.get("translation", "").strip()

    relation, person, number, polarity, confidence, reason = infer_imperative_form(
        lemma, original_lemma, pos, allow_regular_tu
    )

    row["imperative_relation"] = relation
    row["imperative_person"] = person
    row["imperative_number"] = number
    row["imperative_polarity"] = polarity
    row["imperative_confidence"] = confidence
    row["imperative_reason"] = reason

    cleaned = clean_translation(raw_translation)
    row["translation"] = append_imperative_context_if_safe(raw_translation, cleaned, person, polarity)
    row["tags"] = build_tags(row.get("tags", ""), person, number, polarity)

    return row


def output_fieldnames(fieldnames: list[str]) -> list[str]:
    required = {"rank", "lemma", "original_lemma", "translation", "pos"}
    missing = [name for name in required if name not in set(fieldnames)]
    if missing:
        raise SystemExit(f"Input CSV is missing required columns: {', '.join(missing)}")
    return OUTPUT_FIELDNAMES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect Spanish imperative forms and annotate translations.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--allow-regular-tu",
        action="store_true",
        default=False,
        help="Also detect regular tú imperatives (low confidence, ambiguous with present indicative).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    review_log_path = output_path.with_name(f"{output_path.stem}-imperative-review.csv")

    with input_path.open("r", newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise SystemExit("Input CSV has no header row.")
        fieldnames = output_fieldnames(list(reader.fieldnames))
        original_rows = list(reader)

    rows = [rewrite_row(row, args.allow_regular_tu) for row in original_rows]

    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    review_rows = []
    for old_row, new_row in zip(original_rows, rows):
        old_t = (old_row.get("translation", "") or "").strip()
        new_t = (new_row.get("translation", "") or "").strip()
        if old_t != new_t:
            review_rows.append({
                "rank": new_row.get("rank", ""),
                "lemma": new_row.get("lemma", ""),
                "original_lemma": new_row.get("original_lemma", ""),
                "new_translation": new_t,
                "imperative_person": new_row.get("imperative_person", ""),
                "imperative_polarity": new_row.get("imperative_polarity", ""),
                "reason": new_row.get("imperative_reason", ""),
            })

    with review_log_path.open("w", newline="", encoding="utf-8") as logfile:
        writer = csv.DictWriter(
            logfile,
            fieldnames=["rank", "lemma", "original_lemma", "new_translation", "imperative_person", "imperative_polarity", "reason"],
        )
        writer.writeheader()
        writer.writerows(review_rows)

    print(f"Saved {len(rows)} rows to {output_path}.")
    print(f"Saved {len(review_rows)} changed rows to {review_log_path}.")


if __name__ == "__main__":
    main()
