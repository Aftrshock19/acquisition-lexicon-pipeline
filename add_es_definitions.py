#!/usr/bin/env python3
"""
add_es_definitions.py

Adds a `definitions` column with full Spanish dictionary definitions sourced
from es-extract.jsonl (Spanish Wiktionary).  Lookup is by the `lemma` column.

Example output:
  comer  → "Ingerir alimentos sólidos o líquidos por la boca..."
  casa   → "Edificio o parte de él destinado a vivienda."

Form-of entries ("forma de ...", "plural de ...") are filtered out so verb
conjugations and noun plurals don't produce useless definitions.

Usage:
  python add_es_definitions.py \\
    --input-csv   spa-eng-lemmatized.csv \\
    --kaikki-jsonl es-extract.jsonl \\
    --output-csv  spa-eng-with-defs.csv
"""

import argparse
import csv
import gzip
import re
from collections import defaultdict
from pathlib import Path

import orjson
from tqdm import tqdm

# ── Filters ───────────────────────────────────────────────────────────────────

BAD_GLOSS_PREFIXES = (
    "forma de ",
    "forma del ",
    "forma flexiva de ",
    "plural de ",
    "singular de ",
    "participio de ",
    "gerundio de ",
    "pasado de ",
    "femenino de ",
    "masculino de ",
    "apócope de ",
    "variante de ",
    "variante ortográfica de ",
    "abreviatura de ",
    "sigla de ",
)

LOW_PRIORITY_TAGS = {
    "arcaico", "antiguo", "obsoleto", "poco usado",
    "desusado", "coloquial", "vulgar", "regional", "dialectal",
}

PREFERRED_POS = {
    "verb": 100, "noun": 95, "adj": 90, "adv": 88,
    "pron": 85, "det": 84, "article": 84,
    "prep": 84, "conj": 84, "interj": 80,
}

# CSV POS → set of wiktextract pos values that match
_CSV_TO_WIKT: dict[str, frozenset[str]] = {
    "verb":         frozenset({"verb"}),
    "noun":         frozenset({"noun", "prop", "proper noun"}),
    "adjective":    frozenset({"adj", "adjective"}),
    "adverb":       frozenset({"adv", "adverb"}),
    "pronoun":      frozenset({"pron", "pronoun"}),
    "determiner":   frozenset({"det", "determiner"}),
    "article":      frozenset({"article", "det", "determiner"}),
    "preposition":  frozenset({"prep", "preposition"}),
    "conjunction":  frozenset({"conj", "conjunction"}),
    "number":       frozenset({"num", "numeral", "number"}),
    "interjection": frozenset({"intj", "interj", "interjection"}),
    "contraction":  frozenset({"contraction"}),
    "phrase":       frozenset({"phrase"}),
    "particle":     frozenset({"particle"}),
    "name":         frozenset({"name", "prop", "proper noun"}),
}


def _pos_matches(wikt_pos: str, csv_pos: str) -> bool:
    return wikt_pos.lower().strip() in _CSV_TO_WIKT.get(csv_pos.lower().strip(), frozenset())

_SPACE_RE        = re.compile(r"\s+")
_LEADING_ENUM_RE = re.compile(r"^\s*\d+[\.\)]\s*")
_LEADING_PUNCT_RE = re.compile(r"^[\s:;,\-–—]+")
_TRAILING_PUNCT_RE = re.compile(r"[\s:;,]+$")


def _clean(gloss: str) -> str:
    gloss = _SPACE_RE.sub(" ", gloss.strip())
    gloss = _LEADING_ENUM_RE.sub("", gloss)
    gloss = _LEADING_PUNCT_RE.sub("", gloss)
    gloss = _TRAILING_PUNCT_RE.sub("", gloss)
    return gloss


def _is_bad(gloss: str) -> bool:
    g = _clean(gloss).lower()
    return any(g.startswith(p) for p in BAD_GLOSS_PREFIXES)


# ── Scoring & picking ─────────────────────────────────────────────────────────

def _score_sense(sense: dict, entry_pos: str) -> int:
    tags       = {str(t).strip().lower() for t in (sense.get("tags") or [])}
    all_glosses = [g for g in (sense.get("glosses") or []) + (sense.get("raw_glosses") or [])
                   if isinstance(g, str) and g.strip()]

    if not all_glosses:
        return -10_000

    score  = PREFERRED_POS.get((entry_pos or "").lower(), 50)
    score += 100 if any(not _is_bad(g) for g in all_glosses) else -100

    if "form-of" in tags or "alt-of" in tags:
        score -= 120

    for tag in tags:
        if tag in LOW_PRIORITY_TAGS:
            score -= 10

    best_len = max((len(_clean(g)) for g in all_glosses), default=0)
    score   += min(best_len, 120)
    return score


def _best_from_entries(entries: list[dict]) -> str:
    """Pick the best non-form-of definition from a list of wiktextract entries."""
    best_def   = ""
    best_score = -10_000

    for entry in entries:
        pos    = str(entry.get("pos", "")).strip()
        senses = entry.get("senses") or []
        ranked = sorted(senses, key=lambda s: _score_sense(s, pos), reverse=True)

        for sense in ranked:
            entry_score = _score_sense(sense, pos)
            if entry_score <= best_score:
                continue
            for source in (sense.get("glosses") or [], sense.get("raw_glosses") or []):
                for gloss in source:
                    if not isinstance(gloss, str):
                        continue
                    cleaned = _clean(gloss)
                    if cleaned and not _is_bad(cleaned):
                        best_def   = cleaned
                        best_score = entry_score
                        break
                if best_def and _score_sense(sense, pos) == best_score:
                    break

    return best_def


def pick_best_definition(entries: list[dict], csv_pos: str = "") -> str:
    """
    Return the best Spanish definition, preferring entries whose POS matches
    the CSV's POS column.  Falls back to all entries if no match found.
    """
    matching     = [e for e in entries if _pos_matches(str(e.get("pos", "")), csv_pos)]
    non_matching = [e for e in entries if not _pos_matches(str(e.get("pos", "")), csv_pos)]

    # Try POS-matching entries first
    if matching:
        defn = _best_from_entries(matching)
        if defn:
            return defn

    # Fall back to remaining entries
    defn = _best_from_entries(non_matching)
    if defn:
        return defn

    # Last resort: accept any gloss even if it's a form-of
    for entry in entries:
        for sense in (entry.get("senses") or []):
            for gloss in (sense.get("glosses") or []):
                cleaned = _clean(str(gloss))
                if cleaned:
                    return cleaned
    return ""


# ── Streaming indexer ─────────────────────────────────────────────────────────

def stream_index(jsonl_path: Path, wanted: set[str]) -> dict[str, list[dict]]:
    """
    Single-pass stream — only keeps Spanish entries (`lang_code == "es"`)
    whose `word` is in `wanted`.

    lang_code filtering is required: es-extract.jsonl is the Spanish Wiktionary
    which contains entries for ALL languages (French, Portuguese, Latin, etc.).
    Without this filter, common words like "de", "en", "y" get definitions from
    the wrong language.
    """
    index: dict[str, list[dict]] = defaultdict(list)
    total_bytes = jsonl_path.stat().st_size if jsonl_path.suffix != ".gz" else None

    with (gzip.open(jsonl_path, "rb") if jsonl_path.suffix == ".gz"
          else jsonl_path.open("rb")) as f:
        with tqdm(total=total_bytes, desc="Scanning es-extract",
                  unit="B", unit_scale=True, unit_divisor=1024) as pbar:
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
                if obj.get("lang_code") != "es":   # skip French, Portuguese, Latin, etc.
                    continue
                word = obj.get("word")
                if isinstance(word, str) and word.strip() in wanted:
                    index[word.strip()].append(obj)

    return dict(index)


# ── Column helpers ────────────────────────────────────────────────────────────

def _output_fieldnames(fieldnames: list[str]) -> list[str]:
    if "definitions" in fieldnames:
        return list(fieldnames)
    out = list(fieldnames)
    if "translation" in out:
        i = out.index("translation")
        out.insert(i + 1, "definitions")
    else:
        out.append("definitions")
    return out


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv",    required=True)
    parser.add_argument("--kaikki-jsonl", required=True)
    parser.add_argument("--output-csv",   required=True)
    args = parser.parse_args()

    input_csv    = Path(args.input_csv)
    kaikki_jsonl = Path(args.kaikki_jsonl)
    output_csv   = Path(args.output_csv)

    # 1. Load CSV and collect wanted lemmas
    with input_csv.open("r", encoding="utf-8", newline="") as f:
        reader     = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        if "lemma" not in fieldnames:
            raise ValueError("Input CSV must contain a 'lemma' column.")
        rows = list(reader)

    word_pos: dict[str, str] = {}
    for r in rows:
        w = (r.get("lemma") or "").strip()
        if w and w not in word_pos:
            word_pos[w] = (r.get("pos") or "").strip()
    wanted = set(word_pos)
    wanted.discard("")
    print(f"Loaded {len(rows):,} rows, {len(wanted):,} unique lemmas")

    # 2. Stream JSONL — Spanish entries only, wanted words only
    grouped = stream_index(kaikki_jsonl, wanted)
    print(f"Found entries for {len(grouped):,} / {len(wanted):,} lemmas")

    # 3. Build definition per lemma (POS-aware)
    def_map: dict[str, str] = {
        word: pick_best_definition(entries, csv_pos=word_pos.get(word, ""))
        for word, entries in grouped.items()
    }

    # 4. Write output
    out_fieldnames = _output_fieldnames(fieldnames)
    filled = 0

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        for row in rows:
            lemma              = (row.get("lemma") or "").strip()
            defn               = def_map.get(lemma, "")
            row["definitions"] = defn
            if defn:
                filled += 1
            writer.writerow({k: row.get(k, "") for k in out_fieldnames})

    total = len(rows)
    print(f"\n{'─' * 50}")
    print(f"Total rows:          {total:>8,}")
    print(f"Definitions filled:  {filled:>8,}  ({100 * filled / total:.1f}%)")
    print(f"No entry found:      {total - filled:>8,}")
    print(f"Output: {output_csv}")


if __name__ == "__main__":
    main()
