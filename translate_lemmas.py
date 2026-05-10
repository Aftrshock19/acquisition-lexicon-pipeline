#!/usr/bin/env python3
import argparse
import csv
import os
import re
import shutil
import subprocess
import unicodedata
import warnings
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import DefaultDict, Dict, List, Optional, Sequence, Tuple

OVERRIDES = {
    "el": "the (masc.)",
    "la": "the (fem.)",
    "los": "the (pl., masc.)",
    "las": "the (pl., fem.)",
    "un": "a/an (masc.)",
    "una": "a/an (fem.)",
    "unos": "some (masc.)",
    "unas": "some (fem.)",
    "y": "and",
    "e": "and",
    "o": "or",
    "u": "or",
    "pero": "but",
    "aunque": "although",
    "si": "if",
    "sí": "yes",
    "no": "no",
    "muy": "very",
    "más": "more",
    "menos": "less",
    "ya": "already",
    "aún": "still/yet",
    "también": "also",
    "solo": "only",
    "sólo": "only",
    "a": "to (prep.)",
    "de": "of/from",
    "del": "of the/from the",
    "al": "to the",
    "en": "in/on/at",
    "con": "with",
    "sin": "without",
    "sobre": "about/on",
    "entre": "between/among",
    "para": "for (purpose)",
    "por": "by/for (cause/means)",
    "como": "like/as",
    "cuando": "when",
    "donde": "where",
    "qué": "what",
    "que": "that/which",
    "quien": "who",
    "cuál": "which",
    "cual": "which",
    "porque": "because",
    "porqué": "reason/motive",
    "desde": "from/since",
    "hasta": "until/up to",
    "ser": "to be (identity/essence)",
    "estar": "to be (state/location)",
    "haber": "to have (aux.)/there is",
    "tener": "to have/possess",
    "hacer": "to do/make",
    "decir": "to say/tell",
    "ir": "to go",
    "ver": "to see",
    "dar": "to give",
    "saber": "to know (a fact)",
    "conocer": "to know (be familiar with)",
    "poder": "to be able to/can",
    "querer": "to want",
    "lo": "it/him (direct object)",
    "se": "oneself/himself/herself/itself; reflexive marker",
    "me": "me",
    "te": "you",
    "su": "his/her/your/their",
    "mi": "my",
    "yo": "I",
    "le": "him/her/to him/to her",
    "aquí": "here",
    "tu": "your",
    "todo": "everything/all",
    "esto": "this",
    "esta": "this",
    "ahora": "now",
    "así": "like this/so",
    "hay": "there is/there are",
    "este": "this",
    "algo": "something",
    "él": "he/him",
    "bueno": "good/well",
    "nos": "us",
    "nosotros": "we/us",
    "vosotros": "you all (informal, Spain)",
    "vosotras": "you all (informal, fem., Spain)",
    "usted": "you (formal)",
    "ustedes": "you all (formal)",
    "conmigo": "with me",
    "contigo": "with you",
    "sus": "his/her/your/their",
    "nada": "nothing",
    "tú": "you",
    "vez": "time/occasion",
    "ella": "she/her",
    "todos": "everyone/all",
    "gracias": "thanks",
    "dos": "two",
    "tan": "so",
    "entonces": "then/so",
    "tiempo": "time",
    "bien": "well",
    "eso": "that",
}

EDGE_PUNCT = " \t\r\n\"'“”‘’`´¡!¿?.,;:()[]{}<>…—–-_/\\|@#$%^&*+=~"
MULTI_TRANSLATIONS = True

DEFAULT_APERTIUM_ANALYZER_CMD = [
    "apertium",
    "-d",
    os.path.expanduser("~/apertium-spa"),
    "spa-morph",
]


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalize_token(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.strip()
    s = s.strip(EDGE_PUNCT)
    s = s.lower()
    return normalize_spaces(s)


def normalize_gloss(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.strip()
    return normalize_spaces(s).lower()


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def safe_int(x) -> int:
    try:
        return int(str(x).strip())
    except Exception:
        return 0


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def dix_node_text(node: ET.Element) -> str:
    parts: List[str] = []

    if node.text:
        parts.append(node.text)

    for child in node:
        tag = local_tag(child.tag)

        if tag == "b":
            parts.append(" ")
        elif tag in {"s", "a", "j", "par", "re"}:
            pass
        else:
            parts.append(dix_node_text(child))

        if child.tail:
            parts.append(child.tail)

    return normalize_spaces("".join(parts))


def extract_first_lemma_from_token(token_analysis: str, fallback: str) -> str:
    if "<sent>" in token_analysis:
        return normalize_token(fallback)

    match = re.search(r"\^[^/]+/([^<$/]+)", token_analysis)
    if match:
        return normalize_token(match.group(1))

    return normalize_token(fallback)


def lemmatize_surface_forms(
    surface_forms: Sequence[str],
    analyzer_cmd: Optional[Sequence[str]] = None,
) -> Dict[str, str]:
    cleaned = [normalize_token(x) for x in surface_forms if normalize_token(x)]
    if not cleaned:
        return {}

    cmd = list(analyzer_cmd or DEFAULT_APERTIUM_ANALYZER_CMD)

    if shutil.which(cmd[0]) is None:
        raise FileNotFoundError(f"Apertium analyzer command not found: {cmd[0]}")

    text = " ".join(cleaned) + "\n"

    proc = subprocess.run(
        cmd,
        input=text.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            "spa-morph failed:\n" + proc.stderr.decode("utf-8", errors="replace")
        )

    output = proc.stdout.decode("utf-8", errors="replace")
    raw_chunks = re.findall(r"\^.*?\$", output)
    chunks = [chunk for chunk in raw_chunks if "<sent>" not in chunk]

    if len(chunks) < len(cleaned):
        raise RuntimeError(
            f"spa-morph token alignment mismatch: got {len(chunks)} analyses for {len(cleaned)} inputs"
        )

    mapping = {}
    for surf, chunk in zip(cleaned, chunks):
        mapping[surf] = extract_first_lemma_from_token(chunk, surf)

    for surf in cleaned:
        mapping.setdefault(surf, surf)

    return mapping


def infer_column(fieldnames: Sequence[str]) -> str:
    preferred = ["lemma", "spanish", "word", "token", "surface"]
    lowered = {name.lower(): name for name in fieldnames}

    for cand in preferred:
        if cand in lowered:
            return lowered[cand]

    raise ValueError(
        f"Could not find a source column. Available columns: {list(fieldnames)}"
    )


def infer_reverse_from_filename(dict_path: str) -> bool:
    name = os.path.basename(dict_path).lower()

    if "eng-spa" in name or "en-es" in name:
        return True

    if "spa-eng" in name or "es-en" in name:
        return False

    return False


def allowed_entry(direction_attr: str, reverse: bool) -> bool:
    direction_attr = (direction_attr or "").strip().upper()

    if not direction_attr:
        return True

    return direction_attr == ("RL" if reverse else "LR")


def add_mapping(
    mapping: DefaultDict[str, List[str]],
    src: str,
    tgt: str,
    max_alts_per_word: int,
) -> None:
    if src and tgt and tgt not in mapping[src] and len(mapping[src]) < max_alts_per_word:
        mapping[src].append(tgt)


def load_dictionary(
    dict_path: str,
    max_alts_per_word: int = 3,
    reverse: Optional[bool] = None,
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    bilingual: DefaultDict[str, List[str]] = defaultdict(list)
    accent_index: DefaultDict[str, List[str]] = defaultdict(list)

    if reverse is None:
        reverse = infer_reverse_from_filename(dict_path)

    if dict_path.lower().endswith(".dix"):
        root = ET.parse(dict_path).getroot()

        for entry in root.findall(".//e"):
            direction = entry.attrib.get("r", "")

            for pair in entry.findall("p"):
                left_node = pair.find("l")
                right_node = pair.find("r")
                if left_node is None or right_node is None:
                    continue

                if not allowed_entry(direction, reverse):
                    continue

                left_text = normalize_gloss(dix_node_text(left_node))
                right_text = normalize_token(dix_node_text(right_node))

                if reverse:
                    src, tgt = right_text, left_text
                else:
                    src = normalize_token(dix_node_text(left_node))
                    tgt = normalize_gloss(dix_node_text(right_node))

                add_mapping(bilingual, src, tgt, max_alts_per_word)
                add_mapping(accent_index, strip_accents(src), tgt, max_alts_per_word)

            identity = entry.find("i")
            if identity is not None:
                word = normalize_token(dix_node_text(identity))
                add_mapping(bilingual, word, word, 1)
                add_mapping(accent_index, strip_accents(word), word, 1)

        return dict(bilingual), dict(accent_index)

    with open(dict_path, "r", encoding="utf-8") as infile:
        for line in infile:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "\t" in line:
                src_raw, tgt_raw = line.split("\t", 1)
                src = normalize_token(src_raw)
                tgt = normalize_gloss(tgt_raw)
            else:
                parts = re.split(r"\s+", line)
                if len(parts) < 2:
                    continue
                src = normalize_token(parts[0])
                tgt = normalize_gloss(" ".join(parts[1:]))

            add_mapping(bilingual, src, tgt, max_alts_per_word)
            add_mapping(accent_index, strip_accents(src), tgt, max_alts_per_word)

    return dict(bilingual), dict(accent_index)


def heuristic_candidates(word: str) -> List[str]:
    candidates: List[str] = []

    def add(value: str) -> None:
        value = normalize_token(value)
        if value and value not in candidates:
            candidates.append(value)

    add(word)

    if word.endswith("se"):
        add(word[:-2])
    else:
        add(word + "se")

    if word.endswith("es") and len(word) > 3:
        add(word[:-2])
    if word.endswith("s") and len(word) > 2:
        add(word[:-1])

    derivations = {
        "ado": ["ar"],
        "ada": ["ar"],
        "ados": ["ar"],
        "adas": ["ar"],
        "ido": ["er", "ir"],
        "ida": ["er", "ir"],
        "idos": ["er", "ir"],
        "idas": ["er", "ir"],
        "ando": ["ar"],
        "iendo": ["er", "ir"],
        "yendo": ["er", "ir"],
    }

    for suffix, infinitives in derivations.items():
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            stem = word[:-len(suffix)]
            for infinitive in infinitives:
                add(stem + infinitive)
                add(stem + infinitive + "se")

    return candidates


def join_alts(alts: Sequence[str]) -> str:
    if MULTI_TRANSLATIONS and len(alts) > 1:
        return " / ".join(alts)
    return alts[0]


def translate_lemma(
    raw_lemma: str,
    dictionary: Dict[str, List[str]],
    accent_dictionary: Dict[str, List[str]],
) -> Tuple[str, str, bool, str]:
    normalized = normalize_token(raw_lemma)

    if not normalized:
        return "[UNTRANSLATED]", normalized, False, "untranslated"

    if normalized in OVERRIDES:
        return OVERRIDES[normalized], normalized, True, "override"

    if normalized in dictionary:
        return join_alts(dictionary[normalized]), normalized, True, "dict"

    plain = strip_accents(normalized)
    if plain in accent_dictionary:
        return join_alts(accent_dictionary[plain]), normalized, True, "dict_unaccented"

    for candidate in heuristic_candidates(normalized)[1:]:
        if candidate in OVERRIDES:
            return OVERRIDES[candidate], candidate, True, "heuristic_override"
        if candidate in dictionary:
            return join_alts(dictionary[candidate]), candidate, True, "heuristic_dict"
        plain_candidate = strip_accents(candidate)
        if plain_candidate in accent_dictionary:
            return (
                join_alts(accent_dictionary[plain_candidate]),
                candidate,
                True,
                "heuristic_dict_unaccented",
            )

    if " " in normalized:
        out = []
        ok_any = False

        for token in normalized.split():
            translated, _, ok, _ = translate_lemma(token, dictionary, accent_dictionary)
            out.append(translated if ok else f"[UNTRANSLATED:{token}]")
            ok_any = ok_any or ok

        return " ".join(out), normalized, ok_any, (
            "token_fallback" if ok_any else "untranslated"
        )

    return f"[UNTRANSLATED] {normalized}", normalized, False, "untranslated"


def translate_csv(
    input_csv: str,
    dict_path: str,
    out_main: str,
    out_detail: str,
    out_untranslated: str,
    top_n: int = 100,
    assume_input_is_surface: bool = False,
    source_column: Optional[str] = None,
    reverse_dict: Optional[bool] = None,
    analyzer_cmd: Optional[Sequence[str]] = None,
) -> None:
    dictionary, accent_dictionary = load_dictionary(dict_path, reverse=reverse_dict)

    rows_cache: List[Dict[str, str]] = []
    all_input_values: List[str] = []
    untranslated_rows: List[Dict[str, str]] = []

    with open(input_csv, "r", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise ValueError("Input CSV has no headers.")

        source_column = source_column or infer_column(reader.fieldnames)
        fieldnames = list(reader.fieldnames)

        for row in reader:
            rows_cache.append(row)
            all_input_values.append(row.get(source_column, ""))

    lemma_map: Dict[str, str] = {}
    if assume_input_is_surface:
        unique_surface = sorted(
            {normalize_token(x) for x in all_input_values if normalize_token(x)}
        )
        try:
            lemma_map = lemmatize_surface_forms(unique_surface, analyzer_cmd=analyzer_cmd)
        except Exception as exc:
            warnings.warn(f"Lemmatization disabled: {exc}")
            lemma_map = {token: token for token in unique_surface}

    with open(out_main, "w", encoding="utf-8", newline="") as main_out, open(
        out_detail, "w", encoding="utf-8", newline=""
    ) as detail_out:
        writer_main = csv.DictWriter(main_out, fieldnames=fieldnames)
        writer_main.writeheader()

        detail_fieldnames = fieldnames + [
            "source_column",
            "lemma_original",
            "lemma_normalized",
            "lemma_lemmatized",
            "lemma_lookup_used",
            "lemma_translated",
            "translated_flag",
            "translation_source",
        ]
        writer_detail = csv.DictWriter(detail_out, fieldnames=detail_fieldnames)
        writer_detail.writeheader()

        for row in rows_cache:
            lemma_original = row.get(source_column, "")
            lemma_normalized = normalize_token(lemma_original)

            if assume_input_is_surface:
                lemma_lemmatized = lemma_map.get(lemma_normalized, lemma_normalized)
            else:
                lemma_lemmatized = lemma_normalized

            translated, lemma_used, ok, source = translate_lemma(
                lemma_lemmatized,
                dictionary,
                accent_dictionary,
            )

            main_row = dict(row)
            main_row[source_column] = translated
            writer_main.writerow(main_row)

            detail_row = dict(row)
            detail_row.update(
                {
                    "source_column": source_column,
                    "lemma_original": lemma_original,
                    "lemma_normalized": lemma_normalized,
                    "lemma_lemmatized": lemma_lemmatized,
                    "lemma_lookup_used": lemma_used,
                    "lemma_translated": translated,
                    "translated_flag": "TRUE" if ok else "FALSE",
                    "translation_source": source,
                }
            )
            writer_detail.writerow(detail_row)

            if not ok:
                untranslated_rows.append(detail_row)

    untranslated_rows.sort(key=lambda row: safe_int(row.get("count", 0)), reverse=True)

    with open(out_untranslated, "w", encoding="utf-8", newline="") as outfile:
        if untranslated_rows:
            fieldnames = list(untranslated_rows[0].keys())
        else:
            fieldnames = [source_column or "lemma", "count", "lemma_normalized"]

        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in untranslated_rows[:top_n]:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate a Spanish word column into English using an Apertium bilingual dictionary + overrides."
    )
    parser.add_argument("--input", required=True, help="Input CSV")
    parser.add_argument("--dict", required=True, help="Dictionary file (.txt or .dix)")
    parser.add_argument(
        "--column",
        default=None,
        help="Column to translate. Auto-detects lemma/spanish/word/token/surface if omitted.",
    )
    parser.add_argument("--out_main", default=None, help="Main translated CSV output")
    parser.add_argument("--out_detail", default=None, help="Detailed CSV output")
    parser.add_argument(
        "--out_untranslated",
        default=None,
        help="Top untranslated CSV output",
    )
    parser.add_argument(
        "--top_n",
        type=int,
        default=100,
        help="How many untranslated rows to report",
    )
    parser.add_argument(
        "--input_is_surface",
        action="store_true",
        help="Treat source column as surface forms and lemmatize before lookup",
    )
    parser.add_argument(
        "--reverse_dict",
        action="store_true",
        help="Read a bilingual .dix in reverse",
    )
    parser.add_argument(
        "--analyzer_cmd",
        nargs="+",
        default=None,
        help="Override spa-morph command",
    )
    args = parser.parse_args()

    base, ext = os.path.splitext(args.input)
    out_main = args.out_main or f"{base}_en{ext}"
    out_detail = args.out_detail or f"{base}_en_detail{ext}"
    out_untranslated = (
        args.out_untranslated or f"{base}_untranslated_top{args.top_n}{ext}"
    )

    reverse_dict = args.reverse_dict or infer_reverse_from_filename(args.dict)

    translate_csv(
        input_csv=args.input,
        dict_path=args.dict,
        out_main=out_main,
        out_detail=out_detail,
        out_untranslated=out_untranslated,
        top_n=args.top_n,
        assume_input_is_surface=args.input_is_surface,
        source_column=args.column,
        reverse_dict=reverse_dict,
        analyzer_cmd=args.analyzer_cmd,
    )

    print("Done.")
    print("Main:        ", out_main)
    print("Detail:      ", out_detail)
    print("Untranslated:", out_untranslated)


if __name__ == "__main__":
    main()