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
    """Create a normalized version of a label for stable keying.

    The same position is typeset slightly differently from one Haushaltsplan to the
    next – "u.- beiträgen" in one, "u.-beiträgen" in the next. Dropping punctuation
    but keeping the surrounding whitespace turned that into two different keys
    ("..._u_beitragen" vs "..._ubeitragen"), so the same position competed with
    itself across documents and the year-over-year comparison read a missing
    previous value as a 100 % drop.

    Punctuation is therefore removed together with the whitespace around it, and
    the remaining words are joined without separators: what survives is the letters
    and digits alone, which is what actually identifies the position.
    """
    s = label.lower().strip()
    s = unicodedata.normalize("NFKD", s)
    # Diakritika entfernen (ü → u), damit "für"/"fuer" nicht auseinanderfallen
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "", s)
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
        with open(prov_path, encoding="utf-8") as f:
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


# ── Document authority ─────────────────────────────────────

# Which document wins when the same position×year appears in several documents.
# Higher rank supersedes lower. Rationale: a plan document is superseded by the
# decision on it, that in turn by any later amendment, and a planned figure is
# always superseded by the actual result once the accounts are closed.
#
# This used to be an alphabetical comparison of document_id with the comment
# "alphabetical ≈ chronological for our naming" – which is false for our naming:
# "..._entwurf" > "..._beschluss" (e after b), so the draft beat the decision for
# every year where both exist. Keep this table as the single source of truth and
# override per document via `authority:` in sources.yaml only when unavoidable.
DOC_TYPE_AUTHORITY: dict[str, int] = {
    "haushaltsplan_entwurf": 10,
    "haushaltsplan_neufassung": 15,   # revised draft, not yet decided on
    "haushaltsplan_beschluss": 20,
    "haushaltssatzung": 25,
    "nachtragshaushalt": 30,
    "anpassungsbeschluss": 40,
    "jahresabschluss": 50,
    # Bewusst UNTER dem Jahresabschluss: der Gesamtabschluss ist nicht genauer,
    # sondern misst etwas anderes – er konsolidiert Eigenbetriebe und Beteiligungen
    # mit. Für 2021 nennt er 74,4 Mio ordentliche Erträge, der Jahresabschluss
    # 64,0 Mio. In einer Zeitreihe des Kernhaushalts hat er nichts verloren; ihn
    # gewinnen zu lassen erzeugt einen Sprung, der wie ein Datenfehler aussieht.
    # Sauber wäre eine eigene Dimension für den Konsolidierungskreis.
    "gesamtabschluss": 45,
}

# Documents we hold for context only must never overwrite a figure from a
# primary source, whatever their doc_type ranks at.
SECONDARY_AUTHORITY = -1

UNKNOWN_AUTHORITY = 0


def document_authority(source_doc: dict) -> int:
    """Return the supersession rank of a document from sources.yaml.

    An explicit `authority:` in sources.yaml wins; otherwise the rank is derived
    from `doc_type`. Documents marked `priority: secondary` are pinned below every
    primary source.
    """
    explicit = source_doc.get("authority")
    if explicit is not None:
        return int(explicit)
    if source_doc.get("priority") == "secondary":
        return SECONDARY_AUTHORITY
    return DOC_TYPE_AUTHORITY.get(source_doc.get("doc_type"), UNKNOWN_AUTHORITY)


def build_authority_index(source_docs: dict[str, dict]) -> dict[str, dict]:
    """Map document_id → {rank, years} for every document in sources.yaml."""
    return {
        doc_id: {
            "rank": document_authority(doc),
            "years": {int(y) for y in doc.get("years", [])},
            "doc_type": doc.get("doc_type"),
        }
        for doc_id, doc in source_docs.items()
    }


def authority_rank(authority: dict[str, dict], document_id: str, year: int) -> tuple:
    """Ordering key deciding which document's value for *year* is the current one.

    Sorted by, in order:

    1. Whether the document is *about* that year at all. A Haushaltsplan carries
       three or four Finanzplanung columns beyond its own budget years; those are
       projections, and the document that actually budgets the year must win over
       them however authoritative it is otherwise. Without this, the 2024/2025
       Beschluss – a plain `haushaltsplan_beschluss` – outranks the Neufassung 2026
       for the year 2026 and the site shows a two-year-old projection.
    2. How recent the document is, by the last year it budgets. This only bites for
       years nobody budgets – the far end of the Finanzplanung – where the newest
       projection is the best one available. Without it the series switches source
       document midway (2026 from the Neufassung, 2027 from the two-year-old
       Beschluss) and jumps from deficit to surplus for no visible reason.
    3. The doc_type rank (see DOC_TYPE_AUTHORITY): the decision supersedes the
       draft it decided on, the closed accounts supersede any plan.
    4. document_id, so ties resolve the same way on every run.

    Note that 1 outranks 2: for a year that two documents budget, the doc_type
    decides, not recency – a later draft never beats the decision on an earlier one.
    """
    info = authority.get(document_id)
    if info is None:
        return (0, 0, UNKNOWN_AUTHORITY, document_id)
    covers = int(year in info["years"])
    recency = max(info["years"], default=0) if not covers else 0
    return (covers, recency, info["rank"], document_id)


# ── Deduplication ───────────────────────────────────────

def deduplicate_line_items(
    items: list[dict],
    authority: dict[str, dict] | None = None,
) -> list[dict]:
    """Mark superseded values where the same position×year appears in several documents.

    When the same (line_item_key, year, amount_type) comes from more than one
    document, the one from the document with the higher authority rank is the
    current value; every other one keeps its place in the output but carries
    ``superseded_by`` naming the document that replaced it. Consumers that want
    "the" number filter on ``superseded_by is None`` (see `current_only`); the
    comparison views need the losers and would otherwise have nothing to show.

    Ties – and documents missing from *authority* – fall back to comparing
    document_id, which keeps the ordering stable and reproducible.

    Duplicates from the *same* document are extraction artefacts (a table spanning
    overlapping page ranges), not alternative versions, and are dropped outright.
    """
    authority = authority or {}

    def rank(item: dict) -> tuple:
        return authority_rank(authority, item["document_id"], item["year"])

    # Group by (key, year, amount_type), keeping one entry per document
    groups: dict[tuple, dict[str, dict]] = {}
    same_doc_dupes = 0
    for item in items:
        k = (item["line_item_key"], item["year"], item["amount_type"])
        per_doc = groups.setdefault(k, {})
        if item["document_id"] in per_doc:
            same_doc_dupes += 1
            continue
        per_doc[item["document_id"]] = item

    out: list[dict] = []
    superseded: dict[tuple[str, str], int] = {}
    for per_doc in groups.values():
        winner = max(per_doc.values(), key=rank)
        for item in per_doc.values():
            if item is winner:
                item["superseded_by"] = None
            else:
                item["superseded_by"] = winner["document_id"]
                pair = (winner["document_id"], item["document_id"])
                superseded[pair] = superseded.get(pair, 0) + 1
            out.append(item)

    for (win, lose), n in sorted(superseded.items(), key=lambda kv: -kv[1]):
        logger.info("  Dedup: %s supersedes %s for %d values", win, lose, n)

    n_superseded = sum(superseded.values())
    if same_doc_dupes or n_superseded:
        logger.info(
            "  Dedup: dropped %d same-document duplicates, marked %d superseded, "
            "%d values current",
            same_doc_dupes, n_superseded, len(out) - n_superseded,
        )

    return out


def current_only(items: list[dict]) -> list[dict]:
    """Keep only the values that are not superseded by a more authoritative document."""
    return [i for i in items if not i.get("superseded_by")]


# ── Main entry point ─────────────────────────────────────────────────

def load_sources_index(sources_path: Path) -> dict[str, dict]:
    """Load sources.yaml into a dict keyed by document_id."""
    with open(sources_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {d["document_id"]: d for d in data.get("documents", [])}


def normalize_all(
    extracted_dir: Path = DEFAULT_EXTRACTED_DIR,
    tables_path: Path = DEFAULT_TABLES,
    sources_path: Path = DEFAULT_SOURCES,
) -> pd.DataFrame:
    """Normalize all extracted tables into a single DataFrame of line_items."""
    with open(tables_path, encoding="utf-8") as f:
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
    all_items = deduplicate_line_items(all_items, build_authority_index(source_docs))

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
    with open(stats_path, "w", encoding="utf-8") as f:
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
