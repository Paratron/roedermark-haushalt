"""Normalize pipeline – transform extracted CSVs into a unified line_items format.

Takes the wide-format CSVs (one column per year) and melts them into long-format:
  one row per (position × year × amount_type).

Usage:
    python -m pipeline.normalize.normalize

Rules (from agents.md § 4):
  • Every row needs provenance (document, page, table, row index)
  • Uncertain matches marked with confidence < 1.0
  • Numbers cleaned and converted to EUR (handle T€, Mio€ via mappings.yaml)
"""

from __future__ import annotations

import csv
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from pipeline.parse.parse_jahresabschluss import parse_all_jahresabschluesse
from pipeline.parse.parse_produkte import parse_all_produkte

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_EXTRACTED_DIR = ROOT_DIR / "data" / "extracted"
DEFAULT_OUT_DIR = ROOT_DIR / "data" / "extracted"  # normalized sits alongside raw extractions
DEFAULT_TABLES = ROOT_DIR / "tables.yaml"
DEFAULT_SOURCES = ROOT_DIR / "sources.yaml"


# ── Number parsing ───────────────────────────────────────────────────

def parse_german_number(s: str | None) -> float | None:
    """Parse a German-formatted number string to float.

    Examples:
        '17.940.642'   → 17940642.0
        '-106.254'     → -106254.0
        '1.244.481'    → 1244481.0
        ''             → None
    """
    if not s or not s.strip():
        return None
    s = s.strip()
    # Remove thousands separators (.) and convert decimal comma to dot
    # German: 17.940.642 → 17940642  |  1.234,56 → 1234.56
    # Detect if there's a comma (decimal separator)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        # No comma → dots are thousands separators only
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


# ── Column classification ────────────────────────────────────────────

# Pattern: "Ergebnis 2021", "Ansatz 2023", "Plan 2024", "Budget 2022"
YEAR_COL_PATTERN = re.compile(
    r"^(Ergebnis|Ansatz|Plan|Budget)\s+(\d{4})$", re.IGNORECASE
)

# Extended patterns for Investitionen tables:
#   "Jahres- ergebnis 2024", "Jahres-ergebnis 2024", "Jahres- ergeb- nis 2018"
#   "Finanzplan 2027", "Finanz-plan 2023"
#   "Finanzplan 2028/2029", "Finanz-plan 2024/ 2025", "Finanzplan 2024/2025"
#   "VE 2020 2021", "VE der HHJ 2024 2025"
INVEST_YEAR_PATTERNS = [
    # "Jahres- ergebnis 2024" → ist
    (re.compile(r"^Jahres[\s-]*e?r?g?e?b[\s-]*n?i?s?\s+(\d{4})$", re.IGNORECASE), "ist"),
    # "Finanzplan 2027" → plan (single year)
    (re.compile(r"^Finanz[\s-]*plan\s+(\d{4})$", re.IGNORECASE), "plan"),
    # "Finanzplan 2028/2029" → plan (dual year, needs special handling)
    (re.compile(r"^Finanz[\s-]*plan\s+(\d{4})[/ ]+(\d{4})$", re.IGNORECASE), "plan"),
]

AMOUNT_TYPE_MAP = {
    "ergebnis": "ist",       # actual result (Jahresabschluss)
    "ansatz": "plan",        # budget appropriation (Haushaltsansatz)
    "plan": "plan",          # financial planning (Finanzplanung)
    "budget": "plan",        # budget column in detail tables
}


def classify_year_columns(columns: list[str]) -> list[tuple[str, int, str] | tuple[str, int, str, int]]:
    """Classify columns into (original_name, year, amount_type) tuples.

    For dual-year columns (Finanzplan 2028/2029), returns
    (original_name, year1, amount_type, year2) with 4 elements.

    Returns only the year-bearing columns.
    """
    result = []
    for col in columns:
        cleaned = col.strip()
        # Standard pattern first
        m = YEAR_COL_PATTERN.match(cleaned)
        if m:
            kind = m.group(1).lower()
            year = int(m.group(2))
            amount_type = AMOUNT_TYPE_MAP.get(kind, kind)
            result.append((col, year, amount_type))
            continue

        # Investment-specific patterns
        for pattern, amount_type in INVEST_YEAR_PATTERNS:
            m = pattern.match(cleaned)
            if m:
                groups = m.groups()
                if len(groups) == 2:  # Dual year: Finanzplan 2028/2029
                    year1 = int(groups[0])
                    year2 = int(groups[1])
                    result.append((col, year1, amount_type, year2))
                else:
                    year = int(groups[0])
                    result.append((col, year, amount_type))
                break
    return result


# ── Stable key generation ────────────────────────────────────────────

def normalize_label(label: str) -> str:
    """Create a normalized version of a label for stable keying."""
    s = label.lower().strip()
    # Remove special chars, keep alphanumeric + spaces
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s


def make_line_item_key(
    haushalt_type: str,  # ergebnishaushalt | finanzhaushalt
    nr: str,
    label: str,
    konto: str | None = None,
) -> str:
    """Build a stable composite key for a line item.

    Format: {haushalt_type}:{nr}:{konto}:{normalized_label}
    """
    parts = [
        haushalt_type,
        str(nr or "").strip(),
        str(konto or "").strip(),
        normalize_label(label or ""),
    ]
    return ":".join(parts)


# ── Determine haushalt type from table_id ────────────────────────────

def get_haushalt_type(table_id: str) -> str:
    """Derive haushalt_type from table_id."""
    tid = table_id.lower()
    if "investitionen" in tid:
        return "investitionen"
    elif "teilfinanzhaushalt" in tid:
        return "teilfinanzhaushalt"
    elif "teilergebnishaushalt" in tid:
        return "teilergebnishaushalt"
    elif "finanzhaushalt" in tid:
        return "finanzhaushalt"
    elif "ergebnishaushalt" in tid:
        return "ergebnishaushalt"
    elif "ergebnisrechnung" in tid:
        # Jahresabschluss / Gesamtabschluss Ergebnisrechnungen
        # → same structure as Ergebnishaushalt summary rows
        return "ergebnishaushalt"
    return "unbekannt"


def is_detail_table(table_id: str) -> bool:
    """Check if a table is a detail/structure table (has Konto column)."""
    return "struktur_" in table_id.lower()


# ── Main normalization ───────────────────────────────────────────────

def normalize_table(
    table_def: dict,
    source_doc: dict,
    extracted_dir: Path,
) -> list[dict]:
    """Normalize a single extracted table CSV into line_items.

    Returns list of line_item dicts.
    """
    table_id = table_def["table_id"]
    document_id = table_def["document_id"]
    haushalt_type = get_haushalt_type(table_id)
    detail = is_detail_table(table_id)

    csv_path = extracted_dir / document_id / "tables" / f"{table_id}.csv"
    prov_path = extracted_dir / document_id / "tables" / f"{table_id}_provenance.json"

    if not csv_path.exists():
        logger.warning("CSV not found: %s", csv_path)
        return []

    # Load provenance if available
    provenance_rows = {}
    if prov_path.exists():
        with open(prov_path) as f:
            prov_data = json.load(f)
        for i, row_prov in enumerate(prov_data.get("rows", [])):
            provenance_rows[i] = row_prov

    # Read CSV
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        rows = list(reader)

    # Extract teilhaushalt metadata from extraction_hints
    hints = table_def.get("extraction_hints", {})
    teilhaushalt_nr = hints.get("teilhaushalt_nr", "")
    teilhaushalt_name = hints.get("teilhaushalt_name", "")
    is_investitionen = haushalt_type == "investitionen"

    # Classify year columns
    year_cols = classify_year_columns(columns)
    if not year_cols:
        logger.warning("No year columns found in %s (columns: %s)", table_id, columns)
        return []

    # Build line items by unpivoting
    line_items = []
    for row_idx, row in enumerate(rows):
        nr = (row.get("Nr.") or "").strip()
        bezeichnung = (row.get("Bezeichnung") or "").strip()
        konto = (row.get("Konto") or "").strip() if detail else None

        # Skip completely empty rows
        if not nr and not bezeichnung:
            continue

        # Generate stable key (include teilhaushalt_nr for sub-budgets)
        if teilhaushalt_nr:
            key = make_line_item_key(haushalt_type, f"th{teilhaushalt_nr}:{nr}", bezeichnung, konto)
        else:
            key = make_line_item_key(haushalt_type, nr, bezeichnung, konto)

        # Provenance for this row
        prov = provenance_rows.get(row_idx, {})
        page = prov.get("page")

        # Unpivot: one output row per year column
        for year_col_info in year_cols:
            col_name = year_col_info[0]
            year = year_col_info[1]
            amount_type = year_col_info[2]
            is_dual_year = len(year_col_info) == 4

            raw_value = row.get(col_name)

            if is_dual_year:
                # Dual-year column like "Finanzplan 2028/2029"
                # Cell contains two values separated by \n
                year2 = year_col_info[3]
                if raw_value:
                    parts = str(raw_value).split("\n")
                    val1 = parse_german_number(parts[0] if parts else None)
                    val2 = parse_german_number(parts[1] if len(parts) > 1 else None)
                else:
                    val1 = val2 = None

                for yr, amt in [(year, val1), (year2, val2)]:
                    if amt is None:
                        continue
                    line_item = {
                        "line_item_key": key,
                        "year": yr,
                        "amount": amt,
                        "amount_type": amount_type,
                        "unit": "EUR",
                        "haushalt_type": haushalt_type,
                        "nr": nr,
                        "bezeichnung": bezeichnung,
                        "document_id": document_id,
                        "table_id": table_id,
                        "page": page,
                        "row_idx": row_idx,
                        "confidence": 1.0,
                    }
                    if konto:
                        line_item["konto"] = konto
                    if teilhaushalt_nr:
                        line_item["teilhaushalt_nr"] = teilhaushalt_nr
                        line_item["teilhaushalt_name"] = teilhaushalt_name
                    line_items.append(line_item)
            else:
                # Standard single-year column
                amount = parse_german_number(raw_value)
                if amount is None:
                    continue

                line_item = {
                    "line_item_key": key,
                    "year": year,
                    "amount": amount,
                    "amount_type": amount_type,
                    "unit": "EUR",
                    "haushalt_type": haushalt_type,
                    "nr": nr,
                    "bezeichnung": bezeichnung,
                    "document_id": document_id,
                    "table_id": table_id,
                    "page": page,
                    "row_idx": row_idx,
                    "confidence": 1.0,
                }
                if konto:
                    line_item["konto"] = konto
                if teilhaushalt_nr:
                    line_item["teilhaushalt_nr"] = teilhaushalt_nr
                    line_item["teilhaushalt_name"] = teilhaushalt_name
                line_items.append(line_item)

    logger.info(
        "  %s: %d source rows → %d line_items (%d year-cols)",
        table_id, len(rows), len(line_items), len(year_cols),
    )
    return line_items


# ── Deduplication ────────────────────────────────────────────────────

def deduplicate_line_items(items: list[dict]) -> list[dict]:
    """Remove duplicates where the same position×year appears in overlapping tables.

    When the same (line_item_key, year, amount_type) appears in multiple documents,
    we keep the one from the latest document (by document priority).

    For the same document, keep as-is (no dups expected).
    """
    # Group by (key, year, amount_type)
    seen: dict[tuple, dict] = {}
    dupes = 0
    for item in items:
        k = (item["line_item_key"], item["year"], item["amount_type"])
        if k in seen:
            existing = seen[k]
            # Prefer the item from the later/more authoritative document
            # Simple heuristic: later table_id wins (alphabetical ≈ chronological for our naming)
            if item["document_id"] > existing["document_id"]:
                seen[k] = item
                dupes += 1
            elif item["document_id"] == existing["document_id"]:
                # Same doc, same key — could be from overlapping pages, keep first
                dupes += 1
            else:
                dupes += 1
        else:
            seen[k] = item

    if dupes:
        logger.info("  Dedup: removed %d duplicates, kept %d items", dupes, len(seen))

    return list(seen.values())


# ── Main entry point ─────────────────────────────────────────────────

def load_sources_index(sources_path: Path) -> dict[str, dict]:
    """Load sources.yaml into a dict keyed by document_id."""
    with open(sources_path) as f:
        data = yaml.safe_load(f)
    return {d["document_id"]: d for d in data.get("documents", [])}


def normalize_all(
    extracted_dir: Path = DEFAULT_EXTRACTED_DIR,
    tables_path: Path = DEFAULT_TABLES,
    sources_path: Path = DEFAULT_SOURCES,
) -> pd.DataFrame:
    """Normalize all extracted tables into a single DataFrame of line_items."""
    with open(tables_path) as f:
        tables_data = yaml.safe_load(f)
    table_defs = tables_data.get("tables", [])
    source_docs = load_sources_index(sources_path)

    # Also parse and include Jahresabschluss/Gesamtabschluss tables
    ja_table_defs = parse_all_jahresabschluesse()
    logger.info("Added %d Jahresabschluss/Gesamtabschluss table definitions", len(ja_table_defs))
    table_defs = table_defs + ja_table_defs

    all_items: list[dict] = []

    for table_def in table_defs:
        doc_id = table_def["document_id"]
        source_doc = source_docs.get(doc_id, {})
        items = normalize_table(table_def, source_doc, extracted_dir)
        all_items.extend(items)

    logger.info("Total raw line_items: %d", len(all_items))

    # Add Produktübersicht line_items (already in normalized format)
    produkt_items = parse_all_produkte()
    logger.info("Added %d Produktübersicht line_items", len(produkt_items))
    all_items.extend(produkt_items)

    # Deduplicate overlapping year data
    all_items = deduplicate_line_items(all_items)

    # Convert to DataFrame
    df = pd.DataFrame(all_items)

    if df.empty:
        logger.warning("No line items produced!")
        return df

    # Sort for readability
    df = df.sort_values(
        ["haushalt_type", "nr", "year", "amount_type", "document_id"]
    ).reset_index(drop=True)

    # Save as CSV (intermediate)
    out_path = extracted_dir / "line_items_normalized.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    logger.info("Wrote %d line_items → %s", len(df), out_path)

    # Save summary stats
    stats = {
        "total_line_items": len(df),
        "unique_positions": df["line_item_key"].nunique(),
        "years": sorted(df["year"].unique().tolist()),
        "amount_types": sorted(df["amount_type"].unique().tolist()),
        "documents": sorted(df["document_id"].unique().tolist()),
        "tables": sorted(df["table_id"].unique().tolist()),
        "haushalt_types": sorted(df["haushalt_type"].unique().tolist()),
        "normalized_at": datetime.now(timezone.utc).isoformat(),
    }
    stats_path = extracted_dir / "normalize_stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    logger.info("Stats → %s", stats_path)

    return df


# ── CLI ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Normalize extracted CSVs into line_items")
    parser.add_argument("--extracted-dir", type=Path, default=DEFAULT_EXTRACTED_DIR)
    parser.add_argument("--tables", type=Path, default=DEFAULT_TABLES)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    args = parser.parse_args()

    df = normalize_all(
        extracted_dir=args.extracted_dir,
        tables_path=args.tables,
        sources_path=args.sources,
    )

    if not df.empty:
        print(f"\n{'='*60}")
        print(f"Normalisierung abgeschlossen: {len(df)} line_items")
        print(f"{'='*60}")
        print(f"\nJahre:        {sorted(df['year'].unique())}")
        print(f"Positionen:   {df['line_item_key'].nunique()}")
        print(f"Dokumente:    {df['document_id'].nunique()}")
        print(f"Tabellen:     {df['table_id'].nunique()}")
        print(f"\nAmount-Typen:")
        print(df.groupby("amount_type")["amount"].agg(["count", "sum"]).to_string())
        print(f"\nPro Haushalt-Typ:")
        print(df.groupby("haushalt_type")["amount"].agg(["count", "sum"]).to_string())
        print(f"\nErgebnis-/Planwerte pro Jahr:")
        pivot = df.groupby(["year", "amount_type"])["line_item_key"].count().unstack(fill_value=0)
        print(pivot.to_string())


if __name__ == "__main__":
    main()
