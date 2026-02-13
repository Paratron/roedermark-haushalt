"""Find Ergebnishaushalt/Finanzhaushalt table pages in the missing PDFs.

Strategy: only scan a narrow set of candidate pages (100-175) which is where
the Gesamthaushalt overview is located in all known PDFs.
"""
import pdfplumber
import sys

pdfs = [
    ("haushaltsplan_2017_2018", "data/raw/haushaltsplan_2017_2018.pdf"),
    ("haushaltsplan_2019", "data/raw/haushaltsplan_2019.pdf"),
    ("haushaltsplan_2020_2021_beschluss", "data/raw/haushaltsplan_2020_2021_beschluss.pdf"),
    ("haushaltsplan_2020_2021_anpassung", "data/raw/haushaltsplan_2020_2021_anpassung.pdf"),
    ("haushaltsplan_2022_entwurf", "data/raw/haushaltsplan_2022_entwurf.pdf"),
    ("haushaltsplan_2023_entwurf", "data/raw/haushaltsplan_2023_entwurf.pdf"),
    ("haushaltsplan_2024_2025_entwurf", "data/raw/haushaltsplan_2024_2025_entwurf.pdf"),
]

# Narrow range - overview tables are typically between page 100-175
SCAN_PAGES = list(range(100, 175))

for name, path in pdfs:
    print(f"\n{'='*70}")
    print(f"{name}")
    try:
        pdf = pdfplumber.open(path)
        total = len(pdf.pages)
        print(f"  Total pages: {total}")

        found_eh = []
        found_fh = []

        for pg_num in SCAN_PAGES:
            if pg_num > total:
                break
            try:
                page = pdf.pages[pg_num - 1]
                text = page.extract_text() or ""
            except Exception:
                continue

            # Skip pages with Teilergebnishaushalt/Teilfinanzhaushalt (those are sub-budgets)
            if "Teilergebnishaushalt" in text or "Teilfinanzhaushalt" in text:
                continue

            lines = text.split("\n")
            for line in lines[:10]:
                lo = line.lower().strip()
                if ("ergebnishaushalt" in lo or "gesamtergebnishaushalt" in lo) and "teil" not in lo:
                    print(f"  Page {pg_num:3d}: EH  | {line.strip()[:100]}")
                    found_eh.append(pg_num)
                elif ("finanzhaushalt" in lo or "gesamtfinanzhaushalt" in lo) and "teil" not in lo:
                    print(f"  Page {pg_num:3d}: FH  | {line.strip()[:100]}")
                    found_fh.append(pg_num)

            # Also check for Nr. + Bezeichnung header pattern (table start)
            if any("Nr." in l and "Bezeichnung" in l for l in lines[:5]):
                if any("Ergebnis" in l or "Ansatz" in l for l in lines[:5]):
                    if pg_num not in found_eh and pg_num not in found_fh:
                        print(f"  Page {pg_num:3d}: TAB | Table header found: {lines[0].strip()[:80]}")

        if not found_eh and not found_fh:
            print("  *** No overview tables found in pages 100-175!")

        pdf.close()
    except Exception as e:
        print(f"  ERROR: {e}")
