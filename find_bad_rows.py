import pandas as pd

df = pd.read_csv("spa-eng-final-fixed2.csv")

mask = (
    df["english_definition"].astype(str).str.contains("I'm sorry", case=False, na=False) |
    df["definitions"].astype(str).str.strip().eq("")
)
bad = df[mask]

bad.to_csv("bad_rows.csv", index=False)
print(f"Found {len(bad)} rows — saved to bad_rows.csv")
