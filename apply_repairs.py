#!/usr/bin/env python3
"""
apply_repairs.py

Idempotent applier. Reads repaired_candidates.csv (produced by
build_repair_report.py) and writes final_sentence / final_english_sentence into
spa-eng.csv. The first time it runs it makes a backup at spa-eng.csv.bak.

This script never calls a model and never produces new sentences. It only
moves data from the candidates file into the master file. Blank
final_english_sentence values are valid and will be applied.

Matching is by (rank, lemma). If --by lemma-only is passed, the rank is
ignored and matching is by lemma alone (be careful, this can hit duplicates).

Usage:
  python apply_repairs.py --dry-run
  python apply_repairs.py
  python apply_repairs.py --candidates other_candidates.csv
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPA_ENG = ROOT / "spa-eng.csv"
BACKUP = ROOT / "spa-eng.csv.bak"
DEFAULT_CANDIDATES = ROOT / "repaired_candidates.csv"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--by", choices=["rank-lemma", "lemma"], default="rank-lemma")
    return p.parse_args()


def load_candidates(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        sys.exit(f"missing candidates file: {path}")
    out: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = f"{r.get('rank','').strip()}|{r.get('lemma','').strip()}"
            out[key] = r
    return out


def main() -> int:
    args = parse_args()
    if not SPA_ENG.exists():
        sys.exit(f"missing {SPA_ENG}")

    candidates = load_candidates(args.candidates)
    if not candidates:
        sys.exit("no candidates to apply")

    print(f"loaded {len(candidates)} candidates from {args.candidates.name}")

    with SPA_ENG.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    if "sentence" not in fieldnames or "english_sentence" not in fieldnames:
        sys.exit("spa-eng.csv missing expected columns")

    by_lemma: dict[str, dict[str, str]] = {}
    if args.by == "lemma":
        by_lemma = {v["lemma"]: v for v in candidates.values()}

    updated = 0
    skipped = 0
    for row in rows:
        rank = (row.get("rank") or "").strip()
        lemma = (row.get("lemma") or "").strip()
        cand: dict[str, str] | None = None
        if args.by == "rank-lemma":
            cand = candidates.get(f"{rank}|{lemma}")
        else:
            cand = by_lemma.get(lemma)
        if cand is None:
            continue
        new_es = (cand.get("final_sentence") or "").strip()
        new_en = cand.get("final_english_sentence") or ""
        if not new_es:
            skipped += 1
            continue
        if row.get("sentence") == new_es and row.get("english_sentence") == new_en:
            continue  # already applied, idempotent
        row["sentence"] = new_es
        row["english_sentence"] = new_en
        updated += 1

    print(f"would update {updated} rows ({skipped} candidates skipped due to empty Spanish)")

    if args.dry_run:
        print("dry-run: spa-eng.csv not modified")
        return 0

    if updated == 0:
        print("nothing to do")
        return 0

    if not BACKUP.exists():
        shutil.copy2(SPA_ENG, BACKUP)
        print(f"backup written to {BACKUP.name}")

    tmp = SPA_ENG.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(SPA_ENG)
    print(f"updated {SPA_ENG.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
