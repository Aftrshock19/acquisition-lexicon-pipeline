#!/usr/bin/env python3
"""
add_original_lemma.py

Adds an `original_lemma` column to spa-eng.csv, mapping every word form to its
canonical dictionary headword across all POS types:
  - inflected nouns:   casas → casa
  - gender forms:      buena → bueno, estas → este
  - apocopic forms:    gran → grande
  - contractions:      al → a + el, del → de + el
  - verb forms:        era → ser, etc.

Resolution order (per word):
  1. Hardcoded overrides (contractions, known edge cases)
  2. POS-matched entries in primary JSONL — structured form_of/alt_of fields
  3. POS-matched entries in primary JSONL — gloss regex fallback
  4. If POS-matched entries exist but none have form_of → word IS a base form
  5. Non-POS-matched entries in primary JSONL (for words not in Wiktionary at
     the expected POS) — same structured+regex logic
  6. Repeat 2–5 for secondary JSONL (es-extract.jsonl), if provided
  7. Default: original_lemma = lemma (no Wiktionary data found)

Usage:
  python add_original_lemma.py \\
    --input   spa-eng.csv \\
    --output  spa-eng-lemmatized.csv \\
    --primary raw-wiktextract-data.es.jsonl \\
    --secondary es-extract.jsonl          # optional

Output columns (order preserved):
  rank, lemma, original_lemma, translation, pos, sentence, english_sentence
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

# ── Import shared helpers from the sibling script ────────────────────────────
# build_wiktionary_glosses_40k.py guards main() so it's safe to import.
try:
    from build_wiktionary_glosses_40k import (
        norm_space,
        get_original_lemma_from_sense,
        get_tags,
        get_glosses,
        BANNED_SENSE_TAGS,
    )
except ImportError as exc:
    sys.exit(
        f"Cannot import from build_wiktionary_glosses_40k.py — "
        f"make sure it is in the same directory.\n{exc}"
    )

# ── Hardcoded overrides ───────────────────────────────────────────────────────
# These take priority over everything else.
HARDCODED: dict[str, str] = {
    "al":  "a + el",   # contraction of a + el
    "del": "de + el",  # contraction of de + el
}

# ── POS mapping: CSV label → set of Wiktionary pos values ────────────────────
# Used to select only the right-POS entries for a word (e.g. treat `hermano`
# only as a noun, not as a verb form of `hermanar`).
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


def _pos_matches(wikt_pos: str, csv_pos: str) -> bool:
    wikt = wikt_pos.lower().strip()
    variants = _CSV_TO_WIKT.get(csv_pos.lower().strip(), frozenset())
    return wikt in variants


# ── Form-of regex patterns ────────────────────────────────────────────────────
# Applied to English glosses (primary source: raw-wiktextract-data.es.jsonl).
_FORM_OF_EN = re.compile(
    r"\b(?:"
    r"plural|singular|feminine|masculine|"
    r"apocopic(?:\s+form)?|"
    r"diminutive|augmentative|"
    r"comparative|superlative|"
    r"inflection|"
    r"(?:alternative|alternate)\s+(?:form|spelling)|"
    r"(?:inflected\s+form)"
    r")\s+of\s+([^\s,;.()\[\]]+)",
    re.IGNORECASE,
)

# Applied to Spanish glosses (secondary source: es-extract.jsonl).
_FORM_OF_ES = re.compile(
    r"\b(?:"
    r"plural|singular|femenino|masculino|"
    r"apócope|apocope|"
    r"diminutivo|aumentativo|"
    r"comparativo|superlativo|"
    r"forma\s+(?:femenina|masculina|alternativa)|"
    r"forma"
    r")\s+de\s+([^\s,;.()\[\]]+)",
    re.IGNORECASE,
)


def _is_valid_lemma(candidate: str) -> bool:
    """Reject multi-word strings, empty values, or implausibly long tokens."""
    if not candidate:
        return False
    if " " in candidate:   # multi-word (e.g. "él and usted") → skip
        return False
    if len(candidate) > 40:
        return False
    return True


# ── Streaming indexer ─────────────────────────────────────────────────────────

def _open(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rb")
    return path.open("rb")


def stream_index(
    jsonl_path: Path,
    wanted_words: set[str],
    lang_code: str,
    desc: str,
) -> dict[str, list[dict]]:
    """
    Single-pass stream over a kaikki.org JSONL file.
    Returns {word: [entry, ...]} for every word in wanted_words.
    Only entries whose lang_code matches are collected.
    """
    index: dict[str, list[dict]] = defaultdict(list)
    lang_code = lang_code.lower()
    total_bytes = _path_size(jsonl_path)
    matched = 0

    with _open(jsonl_path) as f:
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


def _path_size(path: Path) -> Optional[int]:
    if path.suffix == ".gz":
        return None
    try:
        return path.stat().st_size
    except OSError:
        return None


# ── Core resolution logic ─────────────────────────────────────────────────────

def _form_of_from_entries(
    word: str,
    entries: list[dict],
    gloss_re: re.Pattern,
) -> list[str]:
    """
    Collect candidate base-lemma strings from a list of wiktextract entries.
    Tries structured form_of/alt_of first, then gloss regex.
    Rejects the word itself, multi-word values, and banned-tag senses.
    """
    candidates: list[str] = []
    seen: set[str] = set()

    for entry in entries:
        for sense in entry.get("senses") or []:
            if not isinstance(sense, dict):
                continue
            if get_tags(sense) & BANNED_SENSE_TAGS:
                continue

            # Structured link fields (form_of / alt_of)
            base = get_original_lemma_from_sense(sense)
            if base and base != word and _is_valid_lemma(base) and base not in seen:
                seen.add(base)
                candidates.append(base)
                continue  # structured field wins for this sense

            # Gloss text regex fallback
            for gloss in get_glosses(sense):
                m = gloss_re.search(gloss)
                if m:
                    base = m.group(1).strip(".,;:")
                    if base and base != word and _is_valid_lemma(base) and base not in seen:
                        seen.add(base)
                        candidates.append(base)

    return candidates


def resolve_original_lemma(
    word: str,
    csv_pos: str,
    entries: list[dict],
    lemma_set: set[str],
    gloss_re: re.Pattern,
) -> Optional[str]:
    """
    Return the best original_lemma for `word`, or None to signal "keep as-is".

    Logic:
    1. Split entries into POS-matching vs. non-matching.
    2. Try POS-matching entries first.
       - If any form_of found → return it (prefer one present in lemma_set).
       - If POS-matching entries EXIST but have NO form_of → word is a base
         form at this POS → return None (caller keeps lemma unchanged).
    3. If no POS-matching entries, try all entries (same form_of search).
       - form_of found → return it.
       - None found → return None (caller keeps lemma unchanged).
    """
    matching     = [e for e in entries if _pos_matches(e.get("pos", ""), csv_pos)]
    non_matching = [e for e in entries if not _pos_matches(e.get("pos", ""), csv_pos)]

    def _best(candidates: list[str]) -> Optional[str]:
        if not candidates:
            return None
        for c in candidates:
            if c in lemma_set:
                return c
        return candidates[0]

    if matching:
        cands = _form_of_from_entries(word, matching, gloss_re)
        if cands:
            return _best(cands)
        # POS-matching entries exist but no form_of → already a base form
        return None

    # No POS-matching entries → try everything
    cands = _form_of_from_entries(word, non_matching, gloss_re)
    return _best(cands)


# ── I/O ───────────────────────────────────────────────────────────────────────

OUTPUT_FIELDNAMES = [
    "rank", "lemma", "original_lemma", "translation", "pos",
    "sentence", "english_sentence",
]


def load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in OUTPUT_FIELDNAMES})


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add original_lemma column to a Spanish frequency CSV"
    )
    parser.add_argument("--input",     required=True, type=Path,
                        help="Input CSV (spa-eng.csv)")
    parser.add_argument("--output",    required=True, type=Path,
                        help="Output CSV with original_lemma column")
    parser.add_argument("--primary",   required=True, type=Path,
                        help="Primary JSONL: raw-wiktextract-data.es.jsonl")
    parser.add_argument("--secondary", type=Path, default=None,
                        help="Secondary JSONL: es-extract.jsonl (optional)")
    parser.add_argument("--lang-code", default="es",
                        help="Wiktionary language code (default: es)")
    args = parser.parse_args()

    # ── Load CSV ──────────────────────────────────────────────────────────────
    print(f"Loading {args.input} …")
    rows     = load_csv(args.input)
    # Build (word, csv_pos) lookup — one pos per unique word (first occurrence wins)
    word_pos: dict[str, str] = {}
    for r in rows:
        w = norm_space(r.get("lemma", ""))
        if w and w not in word_pos:
            word_pos[w] = norm_space(r.get("pos", ""))
    lemma_set = set(word_pos.keys())
    print(f"  {len(rows):,} rows, {len(lemma_set):,} unique lemmas")

    # resolved[word] = base lemma string (may equal word if already base)
    # A missing key means "not yet processed".
    resolved: dict[str, str] = {}

    # ── Hardcoded overrides ───────────────────────────────────────────────────
    for word, base in HARDCODED.items():
        resolved[word] = base
    print(f"  {len(HARDCODED)} hardcoded overrides applied")

    unresolved: set[str] = lemma_set - set(resolved)

    # ── Primary JSONL pass ────────────────────────────────────────────────────
    grouped_primary = stream_index(
        args.primary, set(unresolved), args.lang_code,
        desc="Primary scan (raw-wiktextract)",
    )

    still_after_primary: set[str] = set()
    for word in tqdm(unresolved, desc="Resolving (primary)", unit="word"):
        entries = grouped_primary.get(word)
        if not entries:
            # No Wiktionary data at all → leave for secondary or default
            still_after_primary.add(word)
            continue
        csv_pos = word_pos.get(word, "")
        base    = resolve_original_lemma(word, csv_pos, entries, lemma_set, _FORM_OF_EN)
        resolved[word] = base if base is not None else word

    # Words with no primary data
    for word in still_after_primary:
        pass  # handled below by secondary or final default

    resolved_count = sum(1 for w, b in resolved.items() if b != w)
    print(f"  Mapped to a base (primary):  {resolved_count:,}")
    print(f"  No primary data:             {len(still_after_primary):,}")

    # ── Secondary JSONL pass (only words with no primary data) ───────────────
    if args.secondary and still_after_primary:
        grouped_secondary = stream_index(
            args.secondary, set(still_after_primary), args.lang_code,
            desc="Secondary scan (es-extract)",
        )
        for word in tqdm(still_after_primary, desc="Resolving (secondary)", unit="word"):
            entries = grouped_secondary.get(word)
            if not entries:
                resolved[word] = word  # no data anywhere → base form
                continue
            csv_pos = word_pos.get(word, "")
            base    = resolve_original_lemma(word, csv_pos, entries, lemma_set, _FORM_OF_ES)
            resolved[word] = base if base is not None else word

        resolved_count2 = sum(1 for w, b in resolved.items() if b != w)
        print(f"  Mapped to a base (after secondary): {resolved_count2:,}")

    # Any word still missing from resolved (no data at all) → identity
    for word in lemma_set:
        if word not in resolved:
            resolved[word] = word

    # ── Attach original_lemma to every row ────────────────────────────────────
    changed = 0
    for row in rows:
        word = norm_space(row.get("lemma", ""))
        base = resolved.get(word, word)
        row["original_lemma"] = base
        if base != word:
            changed += 1

    # ── Write output ──────────────────────────────────────────────────────────
    write_csv(args.output, rows)

    total = len(rows)
    print(f"\n{'─' * 50}")
    print(f"Total rows:              {total:>8,}")
    print(f"Forms mapped to a base:  {changed:>8,}  ({100 * changed / total:.1f}%)")
    print(f"Already base form:       {total - changed:>8,}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
