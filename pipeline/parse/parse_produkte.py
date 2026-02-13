"""Parse 'Gesamtübersicht über die Produkte' tables from Haushaltsplan PDFs.

This parser extracts product-level Zuschussbedarf (net cost per product) data.
It works by parsing text lines from PDF pages since the table has no grid lines.

Output: CSV files per document in data/extracted/{document_id}/tables/

Usage:
    python -m pipeline.parse.parse_produkte
"""

from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
EXTRACTED_DIR = ROOT_DIR / "data" / "extracted"

# ── Table definitions ────────────────────────────────────────────────
# Each document with its Gesamtübersicht pages and column structure.
# year_columns: list of (column_header, year, amount_type)
# - amount_type: "ist" for Ergebnis, "plan" for Ansatz
# The last column(s) are Zuschussbedarf/Einwohner which we skip.

@dataclass
class ProduktTableDef:
    document_id: str
    pdf_file: str
    pages: list[int]  # 1-based page numbers
    year_columns: list[tuple[str, int, str]]  # (label, year, amount_type)


PRODUKT_TABLES: list[ProduktTableDef] = [
    ProduktTableDef(
        document_id="haushaltsplan_2026_entwurf",
        pdf_file="haushaltsplan_2026_entwurf.pdf",
        pages=[107, 108],
        year_columns=[
            ("Ergebnis 2024", 2024, "ist"),
            ("Ansatz 2025", 2025, "plan"),
            ("Ansatz 2026", 2026, "plan"),
            # Column 4: Zuschussbedarf/Einwohner (skip)
        ],
    ),
    ProduktTableDef(
        document_id="haushaltsplan_2024_2025_beschluss",
        pdf_file="haushaltsplan_2024_2025_beschluss.pdf",
        pages=[104, 105],
        year_columns=[
            ("Ergebnis 2022", 2022, "ist"),
            ("Ansatz 2023", 2023, "plan"),
            ("Ansatz 2024", 2024, "plan"),
            ("Ansatz 2025", 2025, "plan"),
            # Columns 5-6: Zuschussbedarf/Einwohner (skip)
        ],
    ),
    ProduktTableDef(
        document_id="haushaltsplan_2023_beschluss",
        pdf_file="haushaltsplan_2023_beschluss.pdf",
        pages=[99, 100, 101],
        year_columns=[
            ("Ergebnis 2021", 2021, "ist"),
            ("Ansatz 2022", 2022, "plan"),
            ("Ansatz 2023", 2023, "plan"),
            # Column 4: Zuschussbedarf/Einwohner (skip)
        ],
    ),
    ProduktTableDef(
        document_id="haushaltsplan_2022_beschluss",
        pdf_file="haushaltsplan_2022_beschluss.pdf",
        pages=[105, 106, 107, 108],
        year_columns=[
            ("Ergebnis 2020", 2020, "ist"),
            ("Ansatz 2021", 2021, "plan"),
            ("Ansatz 2022", 2022, "plan"),
            # Column 4: Zuschussbedarf/Einwohner (skip)
        ],
    ),
    ProduktTableDef(
        document_id="haushaltsplan_2020_2021_beschluss",
        pdf_file="haushaltsplan_2020_2021_beschluss.pdf",
        pages=[105, 106, 107],
        year_columns=[
            ("Ergebnis 2018", 2018, "ist"),
            ("Ansatz 2019", 2019, "plan"),
            ("Ansatz 2020", 2020, "plan"),
            ("Ansatz 2021", 2021, "plan"),
            # Columns 5-6: Zuschussbedarf/Einwohner (skip)
        ],
    ),
    ProduktTableDef(
        document_id="haushaltsplan_2019",
        pdf_file="haushaltsplan_2019.pdf",
        pages=[99, 100, 101],
        year_columns=[
            ("Ansatz 2019", 2019, "plan"),
            ("Ansatz 2018", 2018, "plan"),
            ("Ergebnis 2017", 2017, "ist"),
            # Column 4: Zuschussbedarf/Einwohner (skip)
        ],
    ),
    ProduktTableDef(
        document_id="haushaltsplan_2017_2018",
        pdf_file="haushaltsplan_2017_2018.pdf",
        pages=[117, 118, 119],
        year_columns=[
            ("Ansatz 2018", 2018, "plan"),
            ("Ansatz 2017", 2017, "plan"),
            ("Ansatz 2016", 2016, "plan"),
            ("Ergebnis 2015", 2015, "ist"),
            # Columns 5-6: Zuschussbedarf/Einwohner (skip)
        ],
    ),
]


# ── Number parsing ───────────────────────────────────────────────────

GERMAN_NUM_PATTERN = re.compile(r'^-?\d[\d.]*$')

def parse_german_number(s: str | None) -> float | None:
    """Parse a German-formatted integer (dots as thousands separators)."""
    if not s:
        return None
    s = s.strip()
    if not s or s == '-':
        return None
    # Remove thousand separators
    cleaned = s.replace('.', '')
    try:
        return float(cleaned)
    except ValueError:
        return None


# ── Product line detection ───────────────────────────────────────────

# Product number pattern: 01.1.01, 04.2.03, 14.1.01
PRODUCT_NR_PATTERN = re.compile(r'^(\d{2}\.\d\.\d{2})\s+(.+)')

# Fachbereich header: "1 Zentrale Dienste", "4 Soziales", "14 Sonderbudget ..."
FACHBEREICH_PATTERN = re.compile(r'^(\d{1,2})\s+([A-ZÄÖÜ].+)')

# Productgroup header: "1.1 Personal", "4.2 Jugend"
PRODUCTGROUP_PATTERN = re.compile(r'^(\d{1,2}\.\d)\s+(.+)')

# Skip patterns
SKIP_PATTERNS = [
    re.compile(r'^Seite\s+\d+'),
    re.compile(r'^Gesamtübersicht'),
    re.compile(r'^Ergebnis|^Ansatz|^Zuschussbedarf|^pro Einwohner'),
    re.compile(r'^\d{4}$'),  # Standalone year
    re.compile(r'^Statistische Daten'),
    re.compile(r'^Einwohner mit'),
    re.compile(r'^Budgetübersicht'),
    re.compile(r'^gemäß'),
    re.compile(r'^Produktbereich'),
]


@dataclass
class ProductRow:
    """A parsed product row."""
    produkt_nr: str  # e.g. "04.1.01"
    bezeichnung: str  # e.g. "Kinderkrippen"
    amounts: list[float | None]  # One per year_column
    page: int  # 1-based
    fachbereich_nr: str = ""
    fachbereich_name: str = ""
    productgroup_nr: str = ""
    productgroup_name: str = ""


def extract_text_lines(pdf_path: Path, pages: list[int]) -> list[tuple[str, int]]:
    """Extract clean text lines from specified PDF pages.

    Returns list of (line_text, page_number) tuples.
    Uses extract_text() which handles word merging correctly.
    """
    pdf = pdfplumber.open(str(pdf_path))
    result = []

    for page_num in pages:
        if page_num - 1 >= len(pdf.pages):
            logger.warning("Page %d not found in %s", page_num, pdf_path.name)
            continue
        page = pdf.pages[page_num - 1]
        text = page.extract_text() or ''

        for line in text.split('\n'):
            line = line.strip()
            if line:
                result.append((line, page_num))

    pdf.close()
    return result


def parse_product_lines(
    lines: list[tuple[str, int]],
    n_year_cols: int,
) -> list[ProductRow]:
    """Parse text lines into ProductRow objects.

    Args:
        lines: List of (text, page_number) tuples
        n_year_cols: Number of year/amount columns expected
    """
    products: list[ProductRow] = []
    current_fb_nr = ""
    current_fb_name = ""
    current_pg_nr = ""
    current_pg_name = ""

    for line_text, page_num in lines:
        # Skip known non-data lines
        if any(p.match(line_text) for p in SKIP_PATTERNS):
            continue

        # Skip empty or whitespace-only
        if not line_text.strip():
            continue

        # Check for Fachbereich header
        m = FACHBEREICH_PATTERN.match(line_text)
        if m:
            nr = m.group(1)
            name = m.group(2).strip()
            # Fachbereich headers don't have numeric amounts
            # Check for actual number-like tokens (must contain digits)
            amounts_part = re.findall(r'-?\d[\d.]*', name)
            if not amounts_part:
                current_fb_nr = nr
                current_fb_name = name
                continue

        # Check for Productgroup header
        m = PRODUCTGROUP_PATTERN.match(line_text)
        if m:
            nr = m.group(1)
            name = m.group(2).strip()
            # Productgroup headers typically don't have amounts
            # But filter out false positives where text contains product numbers
            if not PRODUCT_NR_PATTERN.match(line_text):
                current_pg_nr = nr
                current_pg_name = name
                continue

        # Check for Product line
        m = PRODUCT_NR_PATTERN.match(line_text)
        if m:
            produkt_nr = m.group(1)
            rest = m.group(2).strip()

            # Split rest into name and amounts
            # Amounts are German numbers at the end: "Kinderkrippen 1.087.723 687.974 802.803 27,87"
            # The last value might be Zuschussbedarf/Einwohner (with comma for decimals)
            parts = rest.split()

            # Find where amounts start: scan from the end
            # Amounts match: -?[0-9.]+ or -?[0-9.]+,[0-9]+
            amount_pattern = re.compile(r'^-?[\d.]+(?:,\d+)?$')
            first_amount_idx = len(parts)
            for i in range(len(parts) - 1, -1, -1):
                if amount_pattern.match(parts[i]):
                    first_amount_idx = i
                else:
                    break

            bezeichnung = ' '.join(parts[:first_amount_idx])
            raw_amounts = parts[first_amount_idx:]

            # Parse amounts
            # We expect n_year_cols amount columns + possibly 1-2 Zuschussbedarf/Einwohner columns
            # The Zuschussbedarf/Einwohner columns have commas (e.g., "27,87")
            # Regular amounts don't have commas (they use dots only as thousands sep)
            
            year_amounts: list[float | None] = []
            for val in raw_amounts:
                if ',' in val:
                    # This is Zuschussbedarf/Einwohner, stop collecting year amounts
                    break
                year_amounts.append(parse_german_number(val))

            # Right-align: if we got fewer amounts than expected year columns,
            # pad with None at the front (products only having later-year data)
            amounts: list[float | None] = []
            if len(year_amounts) < n_year_cols:
                amounts = [None] * (n_year_cols - len(year_amounts)) + year_amounts
            else:
                amounts = year_amounts[:n_year_cols]

            products.append(ProductRow(
                produkt_nr=produkt_nr,
                bezeichnung=bezeichnung,
                amounts=amounts,
                page=page_num,
                fachbereich_nr=current_fb_nr,
                fachbereich_name=current_fb_name,
                productgroup_nr=current_pg_nr,
                productgroup_name=current_pg_name,
            ))

    return products


def parse_produkt_table(table_def: ProduktTableDef) -> list[dict]:
    """Parse a single Produktübersicht table and return line_items.

    Returns list of dicts with standard line_item fields.
    """
    pdf_path = RAW_DIR / table_def.pdf_file
    if not pdf_path.exists():
        logger.warning("PDF not found: %s", pdf_path)
        return []

    logger.info("Parsing %s pages %s ...", table_def.pdf_file, table_def.pages)

    # Extract text lines
    lines = extract_text_lines(pdf_path, table_def.pages)
    logger.info("  Extracted %d text lines", len(lines))

    # Parse product rows
    n_year_cols = len(table_def.year_columns)
    products = parse_product_lines(lines, n_year_cols)
    logger.info("  Found %d products", len(products))

    # Convert to line_items (one per product × year)
    line_items = []
    provenance_rows = []

    for prod in products:
        for col_idx, (col_label, year, amount_type) in enumerate(table_def.year_columns):
            amount = prod.amounts[col_idx] if col_idx < len(prod.amounts) else None
            if amount is None:
                continue

            # Build a stable key
            key = f"produktuebersicht:{prod.produkt_nr}:{prod.bezeichnung.lower().replace(' ', '_')}"

            line_items.append({
                "line_item_key": key,
                "year": year,
                "amount": amount,
                "amount_type": amount_type,
                "unit": "EUR",
                "haushalt_type": "produktuebersicht",
                "nr": prod.produkt_nr,
                "bezeichnung": prod.bezeichnung,
                "document_id": table_def.document_id,
                "table_id": f"produktuebersicht_{table_def.document_id}",
                "page": prod.page,
                "row_idx": len(provenance_rows),
                "confidence": 1.0,
                "fachbereich_nr": prod.fachbereich_nr,
                "fachbereich_name": prod.fachbereich_name,
                "productgroup_nr": prod.productgroup_nr,
                "productgroup_name": prod.productgroup_name,
            })

        provenance_rows.append({
            "produkt_nr": prod.produkt_nr,
            "bezeichnung": prod.bezeichnung,
            "page": prod.page,
            "fachbereich": f"{prod.fachbereich_nr} {prod.fachbereich_name}",
            "productgroup": f"{prod.productgroup_nr} {prod.productgroup_name}",
        })

    return line_items


def write_csv(line_items: list[dict], table_def: ProduktTableDef) -> Path:
    """Write parsed line_items as CSV to the extracted directory."""
    out_dir = EXTRACTED_DIR / table_def.document_id / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)

    table_id = f"produktuebersicht_{table_def.document_id}"
    csv_path = out_dir / f"{table_id}.csv"

    if not line_items:
        logger.warning("No line items for %s", table_def.document_id)
        return csv_path

    # Determine fieldnames from first item
    fieldnames = list(line_items[0].keys())

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(line_items)

    logger.info("  Wrote %d rows → %s", len(line_items), csv_path)

    # Also write provenance
    prov_path = out_dir / f"{table_id}_provenance.json"
    prov_data = {
        "table_id": table_id,
        "document_id": table_def.document_id,
        "pages": table_def.pages,
        "year_columns": [(label, year, atype) for label, year, atype in table_def.year_columns],
        "total_products": len(set(item["nr"] for item in line_items)),
        "total_line_items": len(line_items),
    }
    with open(prov_path, 'w', encoding='utf-8') as f:
        json.dump(prov_data, f, indent=2, ensure_ascii=False)

    return csv_path


def parse_all_produkte() -> list[dict]:
    """Parse all Produktübersicht tables and return combined line_items."""
    all_items = []

    for table_def in PRODUKT_TABLES:
        items = parse_produkt_table(table_def)
        write_csv(items, table_def)
        all_items.extend(items)

    logger.info("Total Produktübersicht line_items: %d", len(all_items))
    return all_items


# ── CLI ──────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )

    all_items = parse_all_produkte()

    if all_items:
        # Summary
        import pandas as pd
        df = pd.DataFrame(all_items)
        print(f"\n{'='*60}")
        print(f"Produktübersicht: {len(df)} line_items")
        print(f"{'='*60}")
        print(f"Produkte:     {df['nr'].nunique()}")
        print(f"Dokumente:    {df['document_id'].nunique()}")
        print(f"Jahre:        {sorted(df['year'].unique())}")
        print(f"\nPro Dokument:")
        for doc_id, grp in df.groupby('document_id'):
            print(f"  {doc_id}: {grp['nr'].nunique()} Produkte, {len(grp)} Zeilen, Jahre {sorted(grp['year'].unique())}")
        print(f"\nPro Fachbereich (letztes Dokument):")
        latest = df[df['document_id'] == df['document_id'].max()]
        for fb, grp in latest.groupby('fachbereich_nr'):
            fb_name = grp['fachbereich_name'].iloc[0]
            total = grp.groupby('nr')['amount'].first().sum()
            print(f"  FB{fb} {fb_name}: {grp['nr'].nunique()} Produkte, Zuschussbedarf {total:,.0f} EUR")


if __name__ == "__main__":
    main()
