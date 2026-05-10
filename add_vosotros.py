#!/usr/bin/env python3
"""
Detect vosotros verb forms in a CSV and append bracket context to translation.

Usage:
  python3 add_vosotros.py
  python3 add_vosotros.py --input spa-eng.csv --output spa-eng-vosotros.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

DEFAULT_INPUT = Path("spa-eng.csv")
DEFAULT_OUTPUT = Path("spa-eng-vosotros.csv")

VERB_ROOT_DESCRIPTIONS = {
    "ser":   "identity/essence/origin/time",
    "estar": "state/location/result",
    "haber": "auxiliary/existence",
    "tener": "possession/age/need-state",
    "ir":    "movement/direction",
}

# (original_lemma, lemma) -> (relation, tense, mood, reason)
MANUAL_VOSOTROS_MAP: dict[tuple[str, str], tuple[str, str, str, str]] = {
    ("ser",   "sois"):   ("vosotros_form", "present", "indicative", "manual"),
    ("ir",    "vais"):   ("vosotros_form", "present", "indicative", "manual"),
    ("estar", "estáis"): ("vosotros_form", "present", "indicative", "manual"),
    ("haber", "habéis"): ("vosotros_form", "present", "indicative", "manual"),
    ("tener", "tenéis"): ("vosotros_form", "present", "indicative", "manual"),
    ("decir", "decís"):  ("vosotros_form", "present", "indicative", "manual"),
    ("poder", "podéis"): ("vosotros_form", "present", "indicative", "manual"),
    ("venir", "venís"):  ("vosotros_form", "present", "indicative", "manual"),
    ("hacer", "hacéis"): ("vosotros_form", "present", "indicative", "manual"),
    ("dar",   "dais"):   ("vosotros_form", "present", "indicative", "manual"),
    ("ver",   "veis"):   ("vosotros_form", "present", "indicative", "manual"),
    ("saber", "sabéis"): ("vosotros_form", "present", "indicative", "manual"),
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


def infer_vosotros_form(
    lemma: str,
    original_lemma: str,
    pos: str,
) -> tuple[str, str, str, str]:
    """
    Returns (relation, tense, mood, reason).

    relation: "vosotros_form" | "not_vosotros_form" | "unknown"
    tense:    present | preterite | imperfect | future | conditional | imperative | ""
    mood:     indicative | conditional | imperative | ""
    reason:   short tag explaining the decision
    """
    lemma = (lemma or "").strip().lower()
    original = (original_lemma or "").strip().lower()
    pos = normalize_pos(pos)

    if pos != "v":
        return ("unknown", "", "", "pos_not_supported")

    if not original.endswith(("ar", "er", "ir")):
        return ("unknown", "", "", "original_not_infinitive")

    manual = MANUAL_VOSOTROS_MAP.get((original, lemma))
    if manual:
        return manual

    stem = original[:-2]
    ending = original[-2:]

    # Present indicative
    if ending == "ar" and lemma == stem + "áis":
        return ("vosotros_form", "present", "indicative", "ar_present")
    if ending == "er" and lemma == stem + "éis":
        return ("vosotros_form", "present", "indicative", "er_present")
    if ending == "ir" and lemma == stem + "ís":
        return ("vosotros_form", "present", "indicative", "ir_present")

    # Preterite
    if ending == "ar" and lemma == stem + "asteis":
        return ("vosotros_form", "preterite", "indicative", "ar_preterite")
    if ending in {"er", "ir"} and lemma == stem + "isteis":
        return ("vosotros_form", "preterite", "indicative", "er_ir_preterite")

    # Imperfect
    if ending == "ar" and lemma == stem + "abais":
        return ("vosotros_form", "imperfect", "indicative", "ar_imperfect")
    if ending in {"er", "ir"} and lemma == stem + "íais":
        return ("vosotros_form", "imperfect", "indicative", "er_ir_imperfect")

    # Future
    if ending == "ar" and lemma == stem + "aréis":
        return ("vosotros_form", "future", "indicative", "ar_future")
    if ending == "er" and lemma == stem + "eréis":
        return ("vosotros_form", "future", "indicative", "er_future")
    if ending == "ir" and lemma == stem + "iréis":
        return ("vosotros_form", "future", "indicative", "ir_future")

    # Conditional
    if ending == "ar" and lemma == stem + "aríais":
        return ("vosotros_form", "conditional", "conditional", "ar_conditional")
    if ending == "er" and lemma == stem + "eríais":
        return ("vosotros_form", "conditional", "conditional", "er_conditional")
    if ending == "ir" and lemma == stem + "iríais":
        return ("vosotros_form", "conditional", "conditional", "ir_conditional")

    # Affirmative imperative: drop final r, add d
    if lemma == original[:-1] + "d":
        return ("vosotros_form", "imperative", "imperative", "affirmative_imperative")

    return ("not_vosotros_form", "", "", "no_match")


def append_vosotros_context_if_safe(
    raw_translation: str,
    cleaned_translation: str,
    tense: str,
    mood: str,
    original_lemma: str,
) -> str:
    if not tense:
        if has_brackets(raw_translation):
            return raw_translation.strip()
        return cleaned_translation

    if tense == "imperative":
        vosotros_part = "vosotros imperative"
    elif mood == "conditional":
        vosotros_part = "vosotros conditional"
    else:
        vosotros_part = f"vosotros {tense} {mood}"

    verb_desc = VERB_ROOT_DESCRIPTIONS.get(original_lemma.strip().lower(), "")

    # If the translation already has a bracket, append inside it
    m = re.search(r"\(([^()]*)\)\s*$", raw_translation.strip())
    if m:
        existing = m.group(1).strip()
        base = raw_translation[: m.start()].strip()
        inner = "; ".join([existing] + [p for p in [vosotros_part, verb_desc] if p and p not in existing])
        return f"{base} ({inner})"

    parts = [p for p in [vosotros_part, verb_desc] if p]
    suffix = f" ({'; '.join(parts)})"
    if cleaned_translation.endswith(suffix):
        return cleaned_translation
    return f"{cleaned_translation}{suffix}"


def build_tags(existing_tags: str, tense: str, mood: str) -> str:
    tags: list[str] = [t for t in existing_tags.split("|") if t] if existing_tags else []

    if tense:
        tags.append("vosotros")
        tags.append("2nd_person")
        tags.append("plural")

        if tense == "imperative":
            tags.append("imperative")
        elif mood == "conditional":
            tags.append("conditional")
        else:
            tags.append(tense)
            if mood:
                tags.append(mood)

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

    relation, tense, mood, reason = infer_vosotros_form(lemma, original_lemma, pos)

    row["vosotros_relation"] = relation
    row["vosotros_tense"] = tense
    row["vosotros_mood"] = mood
    row["vosotros_confidence"] = "high" if reason == "manual" else ("medium" if relation == "vosotros_form" else "")
    row["vosotros_reason"] = reason

    cleaned = clean_translation(raw_translation)
    row["translation"] = append_vosotros_context_if_safe(raw_translation, cleaned, tense, mood, original_lemma)
    row["tags"] = build_tags(row.get("tags", ""), tense, mood)

    return row


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


def output_fieldnames(fieldnames: list[str]) -> list[str]:
    required = {"rank", "lemma", "original_lemma", "translation", "pos"}
    missing = [name for name in required if name not in set(fieldnames)]
    if missing:
        raise SystemExit(f"Input CSV is missing required columns: {', '.join(missing)}")
    return OUTPUT_FIELDNAMES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect vosotros verb forms and annotate translations.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    review_log_path = output_path.with_name(f"{output_path.stem}-vosotros-review.csv")

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
                "vosotros_tense": new_row.get("vosotros_tense", ""),
                "vosotros_mood": new_row.get("vosotros_mood", ""),
                "reason": new_row.get("vosotros_reason", ""),
            })

    with review_log_path.open("w", newline="", encoding="utf-8") as logfile:
        writer = csv.DictWriter(
            logfile,
            fieldnames=["rank", "lemma", "original_lemma", "new_translation", "vosotros_tense", "vosotros_mood", "reason"],
        )
        writer.writeheader()
        writer.writerows(review_rows)

    print(f"Saved {len(rows)} rows to {output_path}.")
    print(f"Saved {len(review_rows)} changed rows to {review_log_path}.")


if __name__ == "__main__":
    main()
