"""Die Präzedenz muss auch in der Publish-Stufe gelten.

build_summary dedupliziert ein zweites Mal – wenn dort nach document_id sortiert
wird, gewinnt wieder der Entwurf über den Beschluss und der Fix in normalize ist
für die Chart-Zeitreihen wirkungslos.
"""

from __future__ import annotations

import pandas as pd
import pytest
import yaml

from pipeline.normalize.normalize import (
    DEFAULT_SOURCES,
    build_authority_index,
    deduplicate_line_items,
)
from pipeline.publish.publish import build_summary


@pytest.fixture(scope="module")
def authority() -> dict[str, int]:
    with open(DEFAULT_SOURCES, encoding="utf-8") as f:
        return build_authority_index(
            {d["document_id"]: d for d in yaml.safe_load(f)["documents"]}
        )


def frame(rows: list[tuple[str, float]], year: int = 2023) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "table_id": f"ergebnishaushalt_{year}",
                "haushalt_type": "ergebnishaushalt",
                "nr": "100",
                "bezeichnung": "Jahresergebnis",
                "year": year,
                "amount_type": "plan",
                "amount": amount,
                "document_id": doc_id,
                "line_item_key": "erg.100",
            }
            for doc_id, amount in rows
        ]
    )


def test_beschluss_wins_over_entwurf_in_summary(authority):
    df = frame(
        [
            ("haushaltsplan_2023_entwurf", 111.0),
            ("haushaltsplan_2023_beschluss", 222.0),
        ]
    )
    series = build_summary(df, authority)["ergebnishaushalt"]["jahresergebnis"]
    assert len(series) == 1
    assert series[0]["document_id"] == "haushaltsplan_2023_beschluss"
    assert series[0]["amount"] == 222.0


def test_row_order_does_not_decide(authority):
    rows = [
        ("haushaltsplan_2023_beschluss", 222.0),
        ("haushaltsplan_2023_entwurf", 111.0),
    ]
    series = build_summary(frame(rows), authority)["ergebnishaushalt"]["jahresergebnis"]
    assert series[0]["document_id"] == "haushaltsplan_2023_beschluss"


def test_neufassung_wins_over_entwurf_for_2026(authority):
    df = frame(
        [
            ("haushaltsplan_2026_entwurf", 13_809_905.0),
            ("haushaltsplan_2026_neufassung", 6_104_915.0),
        ],
        year=2026,
    )
    series = build_summary(df, authority)["ergebnishaushalt"]["jahresergebnis"]
    assert series[0]["document_id"] == "haushaltsplan_2026_neufassung"


def test_without_authority_it_still_produces_a_single_value(authority):
    """Ohne Präzedenz-Index darf nichts crashen – nur die Auswahl ist dann beliebig."""
    df = frame([("doc_a", 1.0), ("doc_b", 2.0)])
    series = build_summary(df)["ergebnishaushalt"]["jahresergebnis"]
    assert len(series) == 1


def test_superseded_rows_never_reach_the_kennzahlen(authority):
    """Nach der Umstellung auf Markieren statt Löschen liegen beide Fassungen im
    DataFrame. Die Zeitreihen dürfen trotzdem nur die aktuelle sehen."""
    rows = deduplicate_line_items(
        [
            {
                "table_id": "ergebnishaushalt_2026",
                "haushalt_type": "ergebnishaushalt",
                "nr": "300",
                "bezeichnung": "Jahresergebnis",
                "year": 2026,
                "amount_type": "plan",
                "amount": amount,
                "document_id": doc_id,
                "line_item_key": "erg.300",
            }
            for doc_id, amount in [
                ("haushaltsplan_2026_entwurf", 13_809_905.0),
                ("haushaltsplan_2026_neufassung", 6_104_915.0),
            ]
        ],
        authority,
    )
    assert len(rows) == 2, "beide Fassungen müssen im DataFrame liegen"

    series = build_summary(pd.DataFrame(rows), authority)["ergebnishaushalt"]["jahresergebnis"]
    assert len(series) == 1
    assert series[0]["document_id"] == "haushaltsplan_2026_neufassung"
    assert series[0]["amount"] == 6_104_915.0
