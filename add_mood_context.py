#!/usr/bin/env python3
"""
Detect Spanish imperative and subjunctive forms in a CSV and append bracket context to translation.

Usage:
  python3 add_mood_context.py
  python3 add_mood_context.py --input spa-eng.csv --output spa-eng-moods.csv
  python3 add_mood_context.py --allow-regular-tu
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from pathlib import Path

DEFAULT_INPUT = Path("spa-eng.csv")
DEFAULT_OUTPUT = Path("spa-eng-moods.csv")

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

IMPERATIVE_COLUMNS = [
    "imperative_relation",
    "imperative_person",
    "imperative_number",
    "imperative_polarity",
    "imperative_confidence",
    "imperative_reason",
]

SUBJUNCTIVE_COLUMNS = [
    "subjunctive_relation",
    "subjunctive_tense",
    "subjunctive_person",
    "subjunctive_number",
    "subjunctive_confidence",
    "subjunctive_reason",
]

PRONOUN_ATTACHMENT_COLUMNS = [
    "pronoun_attachment_relation",
    "pronoun_attachment_form",
    "pronoun_attachment_type",
    "pronoun_attachment_pronouns",
    "pronoun_attachment_count",
    "pronoun_attachment_confidence",
    "pronoun_attachment_reason",
]

BLOCKED_LEMMA_PAIRS: set[tuple[str, str]] = {
    ("podar", "podemos"),
    ("podar", "podéis"),
    ("crear", "crees"),
    ("crear", "creen"),
    ("crear", "creemos"),
    ("venir", "ven"),
    ("doctorar", "doctores"),
    ("rumorar", "rumores"),
}

MANUAL_IMPERATIVE_MAP: dict[tuple[str, str], tuple[str, str, str, str, str, str]] = {
    ("decir", "di"):  ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("hacer", "haz"): ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("ir", "ve"):     ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("poner", "pon"): ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("salir", "sal"): ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("ser", "sé"):    ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("tener", "ten"): ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("venir", "ven"): ("imperative_form", "tú", "singular", "affirmative", "high", "manual_irregular_tu"),
    ("ser", "sed"):   ("imperative_form", "vosotros", "plural", "affirmative", "high", "manual_irregular_vosotros"),
    ("ir", "id"):     ("imperative_form", "vosotros", "plural", "affirmative", "high", "manual_irregular_vosotros"),
}

MANUAL_SUBJUNCTIVE_MAP: dict[tuple[str, str], tuple[str, str, str, str, str]] = {
    ("ser", "sea"): ("subjunctive_form", "present", "singular_ambiguous", "singular", "manual_irregular"),
    ("ser", "seas"): ("subjunctive_form", "present", "second", "singular", "manual_irregular"),
    ("ser", "seamos"): ("subjunctive_form", "present", "first", "plural", "manual_irregular"),
    ("ser", "seáis"): ("subjunctive_form", "present", "second", "plural", "manual_irregular"),
    ("ser", "sean"): ("subjunctive_form", "present", "third", "plural", "manual_irregular"),
    ("ser", "fuera"): ("subjunctive_form", "imperfect_ra", "singular_ambiguous", "singular", "manual_irregular"),
    ("ser", "fueras"): ("subjunctive_form", "imperfect_ra", "second", "singular", "manual_irregular"),
    ("ser", "fuéramos"): ("subjunctive_form", "imperfect_ra", "first", "plural", "manual_irregular"),
    ("ser", "fuerais"): ("subjunctive_form", "imperfect_ra", "second", "plural", "manual_irregular"),
    ("ser", "fueran"): ("subjunctive_form", "imperfect_ra", "third", "plural", "manual_irregular"),
    ("ser", "fuese"): ("subjunctive_form", "imperfect_se", "singular_ambiguous", "singular", "manual_irregular"),
    ("ser", "fueses"): ("subjunctive_form", "imperfect_se", "second", "singular", "manual_irregular"),
    ("ser", "fuésemos"): ("subjunctive_form", "imperfect_se", "first", "plural", "manual_irregular"),
    ("ser", "fueseis"): ("subjunctive_form", "imperfect_se", "second", "plural", "manual_irregular"),
    ("ser", "fuesen"): ("subjunctive_form", "imperfect_se", "third", "plural", "manual_irregular"),

    ("ir", "vaya"): ("subjunctive_form", "present", "singular_ambiguous", "singular", "manual_irregular"),
    ("ir", "vayas"): ("subjunctive_form", "present", "second", "singular", "manual_irregular"),
    ("ir", "vayamos"): ("subjunctive_form", "present", "first", "plural", "manual_irregular"),
    ("ir", "vayáis"): ("subjunctive_form", "present", "second", "plural", "manual_irregular"),
    ("ir", "vayan"): ("subjunctive_form", "present", "third", "plural", "manual_irregular"),
    ("ir", "fuera"): ("subjunctive_form", "imperfect_ra", "singular_ambiguous", "singular", "manual_irregular"),
    ("ir", "fueras"): ("subjunctive_form", "imperfect_ra", "second", "singular", "manual_irregular"),
    ("ir", "fuéramos"): ("subjunctive_form", "imperfect_ra", "first", "plural", "manual_irregular"),
    ("ir", "fuerais"): ("subjunctive_form", "imperfect_ra", "second", "plural", "manual_irregular"),
    ("ir", "fueran"): ("subjunctive_form", "imperfect_ra", "third", "plural", "manual_irregular"),
    ("ir", "fuese"): ("subjunctive_form", "imperfect_se", "singular_ambiguous", "singular", "manual_irregular"),
    ("ir", "fueses"): ("subjunctive_form", "imperfect_se", "second", "singular", "manual_irregular"),
    ("ir", "fuésemos"): ("subjunctive_form", "imperfect_se", "first", "plural", "manual_irregular"),
    ("ir", "fueseis"): ("subjunctive_form", "imperfect_se", "second", "plural", "manual_irregular"),
    ("ir", "fuesen"): ("subjunctive_form", "imperfect_se", "third", "plural", "manual_irregular"),

    ("haber", "haya"): ("subjunctive_form", "present", "singular_ambiguous", "singular", "manual_irregular"),
    ("haber", "hayas"): ("subjunctive_form", "present", "second", "singular", "manual_irregular"),
    ("haber", "hayamos"): ("subjunctive_form", "present", "first", "plural", "manual_irregular"),
    ("haber", "hayáis"): ("subjunctive_form", "present", "second", "plural", "manual_irregular"),
    ("haber", "hayan"): ("subjunctive_form", "present", "third", "plural", "manual_irregular"),
    ("haber", "hubiera"): ("subjunctive_form", "imperfect_ra", "singular_ambiguous", "singular", "manual_irregular"),
    ("haber", "hubieras"): ("subjunctive_form", "imperfect_ra", "second", "singular", "manual_irregular"),
    ("haber", "hubiéramos"): ("subjunctive_form", "imperfect_ra", "first", "plural", "manual_irregular"),
    ("haber", "hubierais"): ("subjunctive_form", "imperfect_ra", "second", "plural", "manual_irregular"),
    ("haber", "hubieran"): ("subjunctive_form", "imperfect_ra", "third", "plural", "manual_irregular"),
    ("haber", "hubiese"): ("subjunctive_form", "imperfect_se", "singular_ambiguous", "singular", "manual_irregular"),
    ("haber", "hubieses"): ("subjunctive_form", "imperfect_se", "second", "singular", "manual_irregular"),
    ("haber", "hubiésemos"): ("subjunctive_form", "imperfect_se", "first", "plural", "manual_irregular"),
    ("haber", "hubieseis"): ("subjunctive_form", "imperfect_se", "second", "plural", "manual_irregular"),
    ("haber", "hubiesen"): ("subjunctive_form", "imperfect_se", "third", "plural", "manual_irregular"),

    ("estar", "esté"): ("subjunctive_form", "present", "singular_ambiguous", "singular", "manual_irregular"),
    ("estar", "estés"): ("subjunctive_form", "present", "second", "singular", "manual_irregular"),
    ("estar", "estemos"): ("subjunctive_form", "present", "first", "plural", "manual_irregular"),
    ("estar", "estéis"): ("subjunctive_form", "present", "second", "plural", "manual_irregular"),
    ("estar", "estén"): ("subjunctive_form", "present", "third", "plural", "manual_irregular"),
    ("estar", "estuviera"): ("subjunctive_form", "imperfect_ra", "singular_ambiguous", "singular", "manual_irregular"),
    ("estar", "estuvieras"): ("subjunctive_form", "imperfect_ra", "second", "singular", "manual_irregular"),
    ("estar", "estuviéramos"): ("subjunctive_form", "imperfect_ra", "first", "plural", "manual_irregular"),
    ("estar", "estuvierais"): ("subjunctive_form", "imperfect_ra", "second", "plural", "manual_irregular"),
    ("estar", "estuvieran"): ("subjunctive_form", "imperfect_ra", "third", "plural", "manual_irregular"),
    ("estar", "estuviese"): ("subjunctive_form", "imperfect_se", "singular_ambiguous", "singular", "manual_irregular"),
    ("estar", "estuvieses"): ("subjunctive_form", "imperfect_se", "second", "singular", "manual_irregular"),
    ("estar", "estuviésemos"): ("subjunctive_form", "imperfect_se", "first", "plural", "manual_irregular"),
    ("estar", "estuvieseis"): ("subjunctive_form", "imperfect_se", "second", "plural", "manual_irregular"),
    ("estar", "estuviesen"): ("subjunctive_form", "imperfect_se", "third", "plural", "manual_irregular"),

    ("dar", "dé"): ("subjunctive_form", "present", "singular_ambiguous", "singular", "manual_irregular"),
    ("dar", "des"): ("subjunctive_form", "present", "second", "singular", "manual_irregular"),
    ("dar", "demos"): ("subjunctive_form", "present", "first", "plural", "manual_irregular"),
    ("dar", "deis"): ("subjunctive_form", "present", "second", "plural", "manual_irregular"),
    ("dar", "den"): ("subjunctive_form", "present", "third", "plural", "manual_irregular"),
    ("dar", "diera"): ("subjunctive_form", "imperfect_ra", "singular_ambiguous", "singular", "manual_irregular"),
    ("dar", "dieras"): ("subjunctive_form", "imperfect_ra", "second", "singular", "manual_irregular"),
    ("dar", "diéramos"): ("subjunctive_form", "imperfect_ra", "first", "plural", "manual_irregular"),
    ("dar", "dierais"): ("subjunctive_form", "imperfect_ra", "second", "plural", "manual_irregular"),
    ("dar", "dieran"): ("subjunctive_form", "imperfect_ra", "third", "plural", "manual_irregular"),
    ("dar", "diese"): ("subjunctive_form", "imperfect_se", "singular_ambiguous", "singular", "manual_irregular"),
    ("dar", "dieses"): ("subjunctive_form", "imperfect_se", "second", "singular", "manual_irregular"),
    ("dar", "diésemos"): ("subjunctive_form", "imperfect_se", "first", "plural", "manual_irregular"),
    ("dar", "dieseis"): ("subjunctive_form", "imperfect_se", "second", "plural", "manual_irregular"),
    ("dar", "diesen"): ("subjunctive_form", "imperfect_se", "third", "plural", "manual_irregular"),

    ("saber", "sepa"): ("subjunctive_form", "present", "singular_ambiguous", "singular", "manual_irregular"),
    ("saber", "sepas"): ("subjunctive_form", "present", "second", "singular", "manual_irregular"),
    ("saber", "sepamos"): ("subjunctive_form", "present", "first", "plural", "manual_irregular"),
    ("saber", "sepáis"): ("subjunctive_form", "present", "second", "plural", "manual_irregular"),
    ("saber", "sepan"): ("subjunctive_form", "present", "third", "plural", "manual_irregular"),
    ("saber", "supiera"): ("subjunctive_form", "imperfect_ra", "singular_ambiguous", "singular", "manual_irregular"),
    ("saber", "supieras"): ("subjunctive_form", "imperfect_ra", "second", "singular", "manual_irregular"),
    ("saber", "supiéramos"): ("subjunctive_form", "imperfect_ra", "first", "plural", "manual_irregular"),
    ("saber", "supierais"): ("subjunctive_form", "imperfect_ra", "second", "plural", "manual_irregular"),
    ("saber", "supieran"): ("subjunctive_form", "imperfect_ra", "third", "plural", "manual_irregular"),
    ("saber", "supiese"): ("subjunctive_form", "imperfect_se", "singular_ambiguous", "singular", "manual_irregular"),
    ("saber", "supieses"): ("subjunctive_form", "imperfect_se", "second", "singular", "manual_irregular"),
    ("saber", "supiésemos"): ("subjunctive_form", "imperfect_se", "first", "plural", "manual_irregular"),
    ("saber", "supieseis"): ("subjunctive_form", "imperfect_se", "second", "plural", "manual_irregular"),
    ("saber", "supiesen"): ("subjunctive_form", "imperfect_se", "third", "plural", "manual_irregular"),
}

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

INDIRECT_OBJECT_PRONOUNS = {
    "me": "me",
    "te": "you",
    "le": "him or her",
    "les": "them",
    "nos": "us",
    "os": "you all",
    "se": "him or her",
}

REFLEXIVE_PRONOUNS = {"me", "te", "se", "nos", "os"}

ATTACHED_DOUBLE_PRONOUNS = [
    (first, second)
    for first in ("me", "te", "se", "nos", "os", "le", "les")
    for second in ("lo", "la", "los", "las")
]

ATTACHED_PRONOUN_SEQUENCES = sorted(
    [*[(p,) for p in ATTACHED_SINGLE_PRONOUNS], *ATTACHED_DOUBLE_PRONOUNS],
    key=lambda parts: len("".join(parts)),
    reverse=True,
)

GENERIC_PRONOUN_BASE_OVERRIDES = {
    "decir": {
        "infinitive": "tell",
        "gerund": "telling",
        "imperative": "tell",
    },
}

SAFE_SINGLE_INDIRECT_BASES = {
    "decir",
    "dar",
    "ayudar",
    "traer",
    "escuchar",
    "mostrar",
    "mandar",
    "preguntar",
    "ver",
}

SAFE_DOUBLE_BASES = {
    "decir",
    "dar",
    "traer",
    "mostrar",
    "mandar",
}

LEXICAL_REFLEXIVE_TRANSLATIONS = {
    "llamar": {
        "infinitive": "be called",
        "gerund": "being called",
        "imperative": "be called",
    },
    "ir": {
        "infinitive": "go away",
        "gerund": "going away",
        "imperative": "go away",
    },
    "sentar": {
        "infinitive": "sit down",
        "gerund": "sitting down",
        "imperative": "sit down",
    },
    "poner": {
        "infinitive": "put on",
        "gerund": "putting on",
        "imperative": "put on",
    },
    "quitar": {
        "infinitive": "take off",
        "gerund": "taking off",
        "imperative": "take off",
    },
    "lavar": {
        "infinitive": "wash oneself",
        "gerund": "washing oneself",
        "imperative": "wash yourself",
    },
    "quedar": {
        "infinitive": "stay",
        "gerund": "staying",
        "imperative": "stay",
    },
}

REFLEXIVE_DOUBLE_TRANSLATIONS = {
    "poner": {
        "infinitive": "put",
        "gerund": "putting",
        "imperative": "put",
        "particle": "on",
    },
    "quitar": {
        "infinitive": "take",
        "gerund": "taking",
        "imperative": "take",
        "particle": "off",
    },
}

IRREGULAR_GERUNDS = {
    "ir": "yendo",
    "poder": "pudiendo",
    "venir": "viniendo",
    "decir": "diciendo",
    "dormir": "durmiendo",
    "leer": "leyendo",
    "oír": "oyendo",
    "traer": "trayendo",
}

MANUAL_ATTACHED_PRONOUN_MAP = {
    ("ir", "vámonos"): {
        "relation": "attached_pronoun_form",
        "form": "imperative",
        "type": "reflexive",
        "pronouns": ["nos"],
        "count": "1",
        "confidence": "high",
        "reason": "manual_irregular",
        "translation": "let's go",
    },
}

ENGLISH_SUBJECT_PRONOUNS = {"i", "you", "he", "she", "it", "we", "they"}


def normalize_pos(pos: str) -> str:
    p = (pos or "").strip().lower()
    if p in {"v", "verb", "verbo"}:
        return "v"
    return p


def split_infinitive(original_lemma: str) -> tuple[str, bool]:
    original = (original_lemma or "").strip().lower()
    if len(original) >= 4 and original.endswith("se") and original[-4:-2] in {"ar", "er", "ir"}:
        return original[:-2], True
    return original, False


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def has_accented_vowel(text: str) -> bool:
    return any(ch in "áéíóú" for ch in (text or ""))


def first_translation_segment(raw: str) -> str:
    cleaned = clean_translation(raw)
    if not cleaned:
        return ""
    return cleaned.split(";")[0].strip()


def expected_gerund(base_infinitive: str) -> str:
    if base_infinitive in IRREGULAR_GERUNDS:
        return IRREGULAR_GERUNDS[base_infinitive]

    stem = base_infinitive[:-2]
    ending = base_infinitive[-2:]
    if ending == "ar":
        return stem + "ando"
    if ending in {"er", "ir"}:
        if stem and stem[-1] in "aeiouáéíóúü":
            return stem + "yendo"
        return stem + "iendo"
    return ""


def match_attached_pronoun_sequence(lemma: str) -> tuple[str, ...]:
    lemma = (lemma or "").strip().lower()
    for parts in ATTACHED_PRONOUN_SEQUENCES:
        if lemma.endswith("".join(parts)):
            return parts
    return ()


def normalize_english_verb(word: str) -> str:
    lower = word.lower()
    irregular = {
        "is": "be",
        "does": "do",
        "has": "have",
        "goes": "go",
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
    override = GENERIC_PRONOUN_BASE_OVERRIDES.get(base_infinitive, {})
    if override:
        return override.get(form, override.get("infinitive", ""))

    phrase = first_translation_segment(raw_translation)
    if not phrase:
        return ""

    lower = phrase.lower()
    if lower.startswith("to "):
        phrase = phrase[3:].strip()
        lower = phrase.lower()

    if form == "imperative":
        words = phrase.split()
        if words and words[0].lower() in ENGLISH_SUBJECT_PRONOUNS:
            subject = words.pop(0).lower()
            if words and subject in {"he", "she", "it"}:
                words[0] = normalize_english_verb(words[0])
        phrase = " ".join(words).strip()

    return phrase


def render_direct_object(pronoun: str) -> tuple[str, str]:
    return DIRECT_OBJECT_PRONOUNS.get(pronoun, ("", ""))


def render_indirect_object(pronoun: str, with_to: bool) -> str:
    base = INDIRECT_OBJECT_PRONOUNS.get(pronoun, "")
    if not base:
        return ""
    if with_to:
        return f"to {base}"
    return base


def render_reflexive_target(pronoun: str) -> str:
    return {
        "me": "me",
        "te": "yourself",
        "nos": "us",
        "os": "yourselves",
        "se": "",
    }.get(pronoun, "")


def append_note(text: str, note: str) -> str:
    text = (text or "").strip()
    note = (note or "").strip()
    if not text:
        return ""
    if not note:
        return text
    return f"{text} ({note})"


def build_pronoun_translation(
    raw_translation: str,
    base_infinitive: str,
    attachment_form: str,
    attachment_type: str,
    pronouns: list[str],
) -> str:
    if attachment_type == "reflexive":
        reflexive = LEXICAL_REFLEXIVE_TRANSLATIONS.get(base_infinitive, {})
        return reflexive.get(attachment_form, "")

    if attachment_type == "direct_object":
        base = base_translation_phrase(raw_translation, attachment_form, base_infinitive)
        obj, note = render_direct_object(pronouns[0])
        if not base or not obj:
            return ""
        return append_note(f"{base} {obj}", note)

    if attachment_type == "indirect_object":
        if base_infinitive not in SAFE_SINGLE_INDIRECT_BASES:
            return ""
        base = base_translation_phrase(raw_translation, attachment_form, base_infinitive)
        recipient = render_indirect_object(pronouns[0], with_to=False)
        if not base or not recipient:
            return ""
        return f"{base} {recipient}"

    if attachment_type == "double_pronoun" and len(pronouns) == 2:
        first, second = pronouns

        special = REFLEXIVE_DOUBLE_TRANSLATIONS.get(base_infinitive)
        if special and first in REFLEXIVE_PRONOUNS:
            verb = special.get(attachment_form, "")
            particle = special.get("particle", "")
            obj, note = render_direct_object(second)
            target = render_reflexive_target(first)
            if not verb or not obj or not particle:
                return ""
            text = f"{verb} {obj} {particle}"
            if target:
                text = f"{text} {target}"
            return append_note(text, note)

        if base_infinitive not in SAFE_DOUBLE_BASES:
            return ""
        base = base_translation_phrase(raw_translation, attachment_form, base_infinitive)
        obj, note = render_direct_object(second)
        recipient = render_indirect_object(first, with_to=True)
        if not base or not obj or not recipient:
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
    tags = [t for t in (existing_tags or "").split("|") if t]

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
        return result

    pronoun_type = ""
    translation = ""
    confidence = "medium"
    reason = "candidate_only"

    if len(pronoun_parts) == 2:
        pronoun_type = "double_pronoun"
    else:
        pronoun = pronoun_parts[0]
        if pronoun in DIRECT_OBJECT_PRONOUNS:
            pronoun_type = "direct_object"
        elif pronoun in REFLEXIVE_PRONOUNS and base_infinitive in LEXICAL_REFLEXIVE_TRANSLATIONS:
            pronoun_type = "reflexive"
        elif pronoun in {"se"}:
            pronoun_type = "reflexive"
        else:
            pronoun_type = "indirect_object"

    translation = build_pronoun_translation(
        raw_translation=raw_translation,
        base_infinitive=base_infinitive,
        attachment_form=attachment_form,
        attachment_type=pronoun_type,
        pronouns=pronoun_parts,
    )

    if translation:
        confidence = "high"
        if pronoun_type == "reflexive":
            reason = "safe_reflexive_match"
        elif pronoun_type == "double_pronoun":
            reason = "safe_double_pronoun_match"
        else:
            reason = "safe_single_pronoun_match"

    return {
        "relation": "attached_pronoun_form",
        "form": attachment_form,
        "type": pronoun_type or "unknown",
        "pronouns": "+".join(pronoun_parts),
        "count": str(len(pronoun_parts)),
        "confidence": confidence,
        "reason": reason,
        "translation": translation,
    }


def has_parenthetical_gloss(raw: str) -> bool:
    return bool(re.search(r"\([^()]*\)", raw or ""))


def is_blocked_lemma_pair(lemma: str, original_lemma: str) -> bool:
    base_infinitive, _ = split_infinitive(original_lemma)
    return (base_infinitive, (lemma or "").strip().lower()) in BLOCKED_LEMMA_PAIRS


def is_safe_regular_candidate(lemma: str, original_lemma: str) -> bool:
    lemma = (lemma or "").strip().lower()
    base_infinitive, _ = split_infinitive(original_lemma)

    if not lemma or not base_infinitive:
        return False
    if " " in lemma or " " in base_infinitive:
        return False
    if not lemma.isalpha() or not base_infinitive.isalpha():
        return False
    if len(lemma) < 2 or len(base_infinitive) < 3:
        return False
    if not base_infinitive.endswith(("ar", "er", "ir")):
        return False
    if is_blocked_lemma_pair(lemma, original_lemma):
        return False
    return True


def clean_translation(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    cleaned = re.sub(r"\s{2,}", " ", raw)
    parts = [p.strip() for p in cleaned.split(";") if p.strip()]
    deduped: list[str] = []
    for p in parts:
        if p not in deduped:
            deduped.append(p)
    return "; ".join(deduped)


def append_contexts(raw_translation: str, context_parts: list[str]) -> str:
    raw_translation = (raw_translation or "").strip()
    if not context_parts:
        return raw_translation

    cleaned_translation = clean_translation(raw_translation)
    if not cleaned_translation:
        return raw_translation

    m = re.search(r"\(([^()]*)\)\s*$", raw_translation)
    if m:
        existing = [p.strip() for p in m.group(1).split(";") if p.strip()]
        base = raw_translation[: m.start()].rstrip()
        merged = existing[:]
        for part in context_parts:
            if part not in merged:
                merged.append(part)
        return f"{base} ({'; '.join(merged)})"

    return f"{cleaned_translation} ({'; '.join(context_parts)})"


def infer_imperative_form(
    lemma: str,
    original_lemma: str,
    pos: str,
    allow_regular_tu: bool = False,
) -> tuple[str, str, str, str, str, str]:
    lemma = (lemma or "").strip().lower()
    pos = normalize_pos(pos)
    base_infinitive, is_pronominal = split_infinitive(original_lemma)

    if pos != "v":
        return ("unknown", "", "", "", "", "pos_not_supported")

    if not base_infinitive.endswith(("ar", "er", "ir")):
        return ("unknown", "", "", "", "", "original_not_infinitive")

    if is_blocked_lemma_pair(lemma, original_lemma):
        return ("not_imperative_form", "", "", "", "", "blocked_lemma_pair")

    manual = MANUAL_IMPERATIVE_MAP.get((base_infinitive, lemma))
    if manual:
        return manual

    if not is_safe_regular_candidate(lemma, original_lemma):
        return ("not_imperative_form", "", "", "", "", "unsafe_regular_candidate")

    if not is_pronominal and lemma == base_infinitive[:-1] + "d":
        return ("imperative_form", "vosotros", "plural", "affirmative", "high", "regular_vosotros_imperative")

    if allow_regular_tu and not is_pronominal:
        stem = base_infinitive[:-2]
        ending = base_infinitive[-2:]

        if ending == "ar" and lemma == stem + "a":
            return ("imperative_form", "tú", "singular", "affirmative", "low", "regular_tu_ar_ambiguous")

        if ending in {"er", "ir"} and lemma == stem + "e":
            return ("imperative_form", "tú", "singular", "affirmative", "low", "regular_tu_er_ir_ambiguous")

    return ("not_imperative_form", "", "", "", "", "no_safe_match")


def infer_subjunctive_form(
    lemma: str,
    original_lemma: str,
    pos: str,
) -> tuple[str, str, str, str, str, str]:
    lemma = (lemma or "").strip().lower()
    pos = normalize_pos(pos)
    base_infinitive, _ = split_infinitive(original_lemma)

    if pos != "v":
        return ("unknown", "", "", "", "", "pos_not_supported")

    if not base_infinitive.endswith(("ar", "er", "ir")):
        return ("unknown", "", "", "", "", "original_not_infinitive")

    if is_blocked_lemma_pair(lemma, original_lemma):
        return ("not_subjunctive_form", "", "", "", "", "blocked_lemma_pair")

    manual = MANUAL_SUBJUNCTIVE_MAP.get((base_infinitive, lemma))
    if manual:
        return ("subjunctive_form", manual[1], manual[2], manual[3], "high", manual[4])

    if not is_safe_regular_candidate(lemma, original_lemma):
        return ("not_subjunctive_form", "", "", "", "", "unsafe_regular_candidate")

    stem = base_infinitive[:-2]
    ending = base_infinitive[-2:]

    if ending == "ar":
        present_map = {
            stem + "e":    ("present", "singular_ambiguous", "singular"),
            stem + "es":   ("present", "second", "singular"),
            stem + "emos": ("present", "first", "plural"),
            stem + "éis":  ("present", "second", "plural"),
            stem + "en":   ("present", "third", "plural"),
        }
        imperfect_ra_map = {
            stem + "ara":    ("imperfect_ra", "singular_ambiguous", "singular"),
            stem + "aras":   ("imperfect_ra", "second", "singular"),
            stem + "áramos": ("imperfect_ra", "first", "plural"),
            stem + "arais":  ("imperfect_ra", "second", "plural"),
            stem + "aran":   ("imperfect_ra", "third", "plural"),
        }
        imperfect_se_map = {
            stem + "ase":    ("imperfect_se", "singular_ambiguous", "singular"),
            stem + "ases":   ("imperfect_se", "second", "singular"),
            stem + "ásemos": ("imperfect_se", "first", "plural"),
            stem + "aseis":  ("imperfect_se", "second", "plural"),
            stem + "asen":   ("imperfect_se", "third", "plural"),
        }
    else:
        present_map = {
            stem + "a":    ("present", "singular_ambiguous", "singular"),
            stem + "as":   ("present", "second", "singular"),
            stem + "amos": ("present", "first", "plural"),
            stem + "áis":  ("present", "second", "plural"),
            stem + "an":   ("present", "third", "plural"),
        }
        imperfect_ra_map = {
            stem + "iera":    ("imperfect_ra", "singular_ambiguous", "singular"),
            stem + "ieras":   ("imperfect_ra", "second", "singular"),
            stem + "iéramos": ("imperfect_ra", "first", "plural"),
            stem + "ierais":  ("imperfect_ra", "second", "plural"),
            stem + "ieran":   ("imperfect_ra", "third", "plural"),
        }
        imperfect_se_map = {
            stem + "iese":    ("imperfect_se", "singular_ambiguous", "singular"),
            stem + "ieses":   ("imperfect_se", "second", "singular"),
            stem + "iésemos": ("imperfect_se", "first", "plural"),
            stem + "ieseis":  ("imperfect_se", "second", "plural"),
            stem + "iesen":   ("imperfect_se", "third", "plural"),
        }

    if lemma in present_map:
        tense, person, number = present_map[lemma]
        return ("subjunctive_form", tense, person, number, "low", "regular_present")

    if lemma in imperfect_ra_map:
        tense, person, number = imperfect_ra_map[lemma]
        return ("subjunctive_form", tense, person, number, "medium", "regular_imperfect_ra")

    if lemma in imperfect_se_map:
        tense, person, number = imperfect_se_map[lemma]
        return ("subjunctive_form", tense, person, number, "medium", "regular_imperfect_se")

    return ("not_subjunctive_form", "", "", "", "", "no_match")


def imperative_context(person: str, reason: str) -> str:
    return "imperative"


def subjunctive_context(tense: str) -> str:
    if tense == "present":
        return "present subjunctive"
    if tense in {"imperfect_ra", "imperfect_se"}:
        return "past subjunctive"
    return "subjunctive"


def build_tags(
    existing_tags: str,
    imperative_person: str,
    imperative_number: str,
    imperative_polarity: str,
    subjunctive_tense: str,
    subjunctive_person: str,
    subjunctive_number: str,
) -> str:
    tags = [t for t in (existing_tags or "").split("|") if t]

    if imperative_person:
        tags.append(imperative_person)
        tags.append("2nd_person")
        if imperative_number:
            tags.append(imperative_number)
        tags.append("imperative")
        if imperative_polarity:
            tags.append(imperative_polarity)

    if subjunctive_tense:
        tags.append("subjunctive")
        tags.append(subjunctive_tense)
        if subjunctive_person == "singular_ambiguous":
            tags.append("singular_ambiguous")
        else:
            tags.append(subjunctive_person)
            if subjunctive_number:
                tags.append(subjunctive_number)

    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            out.append(tag)
    return "|".join(out)


def should_write_imperative_context(relation: str, confidence: str) -> bool:
    return relation == "imperative_form" and confidence == "high"


def should_write_subjunctive_context(relation: str, confidence: str) -> bool:
    return relation == "subjunctive_form" and confidence == "high"


def review_reason(
    old_row: dict[str, str],
    new_row: dict[str, str],
    skipped_existing_brackets: bool,
) -> str:
    old_translation = (old_row.get("translation", "") or "").strip()
    new_translation = (new_row.get("translation", "") or "").strip()
    translation_changed = old_translation != new_translation

    imp_relation = new_row.get("imperative_relation", "")
    subj_relation = new_row.get("subjunctive_relation", "")
    pronoun_relation = new_row.get("pronoun_attachment_relation", "")
    imp_reason = new_row.get("imperative_reason", "")
    subj_reason = new_row.get("subjunctive_reason", "")
    pronoun_reason = new_row.get("pronoun_attachment_reason", "")

    if translation_changed:
        return "translation_changed"
    if skipped_existing_brackets and (
        imp_relation == "imperative_form"
        or subj_relation == "subjunctive_form"
        or pronoun_relation == "attached_pronoun_form"
    ):
        return "existing_translation_brackets"
    if pronoun_relation == "attached_pronoun_form" and new_row.get("pronoun_attachment_confidence", "") != "high":
        return "attached_pronoun_candidate_only"
    if imp_relation == "imperative_form" and subj_relation == "subjunctive_form":
        return "multiple_mood_matches"
    if imp_relation == "imperative_form" and not should_write_imperative_context(imp_relation, new_row.get("imperative_confidence", "")):
        return "imperative_candidate_only"
    if subj_relation == "subjunctive_form" and not should_write_subjunctive_context(subj_relation, new_row.get("subjunctive_confidence", "")):
        return "subjunctive_candidate_only"
    if pronoun_reason == "manual_irregular":
        return "attached_pronoun_manual_match"
    return ""


def rewrite_row(
    row: dict[str, str],
    allow_regular_tu: bool,
    *,
    enable_mood_context: bool = True,
    enable_pronoun_attachment: bool = False,
) -> dict[str, str]:
    row = dict(row)

    lemma = row.get("lemma", "")
    original_lemma = row.get("original_lemma", "")
    pos = row.get("pos", "")
    raw_translation = row.get("translation", "")

    if enable_pronoun_attachment:
        pronoun_attachment = infer_attached_pronoun_form(
            lemma=lemma,
            original_lemma=original_lemma,
            pos=pos,
            raw_translation=raw_translation,
        )
    else:
        pronoun_attachment = {
            "relation": "",
            "form": "",
            "type": "",
            "pronouns": "",
            "count": "",
            "confidence": "",
            "reason": "",
            "translation": "",
        }

    if enable_mood_context:
        imp_relation, imp_person, imp_number, imp_polarity, imp_confidence, imp_reason = infer_imperative_form(
            lemma=lemma,
            original_lemma=original_lemma,
            pos=pos,
            allow_regular_tu=allow_regular_tu,
        )

        subj_relation, subj_tense, subj_person, subj_number, subj_confidence, subj_reason = infer_subjunctive_form(
            lemma=lemma,
            original_lemma=original_lemma,
            pos=pos,
        )
    else:
        imp_relation = ""
        imp_person = ""
        imp_number = ""
        imp_polarity = ""
        imp_confidence = ""
        imp_reason = ""
        subj_relation = ""
        subj_tense = ""
        subj_person = ""
        subj_number = ""
        subj_confidence = ""
        subj_reason = ""

    row["imperative_relation"] = imp_relation
    row["imperative_person"] = imp_person
    row["imperative_number"] = imp_number
    row["imperative_polarity"] = imp_polarity
    row["imperative_confidence"] = imp_confidence
    row["imperative_reason"] = imp_reason

    row["subjunctive_relation"] = subj_relation
    row["subjunctive_tense"] = subj_tense
    row["subjunctive_person"] = subj_person
    row["subjunctive_number"] = subj_number
    row["subjunctive_confidence"] = subj_confidence
    row["subjunctive_reason"] = subj_reason

    row["pronoun_attachment_relation"] = pronoun_attachment["relation"]
    row["pronoun_attachment_form"] = pronoun_attachment["form"]
    row["pronoun_attachment_type"] = pronoun_attachment["type"]
    row["pronoun_attachment_pronouns"] = pronoun_attachment["pronouns"]
    row["pronoun_attachment_count"] = pronoun_attachment["count"]
    row["pronoun_attachment_confidence"] = pronoun_attachment["confidence"]
    row["pronoun_attachment_reason"] = pronoun_attachment["reason"]

    if has_parenthetical_gloss(raw_translation):
        row["translation"] = raw_translation
        if imp_relation == "imperative_form" or subj_relation == "subjunctive_form":
            row["tags"] = build_tags(
                row.get("tags", ""),
                imp_person,
                imp_number,
                imp_polarity,
                subj_tense,
                subj_person,
                subj_number,
            )
        row["tags"] = build_pronoun_tags(
            row.get("tags", ""),
            pronoun_attachment["relation"],
            pronoun_attachment["type"],
            pronoun_attachment["pronouns"].split("+") if pronoun_attachment["pronouns"] else [],
            pronoun_attachment["confidence"],
        )
        return row

    if (
        pronoun_attachment["relation"] == "attached_pronoun_form"
        and pronoun_attachment["confidence"] == "high"
        and pronoun_attachment["translation"]
    ):
        row["translation"] = pronoun_attachment["translation"]
        row["tags"] = build_pronoun_tags(
            row.get("tags", ""),
            pronoun_attachment["relation"],
            pronoun_attachment["type"],
            pronoun_attachment["pronouns"].split("+") if pronoun_attachment["pronouns"] else [],
            pronoun_attachment["confidence"],
        )
        return row

    contexts: list[str] = []
    if imp_relation == "imperative_form" and subj_relation == "subjunctive_form":
        row["translation"] = raw_translation
        row["tags"] = build_tags(
            row.get("tags", ""),
            imp_person,
            imp_number,
            imp_polarity,
            subj_tense,
            subj_person,
            subj_number,
        )
        row["tags"] = build_pronoun_tags(
            row.get("tags", ""),
            pronoun_attachment["relation"],
            pronoun_attachment["type"],
            pronoun_attachment["pronouns"].split("+") if pronoun_attachment["pronouns"] else [],
            pronoun_attachment["confidence"],
        )
        return row

    if imp_relation == "imperative_form" and should_write_imperative_context(imp_relation, imp_confidence):
        contexts.append(imperative_context(imp_person, imp_reason))
    if subj_relation == "subjunctive_form" and should_write_subjunctive_context(subj_relation, subj_confidence):
        contexts.append(subjunctive_context(subj_tense))

    if imp_relation == "imperative_form" or subj_relation == "subjunctive_form":
        row["tags"] = build_tags(
            row.get("tags", ""),
            imp_person,
            imp_number,
            imp_polarity,
            subj_tense,
            subj_person,
            subj_number,
        )

    row["tags"] = build_pronoun_tags(
        row.get("tags", ""),
        pronoun_attachment["relation"],
        pronoun_attachment["type"],
        pronoun_attachment["pronouns"].split("+") if pronoun_attachment["pronouns"] else [],
        pronoun_attachment["confidence"],
    )

    if contexts:
        row["translation"] = append_contexts(raw_translation, contexts)
    else:
        row["translation"] = raw_translation

    return row


def output_fieldnames(input_fieldnames: list[str]) -> list[str]:
    missing = [c for c in REQUIRED_COLUMNS if c not in set(input_fieldnames)]
    if missing:
        raise SystemExit(f"Input CSV is missing required columns: {', '.join(missing)}")
    return list(OUTPUT_COLUMNS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect Spanish imperative and subjunctive forms and annotate translations.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--allow-regular-tu",
        action="store_true",
        default=False,
        help="Allow ambiguous regular tú imperatives like habla/come/vive with low confidence.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    review_log_path = output_path.with_name(f"{output_path.stem}-mood-review.csv")

    with input_path.open("r", newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise SystemExit("Input CSV has no header row.")
        fieldnames = output_fieldnames(list(reader.fieldnames))
        original_rows = list(reader)

    rows = [
        rewrite_row(
            row,
            args.allow_regular_tu,
            enable_mood_context=True,
            enable_pronoun_attachment=False,
        )
        for row in original_rows
    ]

    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    review_rows = []
    for old_row, new_row in zip(original_rows, rows):
        old_translation = (old_row.get("translation", "") or "").strip()
        new_translation = (new_row.get("translation", "") or "").strip()
        skipped_existing_brackets = has_parenthetical_gloss(old_translation)
        reason = review_reason(old_row, new_row, skipped_existing_brackets)

        if reason:
            review_rows.append({
                "rank": new_row.get("rank", ""),
                "lemma": new_row.get("lemma", ""),
                "original_lemma": new_row.get("original_lemma", ""),
                "old_translation": old_translation,
                "new_translation": new_translation,
                "translation_changed": "yes" if old_translation != new_translation else "no",
                "review_reason": reason,
                "imperative_relation": new_row.get("imperative_relation", ""),
                "imperative_person": new_row.get("imperative_person", ""),
                "imperative_polarity": new_row.get("imperative_polarity", ""),
                "imperative_confidence": new_row.get("imperative_confidence", ""),
                "subjunctive_relation": new_row.get("subjunctive_relation", ""),
                "subjunctive_tense": new_row.get("subjunctive_tense", ""),
                "subjunctive_person": new_row.get("subjunctive_person", ""),
                "subjunctive_confidence": new_row.get("subjunctive_confidence", ""),
                "imperative_reason": new_row.get("imperative_reason", ""),
                "subjunctive_reason": new_row.get("subjunctive_reason", ""),
                "pronoun_attachment_relation": new_row.get("pronoun_attachment_relation", ""),
                "pronoun_attachment_form": new_row.get("pronoun_attachment_form", ""),
                "pronoun_attachment_type": new_row.get("pronoun_attachment_type", ""),
                "pronoun_attachment_pronouns": new_row.get("pronoun_attachment_pronouns", ""),
                "pronoun_attachment_count": new_row.get("pronoun_attachment_count", ""),
                "pronoun_attachment_confidence": new_row.get("pronoun_attachment_confidence", ""),
                "pronoun_attachment_reason": new_row.get("pronoun_attachment_reason", ""),
            })

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
                "imperative_relation",
                "imperative_person",
                "imperative_polarity",
                "imperative_confidence",
                "subjunctive_relation",
                "subjunctive_tense",
                "subjunctive_person",
                "subjunctive_confidence",
                "imperative_reason",
                "subjunctive_reason",
                "pronoun_attachment_relation",
                "pronoun_attachment_form",
                "pronoun_attachment_type",
                "pronoun_attachment_pronouns",
                "pronoun_attachment_count",
                "pronoun_attachment_confidence",
                "pronoun_attachment_reason",
            ],
        )
        writer.writeheader()
        writer.writerows(review_rows)

    print(f"Saved {len(rows)} rows to {output_path}.")
    print(f"Saved {len(review_rows)} review rows to {review_log_path}.")


if __name__ == "__main__":
    main()
