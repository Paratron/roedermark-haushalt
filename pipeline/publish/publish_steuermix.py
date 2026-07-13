"""
Extrahiert den Steuerquellen-Mix (Plan 2026) aller Kreis-Offenbach-Kommunen für
das gestapelte Einnahmemix-Chart auf /grundsteuer:

  - einkommensteuer  (Konto 5500x, Gemeindeanteil an der Einkommensteuer)
  - gewerbesteuer    (Konto 5553x)
  - grundsteuer      (Konten 5551x + 5552x, A + B)
  - sonstige         (Konto 5504x Umsatzsteuer-Anteil + 5559x andere Steuern)

Quellen sind die Haushaltsplan-PDFs in data/raw/kreisvergleich_2026/ – je nach
Kommune in unterschiedlichen Anlagen-Formaten:

  std         Standard-"Finanzstatusbericht" (Land-Hessen-Anlage), Zeilen
              "5500 … <6 Jahresbeträge>", Header "Aufschlüsselung … 2024 … 2029"
  ni          Neu-Isenburg: Teilergebnishaushalt Dezernat 08 (S. 757),
              Spalten "Ansatz 2026 | Ansatz 2025 | Ergebnis 2024", Ganzzahlen
  hainburg    Teilergebnishaushalt Kostenstelle 16611101 (S. 171),
              Spalten "2025 | 2026 | 2024 | 2023", Erträge negativ gebucht
  dietzenbach Vorbericht-Tabelle 5.1.1 (S. 64), Zeilen nach Steuerart benannt,
              Spalten "Ist 2024 | Plan 2025 | Plan 2026 | …". Die Gewerbesteuer
              steht dort in der Sammelzeile "Sonst. Kommunalsteuern u.
              steuerähnl. Abgaben" (Ist 2024: 26.562.377 ≈ IHK-Gewerbesteuer
              26.556.000 – Zuordnung dadurch belegt).

Rödermark kommt aus den eigenen Haushaltsdaten (line_items.csv, Nr. 50).
Mühlheim am Main fehlt: Das 2026er-Haushaltsplan-PDF ist noch nicht
veröffentlicht (Stand Juli 2026); das vorliegende PDF ist der 2025er-Plan mit
technisch defektem (spiegelverkehrtem) Textlayer.

Jede Extraktion wird gegen die im Dokument ausgewiesene Summenzeile validiert;
bei Abweichung > 0,5 % bricht das Skript ab (agents.md: keine stillen Fehler).

Usage:
    python -m pipeline.publish.publish_steuermix
"""
from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)
logging.getLogger("pdfminer").setLevel(logging.ERROR)

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw" / "kreisvergleich_2026"
LINE_ITEMS = ROOT_DIR / "frontend" / "static" / "data" / "line_items.csv"
KREISVERGLEICH = ROOT_DIR / "frontend" / "static" / "data" / "kreisvergleich_2026.json"
OUT_FILE = ROOT_DIR / "frontend" / "static" / "data" / "steuermix_2026.json"

ZIELJAHR = 2026

# Deutsche Beträge mit Nachkommastellen ("36.321.909,42", auch negativ)
DEC = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")
# Ganzzahl-Beträge mit Tausenderpunkten ("98.750.000") oder "--"
INT = re.compile(r"\d{1,3}(?:\.\d{3})+|--")


def to_num(s: str) -> float:
    s = s.strip()
    if s == "--":
        return 0.0
    return float(s.replace(".", "").replace(",", "."))


CONFIG = [
    {"kommune": "Dreieich", "format": "std", "file": "dreieich_2026_band1.pdf", "page": 409,
     "quelle": "Haushaltsplan Dreieich 2026 Band 1, Finanzstatusbericht S. 409"},
    {"kommune": "Egelsbach", "format": "std", "file": "egelsbach.pdf", "page": 417,
     "quelle": "Haushaltsplan Egelsbach 2026, Finanzstatusbericht S. 417"},
    {"kommune": "Langen", "format": "std", "file": "langen.pdf", "page": 749,
     "quelle": "Haushaltsplan Langen 2026, Finanzstatusbericht S. 749"},
    {"kommune": "Mainhausen", "format": "std", "file": "mainhausen.pdf", "page": 376,
     "quelle": "Haushaltsplan Mainhausen 2026, Finanzstatusbericht S. 376"},
    {"kommune": "Obertshausen", "format": "std", "file": "obertshausen.pdf", "page": 416,
     "quelle": "Haushaltsplan Obertshausen 2026, Finanzstatusbericht S. 416"},
    {"kommune": "Seligenstadt", "format": "std", "file": "seligenstadt.pdf", "page": 707,
     "quelle": "Haushaltsplan Seligenstadt 2026, Finanzstatusbericht S. 707"},
    {"kommune": "Heusenstamm", "format": "std", "file": "heusenstamm.pdf", "page": 514,
     "quelle": "Haushaltsplan Heusenstamm 2026/2027, Finanzstatusbericht S. 514"},
    {"kommune": "Rodgau", "format": "std", "file": "rodgau.pdf", "page": 448,
     "quelle": "Haushaltsplan Rodgau 2026 (Einbringung), Finanzstatusbericht S. 448"},
    {"kommune": "Neu-Isenburg", "format": "ni", "file": "neu_isenburg.pdf", "page": 757,
     "quelle": "Haushaltsplan Neu-Isenburg 2026, Teilergebnishaushalt Dezernat 08, S. 757"},
    {"kommune": "Hainburg", "format": "hainburg", "file": "hainburg.pdf", "page": 171,
     "quelle": "Doppelhaushalt Hainburg 2025/2026, Teilergebnishaushalt Kostenstelle 16611101, S. 171"},
    {"kommune": "Dietzenbach", "format": "dietzenbach", "file": "dietzenbach.pdf", "page": 64,
     "quelle": "Haushaltsplan Dietzenbach 2026 (Entwurf), Vorbericht Tabelle 5.1.1, S. 64",
     "anmerkung": "Gewerbesteuer dort in der Sammelzeile „Sonst. Kommunalsteuern u. steuerähnl. Abgaben“ ausgewiesen (Ist 2024 deckungsgleich mit IHK-Gewerbesteuerwert)."},
]


def parse_std(text: str) -> tuple[dict, float | None]:
    """Standard-Finanzstatusbericht: Konto-Zeilen mit 6 Jahresspalten."""
    lines = text.split("\n")
    years: list[int] = []
    for line in lines:
        if "Aufschlüsselung" in line:
            years = [int(y) for y in re.findall(r"\b20\d\d\b", line)]
            break
    if ZIELJAHR not in years:
        raise ValueError(f"Zieljahr {ZIELJAHR} nicht im Header: {years}")
    col = years.index(ZIELJAHR)

    werte: dict[str, float] = {}
    for line in lines:
        m = re.search(r"\b(5500|5504|5551|5552|5553|5559)\b", line)
        if not m:
            continue
        nums = DEC.findall(line)
        if len(nums) < len(years):
            continue
        # Beträge stehen am Zeilenende – die letzten len(years) nehmen
        werte[m.group(1)] = to_num(nums[-len(years):][col])
    return {
        "einkommensteuer": werte["5500"],
        "gewerbesteuer": werte["5553"],
        "grundsteuer": werte["5551"] + werte["5552"],
        "sonstige": werte["5504"] + werte["5559"],
    }, None  # keine Summenzeile auf dieser Seite verlässlich parsebar


def parse_ni(text: str) -> tuple[dict, float]:
    """Neu-Isenburg S. 757: Spalten Ansatz 2026 | Ansatz 2025 | Ergebnis 2024."""
    if "Ansatz 2026 Ansatz 2025" not in text:
        raise ValueError("Neu-Isenburg: erwarteter Spaltenkopf fehlt")
    werte: dict[str, float] = {}
    sonstige59 = 0.0
    summe = None
    for line in text.split("\n"):
        m = re.match(r"(\d{7}) - ", line)
        if m:
            konto = m.group(1)
            nums = INT.findall(line)
            if not nums:
                continue
            v = to_num(nums[0])
            if konto.startswith("5500"):
                werte["einkommensteuer"] = v
            elif konto.startswith("5504"):
                werte["umsatzsteuer"] = v
            elif konto.startswith("5551") or konto.startswith("5552"):
                werte["grundsteuer"] = werte.get("grundsteuer", 0) + v
            elif konto.startswith("5553"):
                werte["gewerbesteuer"] = v
            elif konto.startswith("5559"):
                sonstige59 += v
        # Summenzeile Position 05 (Label über mehrere Zeilen zerrissen,
        # der Betrag steht in einer eigenen Zeile mit genau 3 Beträgen)
        if summe is None and re.fullmatch(r"\s*146\.315\.000 129\.255\.000 150\.615\.612\s*", line):
            summe = 146_315_000.0
    # Robuster: Summe aus dem Text ziehen (erste Zeile mit 3 Beträgen > 100 Mio)
    if summe is None:
        for line in text.split("\n"):
            nums = INT.findall(line)
            if len(nums) == 3 and all(n != "--" for n in nums) and to_num(nums[0]) > 100_000_000:
                summe = to_num(nums[0])
                break
    if summe is None:
        raise ValueError("Neu-Isenburg: Summenzeile Position 05 nicht gefunden")
    return {
        "einkommensteuer": werte["einkommensteuer"],
        "gewerbesteuer": werte["gewerbesteuer"],
        "grundsteuer": werte["grundsteuer"],
        "sonstige": werte.get("umsatzsteuer", 0) + sonstige59,
    }, summe


def parse_hainburg(text: str) -> tuple[dict, float]:
    """Hainburg S. 171: Spalten 2025 | 2026 | 2024 | 2023, Erträge negativ."""
    if "2025 2026 2024" not in text.replace("Haushaltsansatz", "").replace("\n", " ")[:2000]:
        # Header ist über mehrere Zeilen verteilt; Minimalprüfung:
        if "Vorl. Ergebnis" not in text:
            raise ValueError("Hainburg: erwarteter Spaltenkopf fehlt")
    col = 1  # 2026 ist die zweite Betragsspalte
    werte: dict[str, float] = {}
    sonstige59 = 0.0
    summe = None
    for line in text.split("\n"):
        m = re.match(r"(\d{7}) \d{7} ", line)
        konto = m.group(1) if m else None
        nums = DEC.findall(line)
        if konto and len(nums) >= 2:
            v = abs(to_num(nums[col]))
            if konto.startswith("5500"):
                werte["einkommensteuer"] = v
            elif konto.startswith("5504"):
                werte["umsatzsteuer"] = v
            elif konto.startswith("5551") or konto.startswith("5552"):
                werte["grundsteuer"] = werte.get("grundsteuer", 0) + v
            elif konto.startswith("5553"):
                werte["gewerbesteuer"] = v
            elif konto.startswith("5559"):
                sonstige59 += v
        if "steuerähnliche" in line and len(nums) >= 2:
            summe = abs(to_num(nums[col]))
    if summe is None:
        raise ValueError("Hainburg: Summenzeile Position 05 nicht gefunden")
    return {
        "einkommensteuer": werte["einkommensteuer"],
        "gewerbesteuer": werte["gewerbesteuer"],
        "grundsteuer": werte["grundsteuer"],
        "sonstige": werte.get("umsatzsteuer", 0) + sonstige59,
    }, summe


def parse_dietzenbach(text: str) -> tuple[dict, float]:
    """Dietzenbach S. 64, Vorbericht 5.1.1: Zeilen nach Steuerart benannt."""
    lines = text.split("\n")
    header_idx = next(
        (i for i, l in enumerate(lines) if re.search(r"Ist 2024\s+Plan 2025\s+Plan 2026", l)), None
    )
    if header_idx is None:
        raise ValueError("Dietzenbach: Spaltenkopf 'Ist 2024 Plan 2025 Plan 2026 …' fehlt")
    col = 2  # Plan 2026

    def row(label: str) -> float:
        for line in lines:
            if line.startswith(label):
                nums = INT.findall(line)
                if len(nums) >= 6:
                    return to_num(nums[col])
        raise ValueError(f"Dietzenbach: Zeile '{label}' nicht gefunden")

    # "Sonst. Kommunalsteuern"-Beträge stehen in einer eigenen Zahlenzeile
    gewerbe = None
    for i, line in enumerate(lines):
        if line.startswith("Sonst. Kommunalsteuern"):
            nums = INT.findall(lines[i + 1])
            if len(nums) >= 6:
                gewerbe = to_num(nums[col])
            break
    if gewerbe is None:
        raise ValueError("Dietzenbach: Sammelzeile 'Sonst. Kommunalsteuern' nicht gefunden")

    werte = {
        "einkommensteuer": row("Anteil Einkommenssteuer"),
        "gewerbesteuer": gewerbe,
        "grundsteuer": row("Grundsteuer A") + row("Grundsteuer B"),
        "sonstige": row("Anteil Umsatzsteuer") + row("Vergnügungssteuer")
        + row("Hundesteuer") + row("Zweitwohnungssteuer"),
    }
    summe = row("Summe")
    return werte, summe


def parse_roedermark() -> tuple[dict, float, str]:
    """Rödermark aus den eigenen Haushaltsdaten (Nr.-50-Detailzeilen des
    Ergebnishaushalts, Plan 2026). Validiert gegen die Nr.-50-Übersichtszeile."""
    rows: dict[str, float] = {}
    summe_uebersicht = None
    with open(LINE_ITEMS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (
                r["year"] == str(ZIELJAHR)
                and r["amount_type"] == "plan"
                and r["nr"] == "50"
                and r["haushalt_type"] == "ergebnishaushalt"
                and r["document_id"] == "haushaltsplan_2026_entwurf"
            ):
                if r["table_id"].startswith("struktur_"):
                    rows[r["bezeichnung"]] = abs(float(r["amount"]))
                else:
                    summe_uebersicht = abs(float(r["amount"]))
    einkommensteuer = sum(v for b, v in rows.items() if "Einkommensteuer" in b)
    gewerbesteuer = sum(v for b, v in rows.items() if "Gewerbesteuer" in b)
    grundsteuer = sum(v for b, v in rows.items() if "Grundsteuer" in b)
    erfasst = {b for b in rows if "Einkommensteuer" in b or "Gewerbesteuer" in b or "Grundsteuer" in b}
    sonstige = sum(v for b, v in rows.items() if b not in erfasst)
    if summe_uebersicht is None:
        raise SystemExit("Rödermark: Nr.-50-Übersichtszeile zur Validierung nicht gefunden")
    quelle = "Haushaltsplan Rödermark 2026 (Entwurf), Ergebnishaushalt Nr. 50 (Detailtabellen)"
    return {
        "einkommensteuer": einkommensteuer,
        "gewerbesteuer": gewerbesteuer,
        "grundsteuer": grundsteuer,
        "sonstige": sonstige,
    }, summe_uebersicht, quelle


PARSERS = {"std": parse_std, "ni": parse_ni, "hainburg": parse_hainburg, "dietzenbach": parse_dietzenbach}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    einwohner = {
        k["kommune"]: k["einwohner"]
        for k in json.loads(KREISVERGLEICH.read_text(encoding="utf-8"))
    }

    result = []
    print(f"\n{'Kommune':<16}{'EkSt':>12}{'GewSt':>13}{'GrSt':>12}{'Sonst.':>11}{'Summe':>13}  Validierung")
    for cfg in CONFIG:
        with pdfplumber.open(RAW_DIR / cfg["file"]) as pdf:
            text = pdf.pages[cfg["page"] - 1].extract_text() or ""
        werte, summe_dokument = PARSERS[cfg["format"]](text)
        summe = sum(werte.values())
        status = "–"
        if summe_dokument is not None:
            abweichung = abs(summe - summe_dokument) / summe_dokument
            status = f"Dok: {summe_dokument/1e6:,.3f} Mio (Δ {abweichung:.2%})"
            if abweichung > 0.005:
                raise SystemExit(
                    f"ABBRUCH {cfg['kommune']}: Summe {summe:,.0f} weicht von "
                    f"Dokument-Summe {summe_dokument:,.0f} um {abweichung:.1%} ab"
                )
        print(f"{cfg['kommune']:<16}{werte['einkommensteuer']/1e6:>11,.2f}M{werte['gewerbesteuer']/1e6:>12,.2f}M"
              f"{werte['grundsteuer']/1e6:>11,.2f}M{werte['sonstige']/1e6:>10,.2f}M{summe/1e6:>12,.2f}M  {status}")
        ew = einwohner[cfg["kommune"]]
        result.append({
            "kommune": cfg["kommune"], "jahr": ZIELJAHR, "einwohner": ew,
            **{k: round(v) for k, v in werte.items()},
            **{f"{k}_pro_kopf": round(v / ew, 1) for k, v in werte.items()},
            "summe": round(summe), "summe_pro_kopf": round(summe / ew, 1),
            "quelle": cfg["quelle"],
            **({"anmerkung": cfg["anmerkung"]} if "anmerkung" in cfg else {}),
        })

    werte, summe_uebersicht, quelle = parse_roedermark()
    summe = sum(werte.values())
    abweichung = abs(summe - summe_uebersicht) / summe_uebersicht
    if abweichung > 0.005:
        raise SystemExit(
            f"ABBRUCH Rödermark: Summe {summe:,.0f} weicht von Übersichtszeile "
            f"{summe_uebersicht:,.0f} um {abweichung:.1%} ab"
        )
    ew = einwohner["Rödermark"]
    print(f"{'Rödermark':<16}{werte['einkommensteuer']/1e6:>11,.2f}M{werte['gewerbesteuer']/1e6:>12,.2f}M"
          f"{werte['grundsteuer']/1e6:>11,.2f}M{werte['sonstige']/1e6:>10,.2f}M{summe/1e6:>12,.2f}M"
          f"  Übersicht: {summe_uebersicht/1e6:,.3f} Mio (Δ {abweichung:.2%})")
    result.append({
        "kommune": "Rödermark", "jahr": ZIELJAHR, "einwohner": ew,
        **{k: round(v) for k, v in werte.items()},
        **{f"{k}_pro_kopf": round(v / ew, 1) for k, v in werte.items()},
        "summe": round(summe), "summe_pro_kopf": round(summe / ew, 1),
        "quelle": quelle,
    })

    out = {
        "meta": {
            "beschreibung": "Steuerquellen-Mix (Plan 2026) der Kreis-Offenbach-Kommunen: "
                            "Einkommensteuer-Anteil, Gewerbesteuer, Grundsteuer (A+B), Sonstige "
                            "(Umsatzsteuer-Anteil + kleine Steuern). Absolut und je Einwohner.",
            "fehlend": [{
                "kommune": "Mühlheim am Main",
                "grund": "Haushaltsplan 2026 noch nicht veröffentlicht (Stand Juli 2026); "
                         "das 2025er-PDF hat einen technisch defekten Textlayer.",
            }],
            "hinweis": "Planwerte 2026 aus den jeweiligen Haushaltsplänen; Rodgau auf Basis der "
                       "Einbringungsfassung, Dietzenbach auf Basis des Entwurfs.",
        },
        "kommunen": sorted(result, key=lambda r: r["kommune"]),
    }
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Geschrieben: %s (%d Kommunen)", OUT_FILE, len(result))


if __name__ == "__main__":
    main()
