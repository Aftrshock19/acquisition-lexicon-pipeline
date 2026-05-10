#!/usr/bin/env python3
"""
Detect Spanish attached pronoun forms in a CSV and rewrite translations for flashcards.

Usage:
  python3 add_pronoun_attachment_context.py
  python3 add_pronoun_attachment_context.py --input spa-eng.csv --output spa-eng-pronouns.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from add_mood_context import (
    DEFAULT_INPUT,
    clean_translation,
    expected_gerund,
    has_accented_vowel,
    has_parenthetical_gloss,
    infer_imperative_form,
    normalize_pos,
    split_infinitive,
    strip_accents,
)

DEFAULT_OUTPUT = Path("spa-eng-pronouns.csv")

OUTPUT_COLUMNS = [
    "rank",
    "lemma",
    "original_lemma",
    "translation",
    "definitions",
    "english_definition",
    "pos",
    "tags",
    "sentence",
    "english_sentence",
]

REQUIRED_COLUMNS = set(OUTPUT_COLUMNS)

ATTACHED_SINGLE_PRONOUNS = (
    "me",
    "te",
    "se",
    "nos",
    "os",
    "lo",
    "la",
    "los",
    "las",
    "le",
    "les",
)

DIRECT_OBJECT_PRONOUNS = {
    "lo": ("it", "masculine"),
    "la": ("it", "feminine"),
    "los": ("them", "masculine"),
    "las": ("them", "feminine"),
}

PERSON_OBJECT_PRONOUNS = {
    "me": "me",
    "te": "you",
    "nos": "us",
    "os": "you all",
}

INDIRECT_OBJECT_PRONOUNS = {
    "me": "me",
    "te": "you",
    "le": "him or her",
    "les": "them",
    "nos": "us",
    "os": "you all",
}

DOUBLE_RECIPIENT_PRONOUNS = {
    "me": "to me",
    "te": "to you",
    "se": "to him or her or them",
    "nos": "to us",
    "os": "to you all",
}

REFLEXIVE_PRONOUNS = {"me", "te", "se", "nos", "os"}

ATTACHED_DOUBLE_PRONOUNS = [
    (first, second)
    for first in ("me", "te", "se", "nos", "os")
    for second in ("lo", "la", "los", "las")
]

ATTACHED_PRONOUN_SEQUENCES = sorted(
    [*[(p,) for p in ATTACHED_SINGLE_PRONOUNS], *ATTACHED_DOUBLE_PRONOUNS],
    key=lambda parts: len("".join(parts)),
    reverse=True,
)

ENGLISH_SUBJECT_PRONOUNS = {"i", "you", "he", "she", "it", "we", "they"}

FORM_SPECIFIC_BASE_OVERRIDES = {
    "decir": {"imperative": "tell"},
    "pedir": {
        "infinitive": "to ask",
        "gerund": "asking",
        "imperative": "ask",
    },
}

LIKELY_INDIRECT_BASES = {
    "ayudar",
    "contar",
    "dar",
    "decir",
    "explicar",
    "hablar",
    "mandar",
    "mostrar",
    "pedir",
    "preguntar",
    "traer",
}

INDIRECT_ALWAYS_TO_BASES = {
    "decir",
    "dar",
    "explicar",
    "hablar",
    "traer",
}

INDIRECT_PLAIN_BASES = {
    "ayudar",
    "mandar",
    "mostrar",
    "pedir",
    "preguntar",
}

INDIRECT_FROM_BASES = {
    "quitar",
    "sacar",
}

ETHICAL_DATIVE_BASES = {
    "beber",
    "comer",
    "creer",
    "leer",
}

MANUAL_SINGLE_PRONOUN_BASE_MAP = {
    "acordar": {
        "type": "pronominal",
        "semantic_class": "pronominal_lexical",
        "reason": "manual_pronominal_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to remember",
            "gerund": "remembering",
            "imperative": "remember",
        },
    },
    "arrepentir": {
        "type": "pronominal",
        "semantic_class": "pronominal_lexical",
        "reason": "manual_pronominal_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to regret",
            "gerund": "regretting",
            "imperative": "regret",
        },
    },
    "atrever": {
        "type": "pronominal",
        "semantic_class": "pronominal_lexical",
        "reason": "manual_pronominal_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to dare",
            "gerund": "daring",
            "imperative": "dare",
        },
    },
    "beber": {
        "type": "idiomatic_se",
        "semantic_class": "idiomatic_aspectual",
        "reason": "manual_idiomatic_se_match",
        "allowed_pronouns": {"se"},
        "translations": {
            "infinitive": "to drink up",
            "gerund": "drinking up",
            "imperative": "drink up",
        },
    },
    "comer": {
        "type": "idiomatic_se",
        "semantic_class": "idiomatic_aspectual",
        "reason": "manual_idiomatic_se_match",
        "allowed_pronouns": {"se"},
        "translations": {
            "infinitive": "to eat up",
            "gerund": "eating up",
            "imperative": "eat up",
        },
    },
    "encontrar": {
        "type": "reciprocal",
        "semantic_class": "reciprocal",
        "reason": "manual_reciprocal_match",
        "allowed_pronouns": {"se"},
        "translations": {
            "infinitive": "to meet each other",
            "gerund": "meeting each other",
            "imperative": "meet each other",
        },
    },
    "enterar": {
        "type": "pronominal",
        "semantic_class": "pronominal_lexical",
        "reason": "manual_pronominal_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to find out",
            "gerund": "finding out",
            "imperative": "find out",
        },
    },
    "escribir": {
        "type": "reciprocal",
        "semantic_class": "reciprocal",
        "reason": "manual_reciprocal_match",
        "allowed_pronouns": {"se"},
        "translations": {
            "infinitive": "to write to each other",
            "gerund": "writing to each other",
            "imperative": "write to each other",
        },
    },
    "fijar": {
        "type": "pronominal",
        "semantic_class": "pronominal_lexical",
        "reason": "manual_pronominal_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to notice",
            "gerund": "noticing",
            "imperative": "notice",
        },
    },
    "ganar": {
        "type": "idiomatic_se",
        "semantic_class": "idiomatic_aspectual",
        "reason": "manual_idiomatic_se_match",
        "allowed_pronouns": {"se"},
        "translations": {
            "infinitive": "to earn",
            "gerund": "earning",
            "imperative": "earn",
        },
    },
    "hablar": {
        "type": "reciprocal",
        "semantic_class": "reciprocal",
        "reason": "manual_reciprocal_match",
        "allowed_pronouns": {"se"},
        "translations": {
            "infinitive": "to talk to each other",
            "gerund": "talking to each other",
            "imperative": "talk to each other",
        },
    },
    "ir": {
        "type": "pronominal",
        "semantic_class": "pronominal_lexical",
        "reason": "manual_pronominal_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to go away",
            "gerund": "going away",
            "imperative": "go away",
        },
    },
    "lavar": {
        "type": "reflexive",
        "semantic_class": "reflexive_lexical",
        "reason": "manual_reflexive_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to wash oneself",
            "gerund": "washing oneself",
            "imperative": "wash yourself",
        },
    },
    "leer": {
        "type": "idiomatic_se",
        "semantic_class": "idiomatic_aspectual",
        "reason": "manual_idiomatic_se_match",
        "allowed_pronouns": {"se"},
        "translations": {
            "infinitive": "to read through",
            "gerund": "reading through",
            "imperative": "read through",
        },
    },
    "levantar": {
        "type": "reflexive",
        "semantic_class": "reflexive_lexical",
        "reason": "manual_reflexive_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to get up",
            "gerund": "getting up",
            "imperative": "get up",
        },
    },
    "llevar": {
        "type": "idiomatic_se",
        "semantic_class": "idiomatic_aspectual",
        "reason": "manual_idiomatic_se_match",
        "allowed_pronouns": {"se"},
        "translations": {
            "infinitive": "to take away",
            "gerund": "taking away",
            "imperative": "take away",
        },
    },
    "llamar": {
        "type": "pronominal",
        "semantic_class": "pronominal_lexical",
        "reason": "manual_pronominal_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to be called",
            "gerund": "being called",
            "imperative": "be called",
        },
    },
    "marchar": {
        "type": "pronominal",
        "semantic_class": "pronominal_lexical",
        "reason": "manual_pronominal_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to leave",
            "gerund": "leaving",
            "imperative": "leave",
        },
    },
    "olvidar": {
        "type": "pronominal",
        "semantic_class": "pronominal_lexical",
        "reason": "manual_pronominal_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to forget",
            "gerund": "forgetting",
            "imperative": "forget",
        },
    },
    "poner": {
        "type": "reflexive",
        "semantic_class": "reflexive_lexical",
        "reason": "manual_reflexive_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to put on",
            "gerund": "putting on",
            "imperative": "put on",
        },
    },
    "quejar": {
        "type": "pronominal",
        "semantic_class": "pronominal_lexical",
        "reason": "manual_pronominal_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to complain",
            "gerund": "complaining",
            "imperative": "complain",
        },
    },
    "quedar": {
        "type": "pronominal",
        "semantic_class": "pronominal_lexical",
        "reason": "manual_pronominal_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to stay",
            "gerund": "staying",
            "imperative": "stay",
        },
    },
    "quitar": {
        "type": "reflexive",
        "semantic_class": "reflexive_lexical",
        "reason": "manual_reflexive_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to take off",
            "gerund": "taking off",
            "imperative": "take off",
        },
    },
    "saber": {
        "type": "idiomatic_se",
        "semantic_class": "idiomatic_aspectual",
        "reason": "manual_idiomatic_se_match",
        "allowed_pronouns": {"se"},
        "translations": {
            "infinitive": "to know by heart",
            "gerund": "knowing by heart",
            "imperative": "know by heart",
        },
    },
    "sentar": {
        "type": "reflexive",
        "semantic_class": "reflexive_lexical",
        "reason": "manual_reflexive_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to sit down",
            "gerund": "sitting down",
            "imperative": "sit down",
        },
    },
    "ver": {
        "type": "reciprocal",
        "semantic_class": "reciprocal",
        "reason": "manual_reciprocal_match",
        "allowed_pronouns": {"se"},
        "translations": {
            "infinitive": "to see each other",
            "gerund": "seeing each other",
            "imperative": "see each other",
        },
    },
    "volver": {
        "type": "pronominal",
        "semantic_class": "pronominal_lexical",
        "reason": "manual_pronominal_match",
        "allowed_pronouns": REFLEXIVE_PRONOUNS,
        "translations": {
            "infinitive": "to become",
            "gerund": "becoming",
            "imperative": "become",
        },
    },
}

MANUAL_DOUBLE_PRONOUN_BASE_MAP = {
    "beber": {
        "type": "idiomatic_se",
        "semantic_class": "idiomatic_aspectual",
        "reason": "manual_idiomatic_se_match",
        "allowed_first_pronouns": REFLEXIVE_PRONOUNS,
        "templates": {
            "infinitive": "to drink {object} up",
            "gerund": "drinking {object} up",
            "imperative": "drink {object} up",
        },
    },
    "comer": {
        "type": "idiomatic_se",
        "semantic_class": "idiomatic_aspectual",
        "reason": "manual_idiomatic_se_match",
        "allowed_first_pronouns": REFLEXIVE_PRONOUNS,
        "templates": {
            "infinitive": "to eat {object} up",
            "gerund": "eating {object} up",
            "imperative": "eat {object} up",
        },
    },
    "leer": {
        "type": "idiomatic_se",
        "semantic_class": "idiomatic_aspectual",
        "reason": "manual_idiomatic_se_match",
        "allowed_first_pronouns": REFLEXIVE_PRONOUNS,
        "templates": {
            "infinitive": "to read {object} through",
            "gerund": "reading {object} through",
            "imperative": "read {object} through",
        },
    },
    "llevar": {
        "type": "idiomatic_se",
        "semantic_class": "idiomatic_aspectual",
        "reason": "manual_idiomatic_se_match",
        "allowed_first_pronouns": REFLEXIVE_PRONOUNS,
        "templates": {
            "infinitive": "to take {object} away",
            "gerund": "taking {object} away",
            "imperative": "take {object} away",
        },
    },
    "poner": {
        "type": "reflexive",
        "semantic_class": "reflexive_lexical",
        "reason": "manual_reflexive_match",
        "allowed_first_pronouns": REFLEXIVE_PRONOUNS,
        "templates": {
            "infinitive": "to put {object} on {target}",
            "gerund": "putting {object} on {target}",
            "imperative": "put {object} on {target}",
        },
    },
    "quitar": {
        "type": "reflexive",
        "semantic_class": "reflexive_lexical",
        "reason": "manual_reflexive_match",
        "allowed_first_pronouns": REFLEXIVE_PRONOUNS,
        "templates": {
            "infinitive": "to take {object} off {target}",
            "gerund": "taking {object} off {target}",
            "imperative": "take {object} off {target}",
        },
    },
}

MANUAL_ATTACHED_PRONOUN_MAP = {
    ("decir", "dime"): {
        "relation": "attached_pronoun_form",
        "form": "imperative",
        "type": "indirect_object",
        "pronouns": ["me"],
        "count": "1",
        "confidence": "high",
        "reason": "manual_imperative_match",
        "semantic_class": "transparent_indirect",
        "translation": "tell me",
    },
    ("decir", "dímelo"): {
        "relation": "attached_pronoun_form",
        "form": "imperative",
        "type": "double_pronoun",
        "pronouns": ["me", "lo"],
        "count": "2",
        "confidence": "high",
        "reason": "manual_double_pronoun_match",
        "semantic_class": "double_object",
        "translation": "tell it to me",
    },
    ("dejar", "déjame"): {
        "relation": "attached_pronoun_form",
        "form": "imperative",
        "type": "direct_object",
        "pronouns": ["me"],
        "count": "1",
        "confidence": "high",
        "reason": "manual_imperative_match",
        "semantic_class": "transparent_object",
        "translation": "leave me",
    },
    ("ir", "vámonos"): {
        "relation": "attached_pronoun_form",
        "form": "imperative",
        "type": "pronominal",
        "pronouns": ["nos"],
        "count": "1",
        "confidence": "high",
        "reason": "manual_imperative_match",
        "semantic_class": "pronominal_lexical",
        "translation": "let's go",
    },
    ("sentar", "siéntate"): {
        "relation": "attached_pronoun_form",
        "form": "imperative",
        "type": "reflexive",
        "pronouns": ["te"],
        "count": "1",
        "confidence": "high",
        "reason": "manual_imperative_match",
        "semantic_class": "reflexive_lexical",
        "translation": "sit down",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect Spanish verb forms with attached pronouns and rewrite translations for flashcards."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def output_fieldnames(input_fieldnames: list[str]) -> list[str]:
    missing = [column for column in REQUIRED_COLUMNS if column not in set(input_fieldnames)]
    if missing:
        raise SystemExit(f"Input CSV is missing required columns: {', '.join(missing)}")
    return list(OUTPUT_COLUMNS)


def first_translation_segment(raw: str) -> str:
    cleaned = clean_translation(raw)
    if not cleaned:
        return ""
    return cleaned.split(";")[0].strip()


def match_attached_pronoun_sequence(lemma: str) -> tuple[str, ...]:
    lemma = (lemma or "").strip().lower()
    for parts in ATTACHED_PRONOUN_SEQUENCES:
        if lemma.endswith("".join(parts)):
            return parts
    return ()


def normalize_english_verb(word: str) -> str:
    lower = word.lower()
    irregular = {
        "does": "do",
        "goes": "go",
        "has": "have",
        "is": "be",
    }
    if lower in irregular:
        return irregular[lower]
    if lower.endswith("ies") and len(lower) > 3:
        return lower[:-3] + "y"
    if lower.endswith("es") and len(lower) > 3:
        return lower[:-1] if lower[-3] == "v" else lower[:-2]
    if lower.endswith("s") and len(lower) > 2 and not lower.endswith("ss"):
        return lower[:-1]
    return lower


def base_translation_phrase(raw_translation: str, form: str, base_infinitive: str) -> str:
    override = FORM_SPECIFIC_BASE_OVERRIDES.get(base_infinitive, {})
    override_phrase = override.get(form)
    if override_phrase:
        return override_phrase

    phrase = first_translation_segment(raw_translation)
    if not phrase:
        return ""

    if form == "imperative":
        words = phrase.split()
        if words and words[0].lower() in ENGLISH_SUBJECT_PRONOUNS:
            subject = words.pop(0).lower()
            if words and subject in {"he", "she", "it"}:
                words[0] = normalize_english_verb(words[0])
        phrase = " ".join(words).strip()

    return phrase


def append_note(text: str, note: str) -> str:
    text = (text or "").strip()
    note = (note or "").strip()
    if not text:
        return ""
    if not note:
        return text
    return f"{text} ({note})"


def render_direct_object(pronoun: str) -> tuple[str, str]:
    if pronoun in DIRECT_OBJECT_PRONOUNS:
        return DIRECT_OBJECT_PRONOUNS[pronoun]
    return (PERSON_OBJECT_PRONOUNS.get(pronoun, ""), "")


def render_indirect_object(pronoun: str, base_infinitive: str) -> str:
    plain = INDIRECT_OBJECT_PRONOUNS.get(pronoun, "")
    if not plain:
        return ""
    if base_infinitive in INDIRECT_FROM_BASES:
        return f"from {plain}"
    if base_infinitive in INDIRECT_PLAIN_BASES:
        return plain
    if base_infinitive in INDIRECT_ALWAYS_TO_BASES or pronoun in {"le", "les"}:
        return f"to {plain}"
    return plain


def render_double_recipient(pronoun: str) -> str:
    return DOUBLE_RECIPIENT_PRONOUNS.get(pronoun, "")


def render_reflexive_target(pronoun: str) -> str:
    return {
        "me": "me",
        "te": "you",
        "nos": "us",
        "os": "you all",
        "se": "oneself or him or her",
    }.get(pronoun, "")


def manual_single_pronoun_entry(base_infinitive: str, pronoun: str) -> dict[str, object] | None:
    entry = MANUAL_SINGLE_PRONOUN_BASE_MAP.get(base_infinitive)
    if not entry:
        return None
    if pronoun not in entry["allowed_pronouns"]:
        return None
    return entry


def manual_double_pronoun_entry(base_infinitive: str, first_pronoun: str) -> dict[str, object] | None:
    entry = MANUAL_DOUBLE_PRONOUN_BASE_MAP.get(base_infinitive)
    if not entry:
        return None
    if first_pronoun not in entry["allowed_first_pronouns"]:
        return None
    return entry


def build_pronoun_translation(
    raw_translation: str,
    base_infinitive: str,
    attachment_form: str,
    attachment_type: str,
    pronouns: list[str],
) -> str:
    if len(pronouns) == 1:
        pronoun = pronouns[0]
        manual_entry = manual_single_pronoun_entry(base_infinitive, pronoun)
        if manual_entry:
            return manual_entry["translations"].get(attachment_form, "")

        base = base_translation_phrase(raw_translation, attachment_form, base_infinitive)
        if not base:
            return ""

        if attachment_type == "direct_object":
            obj, note = render_direct_object(pronoun)
            if not obj:
                return ""
            return append_note(f"{base} {obj}", note)

        if attachment_type == "indirect_object":
            recipient = render_indirect_object(pronoun, base_infinitive)
            if not recipient:
                return ""
            return f"{base} {recipient}"

        return ""

    if len(pronouns) == 2:
        first, second = pronouns
        obj, note = render_direct_object(second)
        if not obj:
            return ""

        manual_entry = manual_double_pronoun_entry(base_infinitive, first)
        if manual_entry:
            template = manual_entry["templates"].get(attachment_form, "")
            if not template:
                return ""
            target = render_reflexive_target(first)
            text = template.format(object=obj, target=target).replace("  ", " ").strip()
            return append_note(text, note)

        base = base_translation_phrase(raw_translation, attachment_form, base_infinitive)
        recipient = render_double_recipient(first)
        if not base or not recipient:
            return ""
        return append_note(f"{base} {obj} {recipient}", note)

    return ""


def build_pronoun_tags(
    existing_tags: str,
    relation: str,
    attachment_type: str,
    pronouns: list[str],
    confidence: str,
) -> str:
    tags = [tag for tag in (existing_tags or "").split("|") if tag]
    if relation == "attached_pronoun_form" and confidence == "high":
        tags.append("attached_pronoun")
        if attachment_type:
            tags.append(attachment_type)
        tags.extend(pronouns)

    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            out.append(tag)
    return "|".join(out)


def infer_attached_pronoun_form(
    lemma: str,
    original_lemma: str,
    pos: str,
    raw_translation: str,
) -> dict[str, str]:
    lemma = (lemma or "").strip().lower()
    pos = normalize_pos(pos)
    base_infinitive, _ = split_infinitive(original_lemma)

    result = {
        "relation": "not_attached_pronoun_form",
        "form": "",
        "type": "",
        "pronouns": "",
        "count": "",
        "confidence": "",
        "reason": "no_match",
        "semantic_class": "unknown",
        "translation": "",
    }

    if pos != "v":
        result["relation"] = "unknown"
        result["reason"] = "pos_not_supported"
        return result

    manual = MANUAL_ATTACHED_PRONOUN_MAP.get((base_infinitive, lemma))
    if manual:
        return {
            "relation": manual["relation"],
            "form": manual["form"],
            "type": manual["type"],
            "pronouns": "+".join(manual["pronouns"]),
            "count": manual["count"],
            "confidence": manual["confidence"],
            "reason": manual["reason"],
            "semantic_class": manual["semantic_class"],
            "translation": manual["translation"],
        }

    pronoun_parts = list(match_attached_pronoun_sequence(lemma))
    if not pronoun_parts:
        return result

    stripped = lemma[: -len("".join(pronoun_parts))]
    normalized_base = strip_accents(stripped)
    normalized_infinitive = strip_accents(base_infinitive)

    attachment_form = ""
    if normalized_base == normalized_infinitive and normalized_infinitive.endswith(("ar", "er", "ir")):
        attachment_form = "infinitive"
    elif normalized_base == strip_accents(expected_gerund(base_infinitive)):
        attachment_form = "gerund"
    else:
        imp_relation, _, _, _, _, imp_reason = infer_imperative_form(
            lemma=normalized_base,
            original_lemma=original_lemma,
            pos=pos,
            allow_regular_tu=True,
        )
        if imp_relation == "imperative_form":
            if imp_reason.startswith("regular_tu_") and len(normalized_base) > 2 and not has_accented_vowel(lemma):
                return result
            attachment_form = "imperative"

    if not attachment_form:
        result["reason"] = "unsafe_base_form"
        return result

    pronoun_type = "unknown"
    semantic_class = "unknown"
    confidence = "medium"
    reason = "candidate_only"

    if len(pronoun_parts) == 2:
        first, _ = pronoun_parts
        manual_entry = manual_double_pronoun_entry(base_infinitive, first)
        if manual_entry:
            pronoun_type = manual_entry["type"]
            semantic_class = manual_entry["semantic_class"]
            reason = manual_entry["reason"]
        else:
            pronoun_type = "double_pronoun"
            semantic_class = "double_object"
            reason = "safe_double_match"
    else:
        pronoun = pronoun_parts[0]
        manual_entry = manual_single_pronoun_entry(base_infinitive, pronoun)
        if manual_entry:
            pronoun_type = manual_entry["type"]
            semantic_class = manual_entry["semantic_class"]
            reason = manual_entry["reason"]
        elif pronoun in DIRECT_OBJECT_PRONOUNS:
            pronoun_type = "direct_object"
            semantic_class = "transparent_object"
            reason = "safe_direct_match"
        elif pronoun in {"me", "te", "nos", "os"} and base_infinitive in ETHICAL_DATIVE_BASES:
            pronoun_type = "ethical_dative"
            semantic_class = "ethical_dative"
        elif pronoun == "se":
            pronoun_type = "unknown"
            semantic_class = "unknown"
        elif pronoun in {"le", "les"} or base_infinitive in LIKELY_INDIRECT_BASES:
            pronoun_type = "indirect_object"
            semantic_class = "transparent_indirect"
            reason = "safe_indirect_match"
        else:
            pronoun_type = "direct_object"
            semantic_class = "transparent_object"
            reason = "safe_direct_match"

    translation = build_pronoun_translation(
        raw_translation=raw_translation,
        base_infinitive=base_infinitive,
        attachment_form=attachment_form,
        attachment_type=pronoun_type,
        pronouns=pronoun_parts,
    )

    if translation:
        confidence = "high"

    return {
        "relation": "attached_pronoun_form",
        "form": attachment_form,
        "type": pronoun_type,
        "pronouns": "+".join(pronoun_parts),
        "count": str(len(pronoun_parts)),
        "confidence": confidence,
        "reason": reason,
        "semantic_class": semantic_class,
        "translation": translation,
    }


def review_reason(old_row: dict[str, str], new_row: dict[str, str]) -> str:
    old_translation = (old_row.get("translation", "") or "").strip()
    new_translation = (new_row.get("translation", "") or "").strip()

    if old_translation != new_translation:
        return "translation_changed"
    if has_parenthetical_gloss(old_translation) and new_row.get("pronoun_attachment_relation") == "attached_pronoun_form":
        return "existing_translation_brackets"
    if new_row.get("pronoun_attachment_relation") == "attached_pronoun_form" and new_row.get("pronoun_attachment_confidence") != "high":
        return "attached_pronoun_candidate_only"
    if (new_row.get("pronoun_attachment_reason") or "").startswith("manual_"):
        return "attached_pronoun_manual_match"
    return ""


def rewrite_row(row: dict[str, str]) -> dict[str, str]:
    row = dict(row)

    pronoun_attachment = infer_attached_pronoun_form(
        lemma=row.get("lemma", ""),
        original_lemma=row.get("original_lemma", ""),
        pos=row.get("pos", ""),
        raw_translation=row.get("translation", ""),
    )

    row["pronoun_attachment_relation"] = pronoun_attachment["relation"]
    row["pronoun_attachment_form"] = pronoun_attachment["form"]
    row["pronoun_attachment_type"] = pronoun_attachment["type"]
    row["pronoun_attachment_pronouns"] = pronoun_attachment["pronouns"]
    row["pronoun_attachment_count"] = pronoun_attachment["count"]
    row["pronoun_attachment_confidence"] = pronoun_attachment["confidence"]
    row["pronoun_attachment_reason"] = pronoun_attachment["reason"]
    row["pronoun_attachment_semantic_class"] = pronoun_attachment["semantic_class"]

    row["tags"] = build_pronoun_tags(
        row.get("tags", ""),
        pronoun_attachment["relation"],
        pronoun_attachment["type"],
        pronoun_attachment["pronouns"].split("+") if pronoun_attachment["pronouns"] else [],
        pronoun_attachment["confidence"],
    )

    if has_parenthetical_gloss(row.get("translation", "")):
        return row

    if (
        pronoun_attachment["relation"] == "attached_pronoun_form"
        and pronoun_attachment["confidence"] == "high"
        and pronoun_attachment["translation"]
    ):
        row["translation"] = pronoun_attachment["translation"]

    return row


def build_review_rows(
    original_rows: list[dict[str, str]],
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    review_rows: list[dict[str, str]] = []

    for old_row, new_row in zip(original_rows, rows):
        reason = review_reason(old_row, new_row)
        if new_row.get("pronoun_attachment_relation") != "attached_pronoun_form":
            continue
        if reason not in {
            "translation_changed",
            "attached_pronoun_candidate_only",
            "existing_translation_brackets",
            "attached_pronoun_manual_match",
        }:
            continue

        old_translation = (old_row.get("translation", "") or "").strip()
        new_translation = (new_row.get("translation", "") or "").strip()
        review_rows.append({
            "rank": new_row.get("rank", ""),
            "lemma": new_row.get("lemma", ""),
            "original_lemma": new_row.get("original_lemma", ""),
            "old_translation": old_translation,
            "new_translation": new_translation,
            "translation_changed": "yes" if old_translation != new_translation else "no",
            "review_reason": reason,
            "pronoun_attachment_relation": new_row.get("pronoun_attachment_relation", ""),
            "pronoun_attachment_form": new_row.get("pronoun_attachment_form", ""),
            "pronoun_attachment_type": new_row.get("pronoun_attachment_type", ""),
            "pronoun_attachment_pronouns": new_row.get("pronoun_attachment_pronouns", ""),
            "pronoun_attachment_count": new_row.get("pronoun_attachment_count", ""),
            "pronoun_attachment_confidence": new_row.get("pronoun_attachment_confidence", ""),
            "pronoun_attachment_reason": new_row.get("pronoun_attachment_reason", ""),
            "pronoun_attachment_semantic_class": new_row.get("pronoun_attachment_semantic_class", ""),
        })

    return review_rows


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    review_log_path = output_path.with_name(f"{output_path.stem}-pronoun-review.csv")

    with input_path.open("r", newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise SystemExit("Input CSV has no header row.")
        fieldnames = output_fieldnames(list(reader.fieldnames))
        original_rows = list(reader)

    rows = [rewrite_row(row) for row in original_rows]

    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    review_rows = build_review_rows(original_rows, rows)
    with review_log_path.open("w", newline="", encoding="utf-8") as logfile:
        writer = csv.DictWriter(
            logfile,
            fieldnames=[
                "rank",
                "lemma",
                "original_lemma",
                "old_translation",
                "new_translation",
                "translation_changed",
                "review_reason",
                "pronoun_attachment_relation",
                "pronoun_attachment_form",
                "pronoun_attachment_type",
                "pronoun_attachment_pronouns",
                "pronoun_attachment_count",
                "pronoun_attachment_confidence",
                "pronoun_attachment_reason",
                "pronoun_attachment_semantic_class",
            ],
        )
        writer.writeheader()
        writer.writerows(review_rows)

    print(f"Saved {len(rows)} rows to {output_path}.")
    print(f"Saved {len(review_rows)} review rows to {review_log_path}.")


if __name__ == "__main__":
    main()
