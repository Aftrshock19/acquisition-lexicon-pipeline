#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

DEFAULT_INPUT = Path("spa-eng.csv")
DEFAULT_OUTPUT = Path("spa-eng-ido-participles.csv")

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

EXTRA_COLUMNS = [
    "old_translation",
    "new_translation",
    "translation_changed",
    "review_reason",
    "participle_relation",
    "participle_form",
    "participle_family",
    "participle_gender",
    "participle_number",
    "participle_confidence",
    "participle_reason",
]

NEGATIVE_TAG_HINTS = {
    "subjunctive",
    "imperative",
    "finite",
    "present",
    "preterite",
    "imperfect",
    "future",
    "conditional",
    "gerund",
    "infinitive",
}

POSITIVE_PARTICIPLE_TAG_HINTS = {
    "participle",
    "past_participle",
    "past participle",
    "participle_form",
}

PARTICIPLE_ENDING_INFO = {
    "ido": ("ido", "standard_ido", "masculine", "singular"),
    "ida": ("ida", "standard_ida", "feminine", "singular"),
    "idos": ("idos", "standard_idos", "masculine", "plural"),
    "idas": ("idas", "standard_idas", "feminine", "plural"),
    "ído": ("ído", "accented_ido", "masculine", "singular"),
    "ída": ("ída", "accented_ida", "feminine", "singular"),
    "ídos": ("ídos", "accented_idos", "masculine", "plural"),
    "ídas": ("ídas", "accented_idas", "feminine", "plural"),
}

VERBISH_POS = {"v", "verb"}
ADJECTIVE_POS = {"adj", "adjective"}
NOUN_POS = {"n", "noun"}


def normalize(text: str) -> str:
    return (text or "").strip()


def normalize_lower(text: str) -> str:
    return normalize(text).lower()


def parse_tags(raw: str) -> set[str]:
    text = normalize_lower(raw)
    if not text:
        return set()
    parts = re.split(r"[|,;/]+", text)
    return {part.strip() for part in parts if part.strip()}


def looks_like_ido_family(text: str) -> bool:
    lowered = normalize_lower(text)
    return any(lowered.endswith(ending) for ending in PARTICIPLE_ENDING_INFO)


def split_trailing_brackets(text: str) -> tuple[str, list[str]]:
    text = normalize(text)
    if not text:
        return "", []

    m = re.match(r"^(.*?)(?:\s*\(([^()]*)\)\s*)?$", text)
    if not m:
        return text, []

    core = normalize(m.group(1))
    note_blob = normalize(m.group(2) or "")
    if not note_blob:
        return core, []

    notes = [normalize(piece) for piece in note_blob.split(";") if normalize(piece)]
    return core, notes


def dedupe_preserve_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = normalize_lower(item)
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(normalize(item))
    return out


def join_core_and_notes(core: str, notes: list[str]) -> str:
    core = normalize(core)
    notes = dedupe_preserve_order(notes)
    if not notes:
        return core
    if not core:
        return f"({'; '.join(notes)})"
    return f"{core} ({'; '.join(notes)})"


def append_note_to_translation(translation: str, note: str) -> str:
    core, notes = split_trailing_brackets(translation)
    notes.append(note)
    return join_core_and_notes(core, notes)


def looks_like_participle_row(row: dict[str, str]) -> bool:
    pos = normalize_lower(row.get("pos", ""))
    tags = parse_tags(row.get("tags", ""))

    if tags & NEGATIVE_TAG_HINTS and not tags & POSITIVE_PARTICIPLE_TAG_HINTS:
        return False

    if tags & POSITIVE_PARTICIPLE_TAG_HINTS:
        return pos in VERBISH_POS

    return pos in VERBISH_POS


def participle_note(gender: str, number: str) -> str:
    return f"past participle {gender} {number}"


def build_result(
    form: str,
    family: str,
    gender: str,
    number: str,
    confidence: str,
    reason: str,
) -> dict[str, str]:
    return {
        "participle_relation": "past_participle_detected",
        "participle_form": form,
        "participle_family": family,
        "participle_gender": gender,
        "participle_number": number,
        "participle_confidence": confidence,
        "participle_reason": reason,
    }


def detect_ido_participle(lemma: str, original_lemma: str) -> dict[str, str] | None:
    candidates: dict[str, tuple[str, str, str, str]] = {}

    if original_lemma.endswith(("er", "ir")):
        stem = original_lemma[:-2]
        candidates = {f"{stem}{ending}": info for ending, info in PARTICIPLE_ENDING_INFO.items()}
    else:
        for ending in sorted(PARTICIPLE_ENDING_INFO, key=len, reverse=True):
            if original_lemma.endswith(ending):
                stem = original_lemma[: -len(ending)]
                candidates = {f"{stem}{candidate_ending}": info for candidate_ending, info in PARTICIPLE_ENDING_INFO.items()}
                break

    if not candidates:
        return None

    hit = candidates.get(lemma)
    if not hit:
        return None

    form, family, gender, number = hit
    return build_result(
        form=form,
        family=family,
        gender=gender,
        number=number,
        confidence="high",
        reason="regular_ido_participle_match",
    )


def process_row(row: dict[str, str]) -> dict[str, str]:
    out = dict(row)

    old_translation = normalize(row.get("translation", ""))
    extra = {
        "old_translation": old_translation,
        "new_translation": old_translation,
        "translation_changed": "no",
        "review_reason": "",
        "participle_relation": "",
        "participle_form": "",
        "participle_family": "",
        "participle_gender": "",
        "participle_number": "",
        "participle_confidence": "",
        "participle_reason": "",
    }

    lemma = normalize_lower(row.get("lemma", ""))
    original_lemma = normalize_lower(row.get("original_lemma", ""))

    if not lemma or not original_lemma:
        extra["review_reason"] = "missing_lemma_fields"
        out.update(extra)
        return out

    if not looks_like_participle_row(row):
        extra["review_reason"] = "row_not_safe_for_participle_detection"
        out.update(extra)
        return out

    detected = detect_ido_participle(lemma, original_lemma)
    if not detected:
        extra["review_reason"] = "no_ido_participle_match"
        out.update(extra)
        return out

    extra.update(detected)

    note = participle_note(
        gender=detected["participle_gender"],
        number=detected["participle_number"],
    )

    new_translation = append_note_to_translation(old_translation, note)
    out["translation"] = new_translation
    extra["new_translation"] = new_translation
    extra["translation_changed"] = "yes" if new_translation != old_translation else "no"
    extra["review_reason"] = (
        "translation_changed"
        if new_translation != old_translation
        else "context_already_present"
    )

    out.update(extra)
    return out


def build_review_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    review_rows: list[dict[str, str]] = []

    for row in rows:
        review_reason = normalize(row.get("review_reason", ""))
        if not review_reason or review_reason in {
            "missing_lemma_fields",
            "row_not_safe_for_participle_detection",
            "no_ido_participle_match",
        }:
            continue

        review_rows.append({
            "rank": row.get("rank", ""),
            "lemma": row.get("lemma", ""),
            "original_lemma": row.get("original_lemma", ""),
            "old_translation": row.get("old_translation", ""),
            "new_translation": row.get("new_translation", ""),
            "translation_changed": row.get("translation_changed", ""),
            "review_reason": review_reason,
            "participle_relation": row.get("participle_relation", ""),
            "participle_form": row.get("participle_form", ""),
            "participle_family": row.get("participle_family", ""),
            "participle_gender": row.get("participle_gender", ""),
            "participle_number": row.get("participle_number", ""),
            "participle_confidence": row.get("participle_confidence", ""),
            "participle_reason": row.get("participle_reason", ""),
        })

    return review_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    review_log_path = args.output.with_name(f"{args.output.stem}-review.csv")

    with args.input.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Input CSV has no header row")

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        rows = [process_row(row) for row in reader]

    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    review_rows = build_review_rows(rows)
    with review_log_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rank",
                "lemma",
                "original_lemma",
                "old_translation",
                "new_translation",
                "translation_changed",
                "review_reason",
                "participle_relation",
                "participle_form",
                "participle_family",
                "participle_gender",
                "participle_number",
                "participle_confidence",
                "participle_reason",
            ],
        )
        writer.writeheader()
        writer.writerows(review_rows)

    print(f"Saved {len(rows)} rows to {args.output}.")
    print(f"Saved {len(review_rows)} review rows to {review_log_path}.")


if __name__ == "__main__":
    main()
