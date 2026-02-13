"""Find exact pages for main Ergebnis- and Finanzhaushalt tables (not Teil-).

Run: python pipeline/parse/find_gesamt.py
"""

from pathlib import Path
import pdfplumber


PDFS = {
    "2022": "data/raw/haushaltsplan_2022_beschluss.pdf",
    "2024/2025": "data/raw/haushaltsplan_2024_2025_beschluss.pdf",
    "2026 (Entwurf)": "data/raw/haushaltsplan_2026_entwurf.pdf",
}


def find_gesamt_tables(label: str, pdf_path: str) -> None:
    p = Path(pdf_path)
    if not p.exists():
        print(f"  ⚠ {p} nicht vorhanden")
        return

    print(f"\n{'='*70}")
    print(f"{label}: {p.name} ({len(list(pdfplumber.open(p).pages))} Seiten)")
    print(f"{'='*70}")

    with pdfplumber.open(p) as pdf:
        for i, page in enumerate(pdf.pages):
            text = (page.extract_text() or "").strip()
            first_lines = text.split("\n")[:3]
            first_text = " ".join(first_lines).lower()

            # Match ONLY "Ergebnishaushalt" or "Finanzhaushalt" at page start
            # but NOT "Teilergebnishaushalt" or "Teilfinanzhaushalt"
            for target in ["ergebnishaushalt", "finanzhaushalt"]:
                if target in first_text and f"teil{target}" not in first_text and "struktur" not in first_text:
                    tables = page.extract_tables()
                    big_tables = [t for t in tables if len(t) > 5 and len(t[0]) >= 6]
                    if big_tables:
                        t = big_tables[0]
                        # Find the header row with column names
                        for row in t[:3]:
                            cells = [str(c or "").replace("\n", " ")[:35] for c in row]
                            if any("Nr." in c for c in cells) or any("Bezeichnung" in c for c in cells):
                                print(f"  {target.upper()} → S.{i+1} ({len(t)} rows × {len(t[0])} cols)")
                                print(f"    Spalten: {cells}")
                                break


if __name__ == "__main__":
    for label, path in PDFS.items():
        find_gesamt_tables(label, path)
