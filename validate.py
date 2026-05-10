"""
validate.py

Acceptance rules for repaired Spanish + English sentence pairs.
No network. No LLM. Pure functions.

Public API:
    validate_spanish(text: str, lemma: str) -> ValidationResult
    validate_english(text: str) -> ValidationResult
"""

from __future__ import annotations

import re
from dataclasses import dataclass

WORD_LIMIT_ES = 12
WORD_LIMIT_EN = 18  # English allowed a little more headroom

_WORD_RE = re.compile(r"\w+", re.UNICODE)

UNRESOLVED_PRONOUNS = {"eso", "ello", "esto", "aquello"}


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def _lemma_present(text: str, lemma: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(lemma) + r"(?!\w)",
                          text or "", flags=re.IGNORECASE))


def validate_spanish(text: str, lemma: str) -> ValidationResult:
    if not text:
        return ValidationResult(False, "empty")
    text = text.strip()
    wc = _word_count(text)
    if wc > WORD_LIMIT_ES:
        return ValidationResult(False, f"{wc} words (>{WORD_LIMIT_ES})")
    if wc < 3:
        return ValidationResult(False, f"{wc} words (too short)")
    if not _lemma_present(text, lemma):
        return ValidationResult(False, f"target '{lemma}' missing")
    if not text[0].isalpha() and not text[0] in "¿¡":
        return ValidationResult(False, "does not start with a letter")
    if not text[0].isupper() and text[0] not in "¿¡":
        return ValidationResult(False, "first letter not capitalized")
    if text[-1] not in ".!?":
        return ValidationResult(False, "missing terminal punctuation")
    # Unresolved deictics that almost certainly point at deleted context.
    toks_lower = [t.lower() for t in _WORD_RE.findall(text)]
    if toks_lower and toks_lower[0] in UNRESOLVED_PRONOUNS:
        return ValidationResult(False, f"opens with unresolved pronoun '{toks_lower[0]}'")
    # No more than one comma group (rough single-clause test).
    if text.count(",") > 1:
        return ValidationResult(False, "too many commas (>1 clause)")
    return ValidationResult(True)


def validate_english(text: str) -> ValidationResult:
    if not text:
        return ValidationResult(False, "empty")
    text = text.strip()
    wc = _word_count(text)
    if wc > WORD_LIMIT_EN:
        return ValidationResult(False, f"{wc} words (>{WORD_LIMIT_EN})")
    if wc < 2:
        return ValidationResult(False, f"{wc} words (too short)")
    if "[" in text or "]" in text:
        return ValidationResult(False, "contains unresolved gloss placeholder")
    if not text[0].isalpha():
        return ValidationResult(False, "does not start with a letter")
    if not text[0].isupper():
        return ValidationResult(False, "first letter not capitalized")
    if text[-1] not in ".!?":
        return ValidationResult(False, "missing terminal punctuation")
    return ValidationResult(True)
