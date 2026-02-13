#!/usr/bin/env python3
"""
Analyze Rödermark municipal budget PDFs for Teilhaushalte and Investitionsprogramm structure.
Scans all pages, extracts sample tables, and compares across PDFs.
"""

import pdfplumber
import re
import json
from collections import defaultdict
from pathlib import Path

RAW_DIR = Path("data/raw")

# PDFs to analyze (primary + secondary for comparison)
PRIMARY_PDF = RAW_DIR / "haushaltsplan_2026_entwurf.pdf"
SECONDARY_PDF = RAW_DIR / "haushaltsplan_2024_2025_beschluss.pdf"

# Search patterns
TEILHAUSHALT_PATTERNS = [
    re.compile(r"Teilhaushalt", re.IGNORECASE),
    re.compile(r"Teilergebnishaushalt", re.IGNORECASE),
    re.compile(r"Teilfinanzhaushalt", re.IGNORECASE),
    re.compile(r"Produktbereich", re.IGNORECASE),
]

INVESTITION_PATTERNS = [
    re.compile(r"Investitionsprogramm", re.IGNORECASE),
    re.compile(r"Investitionsmaßnahm", re.IGNORECASE),
    re.compile(r"Investitions[uü]bersicht", re.IGNORECASE),
]


def extract_text_pages(pdf_path, patterns, label):
    """Scan all pages for text matching patterns. Return dict of pattern -> list of (page_num, matched_text_snippet)."""
    results = defaultdict(list)
    print(f"\n{'='*80}")
    print(f"Scanning {pdf_path.name} for {label}...")
    print(f"{'='*80}")

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"Total pages: {total_pages}")

        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text() or ""

            for pattern in patterns:
                if pattern.search(text):
                    # Get the line containing the match
                    for line in text.split("\n"):
                        if pattern.search(line):
                            results[pattern.pattern].append((page_num, line.strip()[:120]))
                            break

            if page_num % 50 == 0:
                print(f"  ...scanned {page_num}/{total_pages} pages")

    return results


def find_teilhaushalt_sections(pdf_path):
    """Find all Teilhaushalt sections with detailed structure info."""
    print(f"\n{'='*80}")
    print(f"TEILHAUSHALTE ANALYSIS: {pdf_path.name}")
    print(f"{'='*80}")

    teilhaushalte = []
    current_th = None
    teilergebnis_pages = []
    teilfinanz_pages = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text() or ""

            # Look for Teilhaushalt headers (e.g. "Teilhaushalt 01 - Zentrale Verwaltung")
            th_match = re.search(
                r"Teilhaushalt\s+(\d{1,2})\s*[-–]\s*(.+?)(?:\n|$)", text
            )
            if th_match:
                th_num = th_match.group(1).strip()
                th_name = th_match.group(2).strip()
                key = f"{th_num} - {th_name}"
                if current_th is None or current_th["key"] != key:
                    current_th = {
                        "key": key,
                        "number": th_num,
                        "name": th_name,
                        "first_page": page_num,
                        "last_page": page_num,
                        "teilergebnis_pages": [],
                        "teilfinanz_pages": [],
                    }
                    teilhaushalte.append(current_th)
                else:
                    current_th["last_page"] = page_num

            # Track Teilergebnishaushalt / Teilfinanzhaushalt pages
            if current_th:
                if re.search(r"Teilergebnishaushalt", text, re.IGNORECASE):
                    current_th["teilergebnis_pages"].append(page_num)
                    teilergebnis_pages.append(page_num)
                if re.search(r"Teilfinanzhaushalt", text, re.IGNORECASE):
                    current_th["teilfinanz_pages"].append(page_num)
                    teilfinanz_pages.append(page_num)
                current_th["last_page"] = max(current_th["last_page"], page_num)

            if page_num % 50 == 0:
                print(f"  ...scanned {page_num}/{total_pages} pages")

    # Print summary
    print(f"\nFound {len(teilhaushalte)} Teilhaushalte:")
    for th in teilhaushalte:
        print(
            f"  TH {th['number']:>2s} - {th['name']:<40s} pages {th['first_page']}-{th['last_page']}"
        )
        if th["teilergebnis_pages"]:
            print(f"         Teilergebnishaushalt on pages: {th['teilergebnis_pages'][:5]}")
        if th["teilfinanz_pages"]:
            print(f"         Teilfinanzhaushalt on pages: {th['teilfinanz_pages'][:5]}")

    print(f"\nAll Teilergebnishaushalt pages: {teilergebnis_pages[:20]}{'...' if len(teilergebnis_pages) > 20 else ''}")
    print(f"All Teilfinanzhaushalt pages: {teilfinanz_pages[:20]}{'...' if len(teilfinanz_pages) > 20 else ''}")

    return teilhaushalte, teilergebnis_pages, teilfinanz_pages


def extract_sample_table(pdf_path, page_num, label=""):
    """Extract and display a sample table from a specific page."""
    print(f"\n--- Sample table from page {page_num} ({label}) in {pdf_path.name} ---")

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num - 1]
        text = page.extract_text() or ""

        # Show first 30 lines of text
        lines = text.split("\n")
        print(f"Page text ({len(lines)} lines):")
        for j, line in enumerate(lines[:40]):
            print(f"  {j+1:3d}: {line}")
        if len(lines) > 40:
            print(f"  ... ({len(lines) - 40} more lines)")

        # Extract tables
        tables = page.extract_tables()
        print(f"\nTables found by pdfplumber: {len(tables)}")
        for t_idx, table in enumerate(tables):
            print(f"\n  Table {t_idx + 1}: {len(table)} rows")
            if table:
                # Show headers and first few rows
                for r_idx, row in enumerate(table[:8]):
                    cells = [str(c)[:25] if c else "" for c in row]
                    print(f"    Row {r_idx}: {cells}")
                if len(table) > 8:
                    print(f"    ... ({len(table) - 8} more rows)")
                # Show column count
                col_counts = [len(row) for row in table if row]
                print(f"    Column counts: min={min(col_counts)}, max={max(col_counts)}")


def find_investitionsprogramm(pdf_path):
    """Find Investitionsprogramm sections."""
    print(f"\n{'='*80}")
    print(f"INVESTITIONSPROGRAMM ANALYSIS: {pdf_path.name}")
    print(f"{'='*80}")

    invest_pages = []
    invest_sections = []
    current_section = None

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text() or ""

            is_invest = False
            section_title = None

            # Check for Investitionsprogramm
            if re.search(r"Investitionsprogramm", text, re.IGNORECASE):
                is_invest = True
                m = re.search(r"(Investitionsprogramm[^\n]*)", text, re.IGNORECASE)
                if m:
                    section_title = m.group(1).strip()[:100]

            # Check for Investitionsmaßnahme / Investitionsübersicht
            if re.search(r"Investitionsmaßnahm|Investitions[uü]bersicht|Einzelinvestition", text, re.IGNORECASE):
                is_invest = True
                if not section_title:
                    m = re.search(r"(Investitions[^\n]*)", text, re.IGNORECASE)
                    if m:
                        section_title = m.group(1).strip()[:100]

            if is_invest:
                invest_pages.append(page_num)
                if current_section is None or page_num - current_section["last_page"] > 3:
                    current_section = {
                        "title": section_title or "Unknown",
                        "first_page": page_num,
                        "last_page": page_num,
                        "pages": [page_num],
                    }
                    invest_sections.append(current_section)
                else:
                    current_section["last_page"] = page_num
                    current_section["pages"].append(page_num)

            if page_num % 50 == 0:
                print(f"  ...scanned {page_num}/{total_pages} pages")

    print(f"\nFound {len(invest_pages)} pages with investment content")
    print(f"Grouped into {len(invest_sections)} sections:")
    for sec in invest_sections:
        print(
            f"  Pages {sec['first_page']}-{sec['last_page']} ({len(sec['pages'])} pages): {sec['title']}"
        )

    return invest_pages, invest_sections


def deep_scan_teilergebnis(pdf_path, sample_page):
    """Do a deep scan of a Teilergebnishaushalt page to understand column structure."""
    print(f"\n{'='*80}")
    print(f"DEEP SCAN: Teilergebnishaushalt page {sample_page} in {pdf_path.name}")
    print(f"{'='*80}")

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[sample_page - 1]

        # Extract with different table settings
        text = page.extract_text() or ""
        lines = text.split("\n")

        print(f"\nFull page text ({len(lines)} lines):")
        for j, line in enumerate(lines):
            print(f"  {j+1:3d}: {line}")

        # Try table extraction with different strategies
        tables_default = page.extract_tables()
        print(f"\nDefault table extraction: {len(tables_default)} tables")
        for t_idx, table in enumerate(tables_default):
            print(f"  Table {t_idx+1}: {len(table)} rows x {max(len(r) for r in table) if table else 0} cols")
            for r_idx, row in enumerate(table[:15]):
                cells = [str(c)[:30] if c else "" for c in row]
                print(f"    {r_idx:3d}: {cells}")
            if len(table) > 15:
                print(f"    ... ({len(table)-15} more rows)")

        # Try with explicit vertical strategy
        tables_text = page.extract_tables(
            table_settings={"vertical_strategy": "text", "horizontal_strategy": "text"}
        )
        if tables_text and (not tables_default or len(tables_text) != len(tables_default)):
            print(f"\nText-strategy table extraction: {len(tables_text)} tables")
            for t_idx, table in enumerate(tables_text):
                print(f"  Table {t_idx+1}: {len(table)} rows x {max(len(r) for r in table) if table else 0} cols")
                for r_idx, row in enumerate(table[:10]):
                    cells = [str(c)[:30] if c else "" for c in row]
                    print(f"    {r_idx:3d}: {cells}")


def deep_scan_investition(pdf_path, sample_page):
    """Do a deep scan of an Investitionsprogramm page."""
    print(f"\n{'='*80}")
    print(f"DEEP SCAN: Investitionsprogramm page {sample_page} in {pdf_path.name}")
    print(f"{'='*80}")

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[sample_page - 1]

        text = page.extract_text() or ""
        lines = text.split("\n")

        print(f"\nFull page text ({len(lines)} lines):")
        for j, line in enumerate(lines):
            print(f"  {j+1:3d}: {line}")

        tables = page.extract_tables()
        print(f"\nDefault table extraction: {len(tables)} tables")
        for t_idx, table in enumerate(tables):
            print(f"  Table {t_idx+1}: {len(table)} rows x {max(len(r) for r in table) if table else 0} cols")
            for r_idx, row in enumerate(table[:15]):
                cells = [str(c)[:30] if c else "" for c in row]
                print(f"    {r_idx:3d}: {cells}")
            if len(table) > 15:
                print(f"    ... ({len(table)-15} more rows)")


def scan_all_page_headers(pdf_path):
    """Scan all pages and extract the first non-empty line to build a TOC-like overview."""
    print(f"\n{'='*80}")
    print(f"PAGE HEADER SCAN: {pdf_path.name}")
    print(f"{'='*80}")

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        print(f"Total pages: {total}")

        # Only show pages that contain our keywords
        keywords = [
            "Teilhaushalt", "Teilergebnis", "Teilfinanz",
            "Investition", "Gesamtergebnis", "Gesamtfinanz",
            "Produktbereich", "Produktgruppe",
            "Inhaltsverzeichnis", "Vorbericht",
        ]

        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text() or ""
            first_lines = "\n".join(text.split("\n")[:3])

            for kw in keywords:
                if kw.lower() in text.lower():
                    # Get the relevant line
                    for line in text.split("\n")[:10]:
                        if kw.lower() in line.lower():
                            print(f"  Page {page_num:4d}: {line.strip()[:100]}")
                            break
                    break


def main():
    print("=" * 80)
    print("RÖDERMARK BUDGET PDF STRUCTURE ANALYSIS")
    print("=" * 80)

    # ── Phase 1: Quick overview scan of primary PDF ──
    print("\n\n" + "█" * 80)
    print("PHASE 1: OVERVIEW SCAN OF PRIMARY PDF")
    print("█" * 80)
    scan_all_page_headers(PRIMARY_PDF)

    # ── Phase 2: Teilhaushalte analysis ──
    print("\n\n" + "█" * 80)
    print("PHASE 2: TEILHAUSHALTE ANALYSIS")
    print("█" * 80)

    th_list, te_pages, tf_pages = find_teilhaushalt_sections(PRIMARY_PDF)

    # Deep scan first Teilergebnishaushalt page
    if te_pages:
        deep_scan_teilergebnis(PRIMARY_PDF, te_pages[0])
        # Also scan a second one if available to check consistency
        if len(te_pages) > 2:
            deep_scan_teilergebnis(PRIMARY_PDF, te_pages[2])

    # Deep scan first Teilfinanzhaushalt page
    if tf_pages:
        deep_scan_teilergebnis(PRIMARY_PDF, tf_pages[0])

    # ── Phase 3: Investitionsprogramm analysis ──
    print("\n\n" + "█" * 80)
    print("PHASE 3: INVESTITIONSPROGRAMM ANALYSIS")
    print("█" * 80)

    inv_pages, inv_sections = find_investitionsprogramm(PRIMARY_PDF)

    # Deep scan first and second Investitionsprogramm pages
    if inv_pages:
        deep_scan_investition(PRIMARY_PDF, inv_pages[0])
        if len(inv_pages) > 1:
            deep_scan_investition(PRIMARY_PDF, inv_pages[1])
        # Also check a page in the middle
        if len(inv_pages) > 5:
            mid = len(inv_pages) // 2
            deep_scan_investition(PRIMARY_PDF, inv_pages[mid])

    # ── Phase 4: Compare with secondary PDF ──
    print("\n\n" + "█" * 80)
    print("PHASE 4: COMPARISON WITH SECONDARY PDF")
    print("█" * 80)

    th_list2, te_pages2, tf_pages2 = find_teilhaushalt_sections(SECONDARY_PDF)
    inv_pages2, inv_sections2 = find_investitionsprogramm(SECONDARY_PDF)

    # Deep scan one sample from secondary
    if te_pages2:
        deep_scan_teilergebnis(SECONDARY_PDF, te_pages2[0])
    if inv_pages2:
        deep_scan_investition(SECONDARY_PDF, inv_pages2[0])

    # ── Phase 5: Summary comparison ──
    print("\n\n" + "█" * 80)
    print("PHASE 5: SUMMARY & COMPARISON")
    print("█" * 80)

    print(f"\n{'Metric':<45s} {'2026 Entwurf':>15s} {'2024/25 Beschluss':>18s}")
    print("-" * 80)
    print(f"{'Number of Teilhaushalte':<45s} {len(th_list):>15d} {len(th_list2):>18d}")
    print(f"{'Teilergebnishaushalt pages':<45s} {len(te_pages):>15d} {len(te_pages2):>18d}")
    print(f"{'Teilfinanzhaushalt pages':<45s} {len(tf_pages):>15d} {len(tf_pages2):>18d}")
    print(f"{'Investitionsprogramm pages':<45s} {len(inv_pages):>15d} {len(inv_pages2):>18d}")
    print(f"{'Investitionsprogramm sections':<45s} {len(inv_sections):>15d} {len(inv_sections2):>18d}")

    # Compare Teilhaushalt names
    print("\n\nTeilhaushalte comparison:")
    names1 = {th["number"]: th["name"] for th in th_list}
    names2 = {th["number"]: th["name"] for th in th_list2}
    all_nums = sorted(set(list(names1.keys()) + list(names2.keys())))
    print(f"  {'TH#':<5s} {'2026 Entwurf':<40s} {'2024/25 Beschluss':<40s}")
    print(f"  {'-'*85}")
    for num in all_nums:
        n1 = names1.get(num, "---")
        n2 = names2.get(num, "---")
        diff = " <-- DIFFERENT" if n1 != n2 and n1 != "---" and n2 != "---" else ""
        only = " <-- ONLY IN 2026" if n2 == "---" else (" <-- ONLY IN 2024/25" if n1 == "---" else "")
        print(f"  {num:<5s} {n1:<40s} {n2:<40s}{diff}{only}")

    print("\n\nDone!")


if __name__ == "__main__":
    main()
