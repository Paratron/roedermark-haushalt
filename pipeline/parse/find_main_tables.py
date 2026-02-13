"""Find the main Ergebnishaushalt and Finanzhaushalt pages."""

from pathlib import Path
import pdfplumber


def find_main_tables(pdf_path: Path) -> None:
    targets = [
        "Ergebnishaushalt",
        "Finanzhaushalt",
    ]

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            # Look for pages that START with these keywords (main section pages)
            first_line = text.strip().split("\n")[0] if text.strip() else ""

            for target in targets:
                if target.lower() in first_line.lower() and "teil" not in first_line.lower():
                    tables = page.extract_tables()
                    n_tables = len(tables)
                    max_rows = max((len(t) for t in tables), default=0) if tables else 0
                    max_cols = max((len(t[0]) for t in tables if t), default=0) if tables else 0
                    print(f"S.{i+1:>3}: '{first_line[:80]}'  →  {n_tables} Tabelle(n), max {max_rows}×{max_cols}")

                    # Show table structure
                    for t_idx, table in enumerate(tables):
                        if len(table) > 2 and len(table[0]) >= 4:
                            print(f"       Tab {t_idx+1} Header: {[str(c or '')[:30] for c in table[0]]}")
                            print(f"       Tab {t_idx+1} Row 1:  {[str(c or '')[:30] for c in table[1]]}")
                            if len(table) > 2:
                                print(f"       Tab {t_idx+1} Row 2:  {[str(c or '')[:30] for c in table[2]]}")
                    break

        # Also search for "Teilergebnishaushalt" header pages
        print("\n── Teilergebnis-/Teilfinanzhaushalte (Abschnittsbeginn) ──")
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            lines = text.strip().split("\n")
            for line in lines[:3]:
                if "Teilergebnishaushalt" in line and ("Fachbereich" in line or "FB" in line or "Fachabteilung" in line):
                    tables = page.extract_tables()
                    has_table = any(len(t) > 3 and len(t[0]) >= 5 for t in tables) if tables else False
                    print(f"S.{i+1:>3}: '{line.strip()[:80]}'  Tabelle: {'ja' if has_table else 'nein'}")
                    break
                elif "Teilfinanzhaushalt" in line and ("Fachbereich" in line or "FB" in line or "Fachabteilung" in line):
                    tables = page.extract_tables()
                    has_table = any(len(t) > 3 and len(t[0]) >= 5 for t in tables) if tables else False
                    print(f"S.{i+1:>3}: '{line.strip()[:80]}'  Tabelle: {'ja' if has_table else 'nein'}")
                    break


if __name__ == "__main__":
    find_main_tables(Path("data/raw/haushaltsplan_2023_beschluss.pdf"))
