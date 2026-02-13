"""Parse pipeline – extract tables from PDFs based on tables.yaml definitions.

Usage:
    python -m pipeline.parse.parse [--tables tables.yaml] [--raw-dir data/raw] [--out-dir data/extracted]

Rules (from agents.md § 3):
  • No semantic interpretation – raw extraction only
  • Remove layout artifacts (headers/footers) but preserve raw data
  • Output: CSV per table + provenance metadata
"""

from __future__ import annotations

import csv
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import yaml

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TABLES = ROOT_DIR / "tables.yaml"
DEFAULT_RAW_DIR = ROOT_DIR / "data" / "raw"
DEFAULT_OUT_DIR = ROOT_DIR / "data" / "extracted"


# ── Number cleaning ──────────────────────────────────────────────────

def clean_number(raw: str | None) -> str | None:
    """Clean a German-formatted number string, return as-is (string).

    We do NOT convert to float here – that's the normalize step's job.
    We only strip whitespace and standardize formatting.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    return s


def clean_text(raw: str | None) -> str | None:
    """Collapse newlines and extra whitespace from a cell."""
    if not raw:
        return None
    s = raw.replace("\n", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s if s else None


# ── Table extraction ─────────────────────────────────────────────────

def is_header_row(row: list, header_marker: str | None) -> bool:
    """Detect if a row is a repeated header (to skip on multi-page tables)."""
    if not row:
        return False
    first = str(row[0] or "").strip()
    second = str(row[1] or "").strip() if len(row) > 1 else ""

    # Common header patterns
    if first == "Nr." or second == "Nr.":
        return True
    if header_marker and header_marker.lower() in first.lower():
        return True
    return False


def extract_table_from_pages(
    pdf_path: Path,
    pages: list[int],
    expected_columns: list[str],
    *,
    header_marker: str | None = None,
    skip_repeated_headers: bool = True,
) -> tuple[list[str], list[list[str | None]], list[dict]]:
    """Extract and merge a table spanning multiple PDF pages.

    Returns:
        (columns, rows, provenance_list)
    """
    all_rows: list[list[str | None]] = []
    provenance: list[dict] = []
    columns: list[str] = expected_columns
    n_cols = len(expected_columns)

    with pdfplumber.open(pdf_path) as pdf:
        for page_num in pages:
            if page_num < 1 or page_num > len(pdf.pages):
                logger.warning("Page %d out of range (PDF has %d pages)", page_num, len(pdf.pages))
                continue

            page = pdf.pages[page_num - 1]
            tables = page.extract_tables()

            if not tables:
                logger.warning("No table found on page %d", page_num)
                continue

            # Pick the table with the best column count match
            best_table = None
            best_score = -1
            for t in tables:
                if not t:
                    continue
                t_cols = len(t[0]) if t else 0
                score = -abs(t_cols - n_cols)  # prefer exact match
                if len(t) > 3:  # prefer tables with data
                    score += 10
                if score > best_score:
                    best_score = score
                    best_table = t

            if not best_table:
                logger.warning("No suitable table on page %d", page_num)
                continue

            for row_idx, row in enumerate(best_table):
                # Skip header rows (title row + repeated column headers)
                if skip_repeated_headers and is_header_row(row, header_marker):
                    continue

                # Skip empty rows
                if all(not str(c or "").strip() for c in row):
                    continue

                # Pad or trim to expected column count
                cleaned = []
                for i in range(n_cols):
                    cell = row[i] if i < len(row) else None
                    cleaned.append(cell)

                all_rows.append(cleaned)
                provenance.append({
                    "page": page_num,
                    "row_idx": row_idx,
                    "raw_cells": [str(c or "")[:50] for c in row[:n_cols]],
                })

    return columns, all_rows, provenance


# ── Main parse logic ─────────────────────────────────────────────────

def load_table_definitions(path: Path) -> list[dict]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("tables", [])


def parse_table(
    table_def: dict,
    raw_dir: Path,
    out_dir: Path,
) -> Path | None:
    """Parse a single table definition, write CSV + provenance JSON."""
    table_id = table_def["table_id"]
    document_id = table_def["document_id"]
    pdf_path = raw_dir / f"{document_id}.pdf"

    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        return None

    pages = table_def["pages"]
    expected_columns = table_def["expected_columns"]
    hints = table_def.get("extraction_hints", {})

    logger.info("PARSE %s (pages %s) from %s", table_id, pages, document_id)

    columns, rows, prov = extract_table_from_pages(
        pdf_path,
        pages,
        expected_columns,
        header_marker=hints.get("header_marker"),
        skip_repeated_headers=hints.get("skip_repeated_headers", True),
    )

    if not rows:
        logger.warning("No data extracted for %s", table_id)
        return None

    # Create output directory
    table_dir = out_dir / document_id / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)

    # Write CSV
    csv_path = table_dir / f"{table_id}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            cleaned = []
            for i, cell in enumerate(row):
                # First few columns are text/codes, rest are numbers
                if i <= 1 or (len(expected_columns) == 5 and i <= 2):
                    cleaned.append(clean_text(cell))
                else:
                    cleaned.append(clean_number(cell))
            writer.writerow(cleaned)

    # Write provenance
    prov_path = table_dir / f"{table_id}_provenance.json"
    prov_data = {
        "table_id": table_id,
        "document_id": document_id,
        "pages": pages,
        "columns": columns,
        "n_rows": len(rows),
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "rows": prov,
    }
    with open(prov_path, "w", encoding="utf-8") as f:
        json.dump(prov_data, f, indent=2, ensure_ascii=False)

    logger.info("  → %d rows → %s", len(rows), csv_path)
    return csv_path


def parse_all(
    tables_path: Path = DEFAULT_TABLES,
    raw_dir: Path = DEFAULT_RAW_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> list[Path]:
    """Parse all table definitions and return list of output CSV paths."""
    table_defs = load_table_definitions(tables_path)
    results = []

    for table_def in table_defs:
        csv_path = parse_table(table_def, raw_dir, out_dir)
        if csv_path:
            results.append(csv_path)

    logger.info("Parsed %d/%d tables successfully", len(results), len(table_defs))
    return results


# ── CLI ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Parse tables from PDFs based on tables.yaml")
    parser.add_argument("--tables", type=Path, default=DEFAULT_TABLES)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    parse_all(tables_path=args.tables, raw_dir=args.raw_dir, out_dir=args.out_dir)


if __name__ == "__main__":
    main()
