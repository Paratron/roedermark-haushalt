"""Die Produkt- und Budgetebene der Neufassung 2026.

Das Zahlenwerk führt jede Position auf drei Ebenen: Teilhaushalt (8), Budget (29)
und Produkt (73). Wenn die Ebenen nicht mehr aufeinander aufgehen, stimmt entweder
die Seitenzuordnung in tables.yaml nicht oder eine Spalte ist verrutscht.
"""

from __future__ import annotations

from collections import Counter, defaultdict

import pytest
import yaml

from pipeline.normalize.normalize import (
    DEFAULT_EXTRACTED_DIR,
    DEFAULT_SOURCES,
    DEFAULT_TABLES,
    normalize_table,
)

DOC = "haushaltsplan_2026_neufassung"


@pytest.fixture(scope="module")
def items() -> list[dict]:
    tdefs = [
        t
        for t in yaml.safe_load(open(DEFAULT_TABLES, encoding="utf-8"))["tables"]
        if t["document_id"] == DOC
    ]
    sources = {
        d["document_id"]: d
        for d in yaml.safe_load(open(DEFAULT_SOURCES, encoding="utf-8"))["documents"]
    }
    out: list[dict] = []
    for t in tdefs:
        out.extend(normalize_table(t, sources[DOC], DEFAULT_EXTRACTED_DIR))
    if not out:
        pytest.skip("keine extrahierten Tabellen – erst `make fetch && make parse` laufen lassen")
    return out


def level(th: str | None) -> str | None:
    if not th:
        return None
    return {0: "teilhaushalt", 1: "budget", 2: "produkt"}[th.count(".")]


def test_all_three_levels_are_present(items):
    counts = Counter(level(i.get("teilhaushalt_nr")) for i in items)
    assert counts["teilhaushalt"] > 0
    assert counts["budget"] > 0
    assert counts["produkt"] > 0


def test_levels_do_not_share_keys(items):
    """th{nr}: im Schlüssel muss die Ebenen trennen – sonst verdrängt die Dedup
    die feinere Ebene und wir verlieren genau das, wofür wir sie aufgenommen haben."""
    by_key = defaultdict(set)
    for i in items:
        if (lvl := level(i.get("teilhaushalt_nr"))):
            by_key[i["line_item_key"]].add(lvl)
    mixed = {k: v for k, v in by_key.items() if len(v) > 1}
    assert not mixed, f"Schlüssel über Ebenen hinweg geteilt: {list(mixed)[:5]}"


@pytest.mark.parametrize("budget", ["1.1", "4.1", "7.4"])
def test_products_sum_up_to_their_budget(items, budget):
    """Die Produktseiten führen Cent, die Budgetseiten volle Euro – daher 1 EUR
    Toleranz pro Produkt."""
    def value(th: str) -> float | None:
        for i in items:
            if (
                i.get("teilhaushalt_nr") == th
                and i["nr"] == "100"
                and i["year"] == 2026
                and i["amount_type"] == "plan"
            ):
                return i["amount"]
        return None

    products = sorted(
        th
        for th in {i.get("teilhaushalt_nr") for i in items}
        if th and th.count(".") == 2 and th.lstrip("0").startswith(budget + ".")
    )
    assert products, f"keine Produkte unter Budget {budget} gefunden"

    total = sum(v for p in products if (v := value(p)) is not None)
    expected = value(budget)
    assert expected is not None, f"Budget {budget} nicht gefunden"
    assert abs(total - expected) <= len(products), (
        f"Budget {budget}: Produkte summieren {total:,.2f}, Budget sagt {expected:,.2f}"
    )
