"""Which document wins when the same figure appears in several documents."""

from __future__ import annotations

import pytest
import yaml

from pipeline.normalize.normalize import (
    DEFAULT_SOURCES,
    build_authority_index,
    current_only,
    deduplicate_line_items,
    document_authority,
)


def item(document_id: str, amount: float, key: str = "erg.300", year: int = 2026) -> dict:
    return {
        "line_item_key": key,
        "year": year,
        "amount_type": "plan",
        "amount": amount,
        "document_id": document_id,
    }


@pytest.fixture(scope="module")
def sources() -> dict[str, dict]:
    with open(DEFAULT_SOURCES, encoding="utf-8") as f:
        return {d["document_id"]: d for d in yaml.safe_load(f)["documents"]}


@pytest.fixture(scope="module")
def authority(sources: dict[str, dict]) -> dict[str, dict]:
    return build_authority_index(sources)


def winner(items: list[dict], authority: dict[str, int]) -> str:
    """Das Dokument, dessen Wert nach der Dedup als aktueller Wert übrig bleibt."""
    result = current_only(deduplicate_line_items(items, authority))
    assert len(result) == 1
    return result[0]["document_id"]


@pytest.mark.parametrize(
    "loser, expected",
    [
        # The regression this ranking exists for: alphabetically "entwurf" sorts
        # after "beschluss", so the draft used to beat the decision on it.
        ("haushaltsplan_2023_entwurf", "haushaltsplan_2023_beschluss"),
        ("haushaltsplan_2022_entwurf", "haushaltsplan_2022_beschluss"),
    ],
)
def test_beschluss_beats_entwurf(loser, expected, authority):
    assert winner([item(loser, 1.0), item(expected, 2.0)], authority) == expected
    # order of appearance must not matter
    assert winner([item(expected, 2.0), item(loser, 1.0)], authority) == expected


def test_anpassungsbeschluss_beats_beschluss(authority):
    assert winner(
        [
            item("haushaltsplan_2020_2021_beschluss", 1.0),
            item("haushaltsplan_2020_2021_anpassung", 2.0),
        ],
        authority,
    ) == "haushaltsplan_2020_2021_anpassung"


def test_neufassung_beats_entwurf(authority):
    assert winner(
        [
            item("haushaltsplan_2026_entwurf", 13_809_904.90),
            item("haushaltsplan_2026_neufassung", 6_163_515.0),
        ],
        authority,
    ) == "haushaltsplan_2026_neufassung"


def test_neufassung_loses_to_a_later_beschluss(authority):
    """Once the StVV has decided, the decision supersedes the revised draft."""
    authority = {**authority, "haushaltsplan_2026_beschluss": {
        "rank": document_authority({"doc_type": "haushaltsplan_beschluss", "priority": "primary"}),
        "years": {2026},
    }}
    assert winner(
        [
            item("haushaltsplan_2026_neufassung", 6_163_515.0),
            item("haushaltsplan_2026_beschluss", 6_163_515.0),
        ],
        authority,
    ) == "haushaltsplan_2026_beschluss"


def test_secondary_never_overwrites_a_primary_source(authority):
    assert authority["aenderungsliste_2026"]["rank"] < min(
        authority[d]["rank"] for d in authority if d.startswith("haushaltsplan_")
    )
    assert winner(
        [
            item("aenderungsliste_2026", 1.0),
            item("haushaltsplan_2026_entwurf", 2.0),
        ],
        authority,
    ) == "haushaltsplan_2026_entwurf"


def test_unknown_documents_fall_back_to_stable_ordering(authority):
    assert winner([item("zzz_unknown", 1.0), item("aaa_unknown", 2.0)], authority) == "zzz_unknown"


def test_losers_are_kept_and_marked_not_dropped(authority):
    """Die Vergleichsansichten brauchen die verdrängten Werte – sie dürfen nicht
    verschwinden, sondern tragen den Gewinner in superseded_by."""
    result = deduplicate_line_items(
        [
            item("haushaltsplan_2026_entwurf", 13_809_905.0),
            item("haushaltsplan_2026_neufassung", 6_163_515.0),
        ],
        authority,
    )
    assert len(result) == 2
    by_doc = {i["document_id"]: i for i in result}
    assert by_doc["haushaltsplan_2026_neufassung"]["superseded_by"] is None
    assert by_doc["haushaltsplan_2026_entwurf"]["superseded_by"] == "haushaltsplan_2026_neufassung"


def test_same_document_duplicates_are_dropped_outright(authority):
    """Überlappende Seitenbereiche derselben Tabelle sind Extraktionsartefakte,
    keine alternativen Fassungen."""
    result = deduplicate_line_items(
        [item("haushaltsplan_2026_neufassung", 1.0), item("haushaltsplan_2026_neufassung", 2.0)],
        authority,
    )
    assert len(result) == 1
    assert result[0]["amount"] == 1.0


def test_a_single_value_is_never_marked(authority):
    result = deduplicate_line_items([item("haushaltsplan_2026_neufassung", 1.0)], authority)
    assert result[0]["superseded_by"] is None


def test_distinct_positions_are_kept(authority):
    items = [
        item("haushaltsplan_2026_neufassung", 1.0, key="erg.300"),
        item("haushaltsplan_2026_neufassung", 2.0, key="erg.100"),
        item("haushaltsplan_2026_neufassung", 3.0, key="erg.300", year=2027),
    ]
    assert len(current_only(deduplicate_line_items(items, authority))) == 3


def test_every_primary_document_has_a_ranked_doc_type(sources, authority):
    unranked = [
        doc_id
        for doc_id, doc in sources.items()
        if doc.get("priority", "primary") == "primary" and authority[doc_id]["rank"] == 0
    ]
    assert not unranked, f"doc_type ohne Rang in DOC_TYPE_AUTHORITY: {unranked}"


# ── Jahresnähe schlägt doc_type ──────────────────────────────────────

def test_the_document_that_budgets_the_year_beats_a_projection(authority):
    """Ein Haushaltsplan führt drei bis vier Finanzplanungsspalten über seine
    eigenen Haushaltsjahre hinaus. Für 2026 muss die Neufassung 2026 gewinnen,
    nicht der Beschluss 2024/2025 mit seiner Vorausschau auf 2026 – obwohl
    `haushaltsplan_beschluss` höher rangiert als `haushaltsplan_neufassung`."""
    assert winner(
        [
            item("haushaltsplan_2024_2025_beschluss", -26_376.0, year=2026),
            item("haushaltsplan_2026_neufassung", 6_104_915.0, year=2026),
        ],
        authority,
    ) == "haushaltsplan_2026_neufassung"


def test_projection_still_wins_when_nobody_budgets_the_year(authority):
    """2029 ist in keinem Dokument ein Haushaltsjahr – dann entscheidet die Aktualität."""
    assert winner(
        [
            item("haushaltsplan_2026_entwurf", 1.0, year=2029),
            item("haushaltsplan_2026_neufassung", 2.0, year=2029),
        ],
        authority,
    ) == "haushaltsplan_2026_neufassung"


def test_closed_accounts_beat_a_plan_documents_comparison_column(authority):
    """Der Jahresabschluss 2024 und die Neufassung 2026 führen beide 2024 – der
    Abschluss ist die Ist-Quelle, beide haben 2024 in years."""
    assert winner(
        [
            item("haushaltsplan_2026_neufassung", 1.0, year=2024),
            item("jahresabschluss_2024", 2.0, year=2024),
        ],
        authority,
    ) == "jahresabschluss_2024"


def test_beschluss_still_beats_entwurf_within_the_same_year(authority):
    """Die ursprüngliche Korrektur darf durch die Jahresnähe nicht verloren gehen:
    beide Dokumente budgetieren 2023, dann entscheidet wieder der doc_type."""
    assert winner(
        [
            item("haushaltsplan_2023_entwurf", 1.0, year=2023),
            item("haushaltsplan_2023_beschluss", 2.0, year=2023),
        ],
        authority,
    ) == "haushaltsplan_2023_beschluss"


def test_the_newest_projection_wins_for_years_nobody_budgets(authority):
    """2027 budgetiert niemand. Der Beschluss 2024/2025 rangiert als doc_type höher
    als die Neufassung 2026, seine Vorausschau auf 2027 ist aber zwei Jahre älter.
    Sonst wechselt die Zeitreihe mitten in der Finanzplanung das Quelldokument."""
    assert winner(
        [
            item("haushaltsplan_2024_2025_beschluss", 243_610.0, year=2027),
            item("haushaltsplan_2026_neufassung", -5_367_575.0, year=2027),
        ],
        authority,
    ) == "haushaltsplan_2026_neufassung"


def test_recency_never_overrides_the_decision_for_a_budgeted_year(authority):
    """Aktualität greift nur bei Projektionen: für 2023 budgetieren beide, dann
    gewinnt der Beschluss – auch gegen ein neueres Dokument."""
    assert winner(
        [
            item("haushaltsplan_2023_beschluss", 1.0, year=2023),
            item("haushaltsplan_2023_entwurf", 2.0, year=2023),
        ],
        authority,
    ) == "haushaltsplan_2023_beschluss"


def test_gesamtabschluss_does_not_outrank_jahresabschluss(authority):
    """Verschiedener Konsolidierungskreis, nicht verschiedene Autorität: der
    Gesamtabschluss zieht Eigenbetriebe und Beteiligungen mit hinein und gehört
    nicht in eine Zeitreihe des Kernhaushalts."""
    assert authority["gesamtabschluss_2022"]["rank"] < authority["jahresabschluss_2022"]["rank"]
    assert winner(
        [
            item("gesamtabschluss_2022", 80_332_546.0, year=2022),
            item("jahresabschluss_2022", 70_913_613.0, year=2022),
        ],
        authority,
    ) == "jahresabschluss_2022"
