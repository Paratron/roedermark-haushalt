"""Deep-dive into key pages of a Haushaltsplan PDF.

Run: python pipeline/parse/explore_tables.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pdfplumber


def show_page_tables(pdf_path: Path, pages: list[int]) -> None:
    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        for pg_num in pages:
            if pg_num < 1 or pg_num > n_pages:
                print(f"\n  S.{pg_num}: ungültig (PDF hat {n_pages} Seiten)")
                continue

            page = pdf.pages[pg_num - 1]
            text = (page.extract_text() or "")[:200]
            print(f"\n{'='*80}")
            print(f"SEITE {pg_num}  –  Text-Anfang: {text[:100]}...")
            print(f"{'='*80}")

            tables = page.extract_tables()
            if not tables:
                print("  (keine Tabelle gefunden)")
                continue

            for t_idx, table in enumerate(tables):
                n_rows = len(table)
                n_cols = len(table[0]) if table else 0
                print(f"\n  Tabelle {t_idx + 1}: {n_rows} Zeilen × {n_cols} Spalten")
                # Print ALL rows for small tables, first+last for large
                if n_rows <= 25:
                    rows_to_show = range(n_rows)
                else:
                    rows_to_show = list(range(10)) + ["..."] + list(range(n_rows - 5, n_rows))

                for row_i in rows_to_show:
                    if row_i == "...":
                        print(f"    ... ({n_rows - 15} Zeilen ausgelassen) ...")
                        continue
                    cells = [str(c or "").replace("\n", " ↵ ").strip()[:40] for c in table[row_i]]
                    print(f"    [{row_i:>3}] {' | '.join(cells)}")


if __name__ == "__main__":
    pdf_path = Path("data/raw/haushaltsplan_2023_beschluss.pdf")

    # Interessante Seiten: Ergebnishaushalt (~S.20-22), Finanzhaushalt, Teilergebnis
    # Aus der Keyword-Suche: Teilergebnishaushalt ab S.11/17, Teilfinanzhaushalt ab S.17
    # Tabellen auf S.20 sahen vielversprechend aus
    pages = [11, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]

    show_page_tables(pdf_path, pages)
