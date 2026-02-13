"""Specialized parser for Jahresabschluss and Gesamtabschluss PDFs.

These PDFs have a different table format than Haushaltspläne:
  • Column header "Pos." instead of "Nr."
  • Multi-row merged cells: Pos values like "010\n020\n030\n..."
  • Extra "Konten" column and "VERGLEICH" column
  • Column headers like "ERGEBNIS\n2022" instead of "Ergebnis 2022"
  • The Ergebnisrechnung repeats per Teilhaushalt; we need the
    Gesamtstadt page (identified by large amounts > 10 Mio in Pos 100).

Strategy: extract summary rows (100, 190, 200, 240, 320 etc.) from
the Gesamtstadt Ergebnisrechnung and output a CSV with the same
columns as the Haushaltsplan tables (Nr., Bezeichnung, ...) so the
normalizer can handle them uniformly.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = ROOT_DIR / "data" / "raw"
DEFAULT_OUT_DIR = ROOT_DIR / "data" / "extracted"


def parse_german_number(s: str | None) -> float | None:
    """Parse a German number string (e.g. '-70.913.613,43') into float."""
    if not s or not s.strip():
        return None
    s = s.strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


# ── Column header normalization ──────────────────────────────────────

HEADER_PATTERN = re.compile(r"(ERGEBNIS|ANSATZ)\s*(\d{4})", re.IGNORECASE)

def normalize_ja_headers(raw_headers: list[str | None]) -> list[str]:
    """Normalize JA column headers to the HP convention.

    'ERGEBNIS\\n2022' → 'Ergebnis 2022'
    'ANSATZ\\n2023'   → 'Ansatz 2023'
    'VERGLEICH...'    → skip (we won't include it)
    """
    result = []
    for h in raw_headers:
        if not h:
            result.append("")
            continue
        # Collapse whitespace/newlines
        flat = re.sub(r"\s+", " ", h.strip())
        # VERGLEICH must be checked FIRST — it also contains "ERGEBNIS"
        if "VERGLEICH" in flat.upper():
            result.append("_SKIP_")
        elif "Pos" in flat:
            result.append("Nr.")
        elif "Konten" in flat:
            result.append("_KONTEN_")
        elif "Bezeichnung" in flat:
            result.append("Bezeichnung")
        else:
            m = HEADER_PATTERN.search(flat)
            if m:
                kind = m.group(1).capitalize()  # Ergebnis / Ansatz
                year = m.group(2)
                result.append(f"{kind} {year}")
            else:
                result.append(flat)
    return result


# ── Summary row extraction ───────────────────────────────────────────

# We only keep "summary" Pos values (three-digit: 100, 125, 190, 200, 230, 240, 270, 280, 310, 320)
SUMMARY_POS = {
    "100", "125", "190", "200", "230", "240", "270", "280", "310", "320",
}


def is_gesamtstadt_table(tbl: list[list]) -> bool:
    """Heuristic: the Gesamtstadt table has Pos 100 with amount > 10 Mio."""
    for row in tbl:
        pos = str(row[0] or "").strip()
        if pos == "100" and len(row) > 3:
            val = parse_german_number(str(row[3] or ""))
            if val is not None and abs(val) > 10_000_000:
                return True
    return False


def extract_ergebnisrechnung(
    pdf_path: Path,
    *,
    max_pages: int = 50,
) -> tuple[list[str], list[list[str]], int | None]:
    """Find and extract the Gesamtstadt Ergebnisrechnung from a JA PDF.

    Returns:
        (columns, data_rows, page_number)
        columns are normalized to HP convention: ['Nr.', 'Bezeichnung', 'Ergebnis 2022', ...]
        data_rows contain only summary positions.
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx in range(min(max_pages, len(pdf.pages))):
            page = pdf.pages[page_idx]
            tables = page.extract_tables()
            if not tables:
                continue

            for tbl in tables:
                if len(tbl) < 20:
                    continue

                # Check header for Pos + ERGEBNIS
                header = tbl[0]
                has_pos = any("Pos" in str(c) for c in header if c)
                has_ergebnis = any("ERGEBNIS" in str(c).upper() for c in header if c)
                if not (has_pos and has_ergebnis):
                    continue

                # Check if this is the Gesamtstadt table
                if not is_gesamtstadt_table(tbl):
                    continue

                logger.info("Found Gesamtstadt Ergebnisrechnung on page %d", page_idx + 1)

                # Normalize headers
                norm_headers = normalize_ja_headers([str(c) if c else "" for c in header])

                # Build output columns: Nr., Bezeichnung, then year columns
                out_cols = ["Nr.", "Bezeichnung"]
                year_col_indices = []
                for ci, h in enumerate(norm_headers):
                    if h.startswith("Ergebnis ") or h.startswith("Ansatz "):
                        out_cols.append(h)
                        year_col_indices.append(ci)

                # Extract summary rows
                data_rows = []
                for row in tbl[1:]:  # skip header
                    pos_raw = str(row[0] or "").strip()
                    # The Pos cell might have multiple values joined by \n
                    # For summary rows, it's a single value like "100", "190"
                    pos_values = [p.strip() for p in pos_raw.split("\n") if p.strip()]

                    # Check if any of the Pos values is a summary position
                    if len(pos_values) == 1 and pos_values[0] in SUMMARY_POS:
                        pos = pos_values[0]
                    elif not pos_values:
                        # Empty pos — might be a continuation row, skip
                        continue
                    else:
                        # Multi-pos cell like "010\n020\n030..." — not a summary row
                        continue

                    # Get Bezeichnung (might have \n — collapse)
                    bez_idx = norm_headers.index("Bezeichnung") if "Bezeichnung" in norm_headers else 2
                    bez = re.sub(r"\s+", " ", str(row[bez_idx] or "").strip())

                    # Get year amounts
                    out_row = [pos, bez]
                    for ci in year_col_indices:
                        val = str(row[ci] or "").strip() if ci < len(row) else ""
                        out_row.append(val)

                    data_rows.append(out_row)

                return out_cols, data_rows, page_idx + 1

    return [], [], None


def extract_gesamtabschluss_ergebnisrechnung(
    pdf_path: Path,
    *,
    max_pages: int = 30,
) -> tuple[list[str], list[list[str]], int | None]:
    """Extract the consolidated Ergebnisrechnung from a Gesamtabschluss PDF.

    Gesamtabschlüsse have a simpler format on page 6:
    Pos., Konten, Bezeichnung, ERGEBNIS 2020, ERGEBNIS 2021
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx in range(min(max_pages, len(pdf.pages))):
            page = pdf.pages[page_idx]
            tables = page.extract_tables()
            if not tables:
                continue

            for tbl in tables:
                if len(tbl) < 10:
                    continue

                header = tbl[0]
                has_pos = any("Pos" in str(c) for c in header if c)
                has_ergebnis = any("ERGEBNIS" in str(c).upper() for c in header if c)
                if not (has_pos and has_ergebnis):
                    continue

                # Check for Pos 100 (Summe ordentliche Erträge)
                has_pos100 = any(str(row[0] or "").strip() == "100" for row in tbl)
                if not has_pos100:
                    continue

                logger.info("Found Gesamtabschluss Ergebnisrechnung on page %d", page_idx + 1)

                norm_headers = normalize_ja_headers([str(c) if c else "" for c in header])

                out_cols = ["Nr.", "Bezeichnung"]
                year_col_indices = []
                for ci, h in enumerate(norm_headers):
                    if h.startswith("Ergebnis ") or h.startswith("Ansatz "):
                        out_cols.append(h)
                        year_col_indices.append(ci)

                # Extract rows — Gesamtabschluss has cleaner Pos values
                data_rows = []
                for row in tbl[1:]:
                    pos_raw = str(row[0] or "").strip()
                    pos_values = [p.strip() for p in pos_raw.split("\n") if p.strip()]

                    if not pos_values:
                        continue

                    # Accept both summary and detail positions
                    pos = pos_values[0]
                    if not pos.isdigit():
                        continue

                    bez_idx = norm_headers.index("Bezeichnung") if "Bezeichnung" in norm_headers else 2
                    bez = re.sub(r"\s+", " ", str(row[bez_idx] or "").strip())

                    out_row = [pos, bez]
                    for ci in year_col_indices:
                        val_raw = str(row[ci] or "").strip() if ci < len(row) else ""
                        # GA cells might have \n-merged values — take first line for summary
                        val = val_raw.split("\n")[0].strip() if val_raw else ""
                        out_row.append(val)

                    data_rows.append(out_row)

                return out_cols, data_rows, page_idx + 1

    return [], [], None


# ── Write output ─────────────────────────────────────────────────────

def write_table(
    table_id: str,
    document_id: str,
    columns: list[str],
    rows: list[list[str]],
    page: int | None,
    out_dir: Path,
) -> Path | None:
    """Write extracted data as CSV + provenance JSON (same format as parse.py)."""
    if not rows:
        logger.warning("No data for %s", table_id)
        return None

    table_dir = out_dir / document_id / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)

    csv_path = table_dir / f"{table_id}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    prov_path = table_dir / f"{table_id}_provenance.json"
    prov_data = {
        "table_id": table_id,
        "document_id": document_id,
        "pages": [page] if page else [],
        "columns": columns,
        "n_rows": len(rows),
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "rows": [{"page": page, "row_idx": i} for i in range(len(rows))],
    }
    with open(prov_path, "w", encoding="utf-8") as f:
        json.dump(prov_data, f, indent=2, ensure_ascii=False)

    logger.info("  → %d rows → %s", len(rows), csv_path)
    return csv_path


# ── Definitions of what to extract ───────────────────────────────────

JA_DOCUMENTS = [
    {
        "document_id": "jahresabschluss_2024",
        "table_id": "ergebnisrechnung_ja_2024",
        "description": "Ergebnisrechnung Gesamtstadt aus Jahresabschluss 2024",
    },
    {
        "document_id": "jahresabschluss_2023",
        "table_id": "ergebnisrechnung_ja_2023",
        "description": "Ergebnisrechnung Gesamtstadt aus Jahresabschluss 2023",
    },
    {
        "document_id": "jahresabschluss_2022",
        "table_id": "ergebnisrechnung_ja_2022",
        "description": "Ergebnisrechnung Gesamtstadt aus Jahresabschluss 2022",
    },
    {
        "document_id": "jahresabschluss_2020",
        "table_id": "ergebnisrechnung_ja_2020",
        "description": "Ergebnisrechnung Gesamtstadt aus Jahresabschluss 2020",
    },
    {
        "document_id": "gesamtabschluss_2022",
        "table_id": "ergebnisrechnung_ga_2022",
        "description": "Gesamtergebnisrechnung aus Gesamtabschluss 2022",
    },
    {
        "document_id": "gesamtabschluss_2021",
        "table_id": "ergebnisrechnung_ga_2021",
        "description": "Gesamtergebnisrechnung aus Gesamtabschluss 2021",
    },
]


def parse_all_jahresabschluesse(
    raw_dir: Path = DEFAULT_RAW_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> list[dict]:
    """Parse all available Jahresabschluss/Gesamtabschluss PDFs.

    Returns list of table definition dicts (compatible with tables.yaml
    format) so normalize can process them alongside HP tables.
    """
    table_defs = []

    for doc_def in JA_DOCUMENTS:
        document_id = doc_def["document_id"]
        table_id = doc_def["table_id"]
        pdf_path = raw_dir / f"{document_id}.pdf"

        if not pdf_path.exists():
            logger.warning("PDF not found: %s", pdf_path)
            continue

        logger.info("PARSE %s from %s", table_id, document_id)

        is_ga = document_id.startswith("gesamtabschluss")
        if is_ga:
            columns, rows, page = extract_gesamtabschluss_ergebnisrechnung(pdf_path)
        else:
            columns, rows, page = extract_ergebnisrechnung(pdf_path)

        csv_path = write_table(table_id, document_id, columns, rows, page, out_dir)

        if csv_path:
            # Return a tables.yaml-compatible definition
            table_def = {
                "table_id": table_id,
                "document_id": document_id,
                "description": doc_def["description"],
                "pages": [page] if page else [],
                "expected_columns": columns,
                "extraction_hints": {
                    "tool": "parse_jahresabschluss",
                    "skip_repeated_headers": True,
                },
            }
            table_defs.append(table_def)

    return table_defs


# ── CLI ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Parse Jahresabschluss/Gesamtabschluss PDFs")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    table_defs = parse_all_jahresabschluesse(raw_dir=args.raw_dir, out_dir=args.out_dir)

    print(f"\nExtracted {len(table_defs)} tables from Jahresabschlüsse/Gesamtabschlüsse:")
    for td in table_defs:
        print(f"  • {td['table_id']}: {td['expected_columns']}")


if __name__ == "__main__":
    main()
