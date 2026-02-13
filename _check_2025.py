import csv

print("=== 2025 Jahresergebnis aus allen Quellen ===")
with open('data/published/line_items.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['haushalt_type'] == 'ergebnishaushalt' and 'jahresergebnis' in row['bezeichnung'].lower() and row['year'] == '2025':
            print(f"year={row['year']} type={row['amount_type']:5s} amount={float(row['amount']):>15.2f}  nr={row['nr']:>5s}  doc={row['document_id']}")

print("\n=== HP 2024/2025 Entwurf - alle Jahresergebnis ===")
with open('data/published/line_items.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['document_id'] == 'haushaltsplan_2024_2025_entwurf' and 'jahresergebnis' in row['bezeichnung'].lower():
            print(f"year={row['year']} type={row['amount_type']:5s} amount={float(row['amount']):>15.2f}  nr={row['nr']:>5s}  bez={row['bezeichnung']}")

print("\n=== HP 2026 Entwurf - Nr 260 + 290 + 300 fuer 2025 ===")
with open('data/published/line_items.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['document_id'] == 'haushaltsplan_2026_entwurf' and row['haushalt_type'] == 'ergebnishaushalt' and row['year'] == '2025' and row['nr'] in ('260', '290', '300'):
            print(f"nr={row['nr']:>5s} amount={float(row['amount']):>15.2f}  bez={row['bezeichnung']}")

print("\n=== Dedup-Logik: welches Dokument gewinnt fuer 2025 plan Jahresergebnis? ===")
candidates = []
with open('data/published/line_items.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['haushalt_type'] == 'ergebnishaushalt' and 'jahresergebnis' in row['bezeichnung'].lower() and row['year'] == '2025' and row['amount_type'] == 'plan':
            candidates.append(row)
            print(f"  candidate: doc={row['document_id']} amount={row['amount']}")
print(f"  sorted by doc_id: {sorted([c['document_id'] for c in candidates])}")
print(f"  winner (last alphabetically): {sorted(candidates, key=lambda x: x['document_id'])[-1]['document_id'] if candidates else 'none'}")

print("\n=== Vergleich: Was sagt HP 2024/2025 vs HP 2026 fuer 2025? ===")
with open('data/published/line_items.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['haushalt_type'] == 'ergebnishaushalt' and row['year'] == '2025' and row['nr'] == '300':
            print(f"doc={row['document_id']:45s} nr={row['nr']} amount={float(row['amount']):>15.2f}  type={row['amount_type']}")
