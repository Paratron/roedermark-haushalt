"""
Hebesätze (Grundsteuer A/B, Gewerbesteuer) für die Kommunen im Kreis Offenbach
zusammenstellen aus lokalen Quellen:

  1. IHK Offenbach Gemeindesteckbriefe 2025  (alle 13 Kommunen, 2013–2025)
  2. Haushaltssatzungen aus Rödermark-PDFs    (Rödermark, ggf. zusätzliche Jahre)

Usage:
    python -m pipeline.fetch.fetch_hebesaetze [--dry-run] [-v]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
OUTPUT_DIR = ROOT_DIR / "frontend" / "static" / "data"


# ── Manually curated 2026 values (other Kommunen) ────────────────────────────
# The IHK Steckbriefe only reach 2025.  For the 2026 budget round, several
# Kommunen in the Kreis have published new Hebesätze.  These are entered here
# by hand with a source link and a status flag, because they come from
# individual council documents / press releases rather than the IHK survey.
#
# status:
#   "beschlossen" – formally adopted by the Stadtverordnetenversammlung
#   "geplant"     – proposed / in the council process, not yet decided
#
# Only values with a verifiable public source are listed.  Where a Kommune has
# announced an increase but not published the new Hebesatz (e.g. Dreieich
# Grundsteuer B), or where an increase was rejected (e.g. Dietzenbach), no row
# is added – the chart then carries the last known value forward.
# Maintal is intentionally excluded (Main-Kinzig-Kreis, not Kreis Offenbach).

MANUAL_ROWS: list[dict] = [
    {
        "kommune": "Rödermark", "year": 2026,
        "hebesatz": 1327, "tax_type": "grundsteuer_b", "status": "beschlossen",
        "quelle": "Beschluss der Stadtverordnetenversammlung (Juni 2026, namentlich 20:16), rückwirkend zum 01.01.2026 von 990 auf 1.327 %; HSK-Maßnahme „Erhöhung Hebesatz Grundsteuer B“ Schritt 1",
        "quelle_url": "https://www.rheinmainverlag.de/2026/06/25/die-grundsteuer-in-roedermark-geht-weiter-rauf/",
    },
    {
        "kommune": "Rödermark", "year": 2026,
        "hebesatz": 900, "tax_type": "grundsteuer_a", "status": "beschlossen",
        "quelle": "Beschluss der Stadtverordnetenversammlung (Juni 2026), rückwirkend zum 01.01.2026 von 175 auf 900 %",
        "quelle_url": "https://www.rheinmainverlag.de/2026/06/25/die-grundsteuer-in-roedermark-geht-weiter-rauf/",
    },
    {
        "kommune": "Rödermark", "year": 2026,
        "hebesatz": 400, "tax_type": "gewerbesteuer",
        "quelle": "Haushaltssatzung Stadt Rödermark, Haushaltsplan 2026 (Entwurf), S. 4",
        "quelle_url": "/pdfs/haushaltsplan_2026_entwurf.pdf#page=4",
    },
    {
        "kommune": "Mühlheim am Main", "year": 2026,
        "hebesatz": 1450, "tax_type": "grundsteuer_b", "status": "geplant",
        "quelle": "Haushaltssicherungskonzept 2026 (Entwurf), Beschluss vorgesehen 25.06.2026; aktuell gültig sind 983,35 %; op-online.de, 12.06.2026",
        "quelle_url": "https://www.op-online.de/region/muehlheim/details-zum-haushaltssicherungskonzept-bekannt-stadt-muehlheim-plant-massive-grundsteuererhoehung-94347937.html",
    },
    {
        "kommune": "Rodgau", "year": 2026,
        "hebesatz": 1250, "tax_type": "grundsteuer_b", "status": "geplant",
        "quelle": "Beschlussvorlage DS-0134/2026 (Hebesatzsatzung), Entscheidung Stadtverordnetenversammlung 22.06.2026; aktuell gültig sind 990 %",
        "quelle_url": "https://www.rodgau.sitzung-online.de/public/vo020?VOLFDNR=1003031&refresh=false&TOLFDNR=1009607",
    },
    {
        "kommune": "Rodgau", "year": 2026,
        "hebesatz": 760, "tax_type": "grundsteuer_a", "status": "geplant",
        "quelle": "Beschlussvorlage DS-0134/2026 (Hebesatzsatzung), Entscheidung Stadtverordnetenversammlung 22.06.2026",
        "quelle_url": "https://www.rodgau.sitzung-online.de/public/vo020?VOLFDNR=1003031&refresh=false&TOLFDNR=1009607",
    },
]


# ── IHK Gießen-Friedberg Hebesatzumfrage 2026 (Stand 29.05.2026) ──────────────
# Die hessischen IHKs erheben gemeinsam die Hebesätze der Grundsteuer B und der
# Gewerbesteuer „ab 01.01.2026“ für jede hessische Gemeinde.  Diese Übersicht
# ist aktueller als die Offenbacher Gemeindesteckbriefe (die nur bis 2025
# reichen) und liefert für jede Kommune im Kreis Offenbach einen aktuellen
# 2026-Wert mit einheitlicher, öffentlich zugänglicher Quelle.
#
# Rödermark wird bewusst NICHT aus dieser Umfrage übernommen: für die eigene
# Stadt gelten die Haushaltssatzung (990 %) und das Haushaltssicherungskonzept
# (geplant 1.327 %).  Die Umfrage nennt für Rödermark 877,5 %, was nicht der
# beschlossenen Satzung entspricht.
#
# Quelle: IHK Gießen-Friedberg, „Hebesätze 2026 – Grundsteuer B und
# Gewerbesteuer“, Stand 29.05.2026.
IHK_GIFB_2026_URL = (
    "https://www.ihk.de/giessen-friedberg/geschaeftsbereiche/"
    "recht-und-steuern/steuern/hebesatz-2025-7031788"
)
IHK_GIFB_2026_QUELLE = (
    "IHK Gießen-Friedberg, Hebesatzumfrage 2026 – Hebesätze ab 01.01.2026 "
    "(Stand 29.05.2026)"
)

# (kommune, grundsteuer_b, gewerbesteuer) – Landkreis Offenbach inkl. Stadt
# Offenbach.  Rödermark ist hier absichtlich nicht enthalten (s. o.).
_GIFB_2026_KREIS_OFFENBACH = [
    ("Dietzenbach", 950, 405),
    ("Dreieich", 900, 380),
    ("Egelsbach", 1066, 380),
    ("Hainburg", 615, 381),
    ("Heusenstamm", 1327, 400),
    ("Langen", 1268.77, 385),
    ("Mainhausen", 800, 380),
    ("Mühlheim am Main", 983.35, 380),
    ("Neu-Isenburg", 495, 395),
    ("Obertshausen", 1107, 395),
    ("Offenbach am Main", 1230, 440),
    ("Rodgau", 990, 400),
    ("Seligenstadt", 850, 380),
]


def _build_gifb_rows() -> list[dict]:
    rows: list[dict] = []
    for kommune, grundsteuer_b, gewerbesteuer in _GIFB_2026_KREIS_OFFENBACH:
        rows.append({
            "kommune": kommune, "year": 2026, "hebesatz": grundsteuer_b,
            "tax_type": "grundsteuer_b",
            "quelle": IHK_GIFB_2026_QUELLE, "quelle_url": IHK_GIFB_2026_URL,
        })
        rows.append({
            "kommune": kommune, "year": 2026, "hebesatz": gewerbesteuer,
            "tax_type": "gewerbesteuer",
            "quelle": IHK_GIFB_2026_QUELLE, "quelle_url": IHK_GIFB_2026_URL,
        })
    return rows


IHK_GIFB_2026: list[dict] = _build_gifb_rows()


# ── Merge helper ─────────────────────────────────────────────────────────────

def merge_rows(base: list[dict], priority: list[dict]) -> list[dict]:
    """
    Merge two row lists.  Priority entries overwrite base for the same
    (kommune, year, tax_type) key.
    """
    index: dict[tuple[str, int, str], dict] = {}
    for r in base:
        key = (r["kommune"], r["year"], r["tax_type"])
        index[key] = r
    for r in priority:
        key = (r["kommune"], r["year"], r["tax_type"])
        index[key] = r
    return list(index.values())


# ── PDF Haushaltssatzung extraction ──────────────────────────────────────────

_HEBESATZ_LINE_RE = re.compile(
    r"(Grundsteuer\s*[ABC]|Gewerbesteuer)\)?\s*auf\s+(\d{2,4})\s*v\.?\s*H\.?"
    r"(?:\s+(\d{2,4})\s*v\.?\s*H\.?)?",
    re.IGNORECASE,
)

_SATZUNG_YEARS_RE = re.compile(
    r"(?:Haushaltsjahr(?:e)?\s+)(\d{4})(?:\s+und\s+(\d{4}))?",
    re.IGNORECASE,
)


def extract_hebesaetze_from_pdfs(raw_dir: Path) -> list[dict]:
    """
    Scan Haushaltsplan PDFs for Haushaltssatzung paragraphs and extract
    Hebesätze with full provenance (document, page number).
    """
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed – skipping PDF extraction")
        return []

    rows: list[dict] = []
    pdf_files = sorted(raw_dir.glob("haushaltsplan_*.pdf"))
    if not pdf_files:
        logger.warning("No Haushaltsplan PDFs found in %s", raw_dir)
        return []

    for pdf_path in pdf_files:
        doc_id = pdf_path.stem
        logger.debug("Scanning %s for Hebesätze...", pdf_path.name)

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_idx, page in enumerate(pdf.pages[:30]):
                    text = page.extract_text() or ""
                    text_lower = text.lower()

                    if "v.h" not in text_lower:
                        continue
                    if "grundsteuer" not in text_lower and "gewerbesteuer" not in text_lower:
                        continue

                    year_match = _SATZUNG_YEARS_RE.search(text)
                    if not year_match:
                        continue
                    year1 = int(year_match.group(1))
                    year2 = int(year_match.group(2)) if year_match.group(2) else None

                    page_num = page_idx + 1
                    quelle = (
                        f"Haushaltssatzung in {_format_doc_name(doc_id)}, "
                        f"S. {page_num}"
                    )

                    for m in _HEBESATZ_LINE_RE.finditer(text):
                        steuer_raw = m.group(1).strip()
                        satz1 = int(m.group(2))
                        satz2 = int(m.group(3)) if m.group(3) else None

                        tax_type = _steuer_to_tax_type(steuer_raw)
                        if not tax_type:
                            continue

                        rows.append({
                            "kommune": "Rödermark",
                            "year": year1,
                            "hebesatz": satz1,
                            "tax_type": tax_type,
                            "quelle": quelle,
                        })

                        if year2 is not None:
                            rows.append({
                                "kommune": "Rödermark",
                                "year": year2,
                                "hebesatz": satz2 if satz2 is not None else satz1,
                                "tax_type": tax_type,
                                "quelle": quelle,
                            })

                    break  # only first matching page per PDF

        except Exception as e:
            logger.error("Failed to read %s: %s", pdf_path.name, e)

    logger.info("Extracted %d Hebesatz entries from %d PDFs", len(rows), len(pdf_files))
    return rows


def _steuer_to_tax_type(name: str) -> str | None:
    n = name.upper().replace(" ", "")
    if "GRUNDSTEUERA" in n:
        return "grundsteuer_a"
    if "GRUNDSTEUERB" in n:
        return "grundsteuer_b"
    if "GEWERBESTEUER" in n:
        return "gewerbesteuer"
    return None


def _format_doc_name(doc_id: str) -> str:
    """'haushaltsplan_2024_2025_beschluss' → 'Haushaltsplan 2024/2025 (Beschluss)'"""
    parts = doc_id.split("_")
    typ = parts[0].capitalize()
    years = [p for p in parts[1:] if p.isdigit()]
    suffix = [p for p in parts[1:] if not p.isdigit()]
    label = typ
    if years:
        label += " " + "/".join(years)
    if suffix:
        label += " (" + ", ".join(s.capitalize() for s in suffix) + ")"
    return label


# ── Output ───────────────────────────────────────────────────────────────────

def build_json(rows: list[dict], tax_type: str, description: str) -> dict:
    """
    Build the JSON structure expected by the frontend:
      { meta: {…}, data: [{ kommune, year, hebesatz, quelle }] }
    """
    filtered = sorted(
        [r for r in rows if r["tax_type"] == tax_type],
        key=lambda r: (r["kommune"], r["year"]),
    )

    data = []
    for r in filtered:
        entry = {
            "kommune": r["kommune"],
            "year": r["year"],
            "hebesatz": r["hebesatz"],
            "quelle": r.get("quelle", ""),
        }
        if r.get("status"):
            entry["status"] = r["status"]
        if r.get("quelle_url"):
            entry["quelle_url"] = r["quelle_url"]
        data.append(entry)

    return {
        "meta": {
            "description": description,
            "unit": "Prozent",
            "note": (
                "Datenquellen: IHK Gießen-Friedberg, Hebesatzumfrage 2026 "
                "(Hebesätze ab 01.01.2026, Stand 29.05.2026) für die aktuellen "
                "2026-Werte aller Kommunen im Kreis Offenbach; IHK Offenbach "
                "Gemeindesteckbriefe (Umfrage der IHK, 2013–2025) für die "
                "Vorjahre; Haushaltssatzungen der Stadt Rödermark sowie einzeln "
                "belegte Beschlussvorlagen für geplante Erhöhungen 2026 "
                "(siehe Quellenangabe je Eintrag)."
            ),
        },
        "data": data,
    }


def write_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Wrote %s (%d entries)", path.name, len(data["data"]))


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hebesätze aus IHK-Steckbriefen und Haushaltssatzungen zusammenstellen"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Nur parsen und Zusammenfassung zeigen, nichts schreiben")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Ausführliches Logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # 1. IHK Gemeindesteckbriefe (primary source: all Kommunen, 2013–2025)
    from pipeline.parse.parse_ihk_steckbriefe import parse_all, build_hebesaetze_rows

    ihk_results = parse_all()
    all_rows = build_hebesaetze_rows(ihk_results)
    logger.info("IHK Steckbriefe: %d Hebesatz-Rows", len(all_rows))

    # 2. PDF Haushaltssatzungen (Rödermark, fills additional years like 2026)
    pdf_rows = extract_hebesaetze_from_pdfs(RAW_DIR)
    if pdf_rows:
        all_rows = merge_rows(all_rows, pdf_rows)
        logger.info("After PDF merge: %d rows (+%d from PDFs)", len(all_rows), len(pdf_rows))

    # 3. IHK Gießen-Friedberg Hebesatzumfrage 2026 (alle Kommunen im Kreis
    #    Offenbach, aktueller als die Steckbriefe; Rödermark ausgenommen)
    if IHK_GIFB_2026:
        all_rows = merge_rows(all_rows, IHK_GIFB_2026)
        logger.info("After GiFb 2026 merge: %d rows (+%d survey)", len(all_rows), len(IHK_GIFB_2026))

    # 4. Manually curated, individually sourced 2026 values – geplante
    #    Erhöhungen, die die GiFb-Werte bewusst übersteuern
    if MANUAL_ROWS:
        all_rows = merge_rows(all_rows, MANUAL_ROWS)
        logger.info("After manual merge: %d rows (+%d curated)", len(all_rows), len(MANUAL_ROWS))

    if not all_rows:
        logger.error("Keine Daten – Abbruch")
        return

    # Summary
    tax_types: dict[str, int] = {}
    for r in all_rows:
        tax_types[r["tax_type"]] = tax_types.get(r["tax_type"], 0) + 1

    kommunen = sorted(set(r["kommune"] for r in all_rows))
    years = sorted(set(r["year"] for r in all_rows))

    roedermark = sorted(
        [r for r in all_rows if r["kommune"] == "Rödermark"],
        key=lambda r: (r["tax_type"], r["year"]),
    )

    print(f"\n{'='*60}")
    print(f"Hebesätze: {len(all_rows)} rows, {len(kommunen)} Kommunen, "
          f"Jahre {min(years)}–{max(years)}")
    print(f"{'='*60}")
    for t, c in sorted(tax_types.items()):
        print(f"  {t}: {c} rows")
    print(f"\nRödermark:")
    for r in roedermark:
        src = f" ({r['quelle']})" if r.get("quelle") else ""
        print(f"  {r['year']} {r['tax_type']}: {r['hebesatz']}%{src}")

    if args.dry_run:
        print("\n(Dry run – keine Dateien geschrieben)")
        return

    # 3. Write output JSON files
    for tax_type, desc in [
        ("grundsteuer_b", "Grundsteuer B Hebesätze der Kommunen im Kreis Offenbach"),
        ("gewerbesteuer", "Gewerbesteuer Hebesätze der Kommunen im Kreis Offenbach"),
        ("grundsteuer_a", "Grundsteuer A Hebesätze der Kommunen im Kreis Offenbach"),
    ]:
        if tax_type in tax_types:
            data = build_json(all_rows, tax_type, desc)
            write_json(data, OUTPUT_DIR / f"hebesaetze_{tax_type}.json")

    print(f"\n✓ {len(all_rows)} rows → {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
