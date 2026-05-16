"""
Extrahiert Kerndaten (Erträge, Aufwendungen, Jahresergebnis) aus den
Haushaltssatzungen aller Kommunen des Kreises Offenbach für den Kreisvergleich.
"""
import json
import re
import pdfplumber
from pathlib import Path

RAW_DIR = Path("data/raw/kreisvergleich_2026")
OUT_FILE = Path("data/published/kreisvergleich_2026.json")

def parse_eur(s):
    """'121.132.940' oder '121,132,940' → int"""
    if s is None:
        return None
    s = s.strip().replace(".", "").replace(",", "")
    s = s.lstrip("-").lstrip("–")
    try:
        return int(s)
    except ValueError:
        return None

def scan_pdf_for_haushaltssatzung(path, year=2026, max_pages=40):
    """
    Sucht in den ersten max_pages Seiten nach der Haushaltssatzung
    und liest Erträge, Aufwendungen, Saldo für das Zieljahr aus.
    Gibt dict mit gefundenen Werten zurück.
    """
    found = {}
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            text = page.extract_text() or ""
            if str(year) not in text:
                continue
            e = re.search(r"Gesamtbetrag der Ertr[äa]ge auf\s*[-–]?\s*([\d.,]+)\s*EUR", text)
            a = re.search(r"Gesamtbetrag der Aufwendungen auf\s*[-–]?\s*([\d.,]+)\s*EUR", text)
            if e or a:
                found["pdf_seite"] = i + 1
                if e:
                    found["gesamteinnahmen_eur"] = parse_eur(e.group(1))
                if a:
                    found["gesamtausgaben_eur"] = parse_eur(a.group(1))
                # Jahresergebnis = Einnahmen - Ausgaben
                if found.get("gesamteinnahmen_eur") and found.get("gesamtausgaben_eur"):
                    found["jahresergebnis_eur"] = (
                        found["gesamteinnahmen_eur"] - found["gesamtausgaben_eur"]
                    )
                break
    return found


# ── Manuelle Einträge (aus vorheriger Extraktion bereits bekannt) ────────────
# Format: kommune → {einwohner, plan_jahr, gesamteinnahmen_eur, gesamtausgaben_eur,
#                    jahresergebnis_eur, url, quelle, anmerkung}

MANUAL = {
    "Rödermark": {
        "einwohner": 28064,
        "plan_jahr": 2026,
        "gesamteinnahmen_eur": 92_475_550,
        "gesamtausgaben_eur": 106_285_455,
        "jahresergebnis_eur": -13_751_305,
        "url": "https://roedermark.de/fileadmin/Stadt_und_Stadtverwaltung/Haushalt___Berichte/Haushaltsplan_HH_2026_Entwurf.pdf",
        "quelle": "Haushaltsplan Rödermark 2026 (Entwurf), Ergebnishaushalt Gesamtübersicht Zeile 240/250/300",
        "anmerkung": None,
    },
    # Egelsbach – aus Seite 4 der PDF direkt gelesen
    "Egelsbach": {
        "einwohner": 11_300,
        "plan_jahr": 2026,
        "gesamteinnahmen_eur": 36_406_296,
        "gesamtausgaben_eur": 39_328_070,
        "jahresergebnis_eur": -2_921_774,
        "url": "https://www.egelsbach.de/rathaus-politik/politik/haushalt-finanzen/haushalt-jahresabschluss/einbringung-hh-2026.pdf?cid=3dj",
        "quelle": "Haushaltsplan Egelsbach 2026 (Einbringung 04.12.2025), Haushaltssatzung §1, Seite 4",
        "anmerkung": None,
    },
    # Langen – aus Seite 5 der PDF direkt gelesen
    "Langen": {
        "einwohner": 38_785,
        "plan_jahr": 2026,
        "gesamteinnahmen_eur": 132_106_746,
        "gesamtausgaben_eur": 147_512_712,
        "jahresergebnis_eur": -15_405_966,
        "url": "https://www.langen.de/datei/anzeigen/id/321735,1018/leseexemplar_endfassung_haushalt_2026_ohne_stellenplan.pdf",
        "quelle": "Haushaltsplan Langen 2026 (Beschluss 18.12.2025), Haushaltssatzung §1, Seite 5",
        "anmerkung": None,
    },
    # Neu-Isenburg – aus Seite 6 der PDF direkt gelesen
    "Neu-Isenburg": {
        "einwohner": 38_500,
        "plan_jahr": 2026,
        "gesamteinnahmen_eur": 177_827_883,
        "gesamtausgaben_eur": 205_842_918,
        "jahresergebnis_eur": -28_015_035,
        "url": "https://www.neu-isenburg.de/medien/downloads/buergerservice/haushalt/00_Druckversion_HH2026.pdf",
        "quelle": "Haushaltsplan Neu-Isenburg 2026 (Beschluss 10.12.2025), Haushaltssatzung §1, Seite 6",
        "anmerkung": None,
    },
    # Obertshausen – Doppelhaushalt 2025/2026, 2026-Zahlen aus Seite 4
    "Obertshausen": {
        "einwohner": 25_300,
        "plan_jahr": 2026,
        "gesamteinnahmen_eur": 88_551_987,
        "gesamtausgaben_eur": 91_381_806,
        "jahresergebnis_eur": -2_829_819,
        "url": "https://www.obertshausen.de/fileadmin/Dateien/Dateien/Rathaus/Haushaltsplaene/Doppelhaushalt_2025_und_2026.pdf",
        "quelle": "Doppelhaushalt Obertshausen 2025/2026 (Beschluss 13.02.2025), Haushaltssatzung §1 – 2026-Spalte, Seite 4",
        "anmerkung": "Doppelhaushalt 2025/2026",
    },
    # Rodgau – aus Seite 5 der PDF direkt gelesen
    "Rodgau": {
        "einwohner": 47_600,
        "plan_jahr": 2026,
        "gesamteinnahmen_eur": 130_710_719,
        "gesamtausgaben_eur": 144_784_767,
        "jahresergebnis_eur": -14_074_048,
        "url": "https://www.rodgau.de/de/medien-stadt/pdf-stadt/pdf-rathaus-service/pdf-stadtportrait-daten/haushaltsplan-2026-einbringung-stvv-20260209.pdf?cid=53w",
        "quelle": "Haushaltsplan Rodgau 2026 (Einbringung 09.02.2026), Haushaltssatzung §1, Seite 5",
        "anmerkung": None,
    },
    # Dietzenbach – aus Seite 13 der PDF direkt gelesen (Entwurf, SVV noch offen)
    "Dietzenbach": {
        "einwohner": 34_100,
        "plan_jahr": 2026,
        "gesamteinnahmen_eur": 121_132_940,
        "gesamtausgaben_eur": 118_743_470,
        "jahresergebnis_eur": 2_389_470,
        "url": "https://www.dietzenbach.de/PDF/Entwurf_zum_Haushaltsplan_2026.PDF?ObjSvrID=3651&ObjID=3883&ObjLa=1&Ext=PDF&WTR=1&_ts=1764262808",
        "quelle": "Haushaltsplan Dietzenbach 2026 (Entwurf), Haushaltssatzung §1, Seite 13",
        "anmerkung": "Entwurf – SVV-Beschluss noch ausstehend (xx.xx.xxxx)",
    },
    # Hainburg – Doppelhaushalt 2025/2026, Jahresergebnis aus Ergebnishaushalt Seite 2
    "Hainburg": {
        "einwohner": 14_800,
        "plan_jahr": 2026,
        "gesamteinnahmen_eur": None,  # wird unten per PDF ergänzt
        "gesamtausgaben_eur": None,
        "jahresergebnis_eur": 2_272_907,
        "url": "https://www.hainburg.de/rathaus-politik/politik/haushalt-und-finanzen/hh-plan-2025-2026-nach-anderung.pdf?cid=3ie",
        "quelle": "Doppelhaushalt Hainburg 2025/2026, Ergebnishaushalt Zeile 30 (Jahresergebnis 2026), Seite 2",
        "anmerkung": "Doppelhaushalt 2025/2026 – nur Jahresergebnis verfügbar, keine Einzelsummen in Haushaltssatzung",
    },
    # Seligenstadt – nur 2025-Plan verfügbar
    "Seligenstadt": {
        "einwohner": 22_500,
        "plan_jahr": 2025,
        "gesamteinnahmen_eur": 63_764_538,
        "gesamtausgaben_eur": 67_324_538,
        "jahresergebnis_eur": -3_560_000,
        "url": "https://he.egovernor.de/api/datei/3tdobvN5RgEO1Df3AMIsQ",
        "quelle": "Haushaltsplan Seligenstadt 2025 (Beschluss 10.02.2025), Haushaltssatzung §1, Seite 3",
        "anmerkung": "Kein separater 2026-Plan gefunden – 2025-Werte",
    },
    # Mühlheim – nur 2025-Plan verfügbar
    "Mühlheim am Main": {
        "einwohner": 29_452,
        "plan_jahr": 2025,
        "gesamteinnahmen_eur": 88_334_498,
        "gesamtausgaben_eur": 88_723_811,
        "jahresergebnis_eur": -389_313,
        "url": "https://www.muehlheim.de/medien/medien-rathaus-politik/stadtverwaltung/pdf/haushaltsplan-2025.pdf?cid=52j",
        "quelle": "Haushaltsplan Mühlheim am Main 2025 (Beschluss 28.11.2024), Haushaltssatzung §1, Seite 3",
        "anmerkung": "Kein separater 2026-Plan gefunden – 2025-Werte",
    },
    # Mainhausen – nur 2025-Plan verfügbar; §1 im Vollplan ist Scan-Seite
    "Mainhausen": {
        "einwohner": 14_600,
        "plan_jahr": 2025,
        "gesamteinnahmen_eur": 33_564_600,
        "gesamtausgaben_eur": 34_317_200,
        "jahresergebnis_eur": -752_600,
        "url": "https://www.mainhausen.de/mcwork/files/download/5925",
        "quelle": "Haushaltssatzung Mainhausen 2025 (Bekanntmachung, Beschluss 29.04.2025), §1",
        "anmerkung": "Kein separater 2026-Plan gefunden – 2025-Werte",
    },
    # Dreieich – Band 1 verfügbar seit März 2026; §1 Haushaltssatzung S. 98 (PDF-Seite 100)
    # Quelle: https://www.dreieich.de/rathaus-service/haushalt-finanzen/haushalt-und-finanzen/2026-haushaltsplan-band1.pdf?cid=1r3r
    "Dreieich": {
        "einwohner": 43_200,
        "plan_jahr": 2026,
        "gesamteinnahmen_eur": 149_176_933,
        "gesamtausgaben_eur": 159_738_048,
        "jahresergebnis_eur": -10_561_115,
        "url": "https://www.dreieich.de/rathaus-service/haushalt-finanzen/haushalt-und-finanzen/2026-haushaltsplan-band1.pdf?cid=1r3r",
        "quelle": "Haushaltsplan Dreieich 2026 (Band 1), Haushaltssatzung §1",
        "anmerkung": "Haushaltssicherungskonzept (HSK) beschlossen (§6 Haushaltssatzung).",
    },
}

# ── PDFs die noch automatisch geparst werden ────────────────────────────────
PDF_TO_PARSE = {
    # Mainhausen: §1 der Haushaltssatzung ist Scan-Seite (nicht text-extrahierbar)
    # Zahlen aus der Bekanntmachung der Haushaltssatzung (4-seitiges Dokument) bereits in MANUAL
}

# ── Heusenstamm: aus Haushaltsrede (05.11.2025) ─────────────────────────────
# Ordentliche Erträge: ca. 74,5 Mio. € | Ordentliche Aufwendungen: ca. 77,07 Mio. €
# → ordentliches Defizit: ca. -2,57 Mio. €
# Außerordentliche Erträge (Immobilienverkäufe): 2,8 Mio. €
# → Jahresergebnis gesamt: ca. +316.000 € (formal ausgeglichen durch Einmaleffekte)
HEUSENSTAMM = {
    "kommune": "Heusenstamm",
    "einwohner": 18_800,
    "plan_jahr": 2026,
    "gesamteinnahmen_eur": 74_500_000,
    "gesamtausgaben_eur": 77_070_000,
    "jahresergebnis_eur": 316_000,
    "jahresergebnis_ordentlich_eur": -2_570_000,
    "url": "https://www.heusenstamm.de/de/buerger-und-stadt/pressecenter/aktuelle-meldungen/detail/item/5963/rede-zur-einbringung-des-haushalts-20262027-des-ersten-stadtrats-uwe-michael-hajdu",
    "quelle": "Haushaltsrede Heusenstamm zur Einbringung des Doppelhaushalts 2026/2027 (05.11.2025), Stadtrat Uwe Michael Hajdu",
    "anmerkung": "Doppelhaushalt 2026/2027 – Näherungswerte aus Haushaltsrede. Ordentliches Ergebnis -2,57 Mio. €; positives Jahresergebnis nur durch außerordentliche Erträge aus Anlageveräußerungen (Immobilienverkäufe ~2,8 Mio. €). Haushaltssicherungskonzept erforderlich.",
}

# ── Zusammenführen ──────────────────────────────────────────────────────────
results = []

for kommune, data in MANUAL.items():
    entry = {"kommune": kommune}
    entry.update(data)
    results.append(entry)

for kommune, cfg in PDF_TO_PARSE.items():
    path = RAW_DIR / cfg["pdf"]
    print(f"Parsing {kommune} ({cfg['pdf']})...")
    found = scan_pdf_for_haushaltssatzung(path, cfg["year"], cfg["max_pages"])
    entry = {
        "kommune": kommune,
        "einwohner": cfg["einwohner"],
        "plan_jahr": cfg["year"],
        "gesamteinnahmen_eur": found.get("gesamteinnahmen_eur"),
        "gesamtausgaben_eur": found.get("gesamtausgaben_eur"),
        "jahresergebnis_eur": found.get("jahresergebnis_eur"),
        "url": cfg["url"],
        "quelle": f"Automatisch extrahiert aus {cfg['pdf']}, Seite {found.get('pdf_seite', '?')}",
        "anmerkung": cfg.get("anmerkung"),
    }
    print(f"  -> Erträge: {entry['gesamteinnahmen_eur']}, Aufwend: {entry['gesamtausgaben_eur']}, Ergebnis: {entry['jahresergebnis_eur']}")
    results.append(entry)

results.append(HEUSENSTAMM)

# Berechne pro-Kopf-Ergebnis
for r in results:
    if r.get("jahresergebnis_eur") is not None and r.get("einwohner"):
        r["jahresergebnis_pro_kopf_eur"] = round(r["jahresergebnis_eur"] / r["einwohner"], 2)
    else:
        r["jahresergebnis_pro_kopf_eur"] = None

# Sortieren nach Jahresergebnis
results.sort(key=lambda x: (x.get("jahresergebnis_eur") or 0))

OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nFertig! {len(results)} Kommunen → {OUT_FILE}")
print("\nÜbersicht:")
for r in results:
    ergebnis = r.get("jahresergebnis_eur")
    pk = r.get("jahresergebnis_pro_kopf_eur")
    sign = "+" if ergebnis and ergebnis > 0 else ""
    ergebnis_str = f"{sign}{ergebnis/1e6:.2f} Mio€" if ergebnis is not None else "n/a"
    pk_str = f"{sign}{pk:.0f}€/Kopf" if pk is not None else ""
    jahr = r.get("plan_jahr", "?")
    print(f"  {r['kommune']:<22} {jahr}  {ergebnis_str:<18} {pk_str}")
