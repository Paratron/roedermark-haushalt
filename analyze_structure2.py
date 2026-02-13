#!/usr/bin/env python3
"""
Deep analysis of Rödermark budget PDFs - Phase 2.
Based on Phase 1 findings, we know:
- Teilergebnishaushalt / Teilfinanzhaushalt pages exist (e.g. pages 163, 164, 231, 232...)
- Investitionsprogramm starts around page 44 (from TOC)
- Investment tables also appear within Fachbereich sections (pages 165-166, 233, 265-266...)

This script does targeted deep scans of those specific pages.
"""

import pdfplumber
import re
from pathlib import Path

RAW_DIR = Path("data/raw")
PRIMARY_PDF = RAW_DIR / "haushaltsplan_2026_entwurf.pdf"
SECONDARY_PDF = RAW_DIR / "haushaltsplan_2024_2025_beschluss.pdf"


def deep_page_scan(pdf_path, page_num, label=""):
    """Full dump of a single page: text + all tables."""
    with pdfplumber.open(pdf_path) as pdf:
        if page_num > len(pdf.pages):
            print(f"  Page {page_num} out of range (max {len(pdf.pages)})")
            return
        page = pdf.pages[page_num - 1]
        text = page.extract_text() or ""
        lines = text.split("\n")

        print(f"\n{'='*100}")
        print(f"PAGE {page_num} - {label} - {pdf_path.name}")
        print(f"{'='*100}")
        print(f"Text ({len(lines)} lines):")
        for j, line in enumerate(lines):
            print(f"  {j+1:3d}: {line}")

        tables = page.extract_tables()
        print(f"\npdfplumber tables: {len(tables)}")
        for t_idx, table in enumerate(tables):
            if not table:
                continue
            max_cols = max(len(r) for r in table)
            print(f"\n  TABLE {t_idx+1}: {len(table)} rows x {max_cols} cols")
            for r_idx, row in enumerate(table):
                cells = [str(c)[:35] if c else "" for c in row]
                print(f"    Row {r_idx:3d}: {cells}")


def scan_full_range(pdf_path, start_page, end_page, label=""):
    """Scan a range of pages, showing just headers and table shapes."""
    with pdfplumber.open(pdf_path) as pdf:
        print(f"\n{'#'*100}")
        print(f"RANGE SCAN: Pages {start_page}-{end_page} - {label} - {pdf_path.name}")
        print(f"{'#'*100}")

        for i in range(start_page - 1, min(end_page, len(pdf.pages))):
            page_num = i + 1
            page = pdf.pages[i]
            text = page.extract_text() or ""
            first_line = text.split("\n")[0] if text else "(empty)"
            tables = page.extract_tables()
            table_info = []
            for t in tables:
                if t:
                    table_info.append(f"{len(t)}r x {max(len(r) for r in t)}c")
            tables_str = ", ".join(table_info) if table_info else "no tables"
            print(f"  Page {page_num:4d}: [{tables_str}] {first_line[:80]}")


def find_all_sections_by_header(pdf_path):
    """
    Find all Teilergebnishaushalt and Teilfinanzhaushalt summary pages.
    These are the Fachbereich-level summaries (e.g. "Teilergebnishaushalt 1 Zentrale Dienste")
    as opposed to Produktgruppen-level (e.g. "Teilergebnishaushalt 01.1.01 Personalmanagement").
    """
    print(f"\n{'#'*100}")
    print(f"FINDING ALL SECTION HEADERS: {pdf_path.name}")
    print(f"{'#'*100}")

    fachbereich_teilergebnis = []
    fachbereich_teilfinanz = []
    fachbereich_investitionen = []
    produktgruppe_teilergebnis = []
    investitionsprogramm_pages = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text() or ""
            first_line = text.split("\n")[0].strip() if text else ""

            # Fachbereich-level Teilergebnishaushalt (e.g. "Teilergebnishaushalt 1 Zentrale Dienste")
            m = re.match(r"^Teilergebnishaushalt\s+(\d+)\s+(.+)", first_line)
            if m and "." not in m.group(1):
                fachbereich_teilergebnis.append((page_num, m.group(1), m.group(2)))

            # Fachbereich-level Teilfinanzhaushalt
            m = re.match(r"^Teilfinanzhaushalt\s+(\d+)\s+(.+)", first_line)
            if m and "." not in m.group(1):
                fachbereich_teilfinanz.append((page_num, m.group(1), m.group(2)))

            # Investitionen pages within Fachbereiche
            m = re.match(r"^Investitionen\s+(\d+)\s+(.+)", first_line)
            if m:
                fachbereich_investitionen.append((page_num, m.group(1), m.group(2)))

            # Produktgruppen-level Teilergebnishaushalt (e.g. "Teilergebnishaushalt 01.1.01 ...")
            m = re.match(r"^Teilergebnishaushalt\s+(\d+\.\d+(?:\.\d+)?)\s+(.+)", first_line)
            if m:
                produktgruppe_teilergebnis.append((page_num, m.group(1), m.group(2)))

            # Main Investitionsprogramm (standalone section, not within Fachbereich)
            if re.match(r"^Investitionsprogramm", first_line):
                investitionsprogramm_pages.append((page_num, first_line[:80]))

    print(f"\nFachbereich-level Teilergebnishaushalt ({len(fachbereich_teilergebnis)} found):")
    for pg, num, name in fachbereich_teilergebnis:
        print(f"  Page {pg:4d}: TH {num:>2s} - {name}")

    print(f"\nFachbereich-level Teilfinanzhaushalt ({len(fachbereich_teilfinanz)} found):")
    for pg, num, name in fachbereich_teilfinanz:
        print(f"  Page {pg:4d}: TH {num:>2s} - {name}")

    print(f"\nFachbereich Investitionen pages ({len(fachbereich_investitionen)} found):")
    for pg, num, name in fachbereich_investitionen:
        print(f"  Page {pg:4d}: FB {num:>2s} - {name}")

    print(f"\nProduktgruppen-level Teilergebnishaushalt ({len(produktgruppe_teilergebnis)} found):")
    for pg, num, name in produktgruppe_teilergebnis:
        print(f"  Page {pg:4d}: PG {num:>7s} - {name}")

    print(f"\nMain Investitionsprogramm pages ({len(investitionsprogramm_pages)} found):")
    for pg, title in investitionsprogramm_pages:
        print(f"  Page {pg:4d}: {title}")

    return {
        "fb_teilergebnis": fachbereich_teilergebnis,
        "fb_teilfinanz": fachbereich_teilfinanz,
        "fb_investitionen": fachbereich_investitionen,
        "pg_teilergebnis": produktgruppe_teilergebnis,
        "investitionsprogramm": investitionsprogramm_pages,
    }


def main():
    # ── 1. Find all sections in primary PDF ──
    sections_2026 = find_all_sections_by_header(PRIMARY_PDF)

    # ── 2. Deep scan sample Teilergebnishaushalt (Fachbereich level) ──
    if sections_2026["fb_teilergebnis"]:
        first_te = sections_2026["fb_teilergebnis"][0][0]
        deep_page_scan(PRIMARY_PDF, first_te, "First Fachbereich Teilergebnishaushalt")
        # Also check a second one
        if len(sections_2026["fb_teilergebnis"]) > 2:
            third_te = sections_2026["fb_teilergebnis"][2][0]
            deep_page_scan(PRIMARY_PDF, third_te, "Third Fachbereich Teilergebnishaushalt")

    # ── 3. Deep scan sample Teilfinanzhaushalt (Fachbereich level) ──
    if sections_2026["fb_teilfinanz"]:
        first_tf = sections_2026["fb_teilfinanz"][0][0]
        deep_page_scan(PRIMARY_PDF, first_tf, "First Fachbereich Teilfinanzhaushalt")

    # ── 4. Deep scan the main Investitionsprogramm section (from TOC: starts page 44) ──
    print("\n\n" + "█" * 100)
    print("MAIN INVESTITIONSPROGRAMM (from TOC: page ~44)")
    print("█" * 100)
    # Scan pages 44-55 (before Verpflichtungsermächtigungen at page 56)
    scan_full_range(PRIMARY_PDF, 44, 56, "Main Investitionsprogramm range")
    # Deep scan first 2 actual Investitionsprogramm pages
    deep_page_scan(PRIMARY_PDF, 44, "Investitionsprogramm page 44")
    deep_page_scan(PRIMARY_PDF, 45, "Investitionsprogramm page 45")
    deep_page_scan(PRIMARY_PDF, 46, "Investitionsprogramm page 46")
    deep_page_scan(PRIMARY_PDF, 50, "Investitionsprogramm page 50")

    # ── 5. Deep scan Fachbereich-level Investitionen pages ──
    if sections_2026["fb_investitionen"]:
        first_inv = sections_2026["fb_investitionen"][0][0]
        deep_page_scan(PRIMARY_PDF, first_inv, "First Fachbereich Investitionen")
        # Also next page (these are multi-page)
        deep_page_scan(PRIMARY_PDF, first_inv + 1, "First Fachbereich Investitionen +1")
        # Check the Erläuterung page that follows
        deep_page_scan(PRIMARY_PDF, first_inv + 2, "First Fachbereich Investitionen +2 (Erläuterung?)")

    # ── 6. Deep scan sample Produktgruppen-level Teilergebnishaushalt ──
    if sections_2026["pg_teilergebnis"]:
        first_pg = sections_2026["pg_teilergebnis"][0][0]
        deep_page_scan(PRIMARY_PDF, first_pg, "First Produktgruppe Teilergebnishaushalt")

    # ── 7. Now do the same for secondary PDF ──
    print("\n\n" + "█" * 100)
    print("SECONDARY PDF COMPARISON")
    print("█" * 100)
    sections_2425 = find_all_sections_by_header(SECONDARY_PDF)

    # Deep scan first Teilergebnishaushalt from secondary
    if sections_2425["fb_teilergebnis"]:
        pg = sections_2425["fb_teilergebnis"][0][0]
        deep_page_scan(SECONDARY_PDF, pg, "First FB Teilergebnishaushalt (2024/25)")

    # Deep scan first Teilfinanzhaushalt from secondary
    if sections_2425["fb_teilfinanz"]:
        pg = sections_2425["fb_teilfinanz"][0][0]
        deep_page_scan(SECONDARY_PDF, pg, "First FB Teilfinanzhaushalt (2024/25)")

    # Find and scan Investitionsprogramm in secondary (from TOC: page ~41)
    scan_full_range(SECONDARY_PDF, 41, 50, "Main Investitionsprogramm (2024/25)")
    deep_page_scan(SECONDARY_PDF, 41, "Investitionsprogramm page 41 (2024/25)")
    deep_page_scan(SECONDARY_PDF, 42, "Investitionsprogramm page 42 (2024/25)")

    # Deep scan first Fachbereich Investitionen from secondary
    if sections_2425["fb_investitionen"]:
        pg = sections_2425["fb_investitionen"][0][0]
        deep_page_scan(SECONDARY_PDF, pg, "First FB Investitionen (2024/25)")

    # ── 8. Final summary ──
    print("\n\n" + "█" * 100)
    print("FINAL SUMMARY")
    print("█" * 100)

    for label, key, pdf_name in [
        ("2026 Entwurf", sections_2026, PRIMARY_PDF.name),
        ("2024/25 Beschluss", sections_2425, SECONDARY_PDF.name),
    ]:
        print(f"\n{label} ({pdf_name}):")
        print(f"  Fachbereich Teilergebnishaushalt: {len(key['fb_teilergebnis'])} sections")
        print(f"  Fachbereich Teilfinanzhaushalt:   {len(key['fb_teilfinanz'])} sections")
        print(f"  Fachbereich Investitionen pages:  {len(key['fb_investitionen'])} pages")
        print(f"  Produktgruppen Teilergebnishaush:  {len(key['pg_teilergebnis'])} sections")

        # List all Fachbereiche
        fb_nums = sorted(set(num for _, num, _ in key["fb_teilergebnis"]))
        print(f"  Fachbereich numbers: {fb_nums}")
        for _, num, name in key["fb_teilergebnis"]:
            print(f"    FB {num:>2s}: {name}")


if __name__ == "__main__":
    main()
