"""Explore multiple Haushaltspläne to find equivalent tables across years.

Run: python pipeline/parse/explore_multi.py
"""

from __future__ import annotations

from pathlib import Path
import pdfplumber


PDFS = [
    ("haushaltsplan_2022_beschluss", "2022"),
    ("haushaltsplan_2024_2025_beschluss", "2024/2025"),
    ("haushaltsplan_2026_entwurf", "2026"),
]

RAW_DIR = Path("data/raw")

TARGETS = ["Ergebnishaushalt", "Finanzhaushalt", "Struktur Ergebnishaushalt", "Struktur Finanzhaushalt"]


def explore_pdf(doc_id: str, label: str) -> None:
    pdf_path = RAW_DIR / f"{doc_id}.pdf"
    if not pdf_path.exists():
        print(f"  ⚠ {pdf_path} nicht vorhanden")
        return

    print(f"\n{'='*70}")
    print(f"{label} – {doc_id} ({pdf_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"{'='*70}")

    with pdfplumber.open(pdf_path) as pdf:
        print(f"  Seiten: {len(pdf.pages)}")

        for target in TARGETS:
            found = []
            for i, page in enumerate(pdf.pages):
                text = (page.extract_text() or "").strip()
                first_lines = "\n".join(text.split("\n")[:3])

                if target.lower() in first_lines.lower():
                    # Check if page has substantial table
                    tables = page.extract_tables()
                    big_tables = [t for t in tables if len(t) > 5 and len(t[0]) >= 4]
                    if big_tables:
                        t = big_tables[0]
                        header_cells = [str(c or "")[:25] for c in t[0]]
                        row1_cells = [str(c or "")[:25] for c in t[1]] if len(t) > 1 else []
                        found.append({
                            "page": i + 1,
                            "rows": len(t),
                            "cols": len(t[0]),
                            "header": header_cells,
                            "row1": row1_cells,
                        })

            if found:
                for f in found:
                    print(f"  '{target}' → S.{f['page']} ({f['rows']}×{f['cols']})")
                    print(f"    Header: {f['header']}")
                    print(f"    Row 1:  {f['row1']}")
            else:
                print(f"  '{target}' → nicht gefunden (als Tabellenüberschrift)")


if __name__ == "__main__":
    for doc_id, label in PDFS:
        explore_pdf(doc_id, label)
