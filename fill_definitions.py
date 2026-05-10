import time
import re
import requests
import pandas as pd

EN_WIKT = "https://en.wiktionary.org/api/rest_v1/page/definition/{}"
HEADERS = {"User-Agent": "lemma-definition-filler/1.0"}
DELAY = 0.1


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def fetch_english_definition(lemma: str, original: str) -> str:
    """Fetch the first English definition of a Spanish word from English Wiktionary."""
    for word in [lemma, original]:
        if not word:
            continue
        try:
            r = requests.get(EN_WIKT.format(word), headers=HEADERS, timeout=10)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            data = r.json()
            # Look for the Spanish section (key "es")
            entries = data.get("es", [])
            for entry in entries:
                for defn in entry.get("definitions", []):
                    text = strip_html(defn.get("definition", ""))
                    if len(text) > 8:
                        return text
        except Exception as e:
            print(f"  [error] {word}: {e}")
        time.sleep(DELAY)
    return ""


def main():
    df = pd.read_csv("bad_rows.csv")
    lemmas = df["lemma"].tolist()[:100]
    originals = df["original_lemma"].tolist()[:100]

    print(f"Fetching definitions for {len(lemmas)} lemmas…")
    eng_defs = []
    for i, (lemma, original) in enumerate(zip(lemmas, originals)):
        defn = fetch_english_definition(lemma, str(original))
        eng_defs.append(defn)
        status = defn[:70] if defn else "(not found)"
        print(f"[{i+1}/{len(lemmas)}] {lemma}: {status}")

    df = df.iloc[:100].copy()
    df["english_definition"] = eng_defs
    df.to_csv("bad_rows_filled.csv", index=False)
    found = sum(1 for d in eng_defs if d)
    print(f"\nDone. {found}/{len(lemmas)} definitions filled → bad_rows_filled.csv")


if __name__ == "__main__":
    main()
