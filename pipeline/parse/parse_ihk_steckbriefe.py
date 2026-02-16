"""
Parse IHK Offenbach Gemeindesteckbriefe (2025 edition).

Extracts structured data from all municipality profile PDFs:
  - Gemeindefinanzen: Hebesätze (GrSt A, GrSt B, Gewerbesteuer) + Einnahmen
  - Bevölkerung: Einwohner, Deutsche, Nicht-Deutsche, Fläche, Dichte
  - Kaufkraft: Index, Einzelhandelsrelevante Kaufkraft, Umsatz, Zentralität

Source:  IHK Offenbach am Main – Gemeindesteckbriefe 2025
         https://www.offenbach.ihk.de/standortpolitik/region-offenbach/
         zahlen-daten-fakten/gemeindesteckbriefe/
Data:    "Umfrage der IHK Offenbach" (Gemeindefinanzen)
         Hessisches Statistisches Landesamt (Bevölkerung)
         Michael Bauer Research GmbH (Kaufkraft)

Usage:
    python -m pipeline.parse.parse_ihk_steckbriefe [--dry-run] [-v]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
IHK_DIR = ROOT_DIR / "data" / "raw" / "ihk_gemeindesteckbriefe"
OUTPUT_DIR = ROOT_DIR / "data" / "extracted" / "ihk_gemeindesteckbriefe"

QUELLE_FINANZEN = "IHK Offenbach, Gemeindesteckbrief 2025 (Umfrage der IHK)"
QUELLE_BEVOELKERUNG = "Hessisches Statistisches Landesamt (via IHK-Steckbrief 2025)"
QUELLE_KAUFKRAFT = "Michael Bauer Research GmbH (via IHK-Steckbrief 2025)"

# Map PDF filename stems to canonical kommune names
FILENAME_TO_KOMMUNE: dict[str, str] = {
    "Gemeindesteckbrief_Dietzenbach_2025": "Dietzenbach",
    "Gemeindesteckbrief_Dreieich_2025": "Dreieich",
    "Gemeindesteckbrief_Egelsbach_2025": "Egelsbach",
    "Gemeindesteckbrief_Hainburg_2025": "Hainburg",
    "Gemeindesteckbrief_Heusenstamm_2025": "Heusenstamm",
    "Gemeindesteckbrief_Langen_2025": "Langen",
    "Gemeindesteckbrief_Mainhausen_2025": "Mainhausen",
    "Gemeindesteckbrief_Muehlheim_2025": "Mühlheim am Main",
    "Gemeindesteckbrief_Neu-Isenburg_2025": "Neu-Isenburg",
    "Gemeindesteckbrief_Obertshausen_2025": "Obertshausen",
    "Gemeindesteckbrief_Offenbach_am_Main_2025": "Offenbach am Main",
    "Gemeindesteckbrief_Rodgau_2025": "Rodgau",
    "Gemeindesteckbrief_Roedermark_2025": "Rödermark",
    "Gemeindesteckbrief_Seligenstadt_2025": "Seligenstadt",
    "Steckbrief_Kreis_Offenbach_2025": "Kreis Offenbach",
}


# ── Number helpers ───────────────────────────────────────────────────────────

def _parse_int(val: str | None) -> int | None:
    """Parse a German-formatted integer ('16.762' → 16762, '10' → 10)."""
    if not val:
        return None
    val = val.strip().replace(" ", "").replace(".", "")
    if val in ("*", "-", "...", "/", "x", ""):
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _parse_float(val: str | None) -> float | None:
    """Parse a German-formatted float ('106,2' → 106.2, '5.186,4' → 5186.4)."""
    if not val:
        return None
    val = val.strip().replace(" ", "")
    if val in ("*", "-", "...", "/", "x", ""):
        return None
    # German: thousands separator = '.', decimal = ','
    val = val.replace(".", "").replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return None


def _parse_hebesatz(val: str | None) -> float | None:
    """Parse a Hebesatz value – may be int ('715') or decimal ('660,94').
    Strips footnote markers (*, **, ***) from the value."""
    if not val:
        return None
    val = val.strip().replace(" ", "")
    # Strip trailing footnote asterisks (e.g. '950***' → '950')
    val = val.rstrip("*")
    if val in ("", "-", "...", "/", "x"):
        return None
    val = val.replace(",", ".")
    try:
        f = float(val)
        # Return int if it's a whole number, float otherwise
        return int(f) if f == int(f) else round(f, 2)
    except ValueError:
        return None


# ── Table identification ─────────────────────────────────────────────────────

def _is_finanzen_table(table: list[list[str | None]]) -> bool:
    """Check if a table looks like the Gemeindefinanzen table."""
    if len(table) < 5:
        return False
    flat = " ".join(str(cell) for row in table[:3] for cell in row if cell)
    return "Hebesatz" in flat and ("Gewerbe" in flat or "Grundsteuer" in flat)


def _is_bevoelkerung_table(table: list[list[str | None]]) -> bool:
    """Check if a table looks like the Bevölkerung table."""
    if len(table) < 3:
        return False
    flat = " ".join(str(cell) for row in table[:3] for cell in row if cell)
    return "Bevölkerung" in flat or "insgesamt" in flat and "Deutsche" in flat


def _is_kaufkraft_table(table: list[list[str | None]]) -> bool:
    """Check if a table looks like the Kaufkraft table."""
    if len(table) < 3:
        return False
    flat = " ".join(str(cell) for row in table[:3] for cell in row if cell)
    return "Kaufkraft" in flat and "Index" in flat


# ── Extractors ───────────────────────────────────────────────────────────────

def extract_finanzen(
    table: list[list[str | None]],
    kommune: str,
    pdf_name: str,
) -> list[dict]:
    """
    Extract Gemeindefinanzen rows from a pdfplumber table.

    Expected columns (after header rows):
      [Jahr, Hebesatz Gewerbesteuer, GewSt-Einnahmen T€,
       Hebesatz GrSt A, Hebesatz GrSt B, Einnahmen GrSt A T€, Einnahmen GrSt B T€]
    """
    rows: list[dict] = []
    quelle = f"{QUELLE_FINANZEN}, {pdf_name}"

    # Find the first data row (starts with a year like "2025**" or "2024")
    data_start = None
    for i, row in enumerate(table):
        if row and row[0] and re.match(r"^\d{4}", str(row[0]).strip()):
            data_start = i
            break

    if data_start is None:
        logger.warning("No data rows found in Finanzen table for %s", kommune)
        return []

    for row in table[data_start:]:
        if not row or not row[0]:
            continue

        year_str = re.match(r"(\d{4})", str(row[0]).strip())
        if not year_str:
            continue
        year = int(year_str.group(1))

        # Pad row to 7 columns
        while len(row) < 7:
            row.append(None)

        hs_gew = _parse_hebesatz(row[1])
        einnahmen_gew = _parse_int(row[2])
        hs_grst_a = _parse_hebesatz(row[3])
        hs_grst_b = _parse_hebesatz(row[4])
        einnahmen_grst_a = _parse_int(row[5])
        einnahmen_grst_b = _parse_int(row[6])

        entry = {
            "kommune": kommune,
            "year": year,
            "quelle": quelle,
        }

        if hs_gew is not None:
            rows.append({
                **entry,
                "tax_type": "gewerbesteuer",
                "hebesatz": hs_gew,
                "einnahmen_tsd_eur": einnahmen_gew,
            })

        if hs_grst_a is not None:
            rows.append({
                **entry,
                "tax_type": "grundsteuer_a",
                "hebesatz": hs_grst_a,
                "einnahmen_tsd_eur": einnahmen_grst_a,
            })

        if hs_grst_b is not None:
            rows.append({
                **entry,
                "tax_type": "grundsteuer_b",
                "hebesatz": hs_grst_b,
                "einnahmen_tsd_eur": einnahmen_grst_b,
            })

    return rows


def extract_bevoelkerung(
    table: list[list[str | None]],
    kommune: str,
    pdf_name: str,
) -> dict | None:
    """
    Extract Bevölkerung data from the first table.

    Returns a dict with population data for the kommune (not the Kreis row).
    """
    quelle = f"{QUELLE_BEVOELKERUNG}, {pdf_name}"

    # Find the row that contains the kommune's data (first non-header row
    # that starts with a name, not "Kreis")
    for row in table:
        if not row or not row[0]:
            continue
        label = str(row[0]).strip()
        # Skip header rows and Kreis aggregate
        if label in ("Gebiet", "") or "Kreis" in label:
            continue
        # Skip sub-header rows
        if "insgesamt" in label or "Bevölkerung" in label:
            continue

        # This should be the municipality data row
        while len(row) < 6:
            row.append(None)

        return {
            "kommune": kommune,
            "einwohner_gesamt": _parse_int(row[1]),
            "einwohner_deutsch": _parse_int(row[2]),
            "einwohner_nichtdeutsch": _parse_int(row[3]),
            "flaeche_km2": _parse_float(row[4]),
            "bevoelkerungsdichte": _parse_int(row[5]),
            "stichtag": "2024-06-30",
            "quelle": quelle,
        }

    return None


def extract_kaufkraft(
    table: list[list[str | None]],
    kommune: str,
    pdf_name: str,
) -> dict | None:
    """
    Extract Kaufkraft data.

    Expected rows after header:
      Kaufkraft Index               | value | _ | kreis | hessen
      Einzelhandelsrelevante ...    | value | _ | kreis | hessen
      Einzelhandelsumsatz pro Kopf  | value | _ | kreis | hessen
      Zentralitätskennziffer        | value | _ | kreis | hessen
    """
    quelle = f"{QUELLE_KAUFKRAFT}, {pdf_name}"
    result: dict = {
        "kommune": kommune,
        "jahr": 2025,
        "quelle": quelle,
    }

    for row in table:
        if not row or not row[0]:
            continue
        label = str(row[0]).strip().lower()

        # Find the kommune's value (column 1)
        val = row[1] if len(row) > 1 else None

        if "kaufkraft index" == label:
            result["kaufkraft_index"] = _parse_float(val)
        elif "einzelhandelsrelevante" in label:
            result["einzelhandel_kaufkraft_index"] = _parse_float(val)
        elif "einzelhandelsumsatz" in label:
            result["einzelhandelsumsatz_pro_kopf"] = _parse_float(val)
        elif "zentralität" in label or "zentralitat" in label:
            result["zentralitaetskennziffer"] = _parse_float(val)

    # Only return if we got at least one field
    if "kaufkraft_index" in result:
        return result
    return None


# ── Main parser ──────────────────────────────────────────────────────────────

def parse_steckbrief(pdf_path: Path) -> dict:
    """
    Parse a single IHK Gemeindesteckbrief PDF.

    Returns {
        'kommune': str,
        'finanzen': [...],
        'bevoelkerung': {...} | None,
        'kaufkraft': {...} | None,
    }
    """
    import pdfplumber

    stem = pdf_path.stem
    kommune = FILENAME_TO_KOMMUNE.get(stem, stem)
    pdf_name = pdf_path.name

    logger.info("Parsing %s → %s", pdf_name, kommune)

    result: dict = {
        "kommune": kommune,
        "pdf": pdf_name,
        "finanzen": [],
        "bevoelkerung": None,
        "kaufkraft": None,
    }

    with pdfplumber.open(pdf_path) as pdf:
        # All relevant data is on page 1
        if not pdf.pages:
            logger.warning("Empty PDF: %s", pdf_name)
            return result

        page = pdf.pages[0]
        tables = page.extract_tables()
        logger.debug("Found %d tables on page 1 of %s", len(tables), pdf_name)

        for table in tables:
            if _is_finanzen_table(table):
                result["finanzen"] = extract_finanzen(table, kommune, pdf_name)
                logger.info(
                    "  Finanzen: %d rows (years %s–%s)",
                    len(result["finanzen"]),
                    min(r["year"] for r in result["finanzen"]) if result["finanzen"] else "?",
                    max(r["year"] for r in result["finanzen"]) if result["finanzen"] else "?",
                )

            elif _is_bevoelkerung_table(table):
                result["bevoelkerung"] = extract_bevoelkerung(
                    table, kommune, pdf_name,
                )
                if result["bevoelkerung"]:
                    logger.info(
                        "  Bevölkerung: %s Einwohner",
                        result["bevoelkerung"].get("einwohner_gesamt", "?"),
                    )

            elif _is_kaufkraft_table(table):
                result["kaufkraft"] = extract_kaufkraft(table, kommune, pdf_name)
                if result["kaufkraft"]:
                    logger.info(
                        "  Kaufkraft-Index: %s",
                        result["kaufkraft"].get("kaufkraft_index", "?"),
                    )

    return result


def parse_all(ihk_dir: Path = IHK_DIR) -> list[dict]:
    """Parse all IHK Gemeindesteckbrief PDFs in the given directory."""
    pdf_files = sorted(ihk_dir.glob("*.pdf"))
    if not pdf_files:
        logger.error("No PDFs found in %s", ihk_dir)
        return []

    logger.info("Found %d PDFs in %s", len(pdf_files), ihk_dir)
    results = []
    for pdf_path in pdf_files:
        try:
            result = parse_steckbrief(pdf_path)
            results.append(result)
        except Exception as e:
            logger.error("Failed to parse %s: %s", pdf_path.name, e)

    return results


# ── Output builders ──────────────────────────────────────────────────────────

def build_hebesaetze_rows(results: list[dict]) -> list[dict]:
    """Flatten finanzen data into hebesatz rows for the fetch pipeline."""
    rows = []
    for result in results:
        for entry in result.get("finanzen", []):
            rows.append({
                "kommune": entry["kommune"],
                "year": entry["year"],
                "hebesatz": entry["hebesatz"],
                "tax_type": entry["tax_type"],
                "quelle": entry["quelle"],
            })
    return rows


def build_steuereinnahmen(results: list[dict]) -> list[dict]:
    """Build a flat list of tax revenue data."""
    rows = []
    for result in results:
        for entry in result.get("finanzen", []):
            if entry.get("einnahmen_tsd_eur") is not None:
                rows.append({
                    "kommune": entry["kommune"],
                    "year": entry["year"],
                    "tax_type": entry["tax_type"],
                    "einnahmen_tsd_eur": entry["einnahmen_tsd_eur"],
                    "quelle": entry["quelle"],
                })
    return rows


def build_bevoelkerung(results: list[dict]) -> list[dict]:
    """Build list of population entries."""
    return [r["bevoelkerung"] for r in results if r.get("bevoelkerung")]


def build_kaufkraft(results: list[dict]) -> list[dict]:
    """Build list of purchasing power entries."""
    return [r["kaufkraft"] for r in results if r.get("kaufkraft")]


def write_json(data: object, path: Path, description: str) -> None:
    """Write JSON output file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    count = len(data) if isinstance(data, list) else "?"
    logger.info("Wrote %s (%s entries) → %s", description, count, path.name)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse IHK Offenbach Gemeindesteckbriefe PDFs"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and show summary but do not write output files",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # 1. Parse all PDFs
    results = parse_all()
    if not results:
        logger.error("No results – aborting")
        return

    # 2. Build output datasets
    hebesaetze = build_hebesaetze_rows(results)
    einnahmen = build_steuereinnahmen(results)
    bevoelkerung = build_bevoelkerung(results)
    kaufkraft = build_kaufkraft(results)

    # 3. Summary
    kommunen = sorted(set(r["kommune"] for r in results))
    tax_years = sorted(set(r["year"] for r in hebesaetze)) if hebesaetze else []

    print(f"\n{'='*60}")
    print(f"IHK Gemeindesteckbriefe: {len(results)} PDFs parsed")
    print(f"{'='*60}")
    print(f"Kommunen: {', '.join(kommunen)}")
    print(f"Hebesätze: {len(hebesaetze)} rows", end="")
    if tax_years:
        print(f" (years {min(tax_years)}–{max(tax_years)})")
    else:
        print()
    print(f"Steuereinnahmen: {len(einnahmen)} rows")
    print(f"Bevölkerung: {len(bevoelkerung)} entries")
    print(f"Kaufkraft: {len(kaufkraft)} entries")

    # Show Rödermark detail
    rm_fin = [r for r in hebesaetze if r["kommune"] == "Rödermark"]
    if rm_fin:
        print(f"\nRödermark Hebesätze:")
        for r in sorted(rm_fin, key=lambda x: (x["tax_type"], x["year"])):
            print(f"  {r['year']} {r['tax_type']}: {r['hebesatz']}%")

    rm_bev = next((r for r in bevoelkerung if r["kommune"] == "Rödermark"), None)
    if rm_bev:
        print(f"\nRödermark Bevölkerung: {rm_bev['einwohner_gesamt']} "
              f"(Fläche: {rm_bev['flaeche_km2']} km², "
              f"Dichte: {rm_bev['bevoelkerungsdichte']}/km²)")

    rm_kk = next((r for r in kaufkraft if r["kommune"] == "Rödermark"), None)
    if rm_kk:
        print(f"Rödermark Kaufkraft-Index: {rm_kk['kaufkraft_index']}")

    if args.dry_run:
        print(f"\n(Dry run – no files written)")
        return

    # 4. Write output files
    write_json(hebesaetze, OUTPUT_DIR / "hebesaetze.json",
               "Hebesätze")
    write_json(einnahmen, OUTPUT_DIR / "steuereinnahmen.json",
               "Steuereinnahmen")
    write_json(bevoelkerung, OUTPUT_DIR / "bevoelkerung.json",
               "Bevölkerung")
    write_json(kaufkraft, OUTPUT_DIR / "kaufkraft.json",
               "Kaufkraft")

    # Also write the complete results for reference
    write_json(results, OUTPUT_DIR / "steckbriefe_komplett.json",
               "Komplettdaten")

    print(f"\n✓ Output written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
