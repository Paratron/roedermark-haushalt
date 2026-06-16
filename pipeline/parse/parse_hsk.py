"""Specialized parser for the Haushaltssicherungskonzept (HSK) 2026.

The HSK is a 18-page document that explains how the city of Rödermark plans to
consolidate its budget after the 2026 draft ran a deficit of 13.8 Mio €.

It contains three machine-readable annexes:
  • Anlage 1 (pages 13–15): Konsolidierungsmaßnahmen Ergebnishaushalt
      → ~110 single measures, each with Fachbereich, Produkt, description,
        Hebesatzpunkte Grundsteuer B and values for 2026–2030 + sum.
  • Anlage 2 (pages 16–17): Konsolidierungsmaßnahmen Finanzhaushalt
      → mirror of Anlage 1 with cash-flow signs (not re-extracted; the
        Ergebnishaushalt is the relevant view for citizens).
  • Anlage 3 (page 18): Abbaupfad / Liquiditätsentwicklung 2025–2030.
  • Investment Änderungsliste (page 10): per-project investment cuts.

This parser turns the annexes into a single JSON artifact
``hsk_2026.json`` that the frontend consumes for a dedicated page. Every
number keeps a page reference (provenance) back into the PDF.

Usage:
    python -m pipeline.parse.parse_hsk
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PDF = ROOT_DIR / "data" / "raw" / "Haushaltssicherungskonzept2026.pdf"
DEFAULT_OUT_DIR = ROOT_DIR / "data" / "published"
FRONTEND_DATA_DIR = ROOT_DIR / "frontend" / "static" / "data"

SOURCE_DOCUMENT = "haushaltssicherungskonzept_2026"
SOURCE_FILE = "Haushaltssicherungskonzept2026.pdf"

YEARS = [2026, 2027, 2028, 2029, 2030]


# ── Number parsing ────────────────────────────────────────────────────

def parse_german_number(s: str | None) -> float | None:
    """Parse a German number string (e.g. '-3.117.000,00') into float."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    # keep only number-ish characters (handles stray text like 'h 0,76')
    m = re.search(r"-?\d[\d.]*(?:,\d+)?", s)
    if not m:
        return None
    token = m.group(0)
    if "," in token:
        token = token.replace(".", "").replace(",", ".")
    else:
        token = token.replace(".", "")
    try:
        return float(token)
    except ValueError:
        return None


# ── Fachbereich labels ────────────────────────────────────────────────
# Derived from the measures themselves; kept descriptive and verifiable.
FB_LABELS = {
    "FB1": "Zentrale Steuerung & Verwaltung",
    "FB2": "Finanzen & Steuerverwaltung",
    "FB3": "Öffentliche Ordnung & Sicherheit",
    "FB4": "Kinder, Jugend, Schule & Soziales",
    "FB5": "Kultur, Sport & Bäder",
    "FB6": "Stadtentwicklung, Umwelt & Klima",
    "FB7": "Bauen, Tiefbau, Friedhof & Abfall",
    "SB14": "Steuern & Allgemeine Finanzwirtschaft",
    "ALLE": "Alle Fachbereiche (Querschnitt)",
}


# ── Citizen-facing categories ─────────────────────────────────────────
# Each measure is classified into one bürgernahe Kategorie purely by keyword
# rules so the data stays explainable and reproducible (see agents.md).

CATEGORY_LABELS = {
    "steuern": "Höhere Steuern",
    "gebuehren": "Höhere Gebühren & Entgelte",
    "leistungen": "Gekürzte Leistungen & Zuschüsse",
    "personal": "Personal & Stellen",
    "verwaltung": "Interne Sach- & Verwaltungskosten",
    "gebaeude": "Gebäude & Unterhaltung",
    "sonstige": "Sonstige Maßnahmen",
}

# Order matters: first matching rule wins.
_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("steuern", [
        "grundsteuer", "gewerbesteuer", "hundesteuer", "hundebestand",
        "spielapparatesteuer", "heimatumlage", "gewerbesteuerumlage",
    ]),
    ("gebuehren", [
        "gebühr", "gebuehr", "entgelt", "benutzungsgebühren", "parkhaus",
        "beiträge", "beitrag", "eintritt",
    ]),
    ("leistungen", [
        "zuschuss", "zuschüsse", "zuweisung", "musikschule", "freiwillig",
        "prävention", "leitbild", "förderung", "veranstaltung",
        "öffentlichkeitsarbeit", "anreizprogramm",
    ]),
    ("personal", [
        "stelle", "stellen", "personaleinstellung", "azubi", "pk ",
        "pk kitas", "pk durch", "fbl", "fbl ", "nn ", "eg8", "eg7", "eg5",
        "wiederbesetz", "neu besetzt", "belegschaft", "dienstjubiläen",
        "fachkräftemangel", "austritte", "bäderbetrieb", "badehausleiter",
        "friedhofsgärtner", "polizeidienst", "steuerverwaltung",
    ]),
    ("gebaeude", [
        "bauliche unterhaltung", "schließdienst", "gebäudekosten",
        "grabenpflege", "brückensanierung", "friedhof", "afa",
        "abschreibung",
    ]),
    ("verwaltung", [
        "dv-benutzerentgelte", "edv", "porto", "versand", "büromaterial",
        "drucksachen", "verbrauchsmaterial", "materialaufwand", "honorar",
        "fortbildung", "weiterbildung", "schulung", "beratung", "gutachten",
        "planung", "fachliteratur", "zeitungen", "internet", "printmedien",
        "wärmeplanung", "digitalisierung", "betrieb", "wartung", "dienst",
    ]),
]


# Some measures contain fee words ("entgelt", "gebühr") but are really
# internal IT costs (DV-Benutzerentgelte, paid by the city) or staffing
# lines. These specific keywords must win over the generic gebuehren rule,
# so they are checked before _CATEGORY_RULES.
_PRIORITY_RULES: list[tuple[str, list[str]]] = [
    ("verwaltung", ["dv-benutzerentgelte"]),
    ("personal", ["stelle", "stellen", "steuerverwaltung"]),
]


def classify_measure(massnahme: str, produkt: str, fb: str) -> str:
    """Assign a citizen-facing category to a single measure by keyword."""
    text = f"{massnahme} {produkt}".lower()
    for category, keywords in (*_PRIORITY_RULES, *_CATEGORY_RULES):
        if any(kw in text for kw in keywords):
            return category
    return "sonstige"


# ── Einnahme vs. Ausgabe (revenue side vs. expense side) ──────────────
# A measure either lifts the revenue side (Erträge/Steuern/Gebühren) or
# lowers the expense side (Aufwand/Personal/Sachkosten). Most categories
# imply this directly; only "sonstige" is mixed and decided by keyword.

_REVENUE_KEYWORDS = (
    "ertrag", "erträge", "bußgeld", "bussgeld", "gip", "einnahm",
)


def classify_art(kategorie: str, massnahme: str, is_grundsteuer_b: bool) -> str:
    """Return 'einnahme' (revenue side) or 'ausgabe' (expense side)."""
    if is_grundsteuer_b or kategorie in ("steuern", "gebuehren"):
        return "einnahme"
    if kategorie == "sonstige" and any(
        kw in massnahme.lower() for kw in _REVENUE_KEYWORDS
    ):
        return "einnahme"
    return "ausgabe"


# ── Anlage 1: Konsolidierungsmaßnahmen Ergebnishaushalt ───────────────

# Rows whose "Maßnahme" text marks a total / structural line rather than a
# real consolidation measure.
_TOTAL_MARKERS = (
    "ordentliches ergebnis",
    "summe maßnahmen",
    "neues ordentliches ergebnis",
    "außerordentliches ergeb",
    "ausserordentliches ergeb",
)


def _split_row(cells: list[str | None]) -> dict | None:
    """Split a raw Anlage-1 row into structured fields.

    Layout after dropping the leading row-number column:
        [FB, Produkt, Maßnahme, Hebesatzpunkte, 2026, 2027, 2028, 2029, 2030, Summe]
    Some rows wrap the Maßnahme into an extra cell; we parse from the right.
    """
    cells = [c if c is not None else "" for c in cells]
    # drop spreadsheet column-letter header rows
    if cells[:1] == ["A"]:
        return None
    if not any(c.strip() for c in cells):
        return None

    # last 6 numeric columns: 2026..2030 + Summe
    if len(cells) < 8:
        return None
    nums = cells[-6:]
    hebe_raw = cells[-7]
    fb = cells[0].strip()
    produkt = cells[1].strip()
    massnahme = " ".join(c.strip() for c in cells[2:-7] if c and c.strip()).strip()

    values = [parse_german_number(n) for n in nums]
    # need at least the Summe column to be a numeric data row
    if values[-1] is None and all(v is None for v in values[:-1]):
        return None

    return {
        "fb": fb,
        "produkt": produkt,
        "massnahme": massnahme,
        "hebesatzpunkte": parse_german_number(hebe_raw),
        "values": values[:5],
        "summe": values[5],
    }


def parse_anlage1(pdf: pdfplumber.PDF) -> tuple[list[dict], dict]:
    """Parse the Ergebnishaushalt measures (pages 13–15).

    Returns (measures, totals) where totals holds the summary rows.
    """
    measures: list[dict] = []
    totals: dict = {}
    current_fb = ""

    for page_idx in (12, 13, 14):  # 0-based → pages 13–15
        page = pdf.pages[page_idx]
        page_no = page_idx + 1
        tables = page.extract_tables()
        if not tables:
            continue
        for raw_row in tables[0]:
            row = _split_row(raw_row[1:])  # drop leading row-number cell
            if not row:
                continue

            # Total/structural rows often carry their label in the FB column
            # (e.g. "SUMME", "NEUES ORDENTLICHES ERGEBNIS ..."). Combine both
            # columns for marker detection.
            low = row["massnahme"].lower()
            marker = f"{row['fb']} {row['massnahme']}".strip().lower()

            # ── structural / total rows ──
            if marker.startswith("ordentliches ergebnis nach änderungsliste"):
                totals["ordentliches_ergebnis_aliste"] = {
                    "values": row["values"], "summe": row["summe"], "page": page_no,
                }
                continue
            if "maßnahmen ohne grundsteuer" in marker:
                totals["summe_ohne_grundsteuer_b"] = {
                    "values": row["values"], "summe": row["summe"], "page": page_no,
                }
                continue
            if "maßnahmen mit grundsteuer" in marker:
                totals["summe_mit_grundsteuer_b"] = {
                    "values": row["values"], "summe": row["summe"], "page": page_no,
                }
                continue
            if "neues ordentliches ergebnis" in marker:
                totals["neues_ordentliches_ergebnis"] = {
                    "values": row["values"], "summe": row["summe"], "page": page_no,
                }
                continue
            if "ergebenis nach" in marker or "ergebnis nach äl und hsk" in marker:
                totals["ao_ergebnis_nach_hsk"] = {
                    "values": row["values"], "summe": row["summe"], "page": page_no,
                }
                continue
            if "ergebnis entwurf" in marker:
                totals["ao_ergebnis_entwurf"] = {
                    "values": row["values"], "summe": row["summe"], "page": page_no,
                }
                continue

            # ── außerordentliche Verkäufe (asset sales) ──
            if low.startswith("verkauf"):
                totals.setdefault("verkaeufe", []).append({
                    "bezeichnung": row["massnahme"],
                    "values": row["values"],
                    "summe": row["summe"],
                    "page": page_no,
                })
                continue

            if any(m in marker for m in _TOTAL_MARKERS):
                continue

            # ── carry the Fachbereich forward (only for real FB codes) ──
            if re.match(r"^(FB\d+|SB\d+|ALLE)$", row["fb"]):
                current_fb = row["fb"]

            # ── Grundsteuer B is the single dominant lever – flag it ──
            is_grundsteuer_b = "erhöhung hebesatz grundsteuer b" in low

            if not row["massnahme"]:
                continue

            # skip repeated table header rows (the year labels parse as numbers)
            if row["produkt"].lower() == "produkt" or row["massnahme"].lower() == "maßnahme":
                continue

            category = classify_measure(row["massnahme"], row["produkt"], current_fb)
            kategorie = "steuern" if is_grundsteuer_b else category
            art = classify_art(kategorie, row["massnahme"], is_grundsteuer_b)
            if kategorie == "sonstige":
                gruppe_label = (
                    "Sonstige Erträge" if art == "einnahme"
                    else "Sonstige Einsparungen"
                )
            elif is_grundsteuer_b:
                gruppe_label = CATEGORY_LABELS["steuern"]
            else:
                gruppe_label = CATEGORY_LABELS[category]
            measures.append({
                "fb": current_fb,
                "fb_label": FB_LABELS.get(current_fb, current_fb),
                "produkt": row["produkt"] or None,
                "massnahme": row["massnahme"],
                "kategorie": kategorie,
                "kategorie_label": CATEGORY_LABELS["steuern"] if is_grundsteuer_b
                else CATEGORY_LABELS[category],
                "art": art,
                "gruppe_label": gruppe_label,
                "is_grundsteuer_b": is_grundsteuer_b,
                "hebesatzpunkte": row["hebesatzpunkte"],
                "werte": dict(zip([str(y) for y in YEARS], row["values"])),
                "summe": row["summe"],
                "page": page_no,
            })

    return measures, totals


# ── Anlage 3: Abbaupfad / Liquidität (page 18) ────────────────────────

def parse_anlage3(pdf: pdfplumber.PDF) -> list[dict]:
    """Parse the Abbaupfad table (page 18) into a year-indexed series."""
    page = pdf.pages[17]
    page_no = 18
    rows = {r[1]: r[2:] for r in (page.extract_tables()[0]) if r[1]}

    def vals(label_contains: str) -> list[float | None]:
        for key, cells in rows.items():
            if key and label_contains.lower() in key.lower():
                return [parse_german_number(c) for c in cells]
        return [None] * 6

    # Ergebnishaushalt block has columns 2025..2030 (6 cols);
    # the deficit/HSK rows are populated from 2026 onwards.
    defizit = vals("Defizit ErgHH")
    veraenderung = vals("Veränderung durch HSK")
    ergebnis = vals("Ordentliches Ergebnis nach HSK")
    liquiditaet = vals("Gessamt Liquidität nach HSK")
    saldo_aliste = vals("Saldo lfd. Verwtätigkeit nach Ä-Liste")
    saldo_hsk = vals("Saldo lfd. Verwtätigkeit nach HSK")

    # Ergebnis columns map to 2026..2030 (index 1..5 of the 6-col block,
    # because col 0 = 2025 which is empty for these rows).
    series = []
    for i, year in enumerate(YEARS):
        series.append({
            "year": year,
            "defizit_aliste": defizit[i + 1] if len(defizit) > i + 1 else None,
            "veraenderung_hsk": veraenderung[i + 1] if len(veraenderung) > i + 1 else None,
            "ergebnis_nach_hsk": ergebnis[i + 1] if len(ergebnis) > i + 1 else None,
            "liquiditaet": liquiditaet[i + 1] if len(liquiditaet) > i + 1 else None,
            "saldo_aliste": saldo_aliste[i] if len(saldo_aliste) > i else None,
            "saldo_hsk": saldo_hsk[i] if len(saldo_hsk) > i else None,
            "page": page_no,
        })
    return series


# ── Investment Änderungsliste (page 10) ───────────────────────────────

_FB_HEADER_RE = re.compile(r"^Fachbereich\s+(\d+)", re.IGNORECASE)
_INV_ROW_RE = re.compile(
    r"^(\d[\w./-]*[KE])\s+(.+?)\s+(-?[\d.]+(?:\s+-?[\d.]+){0,3})$"
)


def parse_investitionen(pdf: pdfplumber.PDF) -> list[dict]:
    """Parse the investment Änderungsliste (page 10) per project.

    Each line: <code> <name> <2026> [<2027> <2028> <2029>]
    Negative values = reductions/cuts; positive = shifts into later years.
    """
    page = pdf.pages[9]
    page_no = 10
    text = page.extract_text() or ""
    items: list[dict] = []
    current_fb = ""

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _FB_HEADER_RE.match(line)
        if m:
            current_fb = f"FB{m.group(1)}"
            continue
        rm = _INV_ROW_RE.match(line)
        if not rm:
            continue
        code = rm.group(1)
        name = rm.group(2).strip()
        nums = [parse_german_number(n) for n in rm.group(3).split()]
        # pad to 4 finance-plan years (2026–2029)
        nums = (nums + [None, None, None, None])[:4]
        summe = sum(n for n in nums if n is not None)
        items.append({
            "fb": current_fb,
            "fb_label": FB_LABELS.get(current_fb, current_fb),
            "code": code,
            "name": name,
            "werte": dict(zip(["2026", "2027", "2028", "2029"], nums)),
            "summe": round(summe, 2),
            "page": page_no,
        })
    return items


# ── Static narrative facts (with page references) ─────────────────────
# These come from the running text and are kept here with explicit page refs
# so the frontend can cite them. Values verified against pages 3, 8, 9.
NARRATIVE = {
    "defizit_entwurf_2026": {"value": 13800000, "text": "13,8 Mio. €", "page": 3},
    "ordentliches_ergebnis_2026_vor_hsk": {"value": 13209000, "text": "13.209 T€", "page": 8},
    "ordentliches_ergebnis_2026_nach_hsk": {"value": 6328000, "text": "6.328 T€", "page": 8},
    "investitionen_2026_vorher": {"value": 22557000, "text": "22.557 T€", "page": 9},
    "investitionen_2026_kuerzung": {"value": 11987000, "text": "11.987 T€", "page": 9},
    "investitionen_2026_nachher": {"value": 10569000, "text": "10.569 T€", "page": 9},
    "kreditaufnahme_2026_vorher": {"value": 16319000, "text": "16.319 T€", "page": 9},
    "kreditaufnahme_2026_kuerzung": {"value": 12043000, "text": "12.043 T€", "page": 9},
    "kreditaufnahme_2026_nachher": {"value": 4276000, "text": "4.276 T€", "page": 9},
    "liquiditaet_31_12_2025": {"value": 11128634, "text": "11.128.634 €", "page": 12},
    "ausgleich_ab_jahr": {"value": 2029, "text": "ab 2029", "page": 11},
    "altfehlbetrag_getilgt": {"value": 2030, "text": "im Jahr 2030", "page": 11},
    "kommunalberatung_termin": {"value": "2026-06-25", "text": "25.06.2026", "page": 7},
}


# ── Main ──────────────────────────────────────────────────────────────

def build(pdf_path: Path = DEFAULT_PDF) -> dict:
    logger.info("Parsing HSK 2026 from %s", pdf_path)
    pdf = pdfplumber.open(pdf_path)

    measures, totals = parse_anlage1(pdf)
    abbaupfad = parse_anlage3(pdf)
    investitionen = parse_investitionen(pdf)

    # ── aggregate per citizen category ──
    by_category: dict[str, dict] = {}
    for m in measures:
        cat = m["kategorie"]
        bucket = by_category.setdefault(cat, {
            "kategorie": cat,
            "label": CATEGORY_LABELS[cat],
            "summe": 0.0,
            "anzahl": 0,
        })
        if m["summe"]:
            bucket["summe"] += m["summe"]
        bucket["anzahl"] += 1
    for b in by_category.values():
        b["summe"] = round(b["summe"], 2)

    # ── two pillars: revenue side vs. expense side ──
    year_keys = [str(y) for y in YEARS]

    def _new_gruppe(label: str) -> dict:
        return {
            "label": label,
            "summe": 0.0,
            "anzahl": 0,
            "werte": {y: 0.0 for y in year_keys},
        }

    saeulen: dict[str, dict] = {
        "einnahmen": {"summe": 0.0, "anzahl": 0,
                      "werte": {y: 0.0 for y in year_keys}, "gruppen": {}},
        "ausgaben": {"summe": 0.0, "anzahl": 0,
                     "werte": {y: 0.0 for y in year_keys}, "gruppen": {}},
    }
    for m in measures:
        pillar = "einnahmen" if m["art"] == "einnahme" else "ausgaben"
        side = saeulen[pillar]
        gruppe = side["gruppen"].setdefault(
            m["gruppe_label"], _new_gruppe(m["gruppe_label"])
        )
        gruppe["anzahl"] += 1
        side["anzahl"] += 1
        if m["summe"]:
            gruppe["summe"] += m["summe"]
            side["summe"] += m["summe"]
        for y in year_keys:
            v = m["werte"].get(y) or 0.0
            gruppe["werte"][y] += v
            side["werte"][y] += v

    for side in saeulen.values():
        side["summe"] = round(side["summe"], 2)
        side["werte"] = {y: round(v, 2) for y, v in side["werte"].items()}
        gruppen = []
        for g in side["gruppen"].values():
            g["summe"] = round(g["summe"], 2)
            g["werte"] = {y: round(v, 2) for y, v in g["werte"].items()}
            gruppen.append(g)
        # biggest budget effect first (most negative)
        side["gruppen"] = sorted(gruppen, key=lambda g: g["summe"])

    # ── headline figures ──
    grundsteuer_b = next(
        (m for m in measures if m["is_grundsteuer_b"]), None
    )
    summe_ohne = totals.get("summe_ohne_grundsteuer_b", {}).get("summe")
    summe_mit = totals.get("summe_mit_grundsteuer_b", {}).get("summe")
    grundsteuer_b_summe = grundsteuer_b["summe"] if grundsteuer_b else None

    kennzahlen = {
        "konsolidierung_mit_grundsteuer_b": summe_mit,
        "konsolidierung_ohne_grundsteuer_b": summe_ohne,
        "grundsteuer_b_summe": grundsteuer_b_summe,
        "grundsteuer_b_anteil": (
            round(abs(grundsteuer_b_summe) / abs(summe_mit), 4)
            if grundsteuer_b_summe and summe_mit else None
        ),
        "eigene_massnahmen_anteil": (
            round(abs(summe_ohne) / abs(summe_mit), 4)
            if summe_ohne and summe_mit else None
        ),
        "anzahl_massnahmen": len(measures),
    }

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_document": SOURCE_DOCUMENT,
        "source_file": SOURCE_FILE,
        "laufzeit": [2026, 2030],
        "genehmigungsfaehig": False,
        "narrative": NARRATIVE,
        "kennzahlen": kennzahlen,
        "abbaupfad": abbaupfad,
        "kategorien": sorted(
            by_category.values(), key=lambda b: b["summe"]
        ),
        "saeulen": saeulen,
        "massnahmen": measures,
        "totals": totals,
        "investitionen": investitionen,
    }
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    data = build()

    DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)

    for out_dir in (DEFAULT_OUT_DIR, FRONTEND_DATA_DIR):
        out_path = out_dir / "hsk_2026.json"
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Wrote %s", out_path)

    logger.info(
        "HSK 2026: %d Maßnahmen, %d Abbaupfad-Jahre, %d Investitionen",
        len(data["massnahmen"]), len(data["abbaupfad"]), len(data["investitionen"]),
    )


if __name__ == "__main__":
    main()
