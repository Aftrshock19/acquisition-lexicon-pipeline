import csv
import os

STAGES = [
    ("stage_00",     1,   250, "Pre-A1"),
    ("stage_01",   251,   400, "A1-"),
    ("stage_02",   401,   575, "A1-"),
    ("stage_03",   576,   800, "A1"),
    ("stage_04",   801,  1075, "A1+"),
    ("stage_05",  1076,  1400, "A1+"),
    ("stage_06",  1401,  1800, "A2-"),
    ("stage_07",  1801,  2250, "A2-"),
    ("stage_08",  2251,  2750, "A2"),
    ("stage_09",  2751,  3300, "A2+"),
    ("stage_10",  3301,  3900, "A2+"),
    ("stage_11",  3901,  4600, "B1-"),
    ("stage_12",  4601,  5400, "B1-"),
    ("stage_13",  5401,  6300, "B1"),
    ("stage_14",  6301,  7300, "B1+"),
    ("stage_15",  7301,  8400, "B1+"),
    ("stage_16",  8401,  9600, "B2-"),
    ("stage_17",  9601, 10900, "B2-"),
    ("stage_18", 10901, 12300, "B2"),
    ("stage_19", 12301, 13800, "B2+"),
    ("stage_20", 13801, 15400, "B2+"),
    ("stage_21", 15401, 17100, "C1-"),
    ("stage_22", 17101, 18900, "C1-"),
    ("stage_23", 18901, 20800, "C1"),
    ("stage_24", 20801, 22800, "C1+"),
    ("stage_25", 22801, 24900, "C1+"),
    ("stage_26", 24901, 27000, "C2-"),
    ("stage_27", 27001, 29100, "C2-"),
    ("stage_28", 29101, 31100, "C2"),
    ("stage_29", 31101, 33100, "C2+"),
    ("stage_30", 33101, 35000, "C2+"),
]

# Read all rows from source
with open('rank-lemma-spa.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

os.makedirs('cefr_stages', exist_ok=True)

for stage, start, end, band in STAGES:
    filename = os.path.join('cefr_stages', f'{stage}_{band}.csv')
    with open(filename, 'w', encoding='utf-8', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=['rank', 'lemma', 'original_lemma'])
        writer.writeheader()
        for row in rows:
            rank = int(row['rank'])
            if start <= rank <= end:
                writer.writerow(row)
    print(f'{filename}: rows {start}–{end}')
