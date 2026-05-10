#!/usr/bin/env python3
"""
Detect Spanish subjunctive forms in a CSV and append bracket context to translation.

Usage:
  python3 add_subjunctive.py
  python3 add_subjunctive.py --input spa-eng.csv --output spa-eng-subjunctive.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

DEFAULT_INPUT = Path("spa-eng.csv")
DEFAULT_OUTPUT = Path("spa-eng-subjunctive.csv")

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

# (original_lemma, lemma) -> (relation, tense, person, number, reason)
MANUAL_SUBJUNCTIVE_MAP: dict[tuple[str, str], tuple[str, str, str, str, str]] = {
    # ser — present subjunctive
    ("ser", "sea"):   ("subjunctive_form", "present", "singular_ambiguous", "singular", "manual_irregular"),
    ("ser", "seas"):  ("subjunctive_form", "present", "second", "singular", "manual_irregular"),
    ("ser", "seamos"):("subjunctive_form", "present", "first", "plural", "manual_irregular"),
    ("ser", "seáis"): ("subjunctive_form", "present", "second", "plural", "manual_irregular"),
    ("ser", "sean"):  ("subjunctive_form", "present", "third", "plural", "manual_irregular"),
    # ser — imperfect subjunctive -ra
    ("ser", "fuera"):    ("subjunctive_form", "imperfect_ra", "singular_ambiguous", "singular", "manual_irregular"),
    ("ser", "fueras"):   ("subjunctive_form", "imperfect_ra", "second", "singular", "manual_irregular"),
    ("ser", "fuéramos"): ("subjunctive_form", "imperfect_ra", "first", "plural", "manual_irregular"),
    ("ser", "fuerais"):  ("subjunctive_form", "imperfect_ra", "second", "plural", "manual_irregular"),
    ("ser", "fueran"):   ("subjunctive_form", "imperfect_ra", "third", "plural", "manual_irregular"),
    # ser — imperfect subjunctive -se
    ("ser", "fuese"):    ("subjunctive_form", "imperfect_se", "singular_ambiguous", "singular", "manual_irregular"),
    ("ser", "fueses"):   ("subjunctive_form", "imperfect_se", "second", "singular", "manual_irregular"),
    ("ser", "fuésemos"): ("subjunctive_form", "imperfect_se", "first", "plural", "manual_irregular"),
    ("ser", "fueseis"):  ("subjunctive_form", "imperfect_se", "second", "plural", "manual_irregular"),
    ("ser", "fuesen"):   ("subjunctive_form", "imperfect_se", "third", "plural", "manual_irregular"),

    # ir — present subjunctive
    ("ir", "vaya"):   ("subjunctive_form", "present", "singular_ambiguous", "singular", "manual_irregular"),
    ("ir", "vayas"):  ("subjunctive_form", "present", "second", "singular", "manual_irregular"),
    ("ir", "vayamos"):("subjunctive_form", "present", "first", "plural", "manual_irregular"),
    ("ir", "vayáis"): ("subjunctive_form", "present", "second", "plural", "manual_irregular"),
    ("ir", "vayan"):  ("subjunctive_form", "present", "third", "plural", "manual_irregular"),
    # ir — imperfect subjunctive -ra (shares stem with ser)
    ("ir", "fuera"):    ("subjunctive_form", "imperfect_ra", "singular_ambiguous", "singular", "manual_irregular"),
    ("ir", "fueras"):   ("subjunctive_form", "imperfect_ra", "second", "singular", "manual_irregular"),
    ("ir", "fuéramos"): ("subjunctive_form", "imperfect_ra", "first", "plural", "manual_irregular"),
    ("ir", "fuerais"):  ("subjunctive_form", "imperfect_ra", "second", "plural", "manual_irregular"),
    ("ir", "fueran"):   ("subjunctive_form", "imperfect_ra", "third", "plural", "manual_irregular"),
    # ir — imperfect subjunctive -se
    ("ir", "fuese"):    ("subjunctive_form", "imperfect_se", "singular_ambiguous", "singular", "manual_irregular"),
    ("ir", "fueses"):   ("subjunctive_form", "imperfect_se", "second", "singular", "manual_irregular"),
    ("ir", "fuésemos"): ("subjunctive_form", "imperfect_se", "first", "plural", "manual_irregular"),
    ("ir", "fueseis"):  ("subjunctive_form", "imperfect_se", "second", "plural", "manual_irregular"),
    ("ir", "fuesen"):   ("subjunctive_form", "imperfect_se", "third", "plural", "manual_irregular"),

    # haber — present subjunctive
    ("haber", "haya"):   ("subjunctive_form", "present", "singular_ambiguous", "singular", "manual_irregular"),
    ("haber", "hayas"):  ("subjunctive_form", "present", "second", "singular", "manual_irregular"),
    ("haber", "hayamos"):("subjunctive_form", "present", "first", "plural", "manual_irregular"),
    ("haber", "hayáis"): ("subjunctive_form", "present", "second", "plural", "manual_irregular"),
    ("haber", "hayan"):  ("subjunctive_form", "present", "third", "plural", "manual_irregular"),
    # haber — imperfect subjunctive -ra
    ("haber", "hubiera"):    ("subjunctive_form", "imperfect_ra", "singular_ambiguous", "singular", "manual_irregular"),
    ("haber", "hubieras"):   ("subjunctive_form", "imperfect_ra", "second", "singular", "manual_irregular"),
    ("haber", "hubiéramos"): ("subjunctive_form", "imperfect_ra", "first", "plural", "manual_irregular"),
    ("haber", "hubierais"):  ("subjunctive_form", "imperfect_ra", "second", "plural", "manual_irregular"),
    ("haber", "hubieran"):   ("subjunctive_form", "imperfect_ra", "third", "plural", "manual_irregular"),
    # haber — imperfect subjunctive -se
    ("haber", "hubiese"):    ("subjunctive_form", "imperfect_se", "singular_ambiguous", "singular", "manual_irregular"),
    ("haber", "hubieses"):   ("subjunctive_form", "imperfect_se", "second", "singular", "manual_irregular"),
    ("haber", "hubiésemos"): ("subjunctive_form", "imperfect_se", "first", "plural", "manual_irregular"),
    ("haber", "hubieseis"):  ("subjunctive_form", "imperfect_se", "second", "plural", "manual_irregular"),
    ("haber", "hubiesen"):   ("subjunctive_form", "imperfect_se", "third", "plural", "manual_irregular"),

    # estar — present subjunctive
    ("estar", "esté"):   ("subjunctive_form", "present", "singular_ambiguous", "singular", "manual_irregular"),
    ("estar", "estés"):  ("subjunctive_form", "present", "second", "singular", "manual_irregular"),
    ("estar", "estemos"):("subjunctive_form", "present", "first", "plural", "manual_irregular"),
    ("estar", "estéis"): ("subjunctive_form", "present", "second", "plural", "manual_irregular"),
    ("estar", "estén"):  ("subjunctive_form", "present", "third", "plural", "manual_irregular"),
    # estar — imperfect subjunctive -ra
    ("estar", "estuviera"):    ("subjunctive_form", "imperfect_ra", "singular_ambiguous", "singular", "manual_irregular"),
    ("estar", "estuvieras"):   ("subjunctive_form", "imperfect_ra", "second", "singular", "manual_irregular"),
    ("estar", "estuviéramos"): ("subjunctive_form", "imperfect_ra", "first", "plural", "manual_irregular"),
    ("estar", "estuvierais"):  ("subjunctive_form", "imperfect_ra", "second", "plural", "manual_irregular"),
    ("estar", "estuvieran"):   ("subjunctive_form", "imperfect_ra", "third", "plural", "manual_irregular"),
    # estar — imperfect subjunctive -se
    ("estar", "estuviese"):    ("subjunctive_form", "imperfect_se", "singular_ambiguous", "singular", "manual_irregular"),
    ("estar", "estuvieses"):   ("subjunctive_form", "imperfect_se", "second", "singular", "manual_irregular"),
    ("estar", "estuviésemos"): ("subjunctive_form", "imperfect_se", "first", "plural", "manual_irregular"),
    ("estar", "estuvieseis"):  ("subjunctive_form", "imperfect_se", "second", "plural", "manual_irregular"),
    ("estar", "estuviesen"):   ("subjunctive_form", "imperfect_se", "third", "plural", "manual_irregular"),

    # dar — present subjunctive
    ("dar", "dé"):   ("subjunctive_form", "present", "singular_ambiguous", "singular", "manual_irregular"),
    ("dar", "des"):  ("subjunctive_form", "present", "second", "singular", "manual_irregular"),
    ("dar", "demos"):("subjunctive_form", "present", "first", "plural", "manual_irregular"),
    ("dar", "deis"): ("subjunctive_form", "present", "second", "plural", "manual_irregular"),
    ("dar", "den"):  ("subjunctive_form", "present", "third", "plural", "manual_irregular"),
    # dar — imperfect subjunctive -ra
    ("dar", "diera"):    ("subjunctive_form", "imperfect_ra", "singular_ambiguous", "singular", "manual_irregular"),
    ("dar", "dieras"):   ("subjunctive_form", "imperfect_ra", "second", "singular", "manual_irregular"),
    ("dar", "diéramos"): ("subjunctive_form", "imperfect_ra", "first", "plural", "manual_irregular"),
    ("dar", "dierais"):  ("subjunctive_form", "imperfect_ra", "second", "plural", "manual_irregular"),
    ("dar", "dieran"):   ("subjunctive_form", "imperfect_ra", "third", "plural", "manual_irregular"),
    # dar — imperfect subjunctive -se
    ("dar", "diese"):    ("subjunctive_form", "imperfect_se", "singular_ambiguous", "singular", "manual_irregular"),
    ("dar", "dieses"):   ("subjunctive_form", "imperfect_se", "second", "singular", "manual_irregular"),
    ("dar", "diésemos"): ("subjunctive_form", "imperfect_se", "first", "plural", "manual_irregular"),
    ("dar", "dieseis"):  ("subjunctive_form", "imperfect_se", "second", "plural", "manual_irregular"),
    ("dar", "diesen"):   ("subjunctive_form", "imperfect_se", "third", "plural", "manual_irregular"),

    # saber — present subjunctive
    ("saber", "sepa"):   ("subjunctive_form", "present", "singular_ambiguous", "singular", "manual_irregular"),
    ("saber", "sepas"):  ("subjunctive_form", "present", "second", "singular", "manual_irregular"),
    ("saber", "sepamos"):("subjunctive_form", "present", "first", "plural", "manual_irregular"),
    ("saber", "sepáis"): ("subjunctive_form", "present", "second", "plural", "manual_irregular"),
    ("saber", "sepan"):  ("subjunctive_form", "present", "third", "plural", "manual_irregular"),
    # saber — imperfect subjunctive -ra
    ("saber", "supiera"):    ("subjunctive_form", "imperfect_ra", "singular_ambiguous", "singular", "manual_irregular"),
    ("saber", "supieras"):   ("subjunctive_form", "imperfect_ra", "second", "singular", "manual_irregular"),
    ("saber", "supiéramos"): ("subjunctive_form", "imperfect_ra", "first", "plural", "manual_irregular"),
    ("saber", "supierais"):  ("subjunctive_form", "imperfect_ra", "second", "plural", "manual_irregular"),
    ("saber", "supieran"):   ("subjunctive_form", "imperfect_ra", "third", "plural", "manual_irregular"),
    # saber — imperfect subjunctive -se
    ("saber", "supiese"):    ("subjunctive_form", "imperfect_se", "singular_ambiguous", "singular", "manual_irregular"),
    ("saber", "supieses"):   ("subjunctive_form", "imperfect_se", "second", "singular", "manual_irregular"),
    ("saber", "supiésemos"): ("subjunctive_form", "imperfect_se", "first", "plural", "manual_irregular"),
    ("saber", "supieseis"):  ("subjunctive_form", "imperfect_se", "second", "plural", "manual_irregular"),
    ("saber", "supiesen"):   ("subjunctive_form", "imperfect_se", "third", "plural", "manual_irregular"),
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


def infer_subjunctive_form(
    lemma: str,
    original_lemma: str,
    pos: str,
) -> tuple[str, str, str, str, str]:
    """
    Returns (relation, tense, person, number, reason).
    """
    lemma = (lemma or "").strip().lower()
    original = (original_lemma or "").strip().lower()
    pos = normalize_pos(pos)

    if pos != "v":
        return ("unknown", "", "", "", "pos_not_supported")

    if not original.endswith(("ar", "er", "ir")):
        return ("unknown", "", "", "", "original_not_infinitive")

    manual = MANUAL_SUBJUNCTIVE_MAP.get((original, lemma))
    if manual:
        return manual

    stem = original[:-2]
    ending = original[-2:]

    # Regular present subjunctive
    if ending == "ar":
        present_map = {
            stem + "e":   ("present", "singular_ambiguous", "singular"),
            stem + "es":  ("present", "second", "singular"),
            stem + "emos":("present", "first", "plural"),
            stem + "éis": ("present", "second", "plural"),
            stem + "en":  ("present", "third", "plural"),
        }
    else:
        present_map = {
            stem + "a":   ("present", "singular_ambiguous", "singular"),
            stem + "as":  ("present", "second", "singular"),
            stem + "amos":("present", "first", "plural"),
            stem + "áis": ("present", "second", "plural"),
            stem + "an":  ("present", "third", "plural"),
        }

    if lemma in present_map:
        tense, person, number = present_map[lemma]
        return ("subjunctive_form", tense, person, number, "regular_present")

    # Regular imperfect subjunctive -ra
    # Use full stem+preterite-base so accented plural is caught too
    if ending == "ar":
        imperfect_ra_map = {
            stem + "ara":    ("imperfect_ra", "singular_ambiguous", "singular"),
            stem + "aras":   ("imperfect_ra", "second", "singular"),
            stem + "áramos": ("imperfect_ra", "first", "plural"),
            stem + "arais":  ("imperfect_ra", "second", "plural"),
            stem + "aran":   ("imperfect_ra", "third", "plural"),
        }
        imperfect_se_map = {
            stem + "ase":    ("imperfect_se", "singular_ambiguous", "singular"),
            stem + "ases":   ("imperfect_se", "second", "singular"),
            stem + "ásemos": ("imperfect_se", "first", "plural"),
            stem + "aseis":  ("imperfect_se", "second", "plural"),
            stem + "asen":   ("imperfect_se", "third", "plural"),
        }
    else:
        imperfect_ra_map = {
            stem + "iera":    ("imperfect_ra", "singular_ambiguous", "singular"),
            stem + "ieras":   ("imperfect_ra", "second", "singular"),
            stem + "iéramos": ("imperfect_ra", "first", "plural"),
            stem + "ierais":  ("imperfect_ra", "second", "plural"),
            stem + "ieran":   ("imperfect_ra", "third", "plural"),
        }
        imperfect_se_map = {
            stem + "iese":    ("imperfect_se", "singular_ambiguous", "singular"),
            stem + "ieses":   ("imperfect_se", "second", "singular"),
            stem + "iésemos": ("imperfect_se", "first", "plural"),
            stem + "ieseis":  ("imperfect_se", "second", "plural"),
            stem + "iesen":   ("imperfect_se", "third", "plural"),
        }

    if lemma in imperfect_ra_map:
        tense, person, number = imperfect_ra_map[lemma]
        return ("subjunctive_form", tense, person, number, "regular_imperfect_ra")

    if lemma in imperfect_se_map:
        tense, person, number = imperfect_se_map[lemma]
        return ("subjunctive_form", tense, person, number, "regular_imperfect_se")

    return ("not_subjunctive_form", "", "", "", "no_match")


def append_subjunctive_context_if_safe(
    raw_translation: str,
    cleaned_translation: str,
    tense: str,
    person: str,
    number: str,
) -> str:
    if not tense:
        if has_brackets(raw_translation):
            return raw_translation.strip()
        return cleaned_translation

    if person == "singular_ambiguous":
        subjunctive_part = f"{tense} subjunctive singular ambiguous"
    else:
        subjunctive_part = f"{tense} subjunctive {person} {number}"

    # If the translation already has a bracket, append inside it
    m = re.search(r"\(([^()]*)\)\s*$", raw_translation.strip())
    if m:
        existing = m.group(1).strip()
        base = raw_translation[: m.start()].strip()
        if subjunctive_part in existing:
            return raw_translation.strip()
        inner = f"{existing}; {subjunctive_part}"
        return f"{base} ({inner})"

    suffix = f" ({subjunctive_part})"
    if cleaned_translation.endswith(suffix):
        return cleaned_translation
    return f"{cleaned_translation}{suffix}"


def build_tags(existing_tags: str, tense: str, person: str, number: str) -> str:
    tags: list[str] = [t for t in existing_tags.split("|") if t] if existing_tags else []

    if tense:
        tags.append("subjunctive")
        tags.append(tense)
        if person == "singular_ambiguous":
            tags.append("singular_ambiguous")
        else:
            tags.append(person)
            tags.append(number)

    seen: set[str] = set()
    deduped: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            deduped.append(tag)
    return "|".join(deduped)


def rewrite_row(row: dict[str, str]) -> dict[str, str]:
    row = dict(row)
    lemma = row.get("lemma", "").strip()
    original_lemma = row.get("original_lemma", "").strip()
    pos = row.get("pos", "").strip()
    raw_translation = row.get("translation", "").strip()

    relation, tense, person, number, reason = infer_subjunctive_form(lemma, original_lemma, pos)

    row["subjunctive_relation"] = relation
    row["subjunctive_tense"] = tense
    row["subjunctive_person"] = person
    row["subjunctive_number"] = number
    row["subjunctive_confidence"] = "high" if reason == "manual_irregular" else ("medium" if relation == "subjunctive_form" else "")
    row["subjunctive_reason"] = reason

    cleaned = clean_translation(raw_translation)
    row["translation"] = append_subjunctive_context_if_safe(raw_translation, cleaned, tense, person, number)
    row["tags"] = build_tags(row.get("tags", ""), tense, person, number)

    return row


def output_fieldnames(fieldnames: list[str]) -> list[str]:
    required = {"rank", "lemma", "original_lemma", "translation", "pos"}
    missing = [name for name in required if name not in set(fieldnames)]
    if missing:
        raise SystemExit(f"Input CSV is missing required columns: {', '.join(missing)}")
    return OUTPUT_FIELDNAMES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect Spanish subjunctive forms and annotate translations.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    review_log_path = output_path.with_name(f"{output_path.stem}-subjunctive-review.csv")

    with input_path.open("r", newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise SystemExit("Input CSV has no header row.")
        fieldnames = output_fieldnames(list(reader.fieldnames))
        original_rows = list(reader)

    rows = [rewrite_row(row) for row in original_rows]

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
                "subjunctive_tense": new_row.get("subjunctive_tense", ""),
                "subjunctive_person": new_row.get("subjunctive_person", ""),
                "reason": new_row.get("subjunctive_reason", ""),
            })

    with review_log_path.open("w", newline="", encoding="utf-8") as logfile:
        writer = csv.DictWriter(
            logfile,
            fieldnames=["rank", "lemma", "original_lemma", "new_translation", "subjunctive_tense", "subjunctive_person", "reason"],
        )
        writer.writeheader()
        writer.writerows(review_rows)

    print(f"Saved {len(rows)} rows to {output_path}.")
    print(f"Saved {len(review_rows)} changed rows to {review_log_path}.")


if __name__ == "__main__":
    main()
