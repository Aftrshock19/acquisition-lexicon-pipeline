#!/usr/bin/env python3
"""
Add translation context to `spa-eng.csv` while preserving existing row data.

Usage:
  python3 add_context.py
  python3 add_context.py --input spa-eng.csv --output spa-eng-with-context.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

DEFAULT_INPUT = Path("spa-eng.csv")
DEFAULT_OUTPUT = Path("spa-eng-with-context.csv")
OUTPUT_FIELDNAMES = [
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

ALLOWED_POS_FOR_BRACKETS = {
    "article",
    "determiner",
    "pronoun",
    "verb",
    "preposition",
    "contraction",
}

BRACKET_NORMALIZATION = {
    "fem.": {"gender": "fem", "number": "sg"},
    "masc.": {"gender": "masc", "number": "sg"},
    "fem. pl.": {"gender": "fem", "number": "pl"},
    "masc. pl.": {"gender": "masc", "number": "pl"},
    "neuter": {"gender": "neuter"},
    "formal": {"register": "formal"},
    "formal pl.": {"register": "formal", "number": "pl"},
    "prepositional": {"pronoun_case": "prepositional"},
    "pl.": {"number": "pl"},
    "ser": {"verb_hint": "ser"},
    "estar": {"verb_hint": "estar"},
    "haber": {"verb_hint": "haber"},
    "tener": {"verb_hint": "tener"},
    "ser/ir": {"verb_hint": "ser/ir"},
    "subjunctive of ser": {"verb_hint": "ser", "mood": "subjunctive"},
}

ACCENT_DISTINCTION_OVERRIDES = {
    "el": {"translation": "the", "english_definition": "masculine singular definite article"},
    "él": {"translation": "he; him", "english_definition": "third person singular masculine pronoun"},
    "tu": {"translation": "your", "english_definition": "informal singular possessive determiner"},
    "tú": {"translation": "you", "english_definition": "informal singular subject pronoun"},
    "mi": {"translation": "my", "english_definition": "singular possessive determiner"},
    "mí": {"translation": "me", "english_definition": "first person singular prepositional pronoun"},
    "si": {"translation": "if; whether", "english_definition": "conjunction used for conditions or indirect yes no questions"},
    "sí": {"translation": "yes; oneself", "english_definition": "adverb of affirmation or reflexive prepositional pronoun"},
    "mas": {"translation": "but", "english_definition": "literary or formal variant of pero"},
    "más": {"translation": "more; most", "english_definition": "adverb of quantity or comparison"},
    "que": {"translation": "that; which", "english_definition": "common conjunction or relative pronoun"},
    "qué": {"translation": "what; which", "english_definition": "interrogative or exclamative pronoun"},
    "quien": {"translation": "who", "english_definition": "relative pronoun"},
    "quién": {"translation": "who", "english_definition": "interrogative pronoun"},
    "como": {"translation": "as; like", "english_definition": "conjunction or adverb of comparison"},
    "cómo": {"translation": "how", "english_definition": "interrogative or exclamative adverb"},
    "cuando": {"translation": "when", "english_definition": "conjunction or relative adverb"},
    "cuándo": {"translation": "when", "english_definition": "interrogative or exclamative adverb"},
    "donde": {"translation": "where", "english_definition": "relative adverb"},
    "dónde": {"translation": "where", "english_definition": "interrogative or exclamative adverb"},
    "cual": {"translation": "which", "english_definition": "relative pronoun"},
    "cuál": {"translation": "which; what", "english_definition": "interrogative pronoun"},
}

MANUAL_OVERRIDES = {
    "el": {"translation": "the", "english_definition": "masculine singular definite article", "pos": "article"},
    "la": {"translation": "the", "english_definition": "feminine singular definite article", "pos": "article"},
    "los": {"translation": "the", "english_definition": "masculine plural definite article", "pos": "article"},
    "las": {"translation": "the", "english_definition": "feminine plural definite article", "pos": "article"},
    "lo": {"translation": "it; the", "english_definition": "neuter pronoun or neuter article depending on context", "pos": "pronoun"},
    "un": {"translation": "a; an", "english_definition": "masculine singular indefinite article", "pos": "article"},
    "una": {"translation": "a; an", "english_definition": "feminine singular indefinite article", "pos": "article"},
    "unos": {"translation": "some", "english_definition": "masculine plural indefinite determiner", "pos": "determiner"},
    "unas": {"translation": "some", "english_definition": "feminine plural indefinite determiner", "pos": "determiner"},
    "al": {"translation": "to the", "english_definition": "contraction of a plus el", "pos": "contraction"},
    "del": {"translation": "of the; from the", "english_definition": "contraction of de plus el", "pos": "contraction"},
    "por": {
        "translation": "by; through; because of; for",
        "english_definition": "preposition used for cause means movement through exchange duration or agent",
        "pos": "preposition",
    },
    "para": {
        "translation": "for; to; in order to",
        "english_definition": "preposition used for purpose destination recipient deadline or goal",
        "pos": "preposition",
    },
    "me": {"translation": "me", "english_definition": "first person singular object pronoun", "pos": "pronoun"},
    "te": {"translation": "you", "english_definition": "second person singular object pronoun", "pos": "pronoun"},
    "nos": {"translation": "us", "english_definition": "first person plural object pronoun", "pos": "pronoun"},
    "os": {"translation": "you", "english_definition": "second person plural object pronoun used mainly in Spain", "pos": "pronoun"},
    "mí": {"translation": "me", "english_definition": "first person singular prepositional pronoun", "pos": "pronoun"},
    "ti": {"translation": "you", "english_definition": "second person singular prepositional pronoun", "pos": "pronoun"},
    "sí": {"translation": "oneself; yourself", "english_definition": "reflexive prepositional pronoun", "pos": "pronoun"},
    "usted": {"translation": "you", "english_definition": "formal singular pronoun", "pos": "pronoun"},
    "ustedes": {"translation": "you", "english_definition": "formal or neutral plural pronoun", "pos": "pronoun"},
    "esto": {"translation": "this", "english_definition": "neuter demonstrative pronoun", "pos": "pronoun"},
    "eso": {"translation": "that", "english_definition": "neuter demonstrative pronoun", "pos": "pronoun"},
    "ello": {"translation": "it", "english_definition": "neuter third person pronoun", "pos": "pronoun"},
}

VERB_PERSON_NUMBER_OVERRIDES = {
    "es": ("is", "third person singular present of ser"),
    "soy": ("am", "first person singular present of ser"),
    "eres": ("are", "second person singular present of ser"),
    "somos": ("are", "first person plural present of ser"),
    "son": ("are", "third person plural present of ser"),
    "fue": ("was; went", "third person singular preterite of ser or ir"),
    "fueron": ("were; went", "third person plural preterite of ser or ir"),
    "era": ("was", "third person singular imperfect of ser"),
    "eran": ("were", "third person plural imperfect of ser"),
    "sea": ("be", "third person singular present subjunctive of ser"),
    "será": ("will be", "third person singular future of ser"),
    "está": ("is", "third person singular present of estar"),
    "estoy": ("am", "first person singular present of estar"),
    "estás": ("are", "second person singular present of estar"),
    "estamos": ("are", "first person plural present of estar"),
    "están": ("are", "third person plural present of estar"),
    "estaba": ("was", "third person singular imperfect of estar"),
    "ha": ("has", "third person singular present of haber"),
    "he": ("have", "first person singular present of haber"),
    "has": ("have", "second person singular present of haber"),
    "han": ("have", "third person plural present of haber"),
    "había": ("had", "third person singular imperfect of haber"),
    "haya": ("have", "third person singular present subjunctive of haber"),
    "hubiera": ("had", "third person singular imperfect subjunctive of haber"),
    "tengo": ("have", "first person singular present of tener"),
    "tiene": ("has", "third person singular present of tener"),
    "tienes": ("have", "second person singular present of tener"),
    "tenemos": ("have", "first person plural present of tener"),
    "tenía": ("had", "third person singular imperfect of tener"),
}

ARTICLE_LEMMAS = {"el", "la", "los", "las", "lo", "un", "una", "unos", "unas"}
CONTRACTION_LEMMAS = {"al", "del"}
PREP_MANUAL_LEMMAS = {"por", "para"}
SPECIAL_PRONOUN_LEMMAS = {
    "me", "te", "nos", "os", "lo", "la", "los", "las", "le", "les", "se",
    "mí", "ti", "sí", "usted", "ustedes", "ello", "esto", "eso",
}
VERB_HINTS = {"ser", "estar", "haber", "tener", "ser/ir"}

VARIANT_SUPPORTED_POS = {"article", "determiner", "adjective", "noun", "pronoun"}

MANUAL_VARIANT_MAP = {
    ("el", "los"): ("masculine_plural_of_original", "masc", "pl", "manual"),
    ("la", "las"): ("feminine_plural_of_original", "fem", "pl", "manual"),
    ("un", "una"): ("feminine_of_original", "fem", "sg", "manual"),
    ("un", "unos"): ("masculine_plural_of_original", "masc", "pl", "manual"),
    ("un", "unas"): ("feminine_plural_of_original", "fem", "pl", "manual"),
    ("este", "esta"): ("feminine_of_original", "fem", "sg", "manual"),
    ("este", "estos"): ("masculine_plural_of_original", "masc", "pl", "manual"),
    ("este", "estas"): ("feminine_plural_of_original", "fem", "pl", "manual"),
    ("ese", "esa"): ("feminine_of_original", "fem", "sg", "manual"),
    ("ese", "esos"): ("masculine_plural_of_original", "masc", "pl", "manual"),
    ("ese", "esas"): ("feminine_plural_of_original", "fem", "pl", "manual"),
    ("otro", "otra"): ("feminine_of_original", "fem", "sg", "manual"),
    ("otro", "otros"): ("masculine_plural_of_original", "masc", "pl", "manual"),
    ("otro", "otras"): ("feminine_plural_of_original", "fem", "pl", "manual"),
    ("alguno", "alguna"): ("feminine_of_original", "fem", "sg", "manual"),
    ("alguno", "algunos"): ("masculine_plural_of_original", "masc", "pl", "manual"),
    ("alguno", "algunas"): ("feminine_plural_of_original", "fem", "pl", "manual"),
    ("todo", "toda"): ("feminine_of_original", "fem", "sg", "manual"),
    ("todo", "todos"): ("masculine_plural_of_original", "masc", "pl", "manual"),
    ("todo", "todas"): ("feminine_plural_of_original", "fem", "pl", "manual"),
}

TRANSLATION_CONTEXT_OVERRIDES = {
    "el": "masc.",
    "la": "fem.",
    "los": "masc. pl.",
    "las": "fem. pl.",
    "lo": "neuter",
    "un": "masc.",
    "una": "fem.",
    "unos": "masc. pl.",
    "unas": "fem. pl.",
    "este": "masc.",
    "esta": "fem.",
    "estos": "masc. pl.",
    "estas": "fem. pl.",
    "ese": "masc.",
    "esa": "fem.",
    "esos": "masc. pl.",
    "esas": "fem. pl.",
    "algún": "masc.",
    "alguna": "fem.",
    "algunos": "masc. pl.",
    "algunas": "fem. pl.",
    "ningún": "masc.",
    "ninguna": "fem.",
    "otro": "masc.",
    "otra": "fem.",
    "otros": "masc. pl.",
    "otras": "fem. pl.",
    "todo": None,
    "toda": "fem.",
    "todos": "masc. pl.",
    "todas": "fem. pl.",
    "mucho": None,
    "mucha": "fem.",
    "muchos": "masc. pl.",
    "muchas": "fem. pl.",
    "mí": "prepositional",
    "ti": "prepositional",
    "sí": "prepositional",
    "usted": "formal",
    "ustedes": "formal pl.",
    "esto": "neuter",
    "eso": "neuter",
    "ello": "neuter",
    "por": "por",
    "para": "para",
}

for verb_lemma, (_translation, english_definition) in VERB_PERSON_NUMBER_OVERRIDES.items():
    if " of ser or ir" in english_definition:
        TRANSLATION_CONTEXT_OVERRIDES[verb_lemma] = "ser/ir"
    elif " of ser" in english_definition:
        TRANSLATION_CONTEXT_OVERRIDES[verb_lemma] = "ser"
    elif " of estar" in english_definition:
        TRANSLATION_CONTEXT_OVERRIDES[verb_lemma] = "estar"
    elif " of haber" in english_definition:
        TRANSLATION_CONTEXT_OVERRIDES[verb_lemma] = "haber"
    elif " of tener" in english_definition:
        TRANSLATION_CONTEXT_OVERRIDES[verb_lemma] = "tener"


def context_bracket_from_features(
    lemma: str,
    pos: str,
    features: dict[str, str | bool],
) -> str:
    if lemma in TRANSLATION_CONTEXT_OVERRIDES:
        return TRANSLATION_CONTEXT_OVERRIDES[lemma] or ""

    pos = normalize_pos(pos)

    if pos in {"article", "determiner"}:
        gender = features.get("gender")
        number = features.get("number", "sg")

        if gender == "neuter":
            return "neuter"
        if gender == "masc" and number == "sg":
            return "masc."
        if gender == "fem" and number == "sg":
            return "fem."
        if gender == "masc" and number == "pl":
            return "masc. pl."
        if gender == "fem" and number == "pl":
            return "fem. pl."

    if pos == "pronoun":
        if features.get("pronoun_case") == "prepositional":
            return "prepositional"
        if features.get("register") == "formal" and features.get("number") == "pl":
            return "formal pl."
        if features.get("register") == "formal":
            return "formal"
        if features.get("gender") == "neuter":
            return "neuter"

    if pos == "verb":
        hint = features.get("verb_hint")
        if hint in VERB_HINTS:
            return str(hint)

    if pos == "preposition" and lemma in {"por", "para"}:
        return lemma

    return ""


def add_context_to_translation(
    translation: str,
    lemma: str,
    pos: str,
    features: dict[str, str | bool],
) -> str:
    translation = translation.strip()
    if not translation:
        return translation

    bracket = context_bracket_from_features(lemma, pos, features)
    if not bracket:
        return translation

    suffix = f" ({bracket})"
    if translation.endswith(suffix):
        return translation
    return f"{translation}{suffix}"


def has_brackets(text: str) -> bool:
    return bool(re.search(r"\([^()]*\)", text or ""))


def infer_variant_from_original(
    lemma: str,
    original_lemma: str,
    pos: str,
) -> tuple[str, str | None, str | None, str]:
    lemma = (lemma or "").strip().lower()
    original = (original_lemma or "").strip().lower()
    pos = normalize_pos(pos)

    if pos not in VARIANT_SUPPORTED_POS:
        return ("unknown", None, None, "pos_not_supported")

    if not lemma or not original:
        return ("unknown", None, None, "missing_lemma_or_original")

    manual = MANUAL_VARIANT_MAP.get((original, lemma))
    if manual:
        relation, gender, number, reason = manual
        return (relation, gender, number, reason)

    if lemma == original:
        return ("base", None, "sg", "same_form")

    if original.endswith("o"):
        stem = original[:-1]
        if lemma == stem + "a":
            return ("feminine_of_original", "fem", "sg", "o_to_a")
        if lemma == stem + "os":
            return ("masculine_plural_of_original", "masc", "pl", "o_to_os")
        if lemma == stem + "as":
            return ("feminine_plural_of_original", "fem", "pl", "o_to_as")

    if original.endswith("a"):
        stem = original[:-1]
        if lemma == stem + "o":
            return ("masculine_of_original", "masc", "sg", "a_to_o")

    if lemma == original + "s":
        return ("plural_of_original", None, "pl", "plus_s")

    if lemma == original + "es":
        return ("plural_of_original", None, "pl", "plus_es")

    if original.endswith("z") and lemma == original[:-1] + "ces":
        return ("plural_of_original", None, "pl", "z_to_ces")

    return ("unknown", None, None, "no_safe_match")


def variant_suffix(gender: str | None, number: str | None) -> str:
    bits: list[str] = []

    if gender == "masc":
        bits.append("masculine")
    elif gender == "fem":
        bits.append("feminine")

    if number == "pl":
        bits.append("plural")
    elif number == "sg" and gender is not None:
        bits.append("singular")

    if not bits:
        return ""
    return f" ({' '.join(bits)})"


def append_variant_context_if_safe(
    translation: str,
    lemma: str,
    original_lemma: str,
    pos: str,
    original_translation_had_brackets: bool,
) -> tuple[str, str, str, str, str]:
    cleaned = translation.strip()

    if original_translation_had_brackets:
        return cleaned, "unknown", "", "", "existing_translation_has_brackets"

    if has_brackets(cleaned):
        return cleaned, "unknown", "", "", "translation_already_has_brackets"

    relation, gender, number, reason = infer_variant_from_original(lemma, original_lemma, pos)

    suffix = variant_suffix(gender, number)
    if not suffix:
        return cleaned, relation, gender or "", number or "", reason

    if cleaned.endswith(suffix):
        return cleaned, relation, gender or "", number or "", reason

    return f"{cleaned}{suffix}", relation, gender or "", number or "", reason


def extract_brackets(text: str) -> tuple[list[str], str]:
    if not text:
        return [], ""
    brackets = re.findall(r"\(([^()]*)\)", text)
    cleaned = re.sub(r"\s*\([^()]*\)", "", text).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return [item.strip().lower() for item in brackets], cleaned


def normalize_pos(pos: str) -> str:
    if not pos:
        return ""
    pos = pos.strip().lower()
    mapping = {
        "article": "article",
        "art": "article",
        "determiner": "determiner",
        "det": "determiner",
        "pronoun": "pronoun",
        "pron": "pronoun",
        "preposition": "preposition",
        "prep": "preposition",
        "conjunction": "conjunction",
        "conj": "conjunction",
        "verb": "verb",
        "v": "verb",
        "noun": "noun",
        "n": "noun",
        "adjective": "adjective",
        "adj": "adjective",
        "adverb": "adverb",
        "adv": "adverb",
        "interjection": "interjection",
        "interj": "interjection",
        "contraction": "contraction",
        "number": "numeral",
        "numeral": "numeral",
        "num": "numeral",
        "prop": "proper noun",
        "proper noun": "proper noun",
        "phrase": "phrase",
        "particle": "particle",
        "letter": "letter",
        "prefix": "prefix",
        "none": "",
    }
    return mapping.get(pos, pos)


def split_translation(text: str) -> list[str]:
    return [part.strip() for part in text.split(";") if part.strip()]


def collect_allowed_features(lemma: str, pos: str, brackets: list[str]) -> dict[str, str | bool]:
    pos = normalize_pos(pos)
    if pos not in ALLOWED_POS_FOR_BRACKETS:
        return {}
    features: dict[str, str | bool] = {}
    for bracket in brackets:
        if bracket in BRACKET_NORMALIZATION:
            features.update(BRACKET_NORMALIZATION[bracket])
    if lemma in PREP_MANUAL_LEMMAS:
        features["prep_manual"] = True
    return features


def clean_translation(raw_translation: str) -> tuple[str, list[str]]:
    if not raw_translation:
        return "", []
    brackets, cleaned = extract_brackets(raw_translation)
    parts = split_translation(cleaned)
    deduped: list[str] = []
    for part in parts:
        if part not in deduped:
            deduped.append(part)
    return "; ".join(deduped), brackets


def build_article_definition(features: dict[str, str | bool], definite: bool) -> str:
    gender = features.get("gender")
    number = features.get("number", "sg")
    kind = "definite" if definite else "indefinite"
    gender_word = {
        "masc": "masculine",
        "fem": "feminine",
        "neuter": "neuter",
    }.get(gender, "")
    number_word = {
        "sg": "singular",
        "pl": "plural",
    }.get(number, "")
    bits = [item for item in [gender_word, number_word, kind, "article"] if item]
    return " ".join(bits)


def build_pronoun_definition(lemma: str, features: dict[str, str | bool]) -> str:
    if lemma in {"mí", "ti", "sí"}:
        return {
            "mí": "first person singular prepositional pronoun",
            "ti": "second person singular prepositional pronoun",
            "sí": "reflexive prepositional pronoun",
        }[lemma]
    if lemma == "usted":
        return "formal singular pronoun"
    if lemma == "ustedes":
        return "formal or neutral plural pronoun"
    if lemma in {"esto", "eso", "ello"}:
        return {
            "esto": "neuter demonstrative pronoun",
            "eso": "neuter demonstrative pronoun",
            "ello": "neuter third person pronoun",
        }[lemma]
    if features.get("pronoun_case") == "prepositional":
        return "prepositional pronoun"
    if features.get("register") == "formal" and features.get("number") == "pl":
        return "formal plural pronoun"
    if features.get("register") == "formal":
        return "formal pronoun"
    if features.get("gender") == "neuter":
        return "neuter pronoun"
    return "pronoun"


def build_definition(
    lemma: str,
    pos: str,
    features: dict[str, str | bool],
    cleaned_translation: str,
) -> str:
    pos = normalize_pos(pos)

    if lemma in VERB_PERSON_NUMBER_OVERRIDES and pos == "verb":
        return VERB_PERSON_NUMBER_OVERRIDES[lemma][1]

    if pos == "article":
        definite = lemma in {"el", "la", "los", "las", "lo"}
        return build_article_definition(features, definite)

    if pos == "determiner":
        if lemma in {"mi", "mis", "tu", "tus", "su", "sus", "nuestro", "nuestra", "nuestros", "nuestras"}:
            return "possessive determiner"
        if lemma in {"este", "esta", "estos", "estas", "ese", "esa", "esos", "esas"}:
            return "demonstrative determiner"
        if lemma in {"otro", "otra", "otros", "otras"}:
            return "other or another determiner"
        if lemma in {"todo", "toda", "todos", "todas"}:
            return "all or every determiner"
        if lemma in {"algún", "alguna", "algunos", "algunas"}:
            return "some or any determiner"
        if lemma in {"ningún", "ninguna"}:
            return "no or not any determiner"
        if lemma in {"mucho", "mucha", "muchos", "muchas"}:
            return "much or many determiner"
        return "determiner"

    if pos == "pronoun":
        return build_pronoun_definition(lemma, features)

    if pos == "preposition":
        return "preposition"

    if pos == "contraction":
        return "contraction"

    if pos == "verb":
        hint = features.get("verb_hint")
        if hint in VERB_HINTS:
            return f"verb form of {hint}"
        return "verb"

    if pos == "conjunction":
        return "conjunction"
    if pos == "adverb":
        return "adverb"
    if pos == "adjective":
        return "adjective"
    if pos == "noun":
        return "noun"
    if pos == "numeral":
        return "numeral"
    if pos == "proper noun":
        return "proper noun"
    if pos == "interjection":
        return "interjection"
    if pos == "phrase":
        return "phrase"
    if pos == "particle":
        return "particle"
    if pos == "letter":
        return "letter"
    if pos == "prefix":
        return "prefix"

    if cleaned_translation:
        return ""
    return ""


def accent_override_applies(lemma: str, pos: str) -> bool:
    compatible_pos = {
        "el": {"article", ""},
        "él": {"pronoun", ""},
        "tu": {"determiner", ""},
        "tú": {"pronoun", ""},
        "mi": {"determiner", ""},
        "mí": {"pronoun", ""},
        "si": {"conjunction", ""},
        "sí": {"adverb", "pronoun", ""},
        "mas": {"conjunction", ""},
        "más": {"adverb", "determiner", ""},
        "que": {"conjunction", "pronoun", ""},
        "qué": {"pronoun", ""},
        "quien": {"pronoun", ""},
        "quién": {"pronoun", ""},
        "como": {"conjunction", "adverb", ""},
        "cómo": {"adverb", ""},
        "cuando": {"conjunction", "adverb", ""},
        "cuándo": {"adverb", ""},
        "donde": {"adverb", ""},
        "dónde": {"adverb", ""},
        "cual": {"pronoun", ""},
        "cuál": {"pronoun", ""},
    }
    return pos in compatible_pos.get(lemma, {""})


def article_override_applies(lemma: str, cleaned_translation: str) -> bool:
    parts = set(split_translation(cleaned_translation))
    if lemma in {"el", "la", "los", "las"}:
        return parts == {"the"}
    if lemma == "lo":
        return parts <= {"it", "the"} and bool(parts)
    if lemma in {"un", "una"}:
        return parts <= {"a", "an", "one"} and {"a", "an"} <= parts
    if lemma in {"unos", "unas"}:
        return parts == {"some"}
    return False


def manual_override_applies(row: dict[str, str], cleaned_translation: str) -> bool:
    lemma = row.get("lemma", "").strip()
    pos = normalize_pos(row.get("pos", ""))
    override = MANUAL_OVERRIDES.get(lemma)
    if not override:
        return False

    if lemma in ARTICLE_LEMMAS:
        return article_override_applies(lemma, cleaned_translation)
    if lemma in CONTRACTION_LEMMAS:
        return pos in {"contraction", ""} or cleaned_translation == override["translation"]
    if lemma in PREP_MANUAL_LEMMAS:
        return pos in {"preposition", ""}
    if lemma in SPECIAL_PRONOUN_LEMMAS:
        return pos in {"pronoun", ""}
    return False


def verb_override_applies(row: dict[str, str], brackets: list[str]) -> bool:
    lemma = row.get("lemma", "").strip()
    if lemma not in VERB_PERSON_NUMBER_OVERRIDES:
        return False

    pos = normalize_pos(row.get("pos", ""))
    original_lemma = row.get("original_lemma", "").strip().lower()
    if pos == "verb":
        return True
    if original_lemma in {"ser", "estar", "haber", "tener", "ir"}:
        return True
    return any(bracket in VERB_HINTS for bracket in brackets)


def build_tags(
    pos: str,
    features: dict[str, str | bool],
    variant_relation: str,
    inferred_gender: str,
    inferred_number: str,
    english_definition: str,
) -> str:
    tags: list[str] = []

    # Gender: features (from brackets) take priority, then inferred variant
    gender = features.get("gender")
    if not gender and variant_relation not in {"base", "unknown", ""}:
        gender = inferred_gender or None

    if gender == "masc":
        tags.append("masculine")
    elif gender == "fem":
        tags.append("feminine")
    elif gender == "neuter":
        tags.append("neuter")

    # Number: features take priority, then inferred variant
    # Only tag "plural" for non-verbs (singular is the unmarked default)
    if pos != "verb":
        number = features.get("number")
        if not number and variant_relation not in {"base", "unknown", ""}:
            number = inferred_number or None
        if number == "pl":
            tags.append("plural")

    # Register / pronoun case
    if features.get("register") == "formal":
        tags.append("formal")
    if features.get("pronoun_case") == "prepositional":
        tags.append("prepositional")

    # Verb conjugation — parse the english_definition string
    if pos == "verb" and english_definition:
        defn = english_definition.lower()

        if "first person" in defn:
            tags.append("1st_person")
        elif "second person" in defn:
            tags.append("2nd_person")
        elif "third person" in defn:
            tags.append("3rd_person")

        if "singular" in defn:
            tags.append("singular")
        elif "plural" in defn:
            tags.append("plural")

        if "imperfect subjunctive" in defn:
            tags.append("imperfect_subjunctive")
        elif "present subjunctive" in defn:
            tags.append("present_subjunctive")
        elif "imperfect" in defn:
            tags.append("imperfect")
        elif "preterite" in defn:
            tags.append("preterite")
        elif "future" in defn:
            tags.append("future")
        elif "present" in defn:
            tags.append("present")

        for verb in ["ser/ir", "ser", "estar", "haber", "tener"]:
            if f"of {verb}" in defn:
                tags.append(verb.replace("/", "_"))
                break

    return "|".join(tags)


def rewrite_row(row: dict[str, str]) -> dict[str, str]:
    row = dict(row)
    lemma = row.get("lemma", "").strip()
    original_lemma = row.get("original_lemma", "").strip()
    pos = normalize_pos(row.get("pos", ""))
    raw_translation = row.get("translation", "").strip()
    original_translation_had_brackets = has_brackets(raw_translation)

    cleaned_translation, brackets = clean_translation(raw_translation)
    features = collect_allowed_features(lemma, pos, brackets)

    row["variant_relation"] = "unknown"
    row["inferred_gender"] = ""
    row["inferred_number"] = ""
    row["variant_reason"] = ""

    if pos:
        row["pos"] = pos

    if manual_override_applies(row, cleaned_translation):
        override = MANUAL_OVERRIDES[lemma]
        row["translation"] = override["translation"]
        row["english_definition"] = override["english_definition"]
        if override.get("pos"):
            row["pos"] = override["pos"]
        row["translation"] = add_context_to_translation(
            row["translation"],
            lemma,
            row["pos"],
            features,
        )
    elif lemma in ACCENT_DISTINCTION_OVERRIDES and accent_override_applies(lemma, pos):
        override = ACCENT_DISTINCTION_OVERRIDES[lemma]
        row["translation"] = override["translation"]
        row["english_definition"] = override["english_definition"]
        row["translation"] = add_context_to_translation(
            row["translation"],
            lemma,
            row.get("pos", pos),
            features,
        )
    elif verb_override_applies(row, brackets):
        translation, english_definition = VERB_PERSON_NUMBER_OVERRIDES[lemma]
        row["translation"] = translation
        row["english_definition"] = english_definition
        row["pos"] = "verb"
        verb_features = dict(features)
        if lemma in TRANSLATION_CONTEXT_OVERRIDES:
            verb_features["verb_hint"] = TRANSLATION_CONTEXT_OVERRIDES[lemma]
        row["translation"] = add_context_to_translation(
            row["translation"],
            lemma,
            row["pos"],
            verb_features,
        )
    else:
        row["translation"] = cleaned_translation
        row["english_definition"] = build_definition(
            lemma,
            row.get("pos", pos),
            features,
            cleaned_translation,
        )
        row["translation"] = add_context_to_translation(
            row["translation"],
            lemma,
            row.get("pos", pos),
            features,
        )

    row["translation"], relation, gender, number, reason = append_variant_context_if_safe(
        row["translation"],
        lemma,
        original_lemma,
        row.get("pos", pos),
        original_translation_had_brackets,
    )

    row["variant_relation"] = relation
    row["inferred_gender"] = gender
    row["inferred_number"] = number
    row["variant_reason"] = reason

    row["tags"] = build_tags(
        row.get("pos", pos),
        features,
        relation,
        gender,
        number,
        row.get("english_definition", ""),
    )

    return row


def normalize_output_row(row: dict[str, str]) -> dict[str, str]:
    normalized = {name: row.get(name, "") for name in OUTPUT_FIELDNAMES}
    for name in ("definitions", "sentence", "english_sentence"):
        normalized[name] = normalized.get(name, "") or ""
    return normalized

def output_fieldnames(fieldnames: list[str]) -> list[str]:
    out = list(fieldnames)

    if "english_definition" not in out:
        if "translation" in out:
            index = out.index("translation") + 1
            out = out[:index] + ["english_definition"] + out[index:]
        else:
            out.append("english_definition")

    if "tags" not in out:
        if "pos" in out:
            index = out.index("pos") + 1
            out = out[:index] + ["tags"] + out[index:]
        else:
            out.append("tags")

    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add cleaned translation context to stg_words_spa.csv.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input CSV path")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output CSV path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    review_log_path = output_path.with_name(f"{output_path.stem}-variant-review.csv")

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

    review_rows = []
    for old_row, new_row in zip(original_rows, rows):
        old_translation = (old_row.get("translation", "") or "").strip()
        new_translation = (new_row.get("translation", "") or "").strip()
        if old_translation != new_translation:
            review_rows.append(
                {
                    "rank": new_row.get("rank", ""),
                    "lemma": new_row.get("lemma", ""),
                    "original_lemma": new_row.get("original_lemma", ""),
                    "new_translation": new_translation,
                    "variant_relation": new_row.get("variant_relation", ""),
                    "reason": new_row.get("variant_reason", ""),
                }
            )

    with review_log_path.open("w", newline="", encoding="utf-8") as logfile:
        writer = csv.DictWriter(
            logfile,
            fieldnames=[
                "rank",
                "lemma",
                "original_lemma",
                "new_translation",
                "variant_relation",
                "reason",
            ],
        )
        writer.writeheader()
        writer.writerows(review_rows)

    print(f"Saved {len(rows)} rows to {output_path}.")
    print(f"Saved {len(review_rows)} changed rows to {review_log_path}.")


if __name__ == "__main__":
    main()
