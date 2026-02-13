"""Quick validation: check sum rows against component rows in extracted CSVs.

Run: python pipeline/validate/quick_check.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "data" / "extracted" / "haushaltsplan_2023_beschluss" / "tables"


def parse_german_number(s: str | None) -> float | None:
    """Parse a German-formatted number: '17.940.642' or '-106.254' → float."""
    if not s or not s.strip():
        return None
    s = s.strip()
    # Remove thousands separators (.) and replace decimal comma (,) with dot
    # German format: 17.940.642 = 17940642 (no decimals in these tables)
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def load_csv(name: str) -> list[dict]:
    path = EXTRACTED / name
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check_ergebnishaushalt() -> None:
    print("=" * 70)
    print("ERGEBNISHAUSHALT – Summenchecks")
    print("=" * 70)

    rows = load_csv("ergebnishaushalt_2023.csv")
    by_nr = {r["Nr."]: r for r in rows}

    year_cols = ["Ergebnis 2021", "Ansatz 2022", "Ansatz 2023", "Plan 2024", "Plan 2025", "Plan 2026"]

    checks = [
        # (sum_row_nr, label, component_nrs)
        ("100", "Summe ord. Erträge", ["010", "020", "030", "040", "050", "060", "070", "080", "090"]),
        ("125", "Summe Personalaufwand", ["110", "120"]),
        ("190", "Summe ord. Aufwendungen", ["125", "130", "140", "150", "160", "170", "180"]),
        ("200", "Verwaltungsergebnis", ["100", "190"]),  # 100 - 190 (but sign convention: 100 + 190)
        ("230", "Finanzergebnis", ["210", "220"]),
        ("260", "Ordentliches Ergebnis", ["240", "250"]),
        ("300", "Jahresergebnis", ["260", "290"]),
    ]

    ok_count = 0
    fail_count = 0

    for sum_nr, label, components in checks:
        sum_row = by_nr.get(sum_nr)
        if not sum_row:
            print(f"  ⚠ Nr. {sum_nr} ({label}): Zeile nicht gefunden")
            continue

        for col in year_cols:
            expected = parse_german_number(sum_row.get(col))
            if expected is None:
                continue

            total = 0.0
            missing = False
            for comp_nr in components:
                comp_row = by_nr.get(comp_nr)
                if comp_row:
                    val = parse_german_number(comp_row.get(col))
                    if val is not None:
                        total += val
                    # None is treated as 0
                else:
                    pass  # Component row missing entirely

            diff = abs(expected - total)
            if diff < 2:  # Allow €1 rounding tolerance
                ok_count += 1
            else:
                print(f"  ✗ Nr.{sum_nr} ({label}) [{col}]: expected {expected:,.0f}, got sum {total:,.0f} (diff {diff:,.0f})")
                fail_count += 1

    print(f"\n  Ergebnis: {ok_count} ✓ ok, {fail_count} ✗ Abweichungen")
    print()


def check_finanzhaushalt() -> None:
    print("=" * 70)
    print("FINANZHAUSHALT – Summenchecks")
    print("=" * 70)

    rows = load_csv("finanzhaushalt_2023.csv")
    by_nr = {r["Nr."]: r for r in rows}

    year_cols = ["Ergebnis 2021", "Ansatz 2022", "Ansatz 2023", "Plan 2024", "Plan 2025", "Plan 2026"]

    checks = [
        ("090", "Summe Einz. lfd. Verwaltung", ["010", "020", "030", "040", "050", "060", "070", "080"]),
        ("190", "Summe Ausz. lfd. Verwaltung", ["100", "110", "120", "130", "140", "150", "160", "170", "180"]),
        ("200", "Zahlungsmittelüberschuss lfd.", ["090", "190"]),
    ]

    ok_count = 0
    fail_count = 0

    for sum_nr, label, components in checks:
        sum_row = by_nr.get(sum_nr)
        if not sum_row:
            print(f"  ⚠ Nr. {sum_nr} ({label}): Zeile nicht gefunden")
            continue

        for col in year_cols:
            expected = parse_german_number(sum_row.get(col))
            if expected is None:
                continue

            total = 0.0
            for comp_nr in components:
                comp_row = by_nr.get(comp_nr)
                if comp_row:
                    val = parse_german_number(comp_row.get(col))
                    if val is not None:
                        total += val

            diff = abs(expected - total)
            if diff < 2:
                ok_count += 1
            else:
                print(f"  ✗ Nr.{sum_nr} ({label}) [{col}]: expected {expected:,.0f}, got sum {total:,.0f} (diff {diff:,.0f})")
                fail_count += 1

    print(f"\n  Ergebnis: {ok_count} ✓ ok, {fail_count} ✗ Abweichungen")


if __name__ == "__main__":
    check_ergebnishaushalt()
    check_finanzhaushalt()
