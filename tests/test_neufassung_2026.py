"""Die Eckwerte der Neufassung 2026 gegen die Haushaltssatzung (§ 1) geprüft.

Die Anlage "2_Satzung_BESCHLUSS_NEU 170826.pdf" der Vorlage DS/208/26 nennt die
Beträge im Klartext. Wenn eine Neuextraktion andere Zahlen liefert, hat sich die
Seitenlage im PDF verschoben oder die Spaltenzuordnung ist verrutscht – beides
fällt sonst erst im Frontend auf.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "data" / "extracted" / "haushaltsplan_2026_neufassung" / "tables"

# § 1 der Haushaltssatzung 2026 (Stand 17.08.2026). Vorzeichen wie in der Quelle:
# Erträge/Einzahlungen negativ, Aufwendungen/Auszahlungen positiv.
SATZUNG_ERGEBNISHAUSHALT = {
    "240": -96_482_271,   # Gesamtbetrag der ordentlichen Erträge
    "250": 102_645_786,   # Gesamtbetrag der ordentlichen Aufwendungen
    "260": 6_163_515,     # ordentliches Ergebnis
    "290": -58_600,       # außerordentliches Ergebnis
    "300": 6_104_915,     # Fehlbedarf
}

SATZUNG_FINANZHAUSHALT = {
    "290": -6_181_420,    # Saldo aus Investitionstätigkeit
    "340": -5_422_790,    # Zahlungsmittelbedarf des Haushaltsjahres
}


def read_column(table_id: str, column: str = "Ansatz 2026") -> dict[str, int]:
    path = TABLES / f"{table_id}.csv"
    if not path.exists():
        pytest.skip(f"{path} fehlt – erst `make fetch && make parse` laufen lassen")
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = {}
    for row in rows:
        raw = (row.get(column) or "").strip()
        if row["Nr."] and raw:
            out[row["Nr."]] = int(raw.replace(".", "").replace("−", "-"))
    return out


@pytest.mark.parametrize("nr, expected", sorted(SATZUNG_ERGEBNISHAUSHALT.items()))
def test_ergebnishaushalt_matches_satzung(nr, expected):
    assert read_column("ergebnishaushalt_2026_neufassung")[nr] == expected


@pytest.mark.parametrize("nr, expected", sorted(SATZUNG_FINANZHAUSHALT.items()))
def test_finanzhaushalt_matches_satzung(nr, expected):
    assert read_column("finanzhaushalt_2026_neufassung")[nr] == expected


def test_jahresergebnis_is_the_sum_of_its_parts():
    erg = read_column("ergebnishaushalt_2026_neufassung")
    assert erg["260"] + erg["290"] == erg["300"]
    assert erg["240"] + erg["250"] == erg["260"]


def test_neufassung_supersedes_the_original_draft():
    """Der Entwurf wies für 2026 noch 13.809.905 aus – die Konsolidierung hat das
    auf 6.163.515 gedrückt. Ein Wert nahe der alten Zahl heißt: falsches Dokument."""
    assert read_column("ergebnishaushalt_2026_neufassung")["260"] != 13_809_905
