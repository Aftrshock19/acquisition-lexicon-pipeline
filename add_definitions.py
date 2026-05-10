#!/usr/bin/env python3
"""
add_definitions.py

Adds a `definitions` column to the CSV with clean English dictionary definitions
for each word, based on the `lemma` field (not original_lemma).

`translation` stays as the short flashcard gloss.
`definitions` provides a fuller meaning for the reading feature.

Usage:
  python add_definitions.py \\
    --input   spa-eng-lemmatized.csv \\
    --output  spa-eng-with-defs.csv \\
    --primary raw-wiktextract-data.es.jsonl

Output columns:
  rank, lemma, original_lemma, translation, definitions, pos,
  sentence, english_sentence
"""

import argparse
import csv
import gzip
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import orjson
from tqdm import tqdm

# ── Shared helpers from sibling script ───────────────────────────────────────
try:
    from build_wiktionary_glosses_40k import (
        norm_space,
        get_original_lemma_from_sense,
        get_tags,
        get_glosses,
        compact_to_flashcard_english,
        is_segment_grammar_prose,
        BANNED_SENSE_TAGS,
    )
except ImportError as exc:
    sys.exit(
        f"Cannot import from build_wiktionary_glosses_40k.py — "
        f"make sure it is in the same directory.\n{exc}"
    )

# ── POS mapping ───────────────────────────────────────────────────────────────
_CSV_TO_WIKT: dict[str, frozenset[str]] = {
    "verb":         frozenset({"verb"}),
    "noun":         frozenset({"noun", "prop", "proper noun", "proper_noun"}),
    "adjective":    frozenset({"adj", "adjective"}),
    "adverb":       frozenset({"adv", "adverb"}),
    "pronoun":      frozenset({"pron", "pronoun"}),
    "determiner":   frozenset({"det", "determiner"}),
    "article":      frozenset({"article", "det", "determiner"}),
    "preposition":  frozenset({"prep", "preposition"}),
    "conjunction":  frozenset({"conj", "conjunction"}),
    "number":       frozenset({"num", "numeral", "number"}),
    "interjection": frozenset({"intj", "interjection"}),
    "contraction":  frozenset({"contraction"}),
    "phrase":       frozenset({"phrase"}),
    "particle":     frozenset({"particle"}),
    "name":         frozenset({"name", "prop", "proper noun", "proper_noun"}),
}

# Grammatical case labels that are not useful as stand-alone definitions
# e.g. "dative of él" → skip; "plural of el" → keep
_CASE_ONLY = frozenset({
    "accusative", "dative", "genitive", "nominative", "vocative",
    "prepositional", "locative", "instrumental", "ablative",
})


def _pos_matches(wikt_pos: str, csv_pos: str) -> bool:
    return wikt_pos.lower().strip() in _CSV_TO_WIKT.get(csv_pos.lower().strip(), frozenset())


def _has_letters(text: str) -> bool:
    return bool(re.search(r"[a-zA-Z]", text))


def _is_case_label_only(text: str) -> bool:
    """
    True for bare case labels like "dative of él", "accusative of yo" that
    carry no translatable content.  "plural of el" or "feminine singular of
    este" are NOT considered case-only — they are useful morphological notes.
    """
    words = text.lower().split()
    return bool(words) and words[0] in _CASE_ONLY


# ── Sense processor ───────────────────────────────────────────────────────────

def _sense_definitions(sense: dict, wikt_pos: str) -> list[str]:
    """
    Return clean English definition segments from one Wiktionary sense.

    Form-of senses (have form_of / alt_of):
      Format A — wiktextract multi-part:
        glosses = ["inflection of estar:", "third-person singular present indicative",
                   "second-person singular imperative"]
        → ["third-person singular present indicative of estar",
           "second-person singular imperative of estar"]

      Format B — colon-split: "accusative of yo: me"
        → ["me"]   (grammar label stripped, real translation kept)

      Format C — complete: "third-person singular present indicative of ser"
        → ["third-person singular present indicative of ser"]

      Format D — bare case label: "dative of él"
        → []   (no useful content)

    Base-form senses (no form_of):
      Use compact_to_flashcard_english which handles colon-preamble stripping,
      parenthetical removal, grammar prose filtering, and deduplication.
      Filter out any segment without alphabetic characters (e.g. "'s").
    """
    if get_tags(sense) & BANNED_SENSE_TAGS:
        return []

    form_of_word = get_original_lemma_from_sense(sense)
    glosses      = get_glosses(sense)
    if not glosses:
        return []

    # ── Form-of sense ─────────────────────────────────────────────────────────
    if form_of_word:
        first = glosses[0].strip()

        # Format A: "inflection of WORD:" + subsequent form-detail lines
        if first.endswith(":") and len(glosses) >= 2:
            details = [
                g.strip() for g in glosses[1:]
                if g.strip() and not g.strip().endswith(":")
            ]
            if details:
                return [f"{d} of {form_of_word}" for d in details]
            return [f"form of {form_of_word}"]

        # Format B: colon-split "GRAMMAR_LABEL: actual translation"
        if ":" in first:
            left, right = first.split(":", 1)
            left  = left.strip()
            right = right.strip()
            if is_segment_grammar_prose(left) and right and not is_segment_grammar_prose(right):
                parts = [p.strip() for p in re.split(r"[;,]", right)]
                return [p for p in parts if p and _has_letters(p) and len(p) <= 50]

        # Format D: bare case label, no content ("dative of él")
        if _is_case_label_only(first):
            return []

        # Format C: complete description ("third-person singular present indicative of ser")
        return [first] if _has_letters(first) else []

    # ── Base-form sense: use compact_to_flashcard_english ─────────────────────
    results: list[str] = []
    for gloss in glosses:
        parts = compact_to_flashcard_english(gloss, wikt_pos, max_options=4)
        for p in parts:
            if _has_letters(p):   # drops "'s", punctuation-only segments
                results.append(p)
    return results


# ── Definition builder ────────────────────────────────────────────────────────

def build_definitions(
    word: str,
    csv_pos: str,
    entries: list[dict],
    max_segments: int = 6,
    max_chars: int = 200,
) -> str:
    matching     = [e for e in entries if _pos_matches(e.get("pos", ""), csv_pos)]
    non_matching = [e for e in entries if not _pos_matches(e.get("pos", ""), csv_pos)]
    to_use       = matching if matching else non_matching

    segments: list[str] = []
    seen: set[str]      = set()

    for entry in to_use:
        wikt_pos = entry.get("pos", "")
        for sense in entry.get("senses") or []:
            if not isinstance(sense, dict):
                continue
            for seg in _sense_definitions(sense, wikt_pos):
                key = seg.lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    segments.append(seg)
                    if len(segments) >= max_segments:
                        break
            if len(segments) >= max_segments:
                break
        if len(segments) >= max_segments:
            break

    result = "; ".join(segments)
    if len(result) > max_chars:
        # Trim at the last full segment boundary
        trimmed = result[:max_chars]
        last_sep = trimmed.rfind("; ")
        result   = trimmed[:last_sep] if last_sep > 0 else trimmed
    return result


# ── Streaming indexer ─────────────────────────────────────────────────────────

def _open_file(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rb")
    return path.open("rb")


def stream_index(
    jsonl_path: Path,
    wanted_words: set[str],
    lang_code: str,
    desc: str,
) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = defaultdict(list)
    lang_code   = lang_code.lower()
    total_bytes = jsonl_path.stat().st_size if jsonl_path.suffix != ".gz" else None
    matched     = 0

    with _open_file(jsonl_path) as f:
        with tqdm(total=total_bytes, desc=desc, unit="B",
                  unit_scale=True, unit_divisor=1024) as pbar:
            for raw_line in f:
                if total_bytes is not None:
                    pbar.update(len(raw_line))
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    obj = orjson.loads(raw_line)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                lc = obj.get("lang_code")
                if not isinstance(lc, str) or lc.lower() != lang_code:
                    continue
                word = obj.get("word")
                if not isinstance(word, str) or word not in wanted_words:
                    continue
                index[word].append(obj)
                matched += 1
                if matched % 5000 == 0:
                    pbar.set_postfix(matched=matched)

    return dict(index)


# ── I/O ───────────────────────────────────────────────────────────────────────

def load_csv(path: Path) -> tuple[list[dict], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader    = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        return list(reader), fieldnames


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _output_fieldnames(input_fieldnames: list[str]) -> list[str]:
    """Insert `definitions` after `translation`; handle already-present case."""
    if "definitions" in input_fieldnames:
        return input_fieldnames
    out: list[str] = []
    for col in input_fieldnames:
        out.append(col)
        if col == "translation":
            out.append("definitions")
    if "definitions" not in out:
        out.append("definitions")
    return out


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a `definitions` column to the Spanish frequency CSV"
    )
    parser.add_argument("--input",      required=True, type=Path)
    parser.add_argument("--output",     required=True, type=Path)
    parser.add_argument("--primary",    required=True, type=Path,
                        help="raw-wiktextract-data.es.jsonl")
    parser.add_argument("--lang-code",  default="es")
    parser.add_argument("--max-senses", type=int, default=6)
    args = parser.parse_args()

    print(f"Loading {args.input} …")
    rows, input_fieldnames = load_csv(args.input)
    out_fieldnames         = _output_fieldnames(input_fieldnames)

    word_pos: dict[str, str] = {}
    for r in rows:
        w = norm_space(r.get("lemma", ""))
        if w and w not in word_pos:
            word_pos[w] = norm_space(r.get("pos", ""))
    wanted = set(word_pos)
    print(f"  {len(rows):,} rows, {len(wanted):,} unique lemmas")

    grouped = stream_index(
        args.primary, wanted, args.lang_code,
        desc="Scanning Wiktionary",
    )
    print(f"  Found entries for {len(grouped):,} / {len(wanted):,} lemmas")

    filled = 0
    for row in tqdm(rows, desc="Building definitions", unit="row"):
        word    = norm_space(row.get("lemma", ""))
        csv_pos = word_pos.get(word, "")
        entries = grouped.get(word, [])
        defn    = build_definitions(word, csv_pos, entries,
                                    max_segments=args.max_senses) if entries else ""
        row["definitions"] = defn
        if defn:
            filled += 1

    write_csv(args.output, rows, out_fieldnames)

    total = len(rows)
    print(f"\n{'─' * 50}")
    print(f"Total rows:           {total:>8,}")
    print(f"Definitions filled:   {filled:>8,}  ({100 * filled / total:.1f}%)")
    print(f"No Wiktionary data:   {total - filled:>8,}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
