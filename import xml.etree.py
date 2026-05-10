import xml.etree.ElementTree as ET

INPUT = "apertium-eng-spa.eng-spa.dix"
OUTPUT = "es-en.txt"

tree = ET.parse(INPUT)
root = tree.getroot()

pairs = set()

for e in root.findall(".//e"):
    p = e.find("p")
    if p is None:
        continue

    l = p.find("l")
    r = p.find("r")
    if l is None or r is None:
        continue

    eng = "".join(l.itertext()).strip()
    spa = "".join(r.itertext()).strip()

    if eng and spa:
        pairs.add((spa.lower(), eng.lower()))

with open(OUTPUT, "w", encoding="utf-8") as f:
    for spa, eng in sorted(pairs):
        f.write(f"{spa} {eng}\n")

print("Done. Output:", OUTPUT)