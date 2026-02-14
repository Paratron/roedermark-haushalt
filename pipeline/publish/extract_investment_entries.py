"""
Pipeline step: Extract unique investment entries for LLM classification.

Produces a compact JSON with all unique investment project names,
their TH assignment, typical sign (income/expense), and volume.
This output is designed to be processed by an LLM for semantic grouping.
"""
import csv
import json
from collections import defaultdict

def extract_investment_entries(csv_path: str) -> list[dict]:
    """Extract unique investment entries with metadata for LLM classification."""
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        inv = [r for r in reader if r['haushalt_type'] == 'investitionen']

    by_key = defaultdict(list)
    for r in inv:
        by_key[r['line_item_key']].append(r)

    entries = []
    for key, items in by_key.items():
        amounts = [float(r['amount']) for r in items if float(r['amount']) != 0]
        ist_amounts = [float(r['amount']) for r in items if r['amount_type'] == 'ist' and float(r['amount']) != 0]
        plan_amounts = [float(r['amount']) for r in items if r['amount_type'] == 'plan' and float(r['amount']) != 0]

        # Determine typical sign
        if ist_amounts:
            avg_sign = sum(ist_amounts) / len(ist_amounts)
        elif plan_amounts:
            avg_sign = sum(plan_amounts) / len(plan_amounts)
        else:
            avg_sign = 0

        ist_total = sum(float(r['amount']) for r in items if r['amount_type'] == 'ist')
        plan_total = sum(float(r['amount']) for r in items if r['amount_type'] == 'plan')
        years = sorted(set(int(float(r['year'])) for r in items))

        entries.append({
            'key': key,
            'bezeichnung': items[0]['bezeichnung'],
            'th_nr': items[0].get('teilhaushalt_nr', '').replace('.0', ''),
            'th_name': items[0].get('teilhaushalt_name', ''),
            'sign': 'einnahme' if avg_sign > 0 else 'ausgabe' if avg_sign < 0 else 'null',
            'ist_total': round(ist_total, 2),
            'plan_total': round(plan_total, 2),
            'years': years,
        })

    # Sort by TH, then by bezeichnung
    entries.sort(key=lambda e: (e['th_nr'], e['bezeichnung']))
    return entries


def main():
    entries = extract_investment_entries('data/published/line_items.csv')
    
    # Group by TH for the LLM prompt
    by_th = defaultdict(list)
    for e in entries:
        by_th[e['th_nr']].append(e)

    output = {
        'meta': {
            'total_entries': len(entries),
            'teilhaushalte': sorted(by_th.keys()),
            'description': 'Investment program entries for semantic classification by LLM',
        },
        'entries': entries,
    }

    out_path = 'data/published/investment_entries_for_classification.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'Wrote {len(entries)} entries to {out_path}')
    print(f'Teilhaushalte: {sorted(by_th.keys())}')
    for th in sorted(by_th.keys()):
        items = by_th[th]
        einnahmen = sum(1 for e in items if e['sign'] == 'einnahme')
        ausgaben = sum(1 for e in items if e['sign'] == 'ausgabe')
        null = sum(1 for e in items if e['sign'] == 'null')
        print(f'  TH {th}: {len(items)} entries ({ausgaben} ausgaben, {einnahmen} einnahmen, {null} null)')


if __name__ == '__main__':
    main()
