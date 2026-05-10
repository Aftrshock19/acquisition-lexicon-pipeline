"""
compress.py

Deterministic compression passes for long Spanish example sentences.
No network. No LLM. Operates on string + lemma only.

The goal: bring the sentence to <= 12 words while preserving the exact target
surface form (the lemma) and one clean clause.

Public API:
    compress(sentence: str, lemma: str, max_words: int = 12) -> CompressResult
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Constants used by the passes
# ---------------------------------------------------------------------------

# Discourse fillers - safe to delete from any position.
DISCOURSE_FILLERS = [
    r"entonces",
    r"etnonces",
    r"adem[áa]s",
    r"por consiguiente",
    r"en segundo lugar",
    r"en primer lugar",
    r"en tercer lugar",
    r"de hecho",
    r"bueno",
    r"claro",
    r"pues",
    r"as[íi] pues",
    r"por lo tanto",
    r"sin embargo",
    r"no obstante",
    r"asimismo",
    r"por otra parte",
    r"por otro lado",
    r"dicho esto",
    r"en realidad",
    r"en cualquier caso",
    r"a propósito",
    r"de todos modos",
    r"de todas formas",
    r"a decir verdad",
]

# Optional time/place phrases that can typically be removed.
TIME_PLACE_PHRASES = [
    r"\bayer\b",
    r"\bhoy\b",
    r"\besta ma[ñn]ana\b",
    r"\besta tarde\b",
    r"\besta noche\b",
    r"\banoche\b",
    r"\bel a[ñn]o pasado\b",
    r"\bel mes pasado\b",
    r"\bla semana pasada\b",
    r"\ben el centro(?:\s+de\s+[^,.]+?)?(?=[,.]|$)",
    r"\ba nivel nacional\b",
    r"\ba nivel internacional\b",
    r"\ben todo el mundo\b",
    r"\ben todo el pa[íi]s\b",
    r"\bdurante (un|el|los|las|una|muchos|muchas) [a-zA-ZáéíóúñÁÉÍÓÚÑ]+\b",
    r"\ben la sede de [^,.]+?(?=[,.]|$)",
    r"\ben el a[ñn]o \d+",
    r"\ben \d{4}",
    r"\bel \w+ por la (ma[ñn]ana|tarde|noche)\b",
]

# Subordinate-clause heads we will chop *after* the main clause.
SUBORDINATE_HEADS = [
    " porque ",
    " mientras ",
    " mientras que ",
    " cuando ",
    " aunque ",
    " tras haber ",
    " después de ",
    " antes de ",
    " ya que ",
    " puesto que ",
    " a pesar de ",
    " si bien ",
]

# Coordinators on which we may split into clauses.
COORDINATORS = [" y ", " pero ", " o ", " sino "]

# Sentence-ending punctuation we want to leave/restore.
END_PUNCT_RE = re.compile(r"[.!?]$")

_WORD_RE = re.compile(r"\w+", re.UNICODE)

WINDOW_BAD_START_WORDS = {
    "y", "e", "o", "u", "pero", "sino", "que", "porque", "aunque",
    "cuando", "mientras", "pues", "entonces",
}

WINDOW_BAD_END_WORDS = {
    "y", "e", "o", "u", "pero", "sino", "que", "de", "del", "al",
    "en", "a", "por", "para", "con", "sin", "sobre", "entre",
    "desde", "hasta",
}

WINDOW_BOUNDARY_WORDS = {
    "y", "e", "o", "u", "pero", "sino", "que", "porque", "aunque",
    "cuando", "mientras", "si", "donde", "quien", "quienes", "cuyo",
    "cuya", "cuyos", "cuyas", "por", "para", "con", "sin", "de", "en",
    "a", "hasta", "desde",
}

WINDOW_RELATIVE_WORDS = {
    "que", "cual", "cuales", "quien", "quienes", "cuyo", "cuya",
    "cuyos", "cuyas",
}

WINDOW_ARTICLES = {
    "el", "la", "los", "las", "lo", "un", "una", "unos", "unas",
}


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def _word_spans(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end()) for m in _WORD_RE.finditer(text or "")]


def _strip(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" ,;")


def _capitalize_first(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _ensure_period(text: str) -> str:
    text = text.rstrip()
    if not text:
        return text
    # Remove orphan whitespace and trailing connectors before final punct.
    text = re.sub(r"\s+([.!?,;:])", r"\1", text)
    text = re.sub(r"[,;:]+$", "", text).rstrip()
    if text and text[-1] not in ".!?":
        text += "."
    return text


def _lemma_re(lemma: str) -> re.Pattern[str]:
    return re.compile(r"(?<!\w)" + re.escape(lemma) + r"(?!\w)", re.IGNORECASE)


def lemma_present(text: str, lemma: str) -> bool:
    if not text or not lemma:
        return False
    return bool(_lemma_re(lemma).search(text))


def _remove_first_word(text: str) -> str:
    match = _WORD_RE.search(text)
    if not match:
        return text
    return text[match.end():]


def _remove_last_word(text: str) -> str:
    matches = list(_WORD_RE.finditer(text))
    if not matches:
        return text
    return text[:matches[-1].start()]


def _cleanup_fragment(text: str, lemma: str) -> str:
    out = _strip(text)
    prev = None

    while out and out != prev:
        prev = out
        out = re.sub(r"^\W+", "", out)
        out = re.sub(r"\W+$", "", out)
        out = re.sub(r"\s+([.!?,;:])", r"\1", out)

        words = [w.lower() for w, _, _ in _word_spans(out)]
        if len(words) >= 2 and words[0] in WINDOW_ARTICLES \
                and words[1] in WINDOW_RELATIVE_WORDS \
                and words[0] != lemma.lower():
            candidate = _strip(_remove_first_word(out))
            if candidate and lemma_present(candidate, lemma):
                out = candidate
                continue

        words = [w.lower() for w, _, _ in _word_spans(out)]
        if words and words[0] in WINDOW_BAD_START_WORDS \
                and words[0] != lemma.lower():
            candidate = _strip(_remove_first_word(out))
            if candidate and lemma_present(candidate, lemma):
                out = candidate
                continue

        words = [w.lower() for w, _, _ in _word_spans(out)]
        if words and words[-1] in WINDOW_BAD_END_WORDS \
                and words[-1] != lemma.lower():
            candidate = _strip(_remove_last_word(out))
            if candidate and lemma_present(candidate, lemma):
                out = candidate
                continue

    return _strip(out)


# ---------------------------------------------------------------------------
# Individual passes
# ---------------------------------------------------------------------------

def pass1_remove_discourse_fillers(text: str) -> str:
    out = text
    for f in DISCOURSE_FILLERS:
        # Filler at start of sentence: "Entonces, ..." -> ""
        out = re.sub(rf"^\s*{f}[\s,]+", "", out, flags=re.IGNORECASE)
        # Filler set off by commas mid-sentence: ", entonces, " -> ", "
        out = re.sub(rf",\s*{f}\s*,", ",", out, flags=re.IGNORECASE)
    return _strip(out)


def pass2_remove_time_place(text: str) -> str:
    out = text
    for p in TIME_PLACE_PHRASES:
        out = re.sub(p, "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+,", ",", out)
    out = re.sub(r",\s*,", ",", out)
    return _strip(out)


def pass3_remove_modifiers(text: str, lemma: str) -> str:
    """Conservative: drop intensifiers and a single trailing adjective stack."""
    out = text
    for w in ("muy", "bastante", "realmente", "verdaderamente", "extremadamente",
              "sumamente", "particularmente", "especialmente", "completamente",
              "totalmente", "absolutamente"):
        # Don't strip if it would remove the lemma itself.
        if w == lemma.lower():
            continue
        out = re.sub(rf"\b{w}\b\s*", "", out, flags=re.IGNORECASE)
    return _strip(re.sub(r"\s{2,}", " ", out))


def pass4_remove_subordinate_tail(text: str, lemma: str) -> str:
    """Cut everything from the first subordinate head, but only if doing so
    keeps the lemma in the sentence."""
    lower = text.lower()
    cuts = []
    for head in SUBORDINATE_HEADS:
        idx = lower.find(head)
        if idx > 0:
            cuts.append(idx)
    if not cuts:
        return text
    cut = min(cuts)
    candidate = _strip(text[:cut])
    if lemma_present(candidate, lemma):
        return candidate
    return text


def pass5_reduce_to_one_clause(text: str, lemma: str) -> str:
    """Split on commas / coordinators and pick the smallest contiguous span
    that still contains the lemma and is grammatical-ish."""
    # First try comma splits.
    parts = [p.strip() for p in re.split(r"[,;:]", text) if p.strip()]
    if len(parts) > 1:
        keepers = [p for p in parts if lemma_present(p, lemma)]
        if keepers:
            chosen = min(keepers, key=word_count)
            if word_count(chosen) >= 3:
                return chosen
    # Then coordinator splits.
    out = text
    for c in COORDINATORS:
        if c in f" {out.lower()} ":
            pieces = re.split(c, out, flags=re.IGNORECASE)
            keepers = [p for p in pieces if lemma_present(p, lemma)]
            if keepers:
                chosen = min(keepers, key=word_count)
                if word_count(chosen) >= 3:
                    out = chosen
    return _strip(out)


_PROPER_NAME_RE = re.compile(
    r"(?<!^)(?<![.!?¿¡]\s)\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)(\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*"
)


def pass6_remove_names(text: str, lemma: str) -> str:
    """Drop sequences of capitalized words that are not the first token and
    not the lemma."""
    def repl(match: re.Match[str]) -> str:
        chunk = match.group(0)
        if chunk.lower() == lemma.lower():
            return chunk
        return ""

    out = _PROPER_NAME_RE.sub(repl, text)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.!?])", r"\1", out)
    return _strip(out)


def pass7_extract_lemma_window(text: str, lemma: str, max_words: int) -> str:
    """Last-resort deletion-only fallback.

    Select a contiguous span around the exact lemma surface, then clean the
    edges without inventing new wording.
    """
    spans = _word_spans(text)
    if len(spans) <= max_words:
        return text

    lemma_positions = [i for i, (word, _, _) in enumerate(spans)
                       if word.lower() == lemma.lower()]
    if not lemma_positions:
        return text

    best_candidate = ""
    best_score: tuple[int, int, int, int, int] | None = None
    target_len = min(6, max_words)

    for pos in lemma_positions:
        for start in range(0, pos + 1):
            for end in range(pos, min(len(spans), start + max_words)):
                raw = text[spans[start][1]:spans[end][2]]
                candidate = _cleanup_fragment(raw, lemma)
                candidate_words = [w.lower() for w, _, _ in _word_spans(candidate)]
                if len(candidate_words) < 3 or len(candidate_words) > max_words:
                    continue
                if not lemma_present(candidate, lemma):
                    continue

                first = candidate_words[0]
                last = candidate_words[-1]
                prev_word = spans[start - 1][0].lower() if start > 0 else ""
                next_word = spans[end + 1][0].lower() if end + 1 < len(spans) else ""

                edge_penalty = (
                    (2 if first in WINDOW_BAD_START_WORDS else 0)
                    + (2 if last in WINDOW_BAD_END_WORDS else 0)
                )
                cut_penalty = (
                    (0 if start == 0 or prev_word in WINDOW_BOUNDARY_WORDS else 1)
                    + (0 if end == len(spans) - 1 or next_word in WINDOW_BOUNDARY_WORDS else 1)
                )

                lemma_index = candidate_words.index(lemma.lower())
                before = lemma_index
                after = len(candidate_words) - lemma_index - 1
                context_penalty = (
                    max(0, before - 2)
                    + max(0, after - 5)
                    + (1 if after == 0 and before > 2 else 0)
                )
                length_penalty = abs(len(candidate_words) - target_len)

                score = (
                    context_penalty,
                    edge_penalty + cut_penalty,
                    length_penalty,
                    -len(candidate_words),
                    start,
                )
                if best_score is None or score < best_score:
                    best_score = score
                    best_candidate = candidate

    return best_candidate or text


def pass8_simplify(text: str, lemma: str) -> str:
    """Light cleanup of dangling prepositions and orphan punctuation."""
    out = _cleanup_fragment(text, lemma)
    # Trailing dangling preposition.
    out = re.sub(r"\b(de|en|por|para|con|sin|sobre|entre|hacia|desde|hasta)\s*[.!?]?$",
                 "", out, flags=re.IGNORECASE)
    # Orphan leading punctuation/connector.
    out = re.sub(r"^[,;:\s]+", "", out)
    out = re.sub(r"^(y|pero|o|sino|que|porque|aunque)\s+", "", out, flags=re.IGNORECASE)
    out = _cleanup_fragment(out, lemma)
    return _strip(out)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class CompressResult:
    text: str
    passes_used: list[int] = field(default_factory=list)
    success: bool = False
    reason: str = ""


def compress(sentence: str, lemma: str, max_words: int = 12) -> CompressResult:
    out = sentence
    used: list[int] = []

    passes = [
        (1, lambda t: pass1_remove_discourse_fillers(t)),
        (2, lambda t: pass2_remove_time_place(t)),
        (3, lambda t: pass3_remove_modifiers(t, lemma)),
        (4, lambda t: pass4_remove_subordinate_tail(t, lemma)),
        (5, lambda t: pass5_reduce_to_one_clause(t, lemma)),
        (6, lambda t: pass6_remove_names(t, lemma)),
        (7, lambda t: pass7_extract_lemma_window(t, lemma, max_words)),
        (8, lambda t: pass8_simplify(t, lemma)),
    ]

    for pid, fn in passes:
        new = fn(out)
        if not new or not lemma_present(new, lemma):
            # The pass killed the lemma; skip it but keep going.
            continue
        if new != out:
            out = new
            used.append(pid)
        if word_count(out) <= max_words:
            cleaned = _ensure_period(_capitalize_first(out))
            return CompressResult(text=cleaned, passes_used=used, success=True)

    cleaned = _ensure_period(_capitalize_first(out)) if out else ""
    success = bool(cleaned) and word_count(cleaned) <= max_words and lemma_present(cleaned, lemma)
    reason = "" if success else f"could not get under {max_words} words after all passes"
    return CompressResult(text=cleaned, passes_used=used, success=success, reason=reason)
