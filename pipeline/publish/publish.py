"""Publish pipeline – export normalized line_items to multiple formats.

Outputs to data/published/:
  • line_items.parquet   – columnar format for analytics
  • line_items.csv       – human-readable flat file
  • documents.json       – document metadata index
  • summary.json         – aggregated stats for the frontend
  • haushalt.duckdb      – embedded analytics database

Usage:
    python -m pipeline.publish.publish
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_NORMALIZED = ROOT_DIR / "data" / "extracted" / "line_items_normalized.csv"
DEFAULT_DOCS_JSON = ROOT_DIR / "data" / "raw" / "documents.json"
DEFAULT_SOURCES = ROOT_DIR / "sources.yaml"
DEFAULT_OUT_DIR = ROOT_DIR / "data" / "published"


# ── Data cleaning for publishing ──────────────────────────────────────

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean up the DataFrame for publishing."""
    df = df.copy()

    # Convert Nr. to clean string (remove trailing .0 for pure integers,
    # keep dotted product numbers like 01.1.01 as-is)
    if "nr" in df.columns:
        def _clean_nr(x):
            if pd.isna(x) or x == "":
                return str(x)
            s = str(x)
            # Pure float like "610001.0" → "610001"
            try:
                return str(int(float(s)))
            except (ValueError, OverflowError):
                return s
        df["nr"] = df["nr"].apply(_clean_nr)

    # Ensure year is int
    if "year" in df.columns:
        df["year"] = df["year"].astype(int)

    # Ensure row_idx is int
    if "row_idx" in df.columns:
        df["row_idx"] = df["row_idx"].astype(int)

    # Round amounts to 2 decimal places (EUR cents)
    if "amount" in df.columns:
        df["amount"] = df["amount"].round(2)

    # Negate ergebnishaushalt amounts for intuitive display:
    # PDFs use accounting convention (Erträge=negative, Aufwendungen=positive).
    # After negation: Erträge=positive (income), Aufwendungen=negative (expense),
    # Jahresergebnis: positive=surplus, negative=deficit.
    if "haushalt_type" in df.columns and "amount" in df.columns:
        eh_mask = df["haushalt_type"] == "ergebnishaushalt"
        df.loc[eh_mask, "amount"] = -df.loc[eh_mask, "amount"]

    return df


# ── Parquet export ────────────────────────────────────────────────────

def export_parquet(df: pd.DataFrame, out_dir: Path) -> Path:
    """Export line_items as Parquet with proper schema."""
    out_path = out_dir / "line_items.parquet"

    # Define explicit schema for type safety
    table = pa.Table.from_pandas(df)
    pq.write_table(table, out_path, compression="snappy")

    logger.info("Parquet: %d rows → %s (%.1f KB)", len(df), out_path, out_path.stat().st_size / 1024)
    return out_path


# ── CSV export ────────────────────────────────────────────────────────

def export_csv(df: pd.DataFrame, out_dir: Path) -> Path:
    """Export line_items as CSV."""
    out_path = out_dir / "line_items.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    logger.info("CSV: %d rows → %s (%.1f KB)", len(df), out_path, out_path.stat().st_size / 1024)
    return out_path


# ── Documents JSON ────────────────────────────────────────────────────

def export_documents(docs_json: Path, sources_path: Path, out_dir: Path) -> Path:
    """Merge documents.json (fetched metadata) with sources.yaml info."""
    out_path = out_dir / "documents.json"

    # Load fetched documents
    if docs_json.exists():
        with open(docs_json) as f:
            documents = json.load(f)
    else:
        documents = []

    # Load sources for additional metadata
    with open(sources_path) as f:
        sources_data = yaml.safe_load(f)
    source_map = {d["document_id"]: d for d in sources_data.get("documents", [])}

    # Enrich each document
    existing_ids = set()
    for doc in documents:
        existing_ids.add(doc.get("document_id"))
        src = source_map.get(doc.get("document_id"), {})
        doc.setdefault("doc_type", src.get("doc_type"))
        doc.setdefault("years", src.get("years"))
        doc.setdefault("priority", src.get("priority"))

    # Add documents from sources.yaml that are missing from documents.json
    # (e.g. manually downloaded PDFs not processed by fetch pipeline)
    raw_dir = ROOT_DIR / "data" / "raw"
    for doc_id, src in source_map.items():
        if doc_id in existing_ids:
            continue
        pdf_path = raw_dir / f"{doc_id}.pdf"
        entry = {
            "document_id": doc_id,
            "doc_type": src.get("doc_type"),
            "years": src.get("years"),
            "priority": src.get("priority"),
            "source_url": src.get("url"),
        }
        if pdf_path.exists():
            entry["filename"] = f"{doc_id}.pdf"
            entry["size_bytes"] = pdf_path.stat().st_size
            logger.info("Added document from sources.yaml: %s", doc_id)
        else:
            entry["missing"] = True
            logger.info("Added missing document (no PDF) from sources.yaml: %s", doc_id)
        documents.append(entry)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    logger.info("Documents: %d entries → %s", len(documents), out_path)
    return out_path


# ── Summary JSON for frontend ────────────────────────────────────────

def build_summary(df: pd.DataFrame) -> dict:
    """Build aggregated summary stats for the frontend."""
    overview = df[~df["table_id"].str.startswith("struktur_")].copy()

    def year_totals_by_nr(sub: pd.DataFrame, key_nr: int, label: str,
                          negate: bool = False) -> list[dict]:
        """Get time-series for a position by Nr, deduplicated per (year, amount_type)."""
        mask = sub["nr"] == str(key_nr)
        rows = sub[mask]
        return _dedup_and_collect(rows, label, negate)

    def year_totals_by_bezeichnung(sub: pd.DataFrame, pattern: str, label: str,
                                   negate: bool = False) -> list[dict]:
        """Get time-series by matching bezeichnung (case-insensitive startswith)."""
        mask = sub["bezeichnung"].str.lower().str.startswith(pattern.lower())
        rows = sub[mask]
        return _dedup_and_collect(rows, label, negate)

    def _dedup_and_collect(rows: pd.DataFrame, label: str,
                           negate: bool) -> list[dict]:
        """Deduplicate by (year, amount_type) keeping latest document, collect results."""
        # Sort so later documents come last (will overwrite earlier ones)
        rows = rows.sort_values("document_id")
        best: dict[tuple, dict] = {}
        for _, row in rows.iterrows():
            k = (int(row["year"]), row["amount_type"])
            amount = float(row["amount"])
            if negate:
                amount = -amount
            best[k] = {
                "year": int(row["year"]),
                "amount_type": row["amount_type"],
                "amount": amount,
                "label": label,
                "document_id": row["document_id"],
            }
        return list(best.values())

    eh = overview[overview["haushalt_type"] == "ergebnishaushalt"]
    fh = overview[overview["haushalt_type"] == "finanzhaushalt"]

    # Classify ist/plan years early (needed for last_ist_year)
    all_years = sorted(overview["year"].unique().tolist())
    ist_years = sorted(
        overview[overview["amount_type"] == "ist"]["year"].unique().tolist()
    )
    plan_only_years = sorted([y for y in all_years if y not in ist_years])
    last_ist_year = int(ist_years[-1]) if ist_years else None

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_line_items": len(df),
        "overview_line_items": len(overview),
        "detail_line_items": len(df) - len(overview),
        "years": sorted(df["year"].unique().tolist()),
        "documents": sorted(df["document_id"].unique().tolist()),
        # Key time series for frontend charts
        # Data is already sign-corrected in clean_dataframe():
        #   Erträge: positive (income)  → keep as-is
        #   Aufwendungen: negative (expense) → negate for chart (show as positive)
        #   Ergebnis: positive = surplus, negative = deficit → keep as-is
        "ergebnishaushalt": {
            "ordentliche_ertraege": year_totals_by_nr(eh, 100, "Ordentliche Erträge"),
            "ordentliche_aufwendungen": year_totals_by_nr(eh, 190, "Ordentliche Aufwendungen", negate=True),
            "ordentliches_ergebnis": year_totals_by_bezeichnung(
                eh, "ordentliches ergebnis", "Ordentliches Ergebnis"
            ),
            "jahresergebnis": year_totals_by_bezeichnung(
                eh, "jahresergebnis", "Jahresergebnis"
            ),
        },
        "finanzhaushalt": {
            "einzahlungen_lfd": year_totals_by_nr(fh, 100, "Einzahlungen lfd. Verwaltung", negate=True),
            "auszahlungen_lfd": year_totals_by_nr(fh, 200, "Auszahlungen lfd. Verwaltung"),
            "saldo_lfd": year_totals_by_nr(fh, 300, "Saldo lfd. Verwaltung", negate=True),
        },
        # Coverage matrix
        "coverage": {},
        # Ist vs Plan year classification for frontend
        "ist_years": [int(y) for y in ist_years],
        "plan_only_years": [int(y) for y in plan_only_years],
        "last_ist_year": last_ist_year,
    }

    # Build coverage: which (year, amount_type) combos exist
    for (year, atype), group in overview.groupby(["year", "amount_type"]):
        key = f"{int(year)}_{atype}"
        summary["coverage"][key] = int(len(group))

    return summary


def export_summary(df: pd.DataFrame, out_dir: Path) -> Path:
    """Export summary JSON."""
    out_path = out_dir / "summary.json"
    summary = build_summary(df)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info("Summary → %s", out_path)
    return out_path


# ── DuckDB export ─────────────────────────────────────────────────────

def export_duckdb(df: pd.DataFrame, out_dir: Path) -> Path:
    """Export to DuckDB for embedded analytics."""
    out_path = out_dir / "haushalt.duckdb"

    # Remove old DB if exists
    if out_path.exists():
        out_path.unlink()

    con = duckdb.connect(str(out_path))
    try:
        # Register DataFrame and create table
        con.register("df", df)
        con.execute("CREATE TABLE line_items AS SELECT * FROM df")

        # Create useful views
        con.execute("""
            CREATE VIEW ergebnishaushalt AS
            SELECT * FROM line_items
            WHERE haushalt_type = 'ergebnishaushalt'
              AND table_id NOT LIKE 'struktur_%'
        """)

        con.execute("""
            CREATE VIEW finanzhaushalt AS
            SELECT * FROM line_items
            WHERE haushalt_type = 'finanzhaushalt'
              AND table_id NOT LIKE 'struktur_%'
        """)

        con.execute("""
            CREATE VIEW detail AS
            SELECT * FROM line_items
            WHERE table_id LIKE 'struktur_%'
        """)

        # Create index for common queries
        con.execute("CREATE INDEX idx_year ON line_items(year)")
        con.execute("CREATE INDEX idx_type ON line_items(haushalt_type)")
        con.execute("CREATE INDEX idx_key ON line_items(line_item_key)")

        # Verify
        count = con.execute("SELECT COUNT(*) FROM line_items").fetchone()[0]
        logger.info("DuckDB: %d rows, 3 views → %s (%.1f KB)", count, out_path, out_path.stat().st_size / 1024)
    finally:
        con.close()

    return out_path


# ── Main entry point ─────────────────────────────────────────────────

def publish_all(
    normalized_csv: Path = DEFAULT_NORMALIZED,
    docs_json: Path = DEFAULT_DOCS_JSON,
    sources_path: Path = DEFAULT_SOURCES,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> None:
    """Run the full publish pipeline."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load and clean
    logger.info("Loading normalized data from %s", normalized_csv)
    df = pd.read_csv(normalized_csv)
    df = clean_dataframe(df)
    logger.info("Loaded %d line_items", len(df))

    # Export all formats
    export_parquet(df, out_dir)
    export_csv(df, out_dir)
    export_documents(docs_json, sources_path, out_dir)
    export_summary(df, out_dir)
    export_duckdb(df, out_dir)

    print(f"\n{'='*60}")
    print(f"Publish abgeschlossen → {out_dir}")
    print(f"{'='*60}")
    for p in sorted(out_dir.iterdir()):
        if p.name.startswith("."):
            continue
        size = p.stat().st_size
        if size > 1024 * 1024:
            print(f"  {p.name:30s}  {size/1024/1024:8.1f} MB")
        else:
            print(f"  {p.name:30s}  {size/1024:8.1f} KB")


# ── CLI ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Publish normalized data to multiple formats")
    parser.add_argument("--normalized", type=Path, default=DEFAULT_NORMALIZED)
    parser.add_argument("--docs", type=Path, default=DEFAULT_DOCS_JSON)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    publish_all(
        normalized_csv=args.normalized,
        docs_json=args.docs,
        sources_path=args.sources,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    main()
