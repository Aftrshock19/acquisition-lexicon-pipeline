#!/usr/bin/env python3
"""
fix_grammatical_defs.py

Replaces grammatical-description definitions (e.g. "Segunda persona del singular
del presente de indicativo de bromar") with real dictionary definitions.

Two-phase approach:
  Phase 1: Copy definitions from other rows sharing the same original_lemma
  Phase 2: Look up original_lemma in English Wiktionary JSONL for remaining gaps
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

import orjson
from tqdm import tqdm

INPUT_CSV = "spa-eng-final-fixed.csv"
OUTPUT_CSV = "spa-eng-final-fixed2.csv"
EN_WIKT = "raw-wiktextract-data.es.jsonl"

# Patterns that identify grammatical (non-semantic) definitions
GRAMMATICAL_PATTERNS = [
    "persona del singular",
    "persona del plural",
    "Forma del plural",
    "Forma del masculino",
    "Forma del femenino",
    "Forma del superlativo",
    "Forma del diminutivo",
    "Participio de ",
    "pretérito",
    "indicativo de ",
    "subjuntivo de ",
    "imperativo de ",
    "gerundio de ",
    "infinitivo de ",
    "Forma apocopada",
]

BANNED_SENSE_TAGS = {
    "obsolete", "archaic", "dated", "historical",
    "rare", "uncommon", "superseded", "misspelling",
}

# POS mapping: CSV pos -> wiktextract pos values
CSV_TO_WIKT = {
    "verb":         {"verb"},
    "noun":         {"noun", "name"},
    "adjective":    {"adj"},
    "adverb":       {"adv"},
    "pronoun":      {"pron"},
    "determiner":   {"det"},
    "article":      {"det", "article"},
    "preposition":  {"prep"},
    "conjunction":  {"conj"},
    "number":       {"num", "numeral"},
    "interjection": {"intj"},
    "contraction":  {"contraction"},
    "phrase":       {"phrase"},
    "particle":     {"particle"},
    "name":         {"name", "noun"},
}

FORM_OF_PATTERNS = (
    "inflection of ", "form of ", "past participle of ",
    "present participle of ", "gerund of ", "alternative form of ",
    "alternative spelling of ", "plural of ", "singular of ",
    "feminine singular of ", "masculine singular of ",
    "feminine plural of ", "masculine plural of ",
    "third-person", "second-person", "first-person",
    "superlative of ", "comparative of ", "diminutive of ",
)


def is_grammatical(defn: str) -> bool:
    return any(p in defn for p in GRAMMATICAL_PATTERNS)


def is_form_of_gloss(text: str) -> bool:
    low = text.lower().strip()
    return any(low.startswith(p) for p in FORM_OF_PATTERNS)


def clean_gloss(text: str) -> str:
    """Clean up a Wiktionary English gloss for use as a definition."""
    text = text.strip()
    # Remove trailing citations/references
    text = re.sub(r'\s*\[.*?\]\s*$', '', text)
    # Remove leading "(" tags ")" if the whole thing isn't parenthetical
    text = re.sub(r'^\([^)]*\)\s*', '', text).strip()
    return text


def build_wikt_index(jsonl_path: str) -> dict:
    """Build word -> list of (pos, glosses) from English Wiktionary JSONL."""
    index = defaultdict(list)
    with open(jsonl_path, 'r') as f:
        for line in tqdm(f, desc="Loading English Wiktionary"):
            entry = orjson.loads(line)
            word = entry.get("word", "").strip()
            pos = entry.get("pos", "").strip().lower()
            if not word or not pos:
                continue

            senses = entry.get("senses", [])
            glosses = []
            for sense in senses:
                tags = set()
                for t in sense.get("tags", []):
                    tags.add(t.lower())
                if tags & BANNED_SENSE_TAGS:
                    continue

                for g in sense.get("glosses", []):
                    g = clean_gloss(g)
                    if g and not is_form_of_gloss(g) and len(g) > 2:
                        glosses.append(g)

            if glosses:
                index[word].append((pos, glosses))

    return dict(index)


def get_best_definition(wikt_index: dict, lemma: str, csv_pos: str) -> tuple:
    """
    Get best (spanish_def, english_def) from English Wiktionary for a lemma.
    Returns (None, None) if nothing found.
    """
    entries = wikt_index.get(lemma, [])
    if not entries:
        return None, None

    target_pos = CSV_TO_WIKT.get(csv_pos.lower().strip(), set())

    # Prefer POS-matching entries
    best_glosses = None
    for pos, glosses in entries:
        if pos in target_pos:
            best_glosses = glosses
            break

    # Fallback: use any entry
    if not best_glosses:
        best_glosses = entries[0][1]

    if not best_glosses:
        return None, None

    # Use up to 2 glosses for the English definition
    eng_def = "; ".join(best_glosses[:2])

    # For Spanish definition, we don't have a Spanish source here,
    # so we'll create a brief Spanish description from the English
    # Actually, just use the English glosses - it's better than grammatical nonsense
    return eng_def, eng_def


def build_es_wikt_index(jsonl_path: str) -> dict:
    """Build word -> list of (pos, glosses) from Spanish Wiktionary JSONL."""
    index = defaultdict(list)

    BAD_PREFIXES = (
        "forma de ", "forma del ", "forma flexiva de ",
        "plural de ", "singular de ", "participio de ",
        "gerundio de ", "pasado de ", "femenino de ",
        "masculino de ", "apócope de ", "variante de ",
        "primera persona", "segunda persona", "tercera persona",
    )

    with open(jsonl_path, 'r') as f:
        for line in tqdm(f, desc="Loading Spanish Wiktionary"):
            entry = orjson.loads(line)
            word = entry.get("word", "").strip()
            pos = entry.get("pos", "").strip().lower()
            if not word or not pos:
                continue

            senses = entry.get("senses", [])
            glosses = []
            for sense in senses:
                for g in sense.get("glosses", []):
                    g = g.strip()
                    low = g.lower()
                    if any(low.startswith(p) for p in BAD_PREFIXES):
                        continue
                    if len(g) > 3:
                        glosses.append(g)

            if glosses:
                index[word].append((pos, glosses))

    return dict(index)


def get_best_es_definition(es_index: dict, lemma: str, csv_pos: str) -> str:
    """Get best Spanish definition from Spanish Wiktionary."""
    entries = es_index.get(lemma, [])
    if not entries:
        return None

    target_pos = CSV_TO_WIKT.get(csv_pos.lower().strip(), set())

    best_glosses = None
    for pos, glosses in entries:
        if pos in target_pos:
            best_glosses = glosses
            break

    if not best_glosses:
        best_glosses = entries[0][1]

    if not best_glosses:
        return None

    return best_glosses[0]


def main():
    # ── Read CSV ──────────────────────────────────────────────────────────────
    rows = []
    with open(INPUT_CSV, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            rows.append(row)

    print(f"Loaded {len(rows)} rows from {INPUT_CSV}")

    # ── Phase 0: Index good definitions by original_lemma ─────────────────────
    good_defs = {}  # original_lemma -> (spanish_def, english_def)
    for row in rows:
        defn = row[4] if len(row) > 4 else ""
        eng_defn = row[5] if len(row) > 5 else ""
        orig = row[2] if len(row) > 2 else ""
        if defn.strip() and not is_grammatical(defn) and orig not in good_defs:
            good_defs[orig] = (defn, eng_defn)

    # ── Identify bad rows ─────────────────────────────────────────────────────
    bad_indices = []
    for i, row in enumerate(rows):
        defn = row[4] if len(row) > 4 else ""
        if is_grammatical(defn):
            bad_indices.append(i)

    print(f"Found {len(bad_indices)} rows with grammatical definitions")

    # ── Phase 1: Fix from existing good definitions ───────────────────────────
    phase1_fixed = 0
    still_bad = []
    for i in bad_indices:
        orig = rows[i][2]
        if orig in good_defs:
            rows[i][4], rows[i][5] = good_defs[orig]
            phase1_fixed += 1
        else:
            still_bad.append(i)

    print(f"Phase 1: Fixed {phase1_fixed} rows from existing definitions")
    print(f"Phase 2: {len(still_bad)} rows remaining")

    # ── Phase 2: Look up in Wiktionary ────────────────────────────────────────
    if still_bad:
        # Load Spanish Wiktionary for Spanish definitions
        es_index = build_es_wikt_index("es-extract.jsonl")
        # Load English Wiktionary for English definitions
        en_index = build_wikt_index(EN_WIKT)

        phase2_es = 0
        phase2_en = 0
        phase2_failed = 0

        for i in tqdm(still_bad, desc="Phase 2 lookups"):
            orig = rows[i][2]
            csv_pos = rows[i][6] if len(rows[i]) > 6 else ""

            # Try Spanish Wiktionary first for Spanish def
            es_def = get_best_es_definition(es_index, orig, csv_pos)

            # Try English Wiktionary for English def
            en_def, en_def2 = get_best_definition(en_index, orig, csv_pos)

            if es_def:
                rows[i][4] = es_def
                phase2_es += 1
            elif en_def:
                # Use English def as Spanish def placeholder
                rows[i][4] = en_def

            if en_def:
                rows[i][5] = en_def
                phase2_en += 1

            if not es_def and not en_def:
                phase2_failed += 1
                # Keep original (grammatical) def as last resort

        print(f"Phase 2: Fixed {phase2_es} Spanish defs from es-wikt, {phase2_en} English defs from en-wikt")
        print(f"Phase 2: {phase2_failed} rows still unfixed")

    # ── Write output ──────────────────────────────────────────────────────────
    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"\nWrote {OUTPUT_CSV}")

    # ── Verify ────────────────────────────────────────────────────────────────
    remaining_bad = sum(1 for row in rows if is_grammatical(row[4] if len(row) > 4 else ""))
    print(f"Remaining grammatical definitions: {remaining_bad} ({remaining_bad*100//len(rows)}%)")


if __name__ == "__main__":
    main()
