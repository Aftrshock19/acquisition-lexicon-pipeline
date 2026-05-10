import pandas as pd

df = pd.read_csv("spa-eng-with-eng-defs.csv")
df = df[["rank","lemma","original_lemma","translation","definitions","english_definition","pos","sentence","english_sentence"]]
df.to_csv("spa-eng-final.csv", index=False)
print("done")
