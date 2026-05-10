import argparse
import csv
import re
from collections import Counter, defaultdict


ALLOWED_POS_FOR_BRACKETS = {"art", "determiner", "pron", "v", "prep", "contraction"}

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

POS_MAP = {
    "article": "art",
    "art": "art",
    "determiner": "determiner",
    "det": "determiner",
    "pronoun": "pron",
    "pron": "pron",
    "preposition": "prep",
    "prep": "prep",
    "conjunction": "conj",
    "conj": "conj",
    "verb": "v",
    "v": "v",
    "noun": "n",
    "n": "n",
    "adjective": "adj",
    "adj": "adj",
    "adverb": "adv",
    "adv": "adv",
    "interjection": "interj",
    "interj": "interj",
    "contraction": "contraction",
}

ACCENT_DISTINCTION_OVERRIDES = {
    "el": {"translation": "the", "english_definition": "masculine singular definite article", "pos": "art"},
    "él": {"translation": "he; him", "english_definition": "third person singular masculine pronoun", "pos": "pron"},
    "tu": {"translation": "your", "english_definition": "informal singular possessive determiner", "pos": "determiner"},
    "tú": {"translation": "you", "english_definition": "informal singular subject pronoun", "pos": "pron"},
    "mi": {"translation": "my", "english_definition": "singular possessive determiner", "pos": "determiner"},
    "mí": {"translation": "me", "english_definition": "first person singular prepositional pronoun", "pos": "pron"},
    "si": {"translation": "if; whether", "english_definition": "conjunction used for conditions or indirect yes no questions", "pos": "conj"},
    "sí": {"translation": "yes; oneself", "english_definition": "adverb of affirmation or reflexive prepositional pronoun", "pos": "pron"},
    "mas": {"translation": "but", "english_definition": "literary or formal variant of pero", "pos": "conj"},
    "más": {"translation": "more; most", "english_definition": "adverb of quantity or comparison", "pos": "adv"},
    "que": {"translation": "that; which", "english_definition": "common conjunction or relative pronoun"},
    "qué": {"translation": "what; which", "english_definition": "interrogative or exclamative pronoun", "pos": "pron"},
    "quien": {"translation": "who", "english_definition": "relative pronoun", "pos": "pron"},
    "quién": {"translation": "who", "english_definition": "interrogative pronoun", "pos": "pron"},
    "como": {"translation": "as; like", "english_definition": "conjunction or adverb of comparison"},
    "cómo": {"translation": "how", "english_definition": "interrogative or exclamative adverb", "pos": "adv"},
    "cuando": {"translation": "when", "english_definition": "conjunction or relative adverb"},
    "cuándo": {"translation": "when", "english_definition": "interrogative or exclamative adverb", "pos": "adv"},
    "donde": {"translation": "where", "english_definition": "relative adverb"},
    "dónde": {"translation": "where", "english_definition": "interrogative or exclamative adverb", "pos": "adv"},
    "cual": {"translation": "which", "english_definition": "relative pronoun", "pos": "pron"},
    "cuál": {"translation": "which; what", "english_definition": "interrogative pronoun", "pos": "pron"},
}

MANUAL_OVERRIDES = {
    "la": {"translation": "the", "english_definition": "feminine singular definite article", "pos": "art"},
    "los": {"translation": "the", "english_definition": "masculine plural definite article", "pos": "art"},
    "las": {"translation": "the", "english_definition": "feminine plural definite article", "pos": "art"},
    "lo": {"translation": "it; the", "english_definition": "neuter pronoun or neuter article depending on context", "pos": "pron"},
    "un": {"translation": "a; an", "english_definition": "masculine singular indefinite article", "pos": "art"},
    "una": {"translation": "a; an", "english_definition": "feminine singular indefinite article", "pos": "art"},
    "unos": {"translation": "some", "english_definition": "masculine plural indefinite determiner", "pos": "determiner"},
    "unas": {"translation": "some", "english_definition": "feminine plural indefinite determiner", "pos": "determiner"},
    "al": {"translation": "to the", "english_definition": "contraction of a plus el", "pos": "contraction"},
    "del": {"translation": "of the; from the", "english_definition": "contraction of de plus el", "pos": "contraction"},
    "por": {
        "translation": "by; through; because of; for",
        "english_definition": "preposition used for cause means movement through exchange duration or agent",
        "pos": "prep",
    },
    "para": {
        "translation": "for; to; in order to",
        "english_definition": "preposition used for purpose destination recipient deadline or goal",
        "pos": "prep",
    },
    "me": {"translation": "me", "english_definition": "first person singular object pronoun", "pos": "pron"},
    "te": {"translation": "you", "english_definition": "second person singular object pronoun", "pos": "pron"},
    "nos": {"translation": "us", "english_definition": "first person plural object pronoun", "pos": "pron"},
    "os": {"translation": "you", "english_definition": "second person plural object pronoun used mainly in Spain", "pos": "pron"},
    "ti": {"translation": "you", "english_definition": "second person singular prepositional pronoun", "pos": "pron"},
    "usted": {"translation": "you", "english_definition": "formal singular pronoun", "pos": "pron"},
    "ustedes": {"translation": "you", "english_definition": "formal or neutral plural pronoun", "pos": "pron"},
    "esto": {"translation": "this", "english_definition": "neuter demonstrative pronoun", "pos": "pron"},
    "eso": {"translation": "that", "english_definition": "neuter demonstrative pronoun", "pos": "pron"},
    "ello": {"translation": "it", "english_definition": "neuter third person pronoun", "pos": "pron"},
    "mi": {"translation": "my", "english_definition": "singular possessive determiner", "pos": "determiner"},
    "mis": {"translation": "my", "english_definition": "plural possessive determiner", "pos": "determiner"},
    "tu": {"translation": "your", "english_definition": "informal singular possessive determiner", "pos": "determiner"},
    "tus": {"translation": "your", "english_definition": "informal plural possessive determiner", "pos": "determiner"},
    "su": {"translation": "his; her; its; their; your formal", "english_definition": "possessive determiner", "pos": "determiner"},
    "sus": {"translation": "his; her; its; their; your formal", "english_definition": "plural possessive determiner", "pos": "determiner"},
    "este": {"translation": "this", "english_definition": "masculine singular demonstrative determiner", "pos": "determiner"},
    "esta": {"translation": "this", "english_definition": "feminine singular demonstrative determiner", "pos": "determiner"},
    "estos": {"translation": "these", "english_definition": "masculine plural demonstrative determiner", "pos": "determiner"},
    "estas": {"translation": "these", "english_definition": "feminine plural demonstrative determiner", "pos": "determiner"},
    "ese": {"translation": "that", "english_definition": "masculine singular demonstrative determiner", "pos": "determiner"},
    "esa": {"translation": "that", "english_definition": "feminine singular demonstrative determiner", "pos": "determiner"},
    "esos": {"translation": "those", "english_definition": "masculine plural demonstrative determiner", "pos": "determiner"},
    "esas": {"translation": "those", "english_definition": "feminine plural demonstrative determiner", "pos": "determiner"},
    "algún": {"translation": "some; any", "english_definition": "masculine singular indefinite determiner", "pos": "determiner"},
    "alguna": {"translation": "some; any", "english_definition": "feminine singular indefinite determiner", "pos": "determiner"},
    "algunos": {"translation": "some", "english_definition": "masculine plural indefinite determiner", "pos": "determiner"},
    "algunas": {"translation": "some", "english_definition": "feminine plural indefinite determiner", "pos": "determiner"},
    "ningún": {"translation": "no; not any", "english_definition": "masculine singular negative determiner", "pos": "determiner"},
    "ninguna": {"translation": "no; not any", "english_definition": "feminine singular negative determiner", "pos": "determiner"},
    "otro": {"translation": "other; another", "english_definition": "masculine singular determiner or adjective", "pos": "determiner"},
    "otra": {"translation": "other; another", "english_definition": "feminine singular determiner or adjective", "pos": "determiner"},
    "otros": {"translation": "others; other", "english_definition": "masculine plural determiner or pronoun", "pos": "determiner"},
    "otras": {"translation": "others; other", "english_definition": "feminine plural determiner or pronoun", "pos": "determiner"},
    "todo": {"translation": "all; every; everything", "english_definition": "all or every determiner or pronoun", "pos": "determiner"},
    "toda": {"translation": "all; every", "english_definition": "feminine singular determiner meaning all or every", "pos": "determiner"},
    "todos": {"translation": "all; everyone", "english_definition": "masculine plural determiner or pronoun", "pos": "determiner"},
    "todas": {"translation": "all; everyone", "english_definition": "feminine plural determiner or pronoun", "pos": "determiner"},
    "mucho": {"translation": "much; a lot of", "english_definition": "quantity determiner or adverb", "pos": "determiner"},
    "mucha": {"translation": "much; a lot of", "english_definition": "feminine singular quantity determiner", "pos": "determiner"},
    "muchos": {"translation": "many", "english_definition": "masculine plural quantity determiner", "pos": "determiner"},
    "muchas": {"translation": "many", "english_definition": "feminine plural quantity determiner", "pos": "determiner"},
}

VERB_OVERRIDES = {
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

USEFUL_DONOR_LEMMAS = set(MANUAL_OVERRIDES) | set(VERB_OVERRIDES) | {
    "él", "qué", "quién", "quien", "cómo", "como", "cuándo", "cuando",
    "dónde", "donde", "cuál", "cual", "mí", "sí", "si", "más", "mas"
}


def normalize_pos(pos):
    return POS_MAP.get((pos or "").strip().lower(), (pos or "").strip().lower())


def extract_brackets(text):
    if not text:
        return [], ""
    matches = re.findall(r"\(([^()]*)\)", text)
    cleaned = re.sub(r"\s*\([^()]*\)", "", text).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return [m.strip().lower() for m in matches], cleaned


def clean_translation_text(text):
    _, cleaned = extract_brackets(text)
    parts = [p.strip() for p in cleaned.split(";")]
    out = []
    for part in parts:
        if part and part not in out:
            out.append(part)
    return "; ".join(out)


def load_parentheses_donor(path):
    by_rank = {}
    by_lemma = defaultdict(list)
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"row_number", "lemma", "value"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("parentheses CSV must have columns: row_number, lemma, value")
        for row in reader:
            lemma = (row.get("lemma") or "").strip()
            value = (row.get("value") or "").strip()
            row_number = (row.get("row_number") or "").strip()
            if not lemma or not value:
                continue
            if row_number.isdigit():
                rank = int(row_number) - 1
                if rank > 0:
                    by_rank[rank] = value
            by_lemma[lemma].append(value)
    unique_by_lemma = {}
    for lemma, values in by_lemma.items():
        counts = Counter(values)
        best_value, _ = counts.most_common(1)[0]
        unique_by_lemma[lemma] = best_value
    return by_rank, unique_by_lemma


def choose_donor_value(row, by_rank, by_lemma):
    lemma = (row.get("lemma") or "").strip()
    rank_raw = (row.get("rank") or "").strip()
    if rank_raw.isdigit():
        rank = int(rank_raw)
        if rank in by_rank:
            return by_rank[rank]
    return by_lemma.get(lemma, "")


def allowed_features_from_donor(lemma, pos, donor_value):
    pos = normalize_pos(pos)
    if pos not in ALLOWED_POS_FOR_BRACKETS:
        return {}
    brackets, _ = extract_brackets(donor_value)
    features = {}
    for b in brackets:
        if b in BRACKET_NORMALIZATION:
            features.update(BRACKET_NORMALIZATION[b])
    return features


def article_definition_from_features(features, definite):
    gender = features.get("gender")
    number = features.get("number", "sg")
    gender_word = {"masc": "masculine", "fem": "feminine", "neuter": "neuter"}.get(gender, "")
    number_word = {"sg": "singular", "pl": "plural"}.get(number, "")
    kind_word = "definite" if definite else "indefinite"
    pieces = [p for p in [gender_word, number_word, kind_word, "article"] if p]
    return " ".join(pieces).strip()


def generic_definition(lemma, pos, features):
    pos = normalize_pos(pos)
    if pos == "art":
        return article_definition_from_features(features, lemma in {"el", "la", "los", "las", "lo"})
    if pos == "determiner":
        register = features.get("register")
        gender = features.get("gender")
        number = features.get("number")
        parts = []
        if register == "formal":
            parts.append("formal")
        if gender == "masc":
            parts.append("masculine")
        elif gender == "fem":
            parts.append("feminine")
        elif gender == "neuter":
            parts.append("neuter")
        if number == "sg":
            parts.append("singular")
        elif number == "pl":
            parts.append("plural")
        parts.append("determiner")
        return " ".join(parts).strip()
    if pos == "pron":
        if features.get("pronoun_case") == "prepositional":
            return "prepositional pronoun"
        if features.get("register") == "formal" and features.get("number") == "pl":
            return "formal plural pronoun"
        if features.get("register") == "formal":
            return "formal pronoun"
        if features.get("gender") == "neuter":
            return "neuter pronoun"
        return "pronoun"
    if pos == "prep":
        return "preposition"
    if pos == "contraction":
        return "contraction"
    if pos == "v":
        hint = features.get("verb_hint")
        if hint:
            if features.get("mood") == "subjunctive":
                return f"subjunctive form of {hint}"
            return f"verb form of {hint}"
        return "verb"
    if pos == "conj":
        return "conjunction"
    if pos == "adv":
        return "adverb"
    if pos == "adj":
        return "adjective"
    if pos == "n":
        return "noun"
    if pos == "interj":
        return "interjection"
    return ""


def apply_override(row, override, rule_name):
    row["translation"] = override["translation"]
    row["english_definition"] = override["english_definition"]
    if override.get("pos"):
        row["pos"] = override["pos"]
    row["rule_applied"] = rule_name
    return row


def rewrite_row(row, by_rank, by_lemma):
    lemma = (row.get("lemma") or "").strip()
    pos = normalize_pos(row.get("pos"))
    row["pos"] = pos

    if lemma in MANUAL_OVERRIDES:
        return apply_override(row, MANUAL_OVERRIDES[lemma], "manual_override")

    if lemma in ACCENT_DISTINCTION_OVERRIDES:
        return apply_override(row, ACCENT_DISTINCTION_OVERRIDES[lemma], "accent_override")

    if lemma in VERB_OVERRIDES:
        translation, english_definition = VERB_OVERRIDES[lemma]
        row["translation"] = translation
        row["english_definition"] = english_definition
        row["pos"] = "v"
        row["rule_applied"] = "verb_override"
        return row

    donor_value = choose_donor_value(row, by_rank, by_lemma)
    donor_clean = clean_translation_text(donor_value)
    main_clean = clean_translation_text(row.get("translation", ""))

    if donor_value and lemma in USEFUL_DONOR_LEMMAS:
        row["translation"] = donor_clean or main_clean
        features = allowed_features_from_donor(lemma, pos, donor_value)
        row["english_definition"] = generic_definition(lemma, pos, features)
        row["rule_applied"] = "donor_useful_lemma"
        return row

    features = allowed_features_from_donor(lemma, pos, donor_value)
    if features:
        row["translation"] = donor_clean or main_clean
        row["english_definition"] = generic_definition(lemma, pos, features)
        row["rule_applied"] = "donor_features"
        return row

    row["translation"] = main_clean
    if not row.get("english_definition"):
        row["english_definition"] = generic_definition(lemma, pos, {})
    row["rule_applied"] = "clean_only"
    return row


def process_csv(main_csv, donor_csv, output_csv):
    by_rank, by_lemma = load_parentheses_donor(donor_csv)

    with open(main_csv, newline="", encoding="utf-8-sig") as f_in:
        reader = csv.DictReader(f_in)
        fieldnames = list(reader.fieldnames or [])
        if "english_definition" not in fieldnames:
            fieldnames.append("english_definition")
        if "rule_applied" not in fieldnames:
            fieldnames.append("rule_applied")
        rows = list(reader)

    with open(output_csv, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(rewrite_row(row, by_rank, by_lemma))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-csv", required=True)
    parser.add_argument("--parentheses-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()
    process_csv(args.main_csv, args.parentheses_csv, args.output_csv)


if __name__ == "__main__":
    main()