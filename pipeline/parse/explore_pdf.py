"""Explore a Rödermark Haushaltsplan PDF to understand its structure.

Run:  python pipeline/parse/explore_pdf.py [path_to_pdf]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pdfplumber


def explore(pdf_path: Path, *, sample_pages: list[int] | None = None) -> None:
    print(f"\n{'='*80}")
    print(f"PDF: {pdf_path.name}  ({pdf_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"{'='*80}\n")

    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        print(f"Seiten: {n_pages}\n")

        # ── Inhaltsverzeichnis / erste Seiten sichten ──────────────────
        print("── Erste 8 Seiten (Text-Snippets) ──")
        for i in range(min(8, n_pages)):
            page = pdf.pages[i]
            text = (page.extract_text() or "")[:300].replace("\n", " | ")
            print(f"  S.{i+1:>4}: {text[:200]}...")
        print()

        # ── Suche nach Schlüsselbegriffen ──────────────────────────────
        keywords = [
            "Ergebnishaushalt",
            "Finanzhaushalt",
            "Gesamtergebnishaushalt",
            "Gesamtfinanzhaushalt",
            "Teilhaushalt",
            "Teilergebnishaushalt",
            "Teilfinanzhaushalt",
            "Produktplan",
            "Produktbereich",
            "Haushaltssatzung",
            "Stellenplan",
            "Investitionsprogramm",
            "Vorbericht",
        ]
        print("── Schlüsselwort-Suche (erste Fundstelle je Keyword) ──")
        for kw in keywords:
            found_pages = []
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if kw.lower() in text.lower():
                    found_pages.append(i + 1)
                    if len(found_pages) >= 5:
                        break
            if found_pages:
                pages_str = ", ".join(str(p) for p in found_pages)
                suffix = " ..." if len(found_pages) >= 5 else ""
                print(f"  '{kw}': Seiten {pages_str}{suffix}")
            else:
                print(f"  '{kw}': nicht gefunden")
        print()

        # ── Tabellen auf ausgewählten Seiten extrahieren ───────────────
        if sample_pages is None:
            # Automatisch: erste Seiten mit Tabellen finden
            sample_pages = []
            for i, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if tables:
                    sample_pages.append(i + 1)
                    if len(sample_pages) >= 10:
                        break

        print(f"── Tabellen-Samples (Seiten: {sample_pages}) ──")
        for pg_num in sample_pages:
            if pg_num < 1 or pg_num > n_pages:
                continue
            page = pdf.pages[pg_num - 1]
            tables = page.extract_tables()
            if not tables:
                print(f"\n  S.{pg_num}: keine Tabelle gefunden")
                continue
            for t_idx, table in enumerate(tables):
                print(f"\n  S.{pg_num} Tabelle {t_idx+1} ({len(table)} Zeilen, {len(table[0]) if table else 0} Spalten):")
                # Header + erste Datenzeilen
                for row_i, row in enumerate(table[:8]):
                    cells = [str(c or "").strip()[:30] for c in row]
                    print(f"    [{row_i}] {' | '.join(cells)}")
                if len(table) > 8:
                    print(f"    ... ({len(table) - 8} weitere Zeilen)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        pdf_file = Path(sys.argv[1])
    else:
        pdf_file = Path("data/raw/haushaltsplan_2023_beschluss.pdf")
    explore(pdf_file)
