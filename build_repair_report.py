#!/usr/bin/env python3
"""
build_repair_report.py

Compression-only repair pipeline for long Spanish example sentences in
spa-eng.csv.

Behavior:
  - process only rows whose Spanish sentence has more than 12 words
  - run deterministic compression only via compress.py
  - never rewrite, regenerate, translate, or call any API
  - if compression changes the Spanish sentence:
      * keep the compressed Spanish
      * delete english_sentence
      * record the rank in deleted_english_ranks.csv
  - if compression does not change the Spanish sentence:
      * leave the row unchanged
      * do not delete english_sentence

Outputs:
  - repair_report.csv
  - repaired_candidates.csv
  - deleted_english_ranks.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import compress as compress_mod

ROOT = Path(__file__).resolve().parent
DEFAULT_SPA_ENG = ROOT / "spa-eng.csv"
DEFAULT_CANDIDATES = ROOT / "repaired_candidates.csv"
DEFAULT_REPORT = ROOT / "repair_report.csv"
DEFAULT_DELETED_RANKS = ROOT / "deleted_english_ranks.csv"

WORD_LIMIT = 12

REPORT_FIELDS = [
    "rank",
    "lemma",
    "original_sentence",
    "final_sentence",
    "original_english_sentence",
    "final_english_sentence",
    "original_word_count",
    "final_word_count",
    "repair_action",
    "sentence_changed",
    "english_deleted",
    "compression_passes_used",
]

CANDIDATE_FIELDS = [
    "rank",
    "lemma",
    "original_sentence",
    "final_sentence",
    "original_english_sentence",
    "final_english_sentence",
    "original_word_count",
    "final_word_count",
    "repair_action",
    "sentence_changed",
    "english_deleted",
    "compression_passes_used",
]

DELETED_RANK_FIELDS = [
    "rank",
    "lemma",
    "original_sentence",
    "final_sentence",
    "original_english_sentence",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spa-eng", type=Path, default=DEFAULT_SPA_ENG)
    parser.add_argument("--candidates-out", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--deleted-ranks-out",
        type=Path,
        default=DEFAULT_DELETED_RANKS,
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-rank", type=int, default=None)
    parser.add_argument("--end-rank", type=int, default=None)
    return parser.parse_args()


def compression_report_row(row: dict[str, str]) -> dict[str, str]:
    original_sentence = (row.get("sentence") or "").strip()
    original_english = row.get("english_sentence") or ""
    lemma = (row.get("lemma") or "").strip()

    compressed = compress_mod.compress(original_sentence, lemma, max_words=WORD_LIMIT)
    final_sentence = compressed.text if compressed.text else original_sentence
    sentence_changed = bool(compressed.passes_used) and final_sentence != original_sentence
    final_english = "" if sentence_changed else original_english

    return {
        "rank": (row.get("rank") or "").strip(),
        "lemma": lemma,
        "original_sentence": original_sentence,
        "final_sentence": final_sentence,
        "original_english_sentence": original_english,
        "final_english_sentence": final_english,
        "original_word_count": str(compress_mod.word_count(original_sentence)),
        "final_word_count": str(compress_mod.word_count(final_sentence)),
        "repair_action": "compress",
        "sentence_changed": "true" if sentence_changed else "false",
        "english_deleted": "true" if sentence_changed else "false",
        "compression_passes_used": ",".join(str(pid) for pid in compressed.passes_used),
    }


def iter_target_rows(
    rows: list[dict[str, str]],
    start_rank: int | None,
    end_rank: int | None,
    limit: int | None,
) -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    for row in rows:
        try:
            rank = int((row.get("rank") or "0").strip())
        except ValueError:
            rank = 0

        if start_rank is not None and rank < start_rank:
            continue
        if end_rank is not None and rank > end_rank:
            continue
        if compress_mod.word_count(row.get("sentence", "")) <= WORD_LIMIT:
            continue

        targets.append(row)
        if limit is not None and len(targets) >= limit:
            break
    return targets


def main() -> int:
    args = parse_args()

    if not args.spa_eng.exists():
        sys.exit(f"missing {args.spa_eng}")

    with args.spa_eng.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    targets = iter_target_rows(rows, args.start_rank, args.end_rank, args.limit)
    print(f"found {len(targets)} long rows to process")

    reports: list[dict[str, str]] = []
    changed_candidates: list[dict[str, str]] = []
    deleted_english_rows: list[dict[str, str]] = []

    for row in targets:
        report_row = compression_report_row(row)
        reports.append(report_row)
        if report_row["sentence_changed"] == "true":
            changed_candidates.append({key: report_row[key] for key in CANDIDATE_FIELDS})
            deleted_english_rows.append(
                {key: report_row[key] for key in DELETED_RANK_FIELDS}
            )

    with args.report_out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(reports)

    with args.candidates_out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_FIELDS)
        writer.writeheader()
        writer.writerows(changed_candidates)

    with args.deleted_ranks_out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DELETED_RANK_FIELDS)
        writer.writeheader()
        writer.writerows(deleted_english_rows)

    print(
        f"processed={len(reports)} changed={len(changed_candidates)} "
        f"unchanged={len(reports) - len(changed_candidates)}"
    )
    print(f"report: {args.report_out}")
    print(f"candidates: {args.candidates_out}")
    print(f"deleted english ranks: {args.deleted_ranks_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
