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

from pipeline.normalize.normalize import authority_rank, build_authority_index

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_NORMALIZED = ROOT_DIR / "data" / "extracted" / "line_items_normalized.csv"
DEFAULT_DOCS_JSON = ROOT_DIR / "data" / "raw" / "documents.json"
DEFAULT_SOURCES = ROOT_DIR / "sources.yaml"
DEFAULT_OUT_DIR = ROOT_DIR / "data" / "published"
DEFAULT_FRONTEND_DIR = ROOT_DIR / "frontend" / "static" / "data"

# Was das Frontend aus dieser Pipeline liest. Andere Dateien im selben Verzeichnis
# (Hebesätze, Investitionskommentare, Schuldenstatistik) stammen aus eigenen
# Skripten und dürfen hier nicht angefasst werden.
FRONTEND_FILES = (
    "summary.json",
    "documents.json",
    "line_items.csv",
    "line_items_superseded.csv",
)

# Die Quellen-PDFs, auf die jede Zahl verweist. Lagen bisher nur von Hand kopiert
# in frontend/static/pdfs/ – ein neues Dokument in sources.yaml ließ den Build mit
# "404 /pdfs/<id>.pdf (linked from /quellen)" scheitern.
DEFAULT_RAW_PDF_DIR = ROOT_DIR / "data" / "raw"
FRONTEND_PDF_DIR = "pdfs"


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

    # Identifier columns, not numbers: teilhaushalt_nr runs "7", "7.4" and "07.4.01"
    # across the three levels of the Zahlenwerk, and konto/fachbereich are codes with
    # leading zeros. Left to inference, Arrow types the column from its first values
    # and then fails on the rest ("Could not convert '7' with type str: tried to
    # convert to double").
    for col in ("teilhaushalt_nr", "konto", "fachbereich_nr", "productgroup_nr", "nr"):
        if col in df.columns:
            df[col] = df[col].astype("string")

    # Guarantee the supersession column so every consumer (DuckDB views, summary,
    # frontend) can rely on it, including data normalized before it was introduced.
    if "superseded_by" not in df.columns:
        df["superseded_by"] = pd.NA
    df["superseded_by"] = df["superseded_by"].replace("", pd.NA)

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

def export_csv(df: pd.DataFrame, out_dir: Path) -> tuple[Path, Path | None]:
    """Export line_items as CSV, current values and superseded ones separately.

    Every visitor of the site downloads line_items.csv, so the values that a newer
    Fassung has replaced must not ride along: they roughly double the file and are
    only needed by the comparison views, which can load them on demand.
    """
    out_path = out_dir / "line_items.csv"
    superseded_path = out_dir / "line_items_superseded.csv"

    if "superseded_by" in df.columns:
        is_current = df["superseded_by"].isna()
        current, superseded = df[is_current], df[~is_current]
    else:
        current, superseded = df, df.iloc[:0]

    current.to_csv(out_path, index=False, encoding="utf-8")
    logger.info(
        "CSV: %d rows → %s (%.1f KB)", len(current), out_path, out_path.stat().st_size / 1024
    )

    if superseded.empty:
        superseded_path.unlink(missing_ok=True)
        return out_path, None

    superseded.to_csv(superseded_path, index=False, encoding="utf-8")
    logger.info(
        "CSV: %d superseded rows → %s (%.1f KB)",
        len(superseded), superseded_path, superseded_path.stat().st_size / 1024,
    )
    return out_path, superseded_path


# ── Documents JSON ────────────────────────────────────────────────────

# Die Bausteine, aus denen die Seitendatensätze zusammengesetzt werden: eine
# vollständige Zerlegung des Datensatzes nach Haushaltsart und Detailtiefe. Welche
# Seite welche Bausteine bekommt, steht in PAGE_DATASETS.
ITEM_SLICES: dict[str, dict] = {
    # Gesamtübersicht ohne die Konto-Ebene: die Ergebnis-/Finanzhaushalt-Seiten
    # rufen overviewItems() auf, das struktur_ ohnehin verwirft – 3.154 von 3.994
    # Zeilen wurden geladen, um sofort weggeworfen zu werden.
    "ergebnishaushalt": {"haushalt_type": ["ergebnishaushalt"], "struktur": False},
    "finanzhaushalt": {"haushalt_type": ["finanzhaushalt"], "struktur": False},
    # Konto-Ebene: braucht die Steuer-Seite (Aufschlüsselung Nr. 50) und die
    # Kategorien-Seite (Konto-Detailansicht).
    "ergebnishaushalt_konten": {"haushalt_type": ["ergebnishaushalt"], "struktur": True},
    "finanzhaushalt_konten": {"haushalt_type": ["finanzhaushalt"], "struktur": True},
    # Investitionen samt Finanzierungspositionen – die Investitionsseite trennt
    # beides selbst, die Schulden-Seite nutzt nur die Finanzierungszeilen.
    "investitionen": {"haushalt_type": ["investitionen"]},
    "produktuebersicht": {"haushalt_type": ["produktuebersicht"]},
    # Nur die oberste Teilhaushalt-Ebene – die Budget- und Produktebene darunter
    # wird derzeit von keiner Seite angezeigt und liegt separat.
    "teilhaushalte": {
        "haushalt_type": ["teilergebnishaushalt", "teilfinanzhaushalt"],
        "teilhaushalt_level": "top",
    },
    "teilhaushalte_detail": {
        "haushalt_type": ["teilergebnishaushalt", "teilfinanzhaushalt"],
        "teilhaushalt_level": "sub",
    },
}

# Spalten, die die Pipeline führt, das Frontend aber nirgends liest. In der
# Gesamtübersicht machten sie zusammen rund 5 % der Datei aus, ohne je gelesen zu
# werden – row_idx und confidence werden geparst und danach nicht angefasst.
UNUSED_ITEM_COLUMNS = ("unit", "row_idx", "confidence")


# Was jede Seite lädt, und wonach der Datensatz dafür aufgeteilt wird.
#
# Die Seiten importieren diese Dateien, statt sie per fetch zu holen: static/ landet
# bei adapter-vercel auf dem CDN und ist aus einer Serverless-Funktion gar nicht per
# Dateisystem lesbar, src/lib/ dagegen wird gebündelt und von Vite pro Datei
# gesplittet. Damit ist die Datenfrage unabhängig davon, ob eine Seite prerendert
# oder serverseitig gerendert wird.
#
# split_by teilt zusätzlich auf: die Kategorien-Seite zeigt immer genau ein Jahr,
# lud aber alle fünfzehn – 90 % des Datensatzes für ein Dropdown, das der Server nie
# zu sehen bekam, weil ?year= ein Query-Parameter ist.
PAGE_DATASETS: dict[str, dict] = {
    "ergebnishaushalt": {"slices": ["ergebnishaushalt"], "drop": ["line_item_key"]},
    "finanzhaushalt": {"slices": ["finanzhaushalt"], "drop": ["line_item_key"]},
    # Die Investitionsseite gruppiert nach line_item_key zu Projekten – der bleibt.
    "investitionen": {"slices": ["investitionen"]},
    # Die Schuldenseite kennt aus dem Finanzhaushalt vier Positionen: Zinsen (160),
    # Kassenkredite (301), Kreditaufnahme (310) und Tilgung (320). Die Kredit- und
    # Darlehensprojekte holt sie aus dem Investitionsdatensatz – ihn hier zu
    # wiederholen wären 3,5 MB im Repository für dieselben Zeilen.
    "schulden": {
        "slices": [
            {"slice": "finanzhaushalt", "where": {"nr": ["160", "301", "310", "320"]}},
        ]
    },
    # Die Steuerseite kennt genau eine Position: Nr. 50 samt Konto-Aufschlüsselung.
    # Die restlichen 3.900 Zeilen der Konto-Ebene hat sie nie angefasst.
    "steuern": {
        "slices": [
            {"slice": "ergebnishaushalt", "where": {"nr": ["50"]}},
            {"slice": "ergebnishaushalt_konten", "where": {"nr": ["50"]}},
        ],
        "drop": ["line_item_key"],
    },
    # Die Ertragsseite zeigt Zeitreihen über alle Jahre und liest dafür denselben
    # Datensatz wie die Ergebnishaushalt-Seite.
    # Die Konto-Aufschlüsselung erscheint erst, wenn jemand eine Ertragsart anklickt –
    # und dann nur die eine. Der Browser lädt die passende Datei nach, statt alle
    # zwanzig im Seitenpayload mitzuschleppen.
    "ertrag_konten": {
        "slices": ["ergebnishaushalt_konten"],
        "split_by": "nr",
        "drop": ["line_item_key", "nr"],
    },
    # Die Aufgabenbereiche zeigen immer genau ein Jahr (plus Vorjahresvergleich).
    # Aus der Konto-Ebene brauchen sie nur die beiden Positionen, die der
    # Teilhaushalt 14 aufteilt: Versorgung (120) und Umlagen (160).
    "kategorien": {
        "slices": [
            "ergebnishaushalt",
            {"slice": "ergebnishaushalt_konten", "where": {"nr": ["120", "160"]}},
            "produktuebersicht",
        ],
        "split_by": "year",
        "drop": ["line_item_key"],
    },
    # Die Zeitreihe je Aufgabenbereich läuft quer über alle Jahre und kann deshalb
    # nicht mitgeteilt werden – sie braucht aber nur die drei Summenpositionen.
    "kategorien_serie": {
        "slices": [
            {
                "slice": "teilhaushalte",
                "where": {
                    "haushalt_type": ["teilergebnishaushalt"],
                    "nr": ["120", "160", "190"],
                },
            }
        ],
        "drop": ["line_item_key", "teilhaushalt_name"],
    },
    "teilhaushalte": {
        "slices": ["teilhaushalte"],
        "split_by": "teilhaushalt_nr",
        # Nummer und Name stehen in _index.json, in jeder Zeile wären sie Ballast:
        # eine Datei enthält ohnehin genau einen Teilhaushalt.
        "drop": ["line_item_key", "teilhaushalt_nr", "teilhaushalt_name"],
        # Die Übersichtskacheln brauchen alle Teilhaushalte, die Detailansicht nur
        # einen – ohne diesen Index müsste die Seite alle vierzehn Dateien laden,
        # um die Namen zu kennen.
        "index_name": "teilhaushalt_name",
    },
}

# Was neben den Positionen in src/lib/data/ liegen muss, damit eine Seite ohne HTTP
# auskommt: die Jahresliste (summary) und die Dokumentenliste für die Quellenlinks.
LIB_JSON_FILES = ("summary.json", "documents.json")

DEFAULT_LIB_DATA_DIR = ROOT_DIR / "frontend" / "src" / "lib" / "data"


def _slice_frames(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Die Slices aus ITEM_SLICES als DataFrames, ohne sie zu schreiben."""
    df = df.drop(columns=[c for c in UNUSED_ITEM_COLUMNS if c in df.columns])
    frames = {}
    for name, spec in ITEM_SLICES.items():
        sub = df[df["haushalt_type"].isin(spec["haushalt_type"])]
        if "struktur" in spec:
            is_struktur = sub["table_id"].str.startswith("struktur_")
            sub = sub[is_struktur] if spec["struktur"] else sub[~is_struktur]
        level = spec.get("teilhaushalt_level")
        if level:
            nr = sub["teilhaushalt_nr"].astype("string")
            is_sub = nr.str.contains(".", regex=False, na=False)
            sub = sub[is_sub] if level == "sub" else sub[~is_sub]
        frames[name] = sub
    return frames


def _dropped(sub: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return sub.drop(columns=[c for c in columns if c in sub.columns])


def _selected(frames: dict[str, pd.DataFrame], ref: str | dict) -> pd.DataFrame:
    """Ein Slice, optional auf die Zeilen eingeschränkt, die die Seite auch anzeigt.

    Der Filter gehört zum einzelnen Slice, nicht zur Seite: "nr" bedeutet in der
    Konto-Ebene eine Haushaltsposition und in der Produktübersicht eine Produktnummer.
    """
    if isinstance(ref, str):
        return frames[ref]
    sub = frames[ref["slice"]]
    for column, values in ref.get("where", {}).items():
        sub = sub[sub[column].astype("string").isin(values)]
    return sub


def _write_items(sub: pd.DataFrame, path: Path) -> int:
    """Als JSON-Array schreiben, ohne die in diesem Ausschnitt leeren Spalten."""
    sub = sub.dropna(axis=1, how="all")
    path.parent.mkdir(parents=True, exist_ok=True)
    records = json.loads(sub.to_json(orient="records"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, separators=(",", ":"))
    return path.stat().st_size


def export_page_datasets(
    df: pd.DataFrame,
    lib_dir: Path = DEFAULT_LIB_DATA_DIR,
) -> list[Path]:
    """Write the per-page datasets the frontend imports."""
    pages_dir = lib_dir / "pages"
    if pages_dir.exists():
        shutil.rmtree(pages_dir)

    frames = _slice_frames(df)
    written: list[Path] = []
    for page, spec in PAGE_DATASETS.items():
        data = pd.concat(
            [_selected(frames, ref) for ref in spec["slices"]], ignore_index=True
        )
        # Spalten, die diese Seite nie liest. line_item_key allein macht rund ein
        # Fünftel jeder Datei aus – gebraucht wird er nur dort, wo nach Projekt
        # gruppiert wird. Verworfen wird erst nach dem Aufteilen: die Spalte, nach
        # der geteilt wird, steht oft selbst auf der Liste.
        drop = spec.get("drop", [])
        split_by = spec.get("split_by")

        if not split_by:
            path = pages_dir / f"{page}.json"
            size = _write_items(_dropped(data, drop), path)
            written.append(path)
            logger.info("Page data: %-18s %6d rows → %s (%.0f KB)",
                        page, len(data), path.name, size / 1024)
            continue

        keys = sorted(k for k in data[split_by].dropna().unique())
        total = 0
        index = []
        for key in keys:
            part = data[data[split_by] == key]
            path = pages_dir / page / f"{key}.json"
            index.append(_index_entry(part, key, spec.get("index_name")))
            total += _write_items(_dropped(part, drop), path)
            written.append(path)
        if spec.get("index_name"):
            path = pages_dir / page / "_index.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
            written.append(path)
        logger.info("Page data: %-18s %6d rows → %s/ (%d Dateien, %.0f KB gesamt)",
                    page, len(data), page, len(keys), total / 1024)
    return written


def _index_entry(part: pd.DataFrame, key: str, name_column: str | None) -> dict:
    """Ein Eintrag der Übersicht: Schlüssel, Name und wie viele Zeilen je Haushaltsart.

    Der Name steht in jeder Zeile, aber nicht immer vollständig – ältere Pläne kürzen
    ihn ab. Der längste ist der aussagekräftigste.
    """
    entry: dict = {"key": str(key)}
    if name_column and name_column in part.columns:
        names = part[name_column].dropna().astype(str)
        entry["name"] = max(names, key=len, default="")
    entry["counts"] = {
        str(t): int(n) for t, n in part["haushalt_type"].value_counts().items()
    }
    return entry


def current_for_frontend(df: pd.DataFrame) -> pd.DataFrame:
    """Nur die aktuell gültigen Werte – verdrängte liegen in line_items_superseded.csv."""
    if "superseded_by" not in df.columns:
        return df
    return df[df["superseded_by"].isna()]


def export_documents(docs_json: Path, sources_path: Path, out_dir: Path) -> Path:
    """Merge documents.json (fetched metadata) with sources.yaml info."""
    out_path = out_dir / "documents.json"

    # Load fetched documents
    if docs_json.exists():
        with open(docs_json, encoding="utf-8") as f:
            documents = json.load(f)
    else:
        documents = []

    # Load sources for additional metadata
    with open(sources_path, encoding="utf-8") as f:
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
        for field in ("status", "status_note", "status_url"):
            if src.get(field):
                doc.setdefault(field, src[field])

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
            **{f: src[f] for f in ("status", "status_note", "status_url") if src.get(f)},
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

def build_summary(df: pd.DataFrame, authority: dict[str, dict] | None = None) -> dict:
    """Build aggregated summary stats for the frontend."""
    authority = authority or {}
    # Verdrängte Werte (superseded_by gesetzt) gehören in die Vergleichsansichten,
    # nicht in die Kennzahlen – hier zählt pro Position genau ein aktueller Wert.
    overview = df[~df["table_id"].str.startswith("struktur_")]
    if "superseded_by" in overview.columns:
        overview = overview[overview["superseded_by"].isna()]

    # Der Gesamtabschluss misst einen anderen Konsolidierungskreis – er zieht
    # Eigenbetriebe und Beteiligungen mit hinein. In der Zeitreihe des Kernhaushalts
    # erzeugt er einen Sprung (2021: 74,4 statt 64,0 Mio ordentliche Erträge), der
    # wie ein Extraktionsfehler aussieht. Die Daten bleiben erhalten, nur diese
    # Kennzahlen speisen sich nicht daraus.
    consolidated = {
        doc_id for doc_id, info in (authority or {}).items()
        if info.get("doc_type") == "gesamtabschluss"
    }
    if consolidated:
        overview = overview[~overview["document_id"].isin(consolidated)]

    overview = overview.copy()

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
        """Deduplicate by (year, amount_type), keeping the most authoritative document.

        Same ordering as normalize.deduplicate_line_items – sorting by document_id
        alone would let "..._entwurf" win over "..._beschluss" (e sorts after b) and
        silently undo the precedence applied upstream.
        """
        rows = rows.assign(
            _authority=[
                authority_rank(authority, doc_id, year)
                for doc_id, year in zip(rows["document_id"], rows["year"])
            ]
        ).sort_values("_authority")
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


def export_summary(df: pd.DataFrame, out_dir: Path,
                   sources_path: Path = DEFAULT_SOURCES) -> Path:
    """Export summary JSON."""
    out_path = out_dir / "summary.json"
    with open(sources_path, encoding="utf-8") as f:
        source_docs = {d["document_id"]: d for d in yaml.safe_load(f).get("documents", [])}
    summary = build_summary(df, build_authority_index(source_docs))

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
              AND superseded_by IS NULL
        """)

        con.execute("""
            CREATE VIEW finanzhaushalt AS
            SELECT * FROM line_items
            WHERE haushalt_type = 'finanzhaushalt'
              AND table_id NOT LIKE 'struktur_%'
              AND superseded_by IS NULL
        """)

        # Ältere Fassungen derselben Position – Grundlage der Vergleichsansichten
        con.execute("""
            CREATE VIEW superseded AS
            SELECT * FROM line_items
            WHERE superseded_by IS NOT NULL
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
        logger.info("DuckDB: %d rows, 4 views → %s (%.1f KB)", count, out_path, out_path.stat().st_size / 1024)
    finally:
        con.close()

    return out_path


# ── Main entry point ─────────────────────────────────────────────────

def export_to_frontend(
    out_dir: Path = DEFAULT_OUT_DIR,
    frontend_dir: Path = DEFAULT_FRONTEND_DIR,
) -> list[Path]:
    """Copy the published files the frontend serves into its static directory.

    Without this the pipeline stops at data/published/ and the site keeps serving
    whatever was copied there by hand last – a break in the chain that is invisible
    until someone wonders why new numbers do not show up.
    """
    frontend_dir.mkdir(parents=True, exist_ok=True)
    copied = []

    for name in FRONTEND_FILES:
        src = out_dir / name
        if not src.exists():
            logger.warning("Not published, skipping copy: %s", name)
            continue
        dest = frontend_dir / name
        shutil.copy2(src, dest)
        copied.append(dest)
        logger.info("Frontend: %s (%.1f KB)", dest, dest.stat().st_size / 1024)
    return copied


def export_lib_json(
    out_dir: Path = DEFAULT_OUT_DIR,
    lib_dir: Path = DEFAULT_LIB_DATA_DIR,
) -> list[Path]:
    """Kopiere summary.json und documents.json dorthin, wo die Seiten sie importieren.

    In static/ liegen sie weiterhin für den Explorer und für jeden, der sie direkt
    abrufen will – aus einer Serverless-Funktion ist static/ aber nicht lesbar, es
    landet bei adapter-vercel auf dem CDN.
    """
    lib_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in LIB_JSON_FILES:
        src = out_dir / name
        if not src.exists():
            logger.warning("Not published, skipping lib copy: %s", name)
            continue
        dest = lib_dir / name
        shutil.copy2(src, dest)
        copied.append(dest)
        logger.info("Lib data: %s (%.1f KB)", dest.name, dest.stat().st_size / 1024)
    return copied


def export_pdfs_to_frontend(
    raw_dir: Path = DEFAULT_RAW_PDF_DIR,
    frontend_dir: Path = DEFAULT_FRONTEND_DIR,
) -> list[Path]:
    """Copy source PDFs the Quellen page links to, skipping ones already in place."""
    dest_dir = frontend_dir.parent / FRONTEND_PDF_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for src in sorted(raw_dir.glob("*.pdf")):
        dest = dest_dir / src.name
        if dest.exists() and dest.stat().st_size == src.stat().st_size:
            continue
        shutil.copy2(src, dest)
        copied.append(dest)
        logger.info("Frontend PDF: %s (%.1f MB)", dest.name, dest.stat().st_size / 1024 / 1024)
    if not copied:
        logger.info("Frontend PDFs: alle aktuell")
    return copied


def publish_all(
    normalized_csv: Path = DEFAULT_NORMALIZED,
    docs_json: Path = DEFAULT_DOCS_JSON,
    sources_path: Path = DEFAULT_SOURCES,
    out_dir: Path = DEFAULT_OUT_DIR,
    frontend_dir: Path = DEFAULT_FRONTEND_DIR,
    *,
    to_frontend: bool = True,
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
    export_page_datasets(current_for_frontend(df))
    export_documents(docs_json, sources_path, out_dir)
    export_summary(df, out_dir, sources_path)
    export_duckdb(df, out_dir)
    export_lib_json(out_dir)
    if to_frontend:
        export_to_frontend(out_dir, frontend_dir)
        export_pdfs_to_frontend(frontend_dir=frontend_dir)

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
    import sys

    # Die Windows-Konsole spricht cp1252; ohne das stirbt der Lauf ganz am Ende an
    # einem Pfeil in der Abschlussmeldung – nachdem alles geschrieben ist.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

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
    parser.add_argument("--frontend-dir", type=Path, default=DEFAULT_FRONTEND_DIR)
    parser.add_argument(
        "--no-frontend",
        action="store_true",
        help="Nur nach data/published/ schreiben, frontend/static/data/ nicht anfassen",
    )
    args = parser.parse_args()

    publish_all(
        normalized_csv=args.normalized,
        docs_json=args.docs,
        sources_path=args.sources,
        out_dir=args.out_dir,
        frontend_dir=args.frontend_dir,
        to_frontend=not args.no_frontend,
    )


if __name__ == "__main__":
    main()
