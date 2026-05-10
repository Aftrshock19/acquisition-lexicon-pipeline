"""
detect_junk.py

Pure rule-based junk detector. No network, no LLM.

A row is considered "junk" if its Spanish sentence is so damaged or so far
from a learner-friendly example that compression cannot save it. Junk rows
should skip compression entirely and go straight to template rewrite or
manual review.

Public API:
    classify_junk(sentence: str, english: str, lemma: str) -> JunkResult
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Marker lists
# ---------------------------------------------------------------------------

DOCUMENT_MARKERS = {
    "reglamento", "reglamentos", "resolución", "resoluciones",
    "artículo", "artículos", "dictamen", "dictámenes",
    "comisión", "comisiones", "parlamento", "parlamentario",
    "informe", "informes", "convención", "convenciones",
    "sede", "ejercicio", "tratado", "tratados",
    "directiva", "directivas", "enmienda", "enmiendas",
    "considerando", "anexo", "anexos", "protocolo",
    "constitución", "decreto", "boletín",
}

# Tokens that frequently appear in OCR garbage from the source corpora.
OCR_HINTS = {
    "ce", "no", "do", "doc", "com", "p", "f", "l", "t", "n",
}


# ---------------------------------------------------------------------------
# Tokenization helpers
# ---------------------------------------------------------------------------

_token_re = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+|\d+", re.UNICODE)


def tokens(text: str) -> list[str]:
    return _token_re.findall(text or "")


def alpha_tokens(text: str) -> list[str]:
    return [t for t in tokens(text) if not t.isdigit()]


def is_capitalized(tok: str) -> bool:
    return bool(tok) and tok[0].isupper() and tok[1:].islower()


# ---------------------------------------------------------------------------
# Individual heuristics
# ---------------------------------------------------------------------------

def has_document_markers(sentence: str) -> bool:
    s = sentence.lower()
    hits = sum(1 for m in DOCUMENT_MARKERS if re.search(rf"\b{m}\b", s))
    return hits >= 1


# Single-letter Spanish words that are LEGITIMATE (not OCR garbage).
_LEGIT_SINGLE = {"a", "e", "o", "u", "y"}

def has_ocr_corruption(sentence: str) -> bool:
    toks = tokens(sentence)
    if not toks:
        return True
    # Many illegitimate single-letter alphabetic tokens => OCR garbage.
    illegit_singles = sum(
        1 for t in toks if len(t) == 1 and t.isalpha() and t.lower() not in _LEGIT_SINGLE
    )
    if illegit_singles >= 2:
        return True
    # Repeated identical adjacent tokens (length > 2).
    for a, b in zip(toks, toks[1:]):
        if a.lower() == b.lower() and len(a) > 2:
            return True
    # Three or more single-char tokens in a row anywhere.
    run = 0
    for t in toks:
        if len(t) == 1 and t.isalpha():
            run += 1
            if run >= 3:
                return True
        else:
            run = 0
    return False


def looks_like_heading(sentence: str) -> bool:
    s = sentence.strip()
    if not s:
        return True
    # No sentence-ending punctuation and no finite-verb cue.
    if not re.search(r"[.!?]$", s):
        # Heading-y nominal phrasing: starts with capital, no verb forms common.
        if not re.search(r"\b(es|son|está|están|hay|ser|estar|fue|fui|fue|tiene|tengo|hace|hizo|va|voy|ir|hacer|tener|haber|puede|pueden|debe|deben|quiere|quiero|sabe|sabes|llega|llegó|come|come|vive|vivió)\b", s, re.IGNORECASE):
            return True
    # Mostly Title Case Words is a heading smell.
    toks = alpha_tokens(s)
    if len(toks) >= 4:
        title_like = sum(1 for t in toks[1:] if is_capitalized(t))
        if title_like / max(1, len(toks) - 1) > 0.5:
            return True
    return False


def has_name_overload(sentence: str, lemma: str) -> bool:
    toks = alpha_tokens(sentence)
    if not toks:
        return False
    capitalized_mid = [
        t for i, t in enumerate(toks)
        if i > 0 and is_capitalized(t) and t.lower() != lemma.lower()
    ]
    return len(capitalized_mid) >= 4


def has_acronym_overload(sentence: str) -> bool:
    toks = tokens(sentence)
    acronyms = [t for t in toks if len(t) >= 2 and t.isupper()]
    return len(acronyms) >= 2


def english_is_broken(english: str) -> bool:
    if not english:
        return False  # absent != broken; we only flag visibly damaged text
    s = english.strip()
    if len(s) < 4:
        return True
    # Lowercase first char and no clear sentence structure.
    if not s[0].isupper() and " " in s:
        return True
    # Tons of trailing fragments.
    if s.count(",") >= 4 and word_count(s) > 25:
        return True
    return False


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or "", re.UNICODE))


# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------

@dataclass
class JunkResult:
    is_junk: bool
    flags: list[str] = field(default_factory=list)
    score: int = 0

    def to_csv_field(self) -> str:
        return ",".join(self.flags)


def classify_junk(sentence: str, english: str, lemma: str) -> JunkResult:
    flags: list[str] = []
    score = 0

    if has_document_markers(sentence):
        flags.append("document_markers")
        score += 3
    if has_ocr_corruption(sentence):
        flags.append("ocr_corruption")
        score += 3
    if looks_like_heading(sentence):
        flags.append("heading_feel")
        score += 3
    if has_name_overload(sentence, lemma):
        flags.append("name_overload")
        score += 2
    if has_acronym_overload(sentence):
        flags.append("acronym_overload")
        score += 2
    if english_is_broken(english):
        flags.append("english_broken")
        score += 2

    return JunkResult(is_junk=score >= 3, flags=flags, score=score)
