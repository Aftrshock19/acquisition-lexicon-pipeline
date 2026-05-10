import pandas as pd

PRONOUNS = ["le", "nos", "les", "los", "las", "lo", "la", "te", "me", "se"]

df = pd.read_csv("spa-eng-final.csv")

# Build a lookup: lemma -> (definitions, english_definition) for rows that have definitions
has_def = df[df["definitions"].notna() & (df["definitions"].astype(str).str.strip() != "")]
lemma_to_def = has_def.set_index("lemma")[["definitions", "english_definition"]].to_dict("index")

# Also index by original_lemma as fallback
orig_to_def = {}
for _, row in has_def.iterrows():
    key = row["original_lemma"]
    if key not in orig_to_def:
        orig_to_def[key] = {"definitions": row["definitions"], "english_definition": row["english_definition"]}

filled = 0
for i, row in df.iterrows():
    if pd.notna(row["definitions"]) and str(row["definitions"]).strip():
        continue  # already has a definition

    lemma = str(row["lemma"])
    ends_with_pronoun = any(lemma.endswith(p) for p in PRONOUNS)
    if not ends_with_pronoun:
        continue

    original = str(row["original_lemma"])

    # Try exact lemma match first, then original_lemma match
    source = lemma_to_def.get(original) or orig_to_def.get(original)
    if source:
        df.at[i, "definitions"] = source["definitions"]
        df.at[i, "english_definition"] = source["english_definition"]
        filled += 1
        print(f"  {lemma} → {original}: {str(source['definitions'])[:60]}")
    else:
        print(f"  {lemma} → {original}: (no source found)")

df.to_csv("spa-eng-final-fixed.csv", index=False)
print(f"\nFilled {filled} rows → spa-eng-final-fixed.csv")
