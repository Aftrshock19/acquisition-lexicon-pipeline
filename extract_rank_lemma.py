import csv

with open('spa-eng.csv', 'r', encoding='utf-8') as infile, \
     open('rank-lemma-spa.csv', 'w', encoding='utf-8', newline='') as outfile:
    reader = csv.DictReader(infile)
    writer = csv.DictWriter(outfile, fieldnames=['rank', 'lemma', 'original_lemma'])
    writer.writeheader()
    for row in reader:
        writer.writerow({
            'rank': row['rank'],
            'lemma': row['lemma'],
            'original_lemma': row['original_lemma']
        })
