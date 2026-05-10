import pandas as pd

df = pd.read_csv("spa-eng-final-fixed.csv")

# Build lookups from rows that already have definitions
has_def = df[df["definitions"].notna() & (df["definitions"].astype(str).str.strip() != "")]
lemma_to_def = has_def.set_index("lemma")[["definitions", "english_definition"]].to_dict("index")

orig_to_def = {}
for _, row in has_def.iterrows():
    key = row["original_lemma"]
    if key not in orig_to_def:
        orig_to_def[key] = {"definitions": row["definitions"], "english_definition": row["english_definition"]}


def is_plural(lemma, original):
    """True if lemma looks like a plural of original."""
    if lemma == original:
        return False
    return (
        lemma.endswith("s") and not original.endswith("s")
    )


def is_feminine(lemma, original):
    """True if lemma looks like a feminine form of original."""
    if lemma == original:
        return False
    # -o → -a  (ocupado → ocupada)
    if original.endswith("o") and lemma == original[:-1] + "a":
        return True
    # -or → -ora  (productor → productora)
    if original.endswith("or") and lemma == original + "a":
        return True
    # -ín / -ón → -ina / -ona  (bailarín → bailarina)
    if original.endswith(("ín", "ón")) and lemma == original[:-1] + "na":
        return True
    # -és → -esa  (francés → francesa)
    if original.endswith("és") and lemma == original[:-2] + "esa":
        return True
    return False


filled = 0
for i, row in df.iterrows():
    if pd.notna(row["definitions"]) and str(row["definitions"]).strip():
        continue  # already has a definition

    lemma = str(row["lemma"])
    original = str(row["original_lemma"])

    if not is_plural(lemma, original) and not is_feminine(lemma, original):
        continue

    source = lemma_to_def.get(original) or orig_to_def.get(original)
    if source:
        df.at[i, "definitions"] = source["definitions"]
        df.at[i, "english_definition"] = source["english_definition"]
        filled += 1
        kind = "plural" if is_plural(lemma, original) else "feminine"
        print(f"  [{kind}] {lemma} → {original}: {str(source['definitions'])[:60]}")
    else:
        print(f"  (no source) {lemma} → {original}")

df.to_csv("spa-eng-final-fixed.csv", index=False)
print(f"\nFilled {filled} rows → spa-eng-final-fixed.csv")
