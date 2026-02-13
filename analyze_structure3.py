#!/usr/bin/env python3
"""
Phase 3: Targeted deep scans of specific pages we now know about.
Focus on:
1. Teilfinanzhaushalt structure (page 164 in 2026)
2. Fachbereich Investitionen structure (page 165 in 2026)
3. Main Investitionsprogramm (page 44-55 in 2026)
4. Same sections in 2024/25 Beschluss
"""

import pdfplumber
import re
from pathlib import Path

RAW_DIR = Path("data/raw")
PRIMARY_PDF = RAW_DIR / "haushaltsplan_2026_entwurf.pdf"
SECONDARY_PDF = RAW_DIR / "haushaltsplan_2024_2025_beschluss.pdf"


def dump_page(pdf_path, page_num, label=""):
    """Full dump of a single page."""
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num - 1]
        text = page.extract_text() or ""
        lines = text.split("\n")
        print(f"\n{'='*100}")
        print(f"PAGE {page_num} - {label} - {pdf_path.name}")
        print(f"{'='*100}")
        for j, line in enumerate(lines):
            print(f"  {j+1:3d}: {line}")

        tables = page.extract_tables()
        print(f"\nTables: {len(tables)}")
        for t_idx, table in enumerate(tables):
            if not table:
                continue
            max_cols = max(len(r) for r in table)
            print(f"\n  TABLE {t_idx+1}: {len(table)} rows x {max_cols} cols")
            for r_idx, row in enumerate(table[:20]):
                cells = [str(c)[:40] if c else "" for c in row]
                print(f"    {r_idx:3d}: {cells}")
            if len(table) > 20:
                print(f"    ... ({len(table)-20} more rows)")


def find_investitionsprogramm_pages(pdf_path):
    """Find the main Investitionsprogramm section (the multi-page overview table)."""
    print(f"\n{'#'*100}")
    print(f"FINDING MAIN INVESTITIONSPROGRAMM: {pdf_path.name}")
    print(f"{'#'*100}")

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text() or ""
            first_line = text.split("\n")[0].strip() if text else ""

            # Look for landscape tables with reversed text (Investitionsprogramm)
            # or normal-orientation Investitionsprogramm header
            if "nalpznaniF" in text or "Finanzplan" in first_line:
                tables = page.extract_tables()
                table_info = []
                for t in tables:
                    if t:
                        table_info.append(f"{len(t)}r x {max(len(r) for r in t)}c")
                if tables:
                    print(f"  Page {page_num}: {table_info} - first: {first_line[:60]}")


def main():
    print("=" * 100)
    print("PHASE 3: TARGETED DEEP SCANS")
    print("=" * 100)

    # ── 1. Teilfinanzhaushalt (page 164 in 2026) ──
    dump_page(PRIMARY_PDF, 164, "Teilfinanzhaushalt FB 1")

    # ── 2. Fachbereich Investitionen (page 165-166 in 2026) ──
    dump_page(PRIMARY_PDF, 165, "Investitionen FB 1 (page 1)")
    dump_page(PRIMARY_PDF, 166, "Investitionen FB 1 (page 2)")
    dump_page(PRIMARY_PDF, 167, "Erläuterung der Investitionen")

    # ── 3. Main Investitionsprogramm - find landscape tables ──
    find_investitionsprogramm_pages(PRIMARY_PDF)

    # ── 4. Look at the actual Investitionsprogramm from TOC (page 44) ──
    # The reversed text suggests landscape orientation
    dump_page(PRIMARY_PDF, 44, "Investitionsprogramm start")
    dump_page(PRIMARY_PDF, 45, "Investitionsprogramm page 2")
    dump_page(PRIMARY_PDF, 55, "Investitionsprogramm last page?")

    # ── 5. Produktgruppe level Teilergebnishaushalt (sample) ──
    dump_page(PRIMARY_PDF, 175, "PG 01.1.01 Personalmanagement")

    # ── 6. Secondary PDF: find structure ──
    print("\n\n" + "█" * 100)
    print("SECONDARY PDF: 2024/25 Beschluss")
    print("█" * 100)

    # Find Teilergebnishaushalt headers in 2024/25
    with pdfplumber.open(SECONDARY_PDF) as pdf:
        print(f"\nSearching for Teilergebnishaushalt headers in {SECONDARY_PDF.name}...")
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text() or ""
            first_line = text.split("\n")[0].strip() if text else ""
            if first_line.startswith("Teilergebnishaushalt") or first_line.startswith("Teilfinanzhaushalt"):
                print(f"  Page {page_num}: {first_line[:80]}")

    # The Fachbereich sections start at different pages in 2024/25
    # From TOC: FB1 starts at 154, so Teilergebnishaushalt should be early in that section
    dump_page(SECONDARY_PDF, 154, "FB1 start (2024/25)")
    dump_page(SECONDARY_PDF, 155, "FB1 page 2 (2024/25)")
    dump_page(SECONDARY_PDF, 156, "FB1 page 3 (2024/25)")

    # Find Investitionen pages in 2024/25
    with pdfplumber.open(SECONDARY_PDF) as pdf:
        print(f"\nSearching for Investitionen headers in {SECONDARY_PDF.name}...")
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text() or ""
            first_line = text.split("\n")[0].strip() if text else ""
            if first_line.startswith("Investitionen"):
                print(f"  Page {page_num}: {first_line[:80]}")

    # Main Investitionsprogramm in 2024/25 (from TOC: page 41)
    find_investitionsprogramm_pages(SECONDARY_PDF)
    dump_page(SECONDARY_PDF, 41, "Investitionsprogramm (2024/25)")
    dump_page(SECONDARY_PDF, 42, "Investitionsprogramm p2 (2024/25)")
    dump_page(SECONDARY_PDF, 48, "Investitionsprogramm last (2024/25)")

    # A Fachbereich Investitionen page in 2024/25
    dump_page(SECONDARY_PDF, 253, "FB3 Investitionen (2024/25) - already found")


if __name__ == "__main__":
    main()
