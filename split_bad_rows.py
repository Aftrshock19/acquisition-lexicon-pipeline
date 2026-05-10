import pandas as pd

df = pd.read_csv("bad_rows.csv")
n = len(df)
chunks = [df.iloc[i * n // 5:(i + 1) * n // 5] for i in range(5)]

for i, chunk in enumerate(chunks, 1):
    out = f"bad_rows_{i}.csv"
    chunk.to_csv(out, index=False)
    print(f"bad_rows_{i}.csv — {len(chunk)} rows")
