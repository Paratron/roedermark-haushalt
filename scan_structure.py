"""Scan specific page ranges for Teilhaushalte and Investitionsprogramm."""
import pdfplumber
import re

RAW = "data/raw"

def scan_pdf(pdf_name, teilhaushalt_range, invest_range):
    path = f"{RAW}/{pdf_name}"
    print(f"\n{'='*80}")
    print(f"=== {pdf_name} ===")
    print("=" * 80)

    pdf = pdfplumber.open(path)
    total = len(pdf.pages)
    print(f"Seiten: {total}")

    # --- Teilhaushalte: scan the specific range ---
    print(f"\n--- Teilhaushalte (Seiten {teilhaushalt_range[0]}-{teilhaushalt_range[1]}) ---")

    teil_ergebnis_pages = []
    teil_finanz_pages = []

    for pg_num in range(teilhaushalt_range[0], min(teilhaushalt_range[1]+1, total+1)):
        page = pdf.pages[pg_num - 1]
        text = (page.extract_text() or "")[:600]

        if re.search(r"^Teilergebnishaushalt\s+\d", text, re.M):
            m = re.search(r"Teilergebnishaushalt\s+(\d[\d.]*)\s+(.*?)$", text, re.M)
            if m and "." not in m.group(1):
                teil_ergebnis_pages.append((pg_num, m.group(1), m.group(2).strip()))

        if re.search(r"^Teilfinanzhaushalt\s+\d", text, re.M):
            m = re.search(r"Teilfinanzhaushalt\s+(\d[\d.]*)\s+(.*?)$", text, re.M)
            if m and "." not in m.group(1):
                teil_finanz_pages.append((pg_num, m.group(1), m.group(2).strip()))

    print("\nTeilergebnishaushalte (Top-Level):")
    for pg, nr, name in teil_ergebnis_pages:
        print(f"  Seite {pg}: TH {nr} - {name}")

    print("\nTeilfinanzhaushalte (Top-Level):")
    for pg, nr, name in teil_finanz_pages:
        print(f"  Seite {pg}: TH {nr} - {name}")

    # Sample: extract table from first Teilergebnishaushalt
    if teil_ergebnis_pages:
        sample_pg = teil_ergebnis_pages[0][0]
        print(f"\n  === Sample: Teilergebnishaushalt Seite {sample_pg} ===")
        page = pdf.pages[sample_pg - 1]
        tables = page.extract_tables()
        if tables:
            for ti, t in enumerate(tables):
                print(f"  Tabelle {ti}: {len(t)} Zeilen, {len(t[0])} Spalten")
                for row in t[:6]:
                    print(f"    {row}")
                if len(t) > 6:
                    print(f"    ... ({len(t)} total)")

    # Sample: Teilfinanzhaushalt
    if teil_finanz_pages:
        sample_pg = teil_finanz_pages[0][0]
        print(f"\n  === Sample: Teilfinanzhaushalt Seite {sample_pg} ===")
        page = pdf.pages[sample_pg - 1]
        tables = page.extract_tables()
        if tables:
            for ti, t in enumerate(tables):
                print(f"  Tabelle {ti}: {len(t)} Zeilen, {len(t[0])} Spalten")
                for row in t[:6]:
                    print(f"    {row}")
                if len(t) > 6:
                    print(f"    ... ({len(t)} total)")

    # --- Investitionsprogramm ---
    # Search broader range including within Teilfinanzhaushalte
    print(f"\n--- Investitionsprogramm (Seiten {invest_range[0]}-{invest_range[1]}) ---")
    invest_pages = []

    for pg_num in range(invest_range[0], min(invest_range[1]+1, total+1)):
        page = pdf.pages[pg_num - 1]
        text = (page.extract_text() or "")[:800]

        if re.search(r"Investitions(programm|maßnahm|übersicht)|Einzeldarstellung.*Investition|Muster\s*4|Investitionsauszahlungen", text):
            first_line = text.split("\n")[0].strip()[:100]
            invest_pages.append((pg_num, first_line))

    print(f"Seiten: {len(invest_pages)}")
    for pg, hdr in invest_pages[:20]:
        print(f"  Seite {pg}: {hdr}")

    if invest_pages:
        sample_pg = invest_pages[0][0]
        print(f"\n  === Sample: Investitionsprogramm Seite {sample_pg} ===")
        page = pdf.pages[sample_pg - 1]
        tables = page.extract_tables()
        if tables:
            for ti, t in enumerate(tables):
                print(f"  Tabelle {ti}: {len(t)} Zeilen, {len(t[0])} Spalten")
                for row in t[:10]:
                    print(f"    {row}")
                if len(t) > 10:
                    print(f"    ... ({len(t)} total)")
        else:
            text = page.extract_text() or ""
            lines = text.split("\n")
            print("  (Keine Tabelle, Text-Extrakt:)")
            for line in lines[:25]:
                print(f"    {line}")

    # Also scan within Teilfinanzhaushalt for Investitionen rows
    print("\n--- Investitionen innerhalb der Teilfinanzhaushalte ---")
    if teil_finanz_pages:
        sp = teil_finanz_pages[0][0]
        page = pdf.pages[sp - 1]
        tables = page.extract_tables()
        if tables:
            t = tables[0]
            for row in t:
                row_text = " ".join(str(c) for c in row if c)
                if re.search(r"[Ii]nvest", row_text):
                    print(f"  Seite {sp}: {row}")

    pdf.close()


# 2026 Entwurf: Teilhaushalte start around page 163
scan_pdf("haushaltsplan_2026_entwurf.pdf",
         teilhaushalt_range=(160, 550),
         invest_range=(50, 165))

# 2024/2025 Entwurf
scan_pdf("haushaltsplan_2024_2025_entwurf.pdf",
         teilhaushalt_range=(140, 560),
         invest_range=(50, 145))
