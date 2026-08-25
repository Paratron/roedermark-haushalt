"""Zugeschnittene Teildatensätze für die einzelnen Seiten.

Jede Seite lädt genau die Zeilen, die sie anzeigt. Vorher holte sich jede den
Gesamtdatensatz und warf davon 90 % weg – beim Prerendering landet das im HTML,
und aus 88 KB Seiteninhalt wurden 5,7 MB, auf zehn Seiten. Diese Tests halten
fest, dass die Zerlegung vollständig und überschneidungsfrei ist und dass die
Seitendatensätze nur enthalten, was ihre Seite auch liest.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from pipeline.publish.publish import (
    ITEM_SLICES,
    PAGE_DATASETS,
    UNUSED_ITEM_COLUMNS,
    _slice_frames,
    current_for_frontend,
    export_page_datasets,
)


def row(**kw) -> dict:
    base = {
        "line_item_key": "k",
        "year": 2026,
        "amount": 1.0,
        "amount_type": "plan",
        "haushalt_type": "ergebnishaushalt",
        "nr": "300",
        "bezeichnung": "Jahresergebnis",
        "document_id": "haushaltsplan_2026_neufassung",
        "table_id": "ergebnishaushalt_2026_neufassung",
        "teilhaushalt_nr": None,
        "teilhaushalt_name": None,
        "superseded_by": None,
        "konto": None,
        "unit": "EUR",
        "row_idx": 3,
        "confidence": 1.0,
    }
    base.update(kw)
    return base


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            row(line_item_key="erg", haushalt_type="ergebnishaushalt"),
            row(
                line_item_key="erg_konto",
                haushalt_type="ergebnishaushalt",
                table_id="struktur_ergebnishaushalt_2026",
                nr="50",
                konto="500201",
            ),
            row(line_item_key="fin", haushalt_type="finanzhaushalt"),
            row(
                line_item_key="fin_konto",
                haushalt_type="finanzhaushalt",
                table_id="struktur_finanzhaushalt_2026",
                konto="700100",
            ),
            row(line_item_key="inv", haushalt_type="investitionen"),
            row(line_item_key="prod", haushalt_type="produktuebersicht"),
            row(
                line_item_key="th",
                haushalt_type="teilergebnishaushalt",
                nr="190",
                teilhaushalt_nr="4",
                teilhaushalt_name="Kinder, Jugend u. Senioren",
            ),
            row(
                line_item_key="tf",
                haushalt_type="teilfinanzhaushalt",
                teilhaushalt_nr="4",
                teilhaushalt_name="Kinder, Jugend u. Senioren",
            ),
            row(
                line_item_key="budget",
                haushalt_type="teilergebnishaushalt",
                teilhaushalt_nr="4.1",
            ),
            row(
                line_item_key="produkt",
                haushalt_type="teilergebnishaushalt",
                teilhaushalt_nr="04.1.01",
            ),
        ]
    )


@pytest.fixture
def slices(frame) -> dict[str, list[str]]:
    return {
        name: sorted(sub["line_item_key"]) for name, sub in _slice_frames(frame).items()
    }


def read(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def pages(frame, tmp_path) -> dict[str, list[dict]]:
    export_page_datasets(current_for_frontend(frame), tmp_path)
    root = tmp_path / "pages"
    return {
        path.relative_to(root).with_suffix("").as_posix(): read(path)
        for path in root.rglob("*.json")
    }


# ── Die Zerlegung ─────────────────────────────────────────────────────

def test_every_declared_slice_exists(slices):
    assert set(slices) == set(ITEM_SLICES)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("ergebnishaushalt", {"erg"}),
        ("ergebnishaushalt_konten", {"erg_konto"}),
        ("finanzhaushalt", {"fin"}),
        ("finanzhaushalt_konten", {"fin_konto"}),
        ("investitionen", {"inv"}),
        ("produktuebersicht", {"prod"}),
        ("teilhaushalte", {"th", "tf"}),
        ("teilhaushalte_detail", {"budget", "produkt"}),
    ],
)
def test_slice_contains_exactly_its_rows(slices, name, expected):
    assert set(slices[name]) == expected


def test_the_displayed_level_is_free_of_budget_and_product_rows(frame):
    """Der teilhaushalte-Slice speist die Seite; Budget- und Produktebene zeigt
    derzeit nichts an und darf den Payload nicht aufblähen."""
    sub = _slice_frames(frame)["teilhaushalte"]
    assert all("." not in nr for nr in sub["teilhaushalt_nr"])


def test_slices_partition_the_frame_without_loss_or_overlap(frame, slices):
    keys = [k for rows in slices.values() for k in rows]
    assert sorted(keys) == sorted(frame["line_item_key"])
    assert len(keys) == len(set(keys)), "keine Zeile darf in zwei Slices liegen"


def test_the_overview_slices_are_free_of_konto_rows(frame):
    """Die Ergebnis-/Finanzhaushalt-Seiten rufen overviewItems() auf, das struktur_
    verwirft – diese Zeilen wurden geladen, um sofort weggeworfen zu werden."""
    frames = _slice_frames(frame)
    for name in ("ergebnishaushalt", "finanzhaushalt"):
        assert not frames[name]["table_id"].str.startswith("struktur_").any()


def test_the_konto_slices_carry_only_konto_rows(frame):
    """Steuer- und Ertragsseite brauchen genau diese Zeilen."""
    frames = _slice_frames(frame)
    for name in ("ergebnishaushalt_konten", "finanzhaushalt_konten"):
        assert len(frames[name]) > 0
        assert frames[name]["table_id"].str.startswith("struktur_").all()


@pytest.mark.parametrize("column", UNUSED_ITEM_COLUMNS)
def test_columns_the_frontend_never_reads_are_dropped(frame, column):
    for name, sub in _slice_frames(frame).items():
        assert column not in sub.columns, f"{column} steckt noch in {name}"


# ── Die Seitendatensätze ──────────────────────────────────────────────

def test_every_declared_page_is_written(pages):
    written = {name.split("/")[0] for name in pages}
    assert written == set(PAGE_DATASETS)


def test_superseded_rows_are_kept_out(frame, tmp_path):
    frame.loc[frame["line_item_key"] == "erg", "superseded_by"] = "anderes_dokument"
    export_page_datasets(current_for_frontend(frame), tmp_path)
    assert read(tmp_path / "pages" / "ergebnishaushalt.json") == []


def test_the_tax_page_only_gets_position_50(pages):
    """Die Steuerseite zeigt genau eine Position samt Konten – der übrige
    Ergebnishaushalt hat dort nichts verloren."""
    assert pages["steuern"]
    assert all(r["nr"] == "50" for r in pages["steuern"])


def test_the_teilhaushalt_files_carry_neither_number_nor_name(pages):
    """Beides steht in _index.json; je Zeile wiederholt wären sie reiner Ballast."""
    rows = pages["teilhaushalte/4"]
    assert rows
    assert all("teilhaushalt_nr" not in r and "teilhaushalt_name" not in r for r in rows)


def test_the_teilhaushalt_index_names_every_file(pages):
    index = pages["teilhaushalte/_index"]
    assert [e["key"] for e in index] == ["4"]
    assert index[0]["name"] == "Kinder, Jugend u. Senioren"
    assert index[0]["counts"] == {"teilergebnishaushalt": 1, "teilfinanzhaushalt": 1}


def test_the_split_key_is_dropped_only_after_splitting(pages):
    """teilhaushalt_nr steht auf der drop-Liste und ist zugleich der Schlüssel, nach
    dem geteilt wird – die Reihenfolge entscheidet, ob überhaupt etwas entsteht."""
    assert "teilhaushalte/4" in pages


def test_only_the_project_datasets_keep_the_line_item_key(pages):
    """line_item_key macht rund ein Fünftel jeder Datei aus. Gebraucht wird er nur
    dort, wo nach Projekt gruppiert wird: Investitionen und Schulden."""
    for name, rows in pages.items():
        if not rows or name.endswith("_index"):
            continue
        has_key = any("line_item_key" in r for r in rows)
        expected = name.split("/")[0] in ("investitionen", "schulden")
        assert has_key == expected, name
