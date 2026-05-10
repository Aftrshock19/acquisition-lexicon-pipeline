#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

DEFAULT_INPUT = Path("spa-eng.csv")
DEFAULT_OUTPUT = Path("spa-eng-past.csv")

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

EXTRA_COLUMNS = [
    "old_translation",
    "translation_changed",
    "review_reason",
    "past_relation",
    "past_tense",
    "past_person",
    "past_number",
    "past_context",
    "past_confidence",
    "past_reason",
]

PERSON_NUMBER_MAP = {
    "1sg": ("first", "singular"),
    "2sg": ("second", "singular"),
    "3sg": ("third", "singular"),
    "1pl": ("first", "plural"),
    "2pl": ("second", "plural"),
    "3pl": ("third", "plural"),
    "13sg": ("singular_ambiguous", "singular"),
}

SER_IR_PRETERITE = {
    "fui": "1sg",
    "fuiste": "2sg",
    "fue": "3sg",
    "fuimos": "1pl",
    "fuisteis": "2pl",
    "fueron": "3pl",
}

SER_IMPERFECT = {
    "era": "13sg",
    "eras": "2sg",
    "éramos": "1pl",
    "erais": "2pl",
    "eran": "3pl",
}

IR_IMPERFECT = {
    "iba": "13sg",
    "ibas": "2sg",
    "íbamos": "1pl",
    "ibais": "2pl",
    "iban": "3pl",
}

DAR_PRETERITE = {
    "di": "1sg",
    "diste": "2sg",
    "dio": "3sg",
    "dimos": "1pl",
    "disteis": "2pl",
    "dieron": "3pl",
}

VER_PRETERITE = {
    "vi": "1sg",
    "viste": "2sg",
    "vio": "3sg",
    "vimos": "1pl",
    "visteis": "2pl",
    "vieron": "3pl",
}

HACER_PRETERITE = {
    "hice": "1sg",
    "hiciste": "2sg",
    "hizo": "3sg",
    "hicimos": "1pl",
    "hicisteis": "2pl",
    "hicieron": "3pl",
}

STRONG_PRETERITE_STEMS = {
    "andar": "anduv",
    "andar(se)": "anduv",
    "estar": "estuv",
    "tener": "tuv",
    "poder": "pud",
    "poner": "pus",
    "saber": "sup",
    "querer": "quis",
    "venir": "vin",
    "haber": "hub",
    "caber": "cup",
}

STRONG_PRETERITE_ENDINGS = {
    "e": "1sg",
    "iste": "2sg",
    "o": "3sg",
    "imos": "1pl",
    "isteis": "2pl",
    "ieron": "3pl",
}

J_STEM_LEMMAS = {
    "decir": "dij",
    "predecir": "predij",
    "contradecir": "contradij",
    "traer": "traj",
    "atraer": "atraj",
    "distraer": "distraj",
}

REGULAR_PRETERITE_AR = {
    "é": "1sg",
    "aste": "2sg",
    "ó": "3sg",
    "amos": "1pl",
    "asteis": "2pl",
    "aron": "3pl",
}

REGULAR_PRETERITE_ER_IR = {
    "í": "1sg",
    "iste": "2sg",
    "ió": "3sg",
    "imos": "1pl",
    "isteis": "2pl",
    "ieron": "3pl",
}

REGULAR_IMPERFECT_AR = {
    "aba": "13sg",
    "abas": "2sg",
    "ábamos": "1pl",
    "abais": "2pl",
    "aban": "3pl",
}

REGULAR_IMPERFECT_ER_IR = {
    "ía": "13sg",
    "ías": "2sg",
    "íamos": "1pl",
    "íais": "2pl",
    "ían": "3pl",
}

SUBJECT_RE = re.compile(r"^(I|you|he|she|it|we|they)\s+(.+)$", re.IGNORECASE)

BLOCKING_MOOD_TAGS = {"subjunctive", "imperative"}

MANUAL_PAST_PREDICATES = {
    "advertir": ["warned"],
    "beber": ["drank"],
    "comer": ["ate"],
    "comprar": ["bought"],
    "conducir": ["drove"],
    "conseguir": ["achieved"],
    "costar": ["cost"],
    "crecer": ["grew"],
    "cortar": ["cut"],
    "dar": ["gave"],
    "decidir": ["decided"],
    "decir": ["said"],
    "dormir": ["slept"],
    "elegir": ["chose"],
    "enseñar": ["taught"],
    "entender": ["understood"],
    "escribir": ["wrote"],
    "haber": ["had"],
    "hacer": ["did", "made"],
    "leer": ["read"],
    "ocultar": ["hid"],
    "oir": ["heard"],
    "oír": ["heard"],
    "pensar": ["thought"],
    "poner": ["put"],
    "poder": ["could"],
    "querer": ["wanted"],
    "romper": ["broke"],
    "saber": ["knew"],
    "sentir": ["felt"],
    "tener": ["had"],
    "traer": ["brought"],
    "vender": ["sold"],
    "venir": ["came"],
    "ver": ["saw"],
    "volar": ["flew"],
    "disparar": ["shot"],
    "golpear": ["hit"],
    "jurar": ["swore"],
}

BAD_PAST_TO_BASE = {
    "breaked": "break",
    "buyed": "buy",
    "choosed": "choose",
    "costed": "cost",
    "cuted": "cut",
    "drived": "drive",
    "drinked": "drink",
    "eated": "eat",
    "flied": "fly",
    "growed": "grow",
    "hided": "hide",
    "hited": "hit",
    "selled": "sell",
    "shooted": "shoot",
    "sleeped": "sleep",
    "sweared": "swear",
    "teached": "teach",
}

ENGLISH_IRREGULAR_PAST = {
    "am": "was",
    "are": "were",
    "be": "was",
    "begin": "began",
    "break": "broke",
    "bring": "brought",
    "buy": "bought",
    "can": "could",
    "choose": "chose",
    "come": "came",
    "cost": "cost",
    "cut": "cut",
    "do": "did",
    "drink": "drank",
    "drive": "drove",
    "eat": "ate",
    "feel": "felt",
    "find": "found",
    "fly": "flew",
    "get": "got",
    "give": "gave",
    "go": "went",
    "grow": "grew",
    "have": "had",
    "hear": "heard",
    "hide": "hid",
    "hit": "hit",
    "hurt": "hurt",
    "is": "was",
    "keep": "kept",
    "know": "knew",
    "leave": "left",
    "lose": "lost",
    "make": "made",
    "meet": "met",
    "pay": "paid",
    "put": "put",
    "read": "read",
    "run": "ran",
    "say": "said",
    "see": "saw",
    "sell": "sold",
    "send": "sent",
    "shoot": "shot",
    "show": "showed",
    "sleep": "slept",
    "speak": "spoke",
    "stand": "stood",
    "swear": "swore",
    "teach": "taught",
    "tell": "told",
    "think": "thought",
    "understand": "understood",
    "write": "wrote",
}

ENGLISH_PAST_VALUES = set(ENGLISH_IRREGULAR_PAST.values())


def normalize(text: str) -> str:
    return (text or "").strip()


def normalize_lower(text: str) -> str:
    return normalize(text).lower()


def is_verb_row(row: dict[str, str]) -> bool:
    pos = normalize_lower(row.get("pos", ""))
    return pos in {"v", "verb"}


def split_trailing_brackets(text: str) -> tuple[str, list[str]]:
    text = normalize(text)
    if not text:
        return "", []

    m = re.match(r"^(.*?)(?:\s*\(([^()]*)\)\s*)?$", text)
    if not m:
        return text, []

    core = normalize(m.group(1))
    notes_raw = normalize(m.group(2) or "")
    if not notes_raw:
        return core, []

    notes = [normalize(part) for part in notes_raw.split(";") if normalize(part)]
    return core, notes


def dedupe_preserve_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = normalize_lower(item)
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(normalize(item))
    return out


def build_tags(
    existing_tags: str,
    past_relation: str,
    past_tense: str,
    past_person: str,
    past_number: str,
) -> str:
    tags = [t for t in (existing_tags or "").split("|") if t]

    if past_relation == "past_tense_detected" and past_tense:
        tags.append("past")
        tags.append(past_tense)
        if past_person == "singular_ambiguous":
            tags.append("singular_ambiguous")
        else:
            if past_person:
                tags.append(past_person)
            if past_number:
                tags.append(past_number)
    elif past_relation == "past_candidate_only" and past_tense:
        tags.append("past")
        tags.append(past_tense)
        if past_person:
            tags.append(past_person)
        if past_number:
            tags.append(past_number)

    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            out.append(tag)
    return "|".join(out)


def join_core_and_notes(core: str, notes: list[str]) -> str:
    core = normalize(core)
    notes = dedupe_preserve_order(notes)
    if not notes:
        return core
    if not core:
        return f"({' ; '.join(notes)})".replace(" ; ", "; ")
    return f"{core} ({'; '.join(notes)})"


def build_result(tense: str, code: str, confidence: str, reason: str) -> dict[str, str]:
    person, number = PERSON_NUMBER_MAP[code]
    return {
        "past_relation": "past_tense_detected",
        "past_tense": tense,
        "past_person": person,
        "past_number": number,
        "past_context": past_context_label(tense),
        "past_confidence": confidence,
        "past_reason": reason,
        "past_code": code,
    }


def past_context_label(tense: str) -> str:
    if tense == "preterite":
        return "completed past"
    if tense == "imperfect":
        return "ongoing habitual/background past"
    return tense


def changed_last_vowel(stem: str, old: str, new: str) -> str | None:
    idx = stem.rfind(old)
    if idx == -1:
        return None
    return stem[:idx] + new + stem[idx + 1:]


def detect_manual_irregular(lemma: str, original_lemma: str) -> dict[str, str] | None:
    if original_lemma in {"ser", "ir"} and lemma in SER_IR_PRETERITE:
        return build_result("preterite", SER_IR_PRETERITE[lemma], "high", "manual_ser_ir_preterite")

    if original_lemma == "ser" and lemma in SER_IMPERFECT:
        return build_result("imperfect", SER_IMPERFECT[lemma], "high", "manual_ser_imperfect")

    if original_lemma == "ir" and lemma in IR_IMPERFECT:
        return build_result("imperfect", IR_IMPERFECT[lemma], "high", "manual_ir_imperfect")

    if original_lemma == "dar" and lemma in DAR_PRETERITE:
        return build_result("preterite", DAR_PRETERITE[lemma], "high", "manual_dar_preterite")

    if original_lemma == "ver" and lemma in VER_PRETERITE:
        return build_result("preterite", VER_PRETERITE[lemma], "high", "manual_ver_preterite")

    if original_lemma == "hacer" and lemma in HACER_PRETERITE:
        return build_result("preterite", HACER_PRETERITE[lemma], "high", "manual_hacer_preterite")

    if original_lemma in J_STEM_LEMMAS:
        stem = J_STEM_LEMMAS[original_lemma]
        forms = {
            f"{stem}e": "1sg",
            f"{stem}iste": "2sg",
            f"{stem}o": "3sg",
            f"{stem}imos": "1pl",
            f"{stem}isteis": "2pl",
            f"{stem}eron": "3pl",
        }
        if lemma in forms:
            return build_result("preterite", forms[lemma], "high", "manual_j_stem_preterite")

    if original_lemma.endswith("ducir"):
        stem = original_lemma[:-5] + "duj"
        forms = {
            f"{stem}e": "1sg",
            f"{stem}iste": "2sg",
            f"{stem}o": "3sg",
            f"{stem}imos": "1pl",
            f"{stem}isteis": "2pl",
            f"{stem}eron": "3pl",
        }
        if lemma in forms:
            return build_result("preterite", forms[lemma], "high", "manual_ducir_j_stem_preterite")

    if original_lemma in STRONG_PRETERITE_STEMS:
        stem = STRONG_PRETERITE_STEMS[original_lemma]
        for ending, code in STRONG_PRETERITE_ENDINGS.items():
            if lemma == f"{stem}{ending}":
                return build_result("preterite", code, "high", "manual_strong_preterite")

    return None


def detect_y_preterite(lemma: str, original_lemma: str) -> dict[str, str] | None:
    if original_lemma in J_STEM_LEMMAS or original_lemma.endswith("ducir"):
        return None

    y_family = (
        original_lemma.endswith("eer")
        or original_lemma.endswith("aer")
        or original_lemma.endswith("oír")
        or original_lemma.endswith("oir")
        or (original_lemma.endswith("uir") and not original_lemma.endswith("guir"))
    )

    if not y_family:
        return None

    stem = original_lemma[:-2]
    forms = {
        f"{stem}í": "1sg",
        f"{stem}íste": "2sg",
        f"{stem}yó": "3sg",
        f"{stem}ímos": "1pl",
        f"{stem}ísteis": "2pl",
        f"{stem}yeron": "3pl",
    }

    if lemma in forms:
        return build_result("preterite", forms[lemma], "high", "y_preterite_family")

    return None


def detect_ir_stem_change_preterite(lemma: str, original_lemma: str) -> dict[str, str] | None:
    if not original_lemma.endswith("ir"):
        return None

    stem = original_lemma[:-2]
    candidates: list[str] = []

    last_e_to_i = changed_last_vowel(stem, "e", "i")
    if last_e_to_i:
        candidates.append(last_e_to_i)

    last_o_to_u = changed_last_vowel(stem, "o", "u")
    if last_o_to_u:
        candidates.append(last_o_to_u)

    for changed in dedupe_preserve_order(candidates):
        if lemma == f"{changed}ió":
            return build_result("preterite", "3sg", "medium", "ir_stem_change_preterite_3sg")
        if lemma == f"{changed}ieron":
            return build_result("preterite", "3pl", "medium", "ir_stem_change_preterite_3pl")

    return None


def detect_regular_imperfect(lemma: str, original_lemma: str) -> dict[str, str] | None:
    if original_lemma.endswith("ar"):
        stem = original_lemma[:-2]
        for ending, code in REGULAR_IMPERFECT_AR.items():
            if lemma == f"{stem}{ending}":
                return build_result("imperfect", code, "high", "regular_ar_imperfect")

    if original_lemma.endswith(("er", "ir")):
        stem = original_lemma[:-2]
        for ending, code in REGULAR_IMPERFECT_ER_IR.items():
            if lemma == f"{stem}{ending}":
                return build_result("imperfect", code, "high", "regular_er_ir_imperfect")

    return None


def detect_regular_preterite(
    lemma: str,
    original_lemma: str,
    allow_ambiguous_first_plural: bool,
) -> dict[str, str] | None:
    if original_lemma.endswith("ar"):
        stem = original_lemma[:-2]

        if lemma == f"{stem}é":
            return build_result("preterite", "1sg", "high", "regular_ar_preterite_1sg")
        if lemma == f"{stem}aste":
            return build_result("preterite", "2sg", "high", "regular_ar_preterite_2sg")
        if lemma == f"{stem}ó":
            return build_result("preterite", "3sg", "high", "regular_ar_preterite_3sg")
        if lemma == f"{stem}asteis":
            return build_result("preterite", "2pl", "high", "regular_ar_preterite_2pl")
        if lemma == f"{stem}aron":
            return build_result("preterite", "3pl", "high", "regular_ar_preterite_3pl")

        if lemma == f"{stem}amos":
            if allow_ambiguous_first_plural:
                return build_result("preterite", "1pl", "medium", "regular_ar_preterite_1pl")
            return {
                "past_relation": "past_candidate_only",
                "past_tense": "preterite",
                "past_person": "first",
                "past_number": "plural",
                "past_context": past_context_label("preterite"),
                "past_confidence": "low",
                "past_reason": "regular_ar_1pl_ambiguous_with_present",
                "past_code": "1pl",
            }

        if original_lemma.endswith("car") and lemma == f"{original_lemma[:-3]}qué":
            return build_result("preterite", "1sg", "high", "orthographic_car_preterite_1sg")
        if original_lemma.endswith("gar") and lemma == f"{original_lemma[:-3]}gué":
            return build_result("preterite", "1sg", "high", "orthographic_gar_preterite_1sg")
        if original_lemma.endswith("zar") and lemma == f"{original_lemma[:-1]}cé":
            return build_result("preterite", "1sg", "high", "orthographic_zar_preterite_1sg")
        if original_lemma.endswith("guar") and lemma == f"{original_lemma[:-4]}güé":
            return build_result("preterite", "1sg", "high", "orthographic_guar_preterite_1sg")

    if original_lemma.endswith(("er", "ir")):
        stem = original_lemma[:-2]

        if lemma == f"{stem}í":
            return build_result("preterite", "1sg", "high", "regular_er_ir_preterite_1sg")
        if lemma == f"{stem}iste":
            return build_result("preterite", "2sg", "high", "regular_er_ir_preterite_2sg")
        if lemma == f"{stem}ió":
            return build_result("preterite", "3sg", "high", "regular_er_ir_preterite_3sg")
        if lemma == f"{stem}isteis":
            return build_result("preterite", "2pl", "high", "regular_er_ir_preterite_2pl")
        if lemma == f"{stem}ieron":
            return build_result("preterite", "3pl", "high", "regular_er_ir_preterite_3pl")

        if lemma == f"{stem}imos":
            if original_lemma.endswith("ir") and not allow_ambiguous_first_plural:
                return {
                    "past_relation": "past_candidate_only",
                    "past_tense": "preterite",
                    "past_person": "first",
                    "past_number": "plural",
                    "past_context": past_context_label("preterite"),
                    "past_confidence": "low",
                    "past_reason": "regular_ir_1pl_ambiguous_with_present",
                    "past_code": "1pl",
                }
            return build_result("preterite", "1pl", "high", "regular_er_ir_preterite_1pl")

    return None


def detect_past(
    lemma: str,
    original_lemma: str,
    allow_ambiguous_first_plural: bool,
) -> dict[str, str] | None:
    for detector in (
        detect_manual_irregular,
        detect_y_preterite,
        detect_ir_stem_change_preterite,
        detect_regular_imperfect,
    ):
        hit = detector(lemma, original_lemma)
        if hit:
            return hit

    hit = detect_regular_preterite(lemma, original_lemma, allow_ambiguous_first_plural)
    if hit:
        return hit

    return None


def extract_subject_and_predicate(core: str) -> tuple[str | None, str]:
    core = normalize(core)
    if not core:
        return None, ""

    m = SUBJECT_RE.match(core)
    if m:
        subject = m.group(1)
        predicate = normalize(m.group(2))
        return subject, predicate

    return None, core


def split_semicolon_options(text: str) -> list[str]:
    return dedupe_preserve_order([part.strip() for part in (text or "").split(";") if part.strip()])


def strip_leading_subject(text: str) -> str:
    _, predicate = extract_subject_and_predicate(text)
    return predicate


def has_blocking_mood_context(row: dict[str, str], old_translation: str) -> bool:
    tags = {normalize_lower(part) for part in (row.get("tags", "") or "").split("|") if normalize(part)}
    if tags & BLOCKING_MOOD_TAGS:
        return True
    return "present subjunctive" in normalize_lower(old_translation)


def normalize_english_base_word(word: str) -> str:
    lower = normalize_lower(word)
    if lower in BAD_PAST_TO_BASE:
        return BAD_PAST_TO_BASE[lower]
    irregular_present = {
        "am": "be",
        "are": "be",
        "does": "do",
        "goes": "go",
        "has": "have",
        "is": "be",
    }
    if lower in irregular_present:
        return irregular_present[lower]
    if lower.endswith("ies") and len(lower) > 3:
        return lower[:-3] + "y"
    if lower.endswith("es") and len(lower) > 3:
        if lower.endswith(("ches", "shes", "sses", "xes", "zes", "oes")):
            return lower[:-2]
        if lower[-3] == "v":
            return lower[:-1]
    if lower.endswith("s") and len(lower) > 2 and not lower.endswith("ss"):
        return lower[:-1]
    return lower


def past_word(word: str) -> str:
    base = normalize_english_base_word(word)
    if base in ENGLISH_IRREGULAR_PAST:
        return ENGLISH_IRREGULAR_PAST[base]
    if base.endswith("e"):
        return f"{base}d"
    if len(base) > 1 and base.endswith("y") and base[-2] not in "aeiou":
        return f"{base[:-1]}ied"
    return f"{base}ed"


def is_trusted_past_phrase(phrase: str) -> bool:
    phrase = normalize(phrase)
    if not phrase:
        return False
    first = normalize_lower(phrase.split()[0])
    if first in BAD_PAST_TO_BASE:
        return False
    if first in ENGLISH_PAST_VALUES:
        return True
    return first.endswith("ed")


def inflect_phrase_to_past(phrase: str) -> str | None:
    phrase = normalize(phrase)
    if not phrase or "/" in phrase or phrase.startswith("to "):
        return None
    words = phrase.split()
    if not words:
        return None
    first = words[0]
    if not first.isalpha():
        return None
    words[0] = past_word(first)
    return " ".join(words)


def build_subject_translation_from_predicates(predicates: list[str], code: str) -> tuple[str, list[str]]:
    subject_map = {
        "1sg": ["I"],
        "2sg": ["you"],
        "3sg": ["he", "she", "it"],
        "1pl": ["we"],
        "2pl": ["you"],
        "3pl": ["they"],
        "13sg": ["I", "he", "she", "it"],
    }
    subjects = subject_map.get(code)
    if not subjects:
        return "; ".join(dedupe_preserve_order(predicates)), []

    phrases: list[str] = []
    for predicate in dedupe_preserve_order(predicates):
        for subject in subjects:
            phrases.append(f"{subject} {predicate}")

    notes = ["plural"] if code == "2pl" else []
    return "; ".join(dedupe_preserve_order(phrases)), notes


def derive_past_predicates(core: str, original_lemma: str) -> tuple[list[str] | None, str]:
    manual = MANUAL_PAST_PREDICATES.get(original_lemma)
    if manual:
        return manual, "manual_english_past_override"

    predicates = dedupe_preserve_order([strip_leading_subject(part) for part in split_semicolon_options(core)])
    if not predicates:
        return None, "no_predicates"

    if all(is_trusted_past_phrase(predicate) for predicate in predicates):
        return predicates, "trusted_existing_past_gloss"

    inflected: list[str] = []
    for predicate in predicates:
        past_predicate = inflect_phrase_to_past(predicate)
        if not past_predicate:
            return None, "unsafe_translation_kept"
        inflected.append(past_predicate)

    return dedupe_preserve_order(inflected), "inflected_english_past_gloss"


def build_be_translation(code: str) -> tuple[str, list[str]]:
    if code == "1sg":
        return "I was", []
    if code == "2sg":
        return "you were", []
    if code == "3sg":
        return "he was; she was; it was", []
    if code == "1pl":
        return "we were", []
    if code == "2pl":
        return "you were", ["plural"]
    if code == "3pl":
        return "they were", []
    if code == "13sg":
        return "I was; he was; she was; it was", []
    return "", []


def rewrite_translation_core(
    old_translation: str,
    original_lemma: str,
    past_tense: str,
    past_code: str,
) -> tuple[str, list[str], str, bool]:
    core, existing_notes = split_trailing_brackets(old_translation)
    lower_core = normalize_lower(core)

    if not core:
        return core, existing_notes, "empty_translation", False

    if lower_core.startswith("there "):
        return core, existing_notes, "existential_translation_kept", True

    if original_lemma in {"ser", "estar"}:
        new_core, extra_notes = build_be_translation(past_code)
        return new_core, existing_notes + extra_notes, "rewritten_manual_be", True

    predicates, reason = derive_past_predicates(core, original_lemma)
    if not predicates:
        return core, existing_notes, reason, False

    new_core, extra_notes = build_subject_translation_from_predicates(predicates, past_code)
    return new_core, existing_notes + extra_notes, reason, True


def process_row(row: dict[str, str], allow_ambiguous_first_plural: bool) -> dict[str, str]:
    out = dict(row)

    old_translation = normalize(row.get("translation", ""))
    extra = {
        "old_translation": old_translation,
        "translation_changed": "no",
        "review_reason": "",
        "past_relation": "",
        "past_tense": "",
        "past_person": "",
        "past_number": "",
        "past_context": "",
        "past_confidence": "",
        "past_reason": "",
        "past_code": "",
    }

    if not is_verb_row(row):
        extra["review_reason"] = "not_verb"
        out["tags"] = build_tags(out.get("tags", ""), "", "", "", "")
        out.update({k: v for k, v in extra.items() if k != "past_code"})
        return out

    lemma = normalize_lower(row.get("lemma", ""))
    original_lemma = normalize_lower(row.get("original_lemma", ""))

    if not lemma or not original_lemma:
        extra["review_reason"] = "missing_lemma_fields"
        out["tags"] = build_tags(out.get("tags", ""), "", "", "", "")
        out.update({k: v for k, v in extra.items() if k != "past_code"})
        return out

    if has_blocking_mood_context(row, old_translation):
        extra["review_reason"] = "blocked_by_existing_mood_tag"
        out["tags"] = build_tags(out.get("tags", ""), "", "", "", "")
        out.update({k: v for k, v in extra.items() if k != "past_code"})
        return out

    detected = detect_past(lemma, original_lemma, allow_ambiguous_first_plural)
    if not detected:
        extra["review_reason"] = "no_past_match"
        out["tags"] = build_tags(out.get("tags", ""), "", "", "", "")
        out.update({k: v for k, v in extra.items() if k != "past_code"})
        return out

    extra.update(detected)

    if detected["past_relation"] != "past_tense_detected":
        extra["review_reason"] = detected["past_reason"]
        out["tags"] = build_tags(
            out.get("tags", ""),
            detected["past_relation"],
            detected["past_tense"],
            detected["past_person"],
            detected["past_number"],
        )
        out.update({k: v for k, v in extra.items() if k != "past_code"})
        return out

    rewritten_core, rewritten_notes, rewrite_reason, safe_to_rewrite = rewrite_translation_core(
        old_translation=old_translation,
        original_lemma=original_lemma,
        past_tense=detected["past_tense"],
        past_code=detected["past_code"],
    )

    out["tags"] = build_tags(
        out.get("tags", ""),
        detected["past_relation"],
        detected["past_tense"],
        detected["past_person"],
        detected["past_number"],
    )

    if safe_to_rewrite:
        rewritten_notes = dedupe_preserve_order(rewritten_notes + [detected["past_context"]])
        new_translation = join_core_and_notes(rewritten_core, rewritten_notes)
        out["translation"] = new_translation
        extra["translation_changed"] = "yes" if new_translation != old_translation else "no"
        extra["review_reason"] = rewrite_reason if new_translation != old_translation else "already_correct_or_already_annotated"
    else:
        out["translation"] = old_translation
        extra["translation_changed"] = "no"
        extra["review_reason"] = rewrite_reason

    out.update({k: v for k, v in extra.items() if k != "past_code"})
    return out


def build_review_rows(
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    review_rows: list[dict[str, str]] = []

    for row in rows:
        review_reason = normalize(row.get("review_reason", ""))
        if not review_reason or review_reason in {"not_verb", "missing_lemma_fields", "no_past_match"}:
            continue

        review_rows.append({
            "rank": row.get("rank", ""),
            "lemma": row.get("lemma", ""),
            "original_lemma": row.get("original_lemma", ""),
            "old_translation": row.get("old_translation", ""),
            "new_translation": row.get("translation", ""),
            "translation_changed": row.get("translation_changed", ""),
            "review_reason": review_reason,
            "past_relation": row.get("past_relation", ""),
            "past_tense": row.get("past_tense", ""),
            "past_person": row.get("past_person", ""),
            "past_number": row.get("past_number", ""),
            "past_context": row.get("past_context", ""),
            "past_confidence": row.get("past_confidence", ""),
            "past_reason": row.get("past_reason", ""),
            "tags": row.get("tags", ""),
        })

    return review_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-ambiguous-first-plural-preterite", action="store_true")
    args = parser.parse_args()
    review_stem = args.output.stem
    if not review_stem.endswith("-past"):
        review_stem = f"{review_stem}-past"
    review_log_path = args.output.with_name(f"{review_stem}-review.csv")

    with args.input.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Input CSV has no header row")

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        fieldnames = list(OUTPUT_COLUMNS)

        rows = [
            process_row(row, args.allow_ambiguous_first_plural_preterite)
            for row in reader
        ]

    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    review_rows = build_review_rows(rows)
    with review_log_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rank",
                "lemma",
                "original_lemma",
                "old_translation",
                "new_translation",
                "translation_changed",
                "review_reason",
                "past_relation",
                "past_tense",
                "past_person",
                "past_number",
                "past_context",
                "past_confidence",
                "past_reason",
                "tags",
            ],
        )
        writer.writeheader()
        writer.writerows(review_rows)

    print(f"Saved {len(rows)} rows to {args.output}.")
    print(f"Saved {len(review_rows)} review rows to {review_log_path}.")


if __name__ == "__main__":
    main()
