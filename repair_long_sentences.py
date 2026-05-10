#!/usr/bin/env python3
"""
repair_long_sentences.py

Repair Spanish example sentences in spa-eng.csv where the Spanish sentence has
more than 12 words. For each long row the script asks Claude to:

  1. classify the row as compress | rewrite | regenerate
  2. produce a final Spanish sentence (<= 12 words, target form preserved)
  3. produce a fresh English translation generated from the final Spanish
  4. validate both sides and escalate on failure

Outputs:
  - spa-eng.csv             : updated in place (sentence + english_sentence
                              replaced for accepted repairs). A backup is
                              written to spa-eng.csv.bak the first time.
  - repair_report.csv       : full audit trail with every field from the spec.
                              Written incrementally so the script is resumable.

Usage:
  python repair_long_sentences.py --limit 20 --dry-run
  python repair_long_sentences.py --model claude-sonnet-4-6
  python repair_long_sentences.py --start-rank 1000 --end-rank 2000

Requires: anthropic, ANTHROPIC_API_KEY in env.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Optional

def _load_anthropic():
    try:
        from anthropic import Anthropic
        return Anthropic
    except ImportError:
        sys.exit("anthropic SDK not installed. Run: pip install anthropic")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
SPA_ENG = ROOT / "spa-eng.csv"
BACKUP = ROOT / "spa-eng.csv.bak"
REPORT = ROOT / "repair_report.csv"

WORD_LIMIT = 12

REPORT_FIELDS = [
    "rank",
    "lemma",
    "original_sentence",
    "original_english_sentence",
    "original_word_count",
    "repair_action",
    "repair_reason",
    "final_sentence",
    "final_english_sentence",
    "final_word_count",
    "final_character_count",
    "spanish_valid",
    "english_valid",
    "needs_manual_review",
    "pos_family",
    "target_form_preserved",
    "compression_passes_used",
    "template_id",
    "junk_flags",
    "naturalness_score",
    "clarity_score",
    "escalations",
    "error",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_word_re = re.compile(r"\w+", re.UNICODE)


def word_count(text: str) -> int:
    if not text:
        return 0
    return len(_word_re.findall(text))


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def target_present(sentence: str, lemma: str) -> bool:
    """Loose check: does the lemma surface appear as its own token?

    The model is also asked to preserve the target form, but this guards
    against the obvious failure mode where the lemma is gone entirely.
    """
    if not sentence or not lemma:
        return False
    pattern = r"(?<!\w)" + re.escape(lemma) + r"(?!\w)"
    return re.search(pattern, sentence, flags=re.IGNORECASE) is not None


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You repair long Spanish example sentences for a Spanish-English
flashcard learning deck. Each row has a TARGET LEMMA (a specific Spanish word
or surface form) and a long Spanish example sentence with an English
translation. The Spanish sentence has more than 12 words and must be repaired.

You must choose exactly one of three repair actions:

1. compress  - source is grammatical, target form is used naturally, the main
               clause is good, extra length comes from removable adjuncts /
               subordinate clauses / names that can be cut.
2. rewrite   - source is grammatical-ish but stiff, legal, formal, or
               compression would still sound bad. Build a short fresh sentence
               around the same target form using simple high-frequency vocab.
3. regenerate- source is junk: title/heading fragment, OCR damage, name-chain
               overload, broken English, no clear teachable clause, or
               document/legal boilerplate without learner value.

Strict rules for the FINAL Spanish sentence:
- The exact target form (lemma) MUST appear, conjugated/written as in the
  source if a verb form, otherwise the lemma surface.
- 5 to 10 words preferred, hard maximum 12 words.
- One clause (at most one very light subordinate).
- Self-contained, no unresolved pronouns like "eso" / "ello" referring to
  removed context.
- Natural, learner-friendly Spanish, high-frequency support vocabulary.
- No legal/document/heading feel.

Strict rules for the FINAL English sentence:
- Generate it FRESH from the final Spanish sentence only. Do NOT repair the
  original English. Do not preserve details that no longer exist in Spanish.
- Faithful, concise, grammatical, natural. 4-12 words preferred.
- Tense, person, number, polarity, modality must match the Spanish.

Compression passes (apply in order, stop as soon as <=12 words and natural):
  1. Remove discourse fillers (entonces, además, bueno, claro, ...)
  2. Remove optional time/place phrases
  3. Remove nonessential modifiers / intensifiers
  4. Remove subordinate clauses (que..., porque..., mientras..., cuando...)
  5. Reduce to one clause - keep the one carrying the target
  6. Remove proper names / institutional detail
  7. Simplify syntax

Template bank for rewrite (pick the best match for the target's POS family):

VERB / present indicative      : "Yo [v] mucho." / "Ella [v] aquí."
VERB / preterite               : "Ayer [v] solo." / "Por fin [v]."
VERB / imperfect               : "Antes [v] allí." / "De niño [v] mucho."
VERB / future                  : "Mañana [v]." / "El precio [v] pronto."
VERB / present subjunctive     : "Espero que [v]." / "Quiero que [v]."
                                 "Es posible que [v]." / "Dudo que [v]."
VERB / imperfect subjunctive   : "Si [v], yo iría." / "Ojalá [v]."
VERB / present perfect subj.   : "Es posible que [v]." / "Espero que ya [v]."
VERB / gerund                  : "Está [v]." / "Sigue [v]." / "Aprende [v]."
VERB / past participle (adj)   : "Está [p]." / "Fue [p]." / "Quedó [p]."
NOUN                           : "Hay [n]." / "Tengo [n]." / "Necesitamos [n]."
ADJECTIVE                      : "Es [a]." / "Son [a]." / "[N] está [a]."
ADVERB                         : "Habla [adv]." / "Llegó [adv]."

Function words / fragile items - prefer rewrite or regenerate:
  tan    : "No está tan mal."
  aun    : "Aun así, siguió adelante."
  ello   : "No quiero hablar de ello."
  uno    : "Solo uno faltaba."
  cuya   : "Conocí a una mujer cuya hija vive aquí."
  porque : "No fui porque llovía."
  aunque : "Aunque estaba cansado, siguió."

Hard rejects for the final Spanish:
- > 12 words
- target form missing
- > 1 real clause
- OCR damage / unresolved reference / heading feel / random names dominate
- support vocabulary far harder than the target

You MUST respond with a single JSON object and nothing else, matching:

{
  "repair_action": "compress" | "rewrite" | "regenerate",
  "repair_reason": "<one short sentence>",
  "pos_family": "<verb_present|verb_preterite|verb_imperfect|verb_future|verb_pres_subj|verb_imp_subj|verb_pres_perf_subj|verb_gerund|verb_participle|noun|adjective|adverb|function_word|other>",
  "template_id": "<template name from bank if rewrite/regenerate, else null>",
  "compression_passes_used": [<integers from 1..7>],
  "junk_flags": [<short strings, empty list if none>],
  "final_sentence": "<final Spanish, target form preserved, <=12 words>",
  "final_english_sentence": "<fresh English translation of final_sentence>",
  "target_form_preserved": true | false,
  "spanish_valid": true | false,
  "english_valid": true | false,
  "naturalness_score": <integer 0..10>,
  "clarity_score": <integer 0..10>,
  "needs_manual_review": true | false
}
"""


USER_TEMPLATE = """TARGET LEMMA: {lemma}
ORIGINAL SPANISH ({wc} words): {sentence}
ORIGINAL ENGLISH: {english}
POS HINT: {pos}

Repair this row. Respond with the JSON object only."""


ESCALATION_NOTE = """\n\nNOTE: A previous attempt with action "{prev}" failed validation
because: {why}. Use a stronger action this time."""


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------

def call_claude(client, model: str, user_msg: str,
                max_tokens: int = 1024) -> dict[str, Any]:
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(
        block.text for block in resp.content if getattr(block, "type", "") == "text"
    ).strip()
    # Strip markdown fences if the model added them.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # Last resort: pull the first {...} block.
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise ValueError(f"Model returned non-JSON: {text[:200]}") from exc


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_spanish(final: str, lemma: str) -> tuple[bool, str]:
    if not final:
        return False, "empty final sentence"
    wc = word_count(final)
    if wc > WORD_LIMIT:
        return False, f"final spanish has {wc} words (>12)"
    if not target_present(final, lemma):
        return False, f"target lemma '{lemma}' missing from final spanish"
    return True, ""


def validate_english(final_en: str) -> tuple[bool, str]:
    if not final_en:
        return False, "empty final english"
    if word_count(final_en) > 18:
        return False, "english is too long"
    return True, ""


# ---------------------------------------------------------------------------
# Main repair routine
# ---------------------------------------------------------------------------

def repair_row(client, model: str, row: dict[str, str]) -> dict[str, Any]:
    lemma = row["lemma"]
    sentence = row["sentence"]
    english = row["english_sentence"]
    pos = row.get("pos", "")
    wc = word_count(sentence)

    base_msg = USER_TEMPLATE.format(
        lemma=lemma, wc=wc, sentence=sentence, english=english, pos=pos or "unknown"
    )

    escalations: list[str] = []
    last_result: dict[str, Any] = {}
    last_error: str = ""
    user_msg = base_msg

    for attempt in range(3):  # initial + 2 escalations
        try:
            result = call_claude(client, model, user_msg)
        except Exception as exc:
            last_error = f"api/json error: {exc}"
            break

        last_result = result

        final_es = (result.get("final_sentence") or "").strip()
        final_en = (result.get("final_english_sentence") or "").strip()

        ok_es, why_es = validate_spanish(final_es, lemma)
        if not ok_es:
            escalations.append(f"attempt{attempt+1}:{result.get('repair_action')}:{why_es}")
            user_msg = base_msg + ESCALATION_NOTE.format(
                prev=result.get("repair_action", "?"), why=why_es
            )
            last_error = why_es
            continue

        ok_en, why_en = validate_english(final_en)
        if not ok_en:
            escalations.append(f"attempt{attempt+1}:english:{why_en}")
            user_msg = base_msg + ESCALATION_NOTE.format(
                prev=result.get("repair_action", "?"), why=why_en
            )
            last_error = why_en
            continue

        # success
        return _build_report(row, wc, result, escalations, error="", success=True)

    return _build_report(row, wc, last_result, escalations, error=last_error,
                         success=False)


def _build_report(row: dict[str, str], wc: int, result: dict[str, Any],
                  escalations: list[str], error: str,
                  success: bool) -> dict[str, Any]:
    final_es = (result.get("final_sentence") or "").strip()
    final_en = (result.get("final_english_sentence") or "").strip()
    return {
        "rank": row.get("rank", ""),
        "lemma": row.get("lemma", ""),
        "original_sentence": row.get("sentence", ""),
        "original_english_sentence": row.get("english_sentence", ""),
        "original_word_count": wc,
        "repair_action": result.get("repair_action", ""),
        "repair_reason": result.get("repair_reason", ""),
        "final_sentence": final_es,
        "final_english_sentence": final_en,
        "final_word_count": word_count(final_es),
        "final_character_count": len(final_es),
        "spanish_valid": bool(result.get("spanish_valid")) and success,
        "english_valid": bool(result.get("english_valid")) and success,
        "needs_manual_review": (not success) or bool(result.get("needs_manual_review")),
        "pos_family": result.get("pos_family", ""),
        "target_form_preserved": bool(result.get("target_form_preserved")),
        "compression_passes_used": ",".join(
            str(x) for x in (result.get("compression_passes_used") or [])
        ),
        "template_id": result.get("template_id") or "",
        "junk_flags": ",".join(result.get("junk_flags") or []),
        "naturalness_score": result.get("naturalness_score", ""),
        "clarity_score": result.get("clarity_score", ""),
        "escalations": " | ".join(escalations),
        "error": error,
    }


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

def load_rows() -> tuple[list[str], list[dict[str, str]]]:
    with SPA_ENG.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def save_rows(fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    tmp = SPA_ENG.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(SPA_ENG)


def open_report(resume: bool) -> tuple[Any, Any, set[str]]:
    done_keys: set[str] = set()
    mode = "a" if (resume and REPORT.exists()) else "w"
    if mode == "a":
        with REPORT.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                done_keys.add(f"{r.get('rank','')}|{r.get('lemma','')}")
    f = REPORT.open(mode, newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
    if mode == "w":
        writer.writeheader()
        f.flush()
    return f, writer, done_keys


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="claude-sonnet-4-6",
                   help="Anthropic model id (default: claude-sonnet-4-6)")
    p.add_argument("--limit", type=int, default=None,
                   help="process at most N long rows (after start/end filters)")
    p.add_argument("--start-rank", type=int, default=None)
    p.add_argument("--end-rank", type=int, default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="do not modify spa-eng.csv, only write the report")
    p.add_argument("--no-resume", action="store_true",
                   help="overwrite repair_report.csv instead of appending")
    p.add_argument("--sleep", type=float, default=0.0,
                   help="seconds to sleep between API calls")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set in the environment")

    Anthropic = _load_anthropic()
    client = Anthropic()

    fieldnames, rows = load_rows()
    if "sentence" not in fieldnames or "english_sentence" not in fieldnames:
        sys.exit("spa-eng.csv missing expected columns")

    # Backup once.
    if not args.dry_run and not BACKUP.exists():
        shutil.copy2(SPA_ENG, BACKUP)
        print(f"backup written to {BACKUP.name}")

    # Pick rows to process.
    targets: list[tuple[int, dict[str, str]]] = []
    for idx, row in enumerate(rows):
        try:
            rank = int(row.get("rank") or 0)
        except ValueError:
            rank = 0
        if args.start_rank is not None and rank < args.start_rank:
            continue
        if args.end_rank is not None and rank > args.end_rank:
            continue
        if word_count(row.get("sentence", "")) > WORD_LIMIT:
            targets.append((idx, row))

    print(f"found {len(targets)} long rows (> {WORD_LIMIT} words)")

    report_f, report_w, done_keys = open_report(resume=not args.no_resume)
    if done_keys:
        print(f"resuming, {len(done_keys)} rows already in repair_report.csv")

    processed = 0
    accepted = 0
    failed = 0
    try:
        for idx, row in targets:
            key = f"{row.get('rank','')}|{row.get('lemma','')}"
            if key in done_keys:
                continue
            if args.limit is not None and processed >= args.limit:
                break

            processed += 1
            lemma = row.get("lemma", "")
            print(f"[{processed}] rank={row.get('rank','?')} lemma={lemma!r} "
                  f"wc={word_count(row.get('sentence',''))}")

            try:
                report = repair_row(client, args.model, row)
            except Exception as exc:
                print(f"   ! unhandled error: {exc}")
                report = _build_report(
                    row, word_count(row.get("sentence", "")),
                    {}, [], error=str(exc), success=False,
                )

            report_w.writerow(report)
            report_f.flush()

            if report["spanish_valid"] and report["english_valid"]:
                accepted += 1
                rows[idx]["sentence"] = report["final_sentence"]
                rows[idx]["english_sentence"] = report["final_english_sentence"]
                print(f"   ✓ {report['repair_action']}: {report['final_sentence']}")
            else:
                failed += 1
                print(f"   ✗ manual review needed ({report['error']})")

            if args.sleep:
                time.sleep(args.sleep)
    finally:
        report_f.close()

    print(f"\nprocessed={processed} accepted={accepted} "
          f"manual_review={failed}")

    if not args.dry_run and accepted > 0:
        save_rows(fieldnames, rows)
        print(f"updated {SPA_ENG.name} in place")
    elif args.dry_run:
        print("dry-run: spa-eng.csv not modified")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
