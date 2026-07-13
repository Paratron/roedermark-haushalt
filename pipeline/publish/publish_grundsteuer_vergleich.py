"""
Baut den Datensatz für den Grundsteuer-B-Kreisvergleich (/grundsteuer-Seite):

  1. 2024 (Ist): Einnahmen pro Kopf + implizite Bemessungsgrundlage pro Kopf,
     für alle 13 Kommunen aus den IHK-Gemeindesteckbriefen (Hebesatz + Einnahmen).
     Bemessungsgrundlage ≈ Einnahmen ÷ (Hebesatz / 100).
  2. 2026 (Plan): Hebesatz je Kommune aus hebesaetze_grundsteuer_b.json (bereits
     die aktuellste verfügbare Quelle je Kommune).
  3. 2026 (Plan): Grundsteuer-B-Ertrag (Konto 5552, "Finanzstatusbericht"-Anlage
     der jeweiligen Haushaltspläne) – nur für die Kommunen, bei denen diese
     Anlage im vorliegenden PDF sauber gefunden und gegengelesen wurde. Für die
     übrigen Kommunen bleibt der Wert None (im Frontend transparent als
     "noch nicht verfügbar" auszuweisen, nicht zu erraten).

Rödermark-Sonderfall Rodgau: Die Planzahl 14,5 Mio. € (S. 448 des Rodgau-
Haushaltsplans, Einbringung 09.02.2026) beruht auf einem Hebesatz von 877,5 %.
Der tatsächlich beschlossene Hebesatz 2026 ist 1.250 % (Beschlussvorlage
DS-0134/2026, Stadtverordnetenversammlung 22.06.2026). Da beide Werte im
selben Haushaltsjahr (gleiche Bemessungsgrundlage) liegen, ist eine lineare
Anpassung zulässig: 14,5 Mio. € × (1.250 / 877,5) ≈ 20,65 Mio. €. Diese
Korrektur wird explizit als solche gekennzeichnet, nicht als Originalwert
ausgegeben.

Usage:
    python -m pipeline.publish.publish_grundsteuer_vergleich
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
STECKBRIEFE = ROOT_DIR / "data" / "extracted" / "ihk_gemeindesteckbriefe" / "steckbriefe_komplett.json"
HEBESAETZE_2026 = ROOT_DIR / "frontend" / "static" / "data" / "hebesaetze_grundsteuer_b.json"
OUT_FILE = ROOT_DIR / "frontend" / "static" / "data" / "grundsteuer_kreisvergleich.json"

# ── 2026 Grundsteuer-B-Planzahlen (Konto 5552, Finanzstatusbericht) ──────────
# Nur Kommunen, bei denen die Konto-5552-Zeile im PDF eindeutig gefunden und
# gegen den Kontext (Jahresspalten, Nachbarwerte) plausibilisiert wurde.
# document_id verweist auf die Datei in data/raw/kreisvergleich_2026/.
PLANZAHLEN_2026: dict[str, dict] = {
    "Langen": {
        "betrag_eur": 14_271_008,
        "quelle": "Haushaltsplan Langen 2026, Finanzstatusbericht (Konto 5552), S. 749",
        "document": "langen.pdf",
        "page": 749,
        "hebesatz_basis": None,  # Hebesatz-Zeile für 2026 im selben Dokument nicht eindeutig lesbar (s. Hinweis unten)
        "anmerkung": (
            "Die Steuerhebesätze-Tabelle im selben Dokument zeigt für 2026 fälschlich "
            "die Nivellierungshebesätze (Fließtext-Extraktion ohne Spaltenstruktur, "
            "nicht übernommen). Der amtliche 2026-Hebesatz laut IHK Gießen-Friedberg "
            "beträgt 1.268,77 %."
        ),
    },
    "Rodgau": {
        "betrag_eur": 14_500_000,
        "betrag_eur_angepasst": 20_650_000,
        "quelle": "Haushaltsplan Rodgau 2026 (Einbringung 09.02.2026), Finanzstatusbericht (Konto 5552), S. 448",
        "document": "rodgau.pdf",
        "page": 448,
        "hebesatz_basis": 877.5,
        "hebesatz_aktuell": 1250,
        "anmerkung": (
            "Planzahl beruht auf dem Hebesatz der Einbringung (877,5 %). Der später "
            "beschlossene Hebesatz (1.250 %, Beschlussvorlage DS-0134/2026, SVV "
            "22.06.2026) liegt darüber – linear angepasster Wert: 20,65 Mio. € "
            "(14,5 Mio. € × 1.250/877,5). Gleiches Haushaltsjahr, daher zulässige "
            "Anpassung (keine neue Bemessungsgrundlage wie beim Sprung 2024→2025)."
        ),
    },
    "Dreieich": {
        "betrag_eur": 13_998_000,
        "quelle": "Haushaltsplan Dreieich 2026 Band 1, Finanzstatusbericht (Konto 5552), S. 409",
        "document": "dreieich_2026_band1.pdf",
        "page": 409,
    },
    "Heusenstamm": {
        "betrag_eur": 8_900_000,
        "quelle": "Haushaltsplan Heusenstamm 2026/2027, Finanzstatusbericht (Konto 5552), S. 514",
        "document": "heusenstamm.pdf",
        "page": 514,
    },
    "Obertshausen": {
        "betrag_eur": 8_575_000,
        "quelle": "Haushaltsplan Obertshausen 2026, Finanzstatusbericht (Konto 5552), S. 416",
        "document": "obertshausen.pdf",
        "page": 416,
    },
    "Seligenstadt": {
        "betrag_eur": 6_585_000,
        "quelle": "Haushaltsplan Seligenstadt 2026, Finanzstatusbericht (Konto 5552), S. 707",
        "document": "seligenstadt.pdf",
        "page": 707,
    },
    "Egelsbach": {
        "betrag_eur": 4_621_000,
        "quelle": "Haushaltsplan Egelsbach 2026, Finanzstatusbericht (Konto 5552), S. 417",
        "document": "egelsbach.pdf",
        "page": 417,
    },
    "Mainhausen": {
        "betrag_eur": 2_970_000,
        "quelle": "Haushaltsplan Mainhausen 2026, Finanzstatusbericht (Konto 5552), S. 376",
        "document": "mainhausen.pdf",
        "page": 376,
    },
    # Rödermark selbst kommt aus der eigenen Haushaltsplan-Pipeline, nicht von hier.
    # Fehlend (noch nicht extrahiert):
    #   Dietzenbach     – Finanzstatusbericht im PDF nicht gefunden (anderes Format,
    #                      nur Kontenplan-Referenzliste auf S. 153 ohne Beträge)
    #   Mühlheim a. Main – Finanzstatusbericht vorhanden (S. 59–67), aber Text wird
    #                      von pdfplumber spiegelverkehrt extrahiert (Font-/Encoding-
    #                      Problem dieses PDFs) – braucht Sonderbehandlung
    #   Neu-Isenburg    – kein Finanzstatusbericht im vorliegenden PDF gefunden
    #   Hainburg        – kein Finanzstatusbericht im vorliegenden PDF gefunden
}


# Rodgau 2024: Grundsteuer-A- und -B-Einnahmen brechen laut IHK-Steckbrief bei
# gleichbleibendem Hebesatz (700 %) um ~90 % ein (13,7 Mio. € 2023 → 1,4 Mio. €
# 2024) – höchstwahrscheinlich eine Kassenwirksamkeits-/Bescheid-Verzögerung im
# Zuge der Grundsteuerreform, kein struktureller Einbruch. 2023 ist der letzte
# plausible Wert und wird hier statt 2024 verwendet.
IST_JAHR_OVERRIDE: dict[str, int] = {"Rodgau": 2023}


def load_2024_ist(kommune: str, steckbriefe: list[dict]) -> dict | None:
    entry = next((k for k in steckbriefe if k["kommune"] == kommune), None)
    if not entry:
        return None
    einwohner = entry.get("bevoelkerung", {}).get("einwohner_gesamt")
    if not einwohner:
        return None
    gb_rows = [
        f for f in entry["finanzen"]
        if f["tax_type"] == "grundsteuer_b" and f.get("hebesatz") and f.get("einnahmen_tsd_eur")
    ]
    if not gb_rows:
        return None
    override_year = IST_JAHR_OVERRIDE.get(kommune)
    if override_year is not None:
        latest = next((r for r in gb_rows if r["year"] == override_year), max(gb_rows, key=lambda r: r["year"]))
    else:
        latest = max(gb_rows, key=lambda r: r["year"])
    einnahmen_eur = latest["einnahmen_tsd_eur"] * 1000
    hebesatz = latest["hebesatz"]
    bemessungsgrundlage_eur = einnahmen_eur / (hebesatz / 100)

    # Gewerbesteuer pro Kopf – der Kern der "wer füllt die Stadtkasse"-Erklärung.
    # Unabhängig vom Grundsteuer-Jahr-Override: jüngstes Jahr mit Ist-Einnahmen.
    gew_rows = [
        f for f in entry["finanzen"]
        if f["tax_type"] == "gewerbesteuer" and f.get("einnahmen_tsd_eur")
    ]
    gewerbesteuer = None
    if gew_rows:
        gew = max(gew_rows, key=lambda r: r["year"])
        gewerbesteuer = {
            "jahr": gew["year"],
            "einnahmen_eur": gew["einnahmen_tsd_eur"] * 1000,
            "pro_kopf_eur": round(gew["einnahmen_tsd_eur"] * 1000 / einwohner, 1),
        }

    return {
        "jahr": latest["year"],
        "hebesatz": hebesatz,
        "einnahmen_eur": round(einnahmen_eur),
        "einwohner": einwohner,
        "einnahmen_pro_kopf_eur": round(einnahmen_eur / einwohner, 1),
        "bemessungsgrundlage_pro_kopf_eur": round(bemessungsgrundlage_eur / einwohner, 1),
        "gewerbesteuer": gewerbesteuer,
        "quelle": latest["quelle"],
        "anmerkung": (
            "2024 zeigt einen nicht plausiblen Einbruch der Grundsteuer-A/B-Einnahmen "
            "(vermutlich Kassenwirksamkeits-Effekt der Grundsteuerreform); 2023 als "
            "letzter plausibler Wert verwendet."
        ) if kommune in IST_JAHR_OVERRIDE else None,
    }


def load_2026_hebesatz(kommune: str, hebesaetze: list[dict]) -> dict | None:
    rows = [r for r in hebesaetze if r["kommune"] == kommune]
    if not rows:
        return None
    latest = max(rows, key=lambda r: r["year"])
    return {
        "jahr": latest["year"],
        "hebesatz": latest["hebesatz"],
        "status": latest.get("status"),
        "quelle": latest.get("quelle"),
        "quelle_url": latest.get("quelle_url"),
    }


# Kommune-Namen: Angleichung zwischen steckbriefe_komplett.json und
# hebesaetze_grundsteuer_b.json (leicht unterschiedliche Schreibweisen).
KOMMUNEN = [
    "Dietzenbach", "Dreieich", "Egelsbach", "Hainburg", "Heusenstamm",
    "Langen", "Mainhausen", "Mühlheim am Main", "Neu-Isenburg",
    "Obertshausen", "Rodgau", "Rödermark", "Seligenstadt",
]
PLANZAHLEN_KEY_ALIAS = {"Mühlheim am Main": "Mühlheim am Main"}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    steckbriefe = json.loads(STECKBRIEFE.read_text(encoding="utf-8"))
    hebesaetze = json.loads(HEBESAETZE_2026.read_text(encoding="utf-8"))["data"]

    result = []
    for kommune in KOMMUNEN:
        ist_2024 = load_2024_ist(kommune, steckbriefe)
        hs_2026 = load_2026_hebesatz(kommune, hebesaetze)
        plan_2026 = PLANZAHLEN_2026.get(kommune)

        if ist_2024 is None:
            logger.warning("Keine 2024-Ist-Daten für %s", kommune)
        if hs_2026 is None:
            logger.warning("Kein 2026-Hebesatz für %s", kommune)

        result.append({
            "kommune": kommune,
            "ist_2024": ist_2024,
            "hebesatz_2026": hs_2026,
            "plan_2026_grundsteuer_b": plan_2026,
        })

    result.sort(key=lambda r: r["kommune"])

    out = {
        "meta": {
            "beschreibung": (
                "Grundsteuer-B-Vergleich Kreis Offenbach: Einnahmen/Bemessungsgrundlage "
                "pro Kopf (2024, Ist) und Hebesätze/Planzahlen (2026)."
            ),
            "methodik_pro_kopf": (
                "Bemessungsgrundlage pro Kopf ist keine amtliche Größe, sondern "
                "rückgerechnet aus Ist-Einnahmen ÷ (Hebesatz/100), geteilt durch "
                "Einwohnerzahl. Ein Näherungswert zur Einordnung, kein Messbetrag "
                "des Finanzamts."
            ),
            "methodik_plan_2026": (
                "Planzahlen 2026 stammen aus dem 'Finanzstatusbericht' (Konto 5552, "
                "Land-Hessen-Pflichtanlage jedes Haushaltsplans). Nur für Kommunen "
                "aufgeführt, bei denen diese Anlage im vorliegenden PDF eindeutig "
                "gefunden wurde – für die übrigen ist der Wert null, nicht geschätzt."
            ),
            "generiert_am": "2026-07-12",
        },
        "kommunen": result,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Geschrieben: %s (%d Kommunen)", OUT_FILE, len(result))


if __name__ == "__main__":
    main()
