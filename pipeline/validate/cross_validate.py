"""Cross-validation report: Compare Ist values from Haushaltspläne vs Jahresabschlüsse.

For overlapping years, both HP retrospective columns and JA actual results
should report the same amounts. Mismatches indicate extraction errors.

Usage:
    python -m pipeline.validate.cross_validate
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_NORMALIZED = ROOT_DIR / "data" / "extracted" / "line_items_normalized.csv"
DEFAULT_OUT_DIR = ROOT_DIR / "data" / "published"

# Summary positions we care about for cross-validation
KEY_POSITIONS = {
    100: "Summe ordentliche Erträge",
    190: "Summe ordentliche Aufwendungen",
    200: "Verwaltungsergebnis",
    240: "Ordentliches Ergebnis",
    280: "Ergebnis vor ILB",
    320: "Jahresergebnis",
}


def _classify_source(doc_id: str) -> str:
    """Classify a document_id into source category."""
    if doc_id.startswith("jahresabschluss_"):
        return "jahresabschluss"
    elif doc_id.startswith("gesamtabschluss_"):
        return "gesamtabschluss"
    elif doc_id.startswith("haushaltsplan_"):
        return "haushaltsplan"
    return "other"


def cross_validate(
    normalized_path: Path = DEFAULT_NORMALIZED,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict:
    """Compare HP retrospective Ist values with JA actual results.

    For each (position, year) where both sources exist, compute the
    difference and flag mismatches above a threshold.
    """
    df = pd.read_csv(normalized_path)

    # Focus on ergebnishaushalt ist values at summary positions
    eh = df[
        (df["haushalt_type"] == "ergebnishaushalt")
        & (df["amount_type"] == "ist")
    ].copy()

    # Clean nr to int for matching
    eh["nr_int"] = pd.to_numeric(eh["nr"], errors="coerce")
    eh = eh[eh["nr_int"].isin(KEY_POSITIONS.keys())]
    eh["source_type"] = eh["document_id"].apply(_classify_source)

    # Group: for each (nr, year), collect values by source
    comparisons = []
    for (nr, year), group in eh.groupby(["nr_int", "year"]):
        hp_rows = group[group["source_type"] == "haushaltsplan"]
        ja_rows = group[group["source_type"] == "jahresabschluss"]
        ga_rows = group[group["source_type"] == "gesamtabschluss"]

        # Get best value from each source (latest document)
        hp_val = None
        hp_doc = None
        if not hp_rows.empty:
            best_hp = hp_rows.sort_values("document_id").iloc[-1]
            hp_val = float(best_hp["amount"])
            hp_doc = best_hp["document_id"]

        ja_val = None
        ja_doc = None
        if not ja_rows.empty:
            best_ja = ja_rows.sort_values("document_id").iloc[-1]
            ja_val = float(best_ja["amount"])
            ja_doc = best_ja["document_id"]

        ga_val = None
        ga_doc = None
        if not ga_rows.empty:
            best_ga = ga_rows.sort_values("document_id").iloc[-1]
            ga_val = float(best_ga["amount"])
            ga_doc = best_ga["document_id"]

        comp = {
            "nr": int(nr),
            "position": KEY_POSITIONS.get(int(nr), f"Nr {int(nr)}"),
            "year": int(year),
            "hp_value": hp_val,
            "hp_document": hp_doc,
            "ja_value": ja_val,
            "ja_document": ja_doc,
            "ga_value": ga_val,
            "ga_document": ga_doc,
        }

        # Compute differences
        if hp_val is not None and ja_val is not None:
            diff = abs(hp_val - ja_val)
            rel_diff = diff / max(abs(hp_val), abs(ja_val), 1) * 100
            comp["hp_ja_diff"] = round(diff, 2)
            comp["hp_ja_rel_pct"] = round(rel_diff, 2)
            comp["hp_ja_match"] = "exact" if diff < 0.01 else (
                "close" if rel_diff < 1.0 else "MISMATCH"
            )
        elif hp_val is not None or ja_val is not None:
            comp["hp_ja_diff"] = None
            comp["hp_ja_rel_pct"] = None
            comp["hp_ja_match"] = "single_source"

        if ja_val is not None and ga_val is not None:
            diff = abs(ja_val - ga_val)
            rel_diff = diff / max(abs(ja_val), abs(ga_val), 1) * 100
            comp["ja_ga_diff"] = round(diff, 2)
            comp["ja_ga_rel_pct"] = round(rel_diff, 2)
            comp["ja_ga_match"] = "exact" if diff < 0.01 else (
                "close" if rel_diff < 1.0 else "MISMATCH"
            )

        comparisons.append(comp)

    # Sort by year, then nr
    comparisons.sort(key=lambda x: (x["year"], x["nr"]))

    # Generate report
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "description": (
            "Kreuzvalidierung: Vergleich der Ist-Werte aus Haushaltsplänen (HP), "
            "Jahresabschlüssen (JA) und Gesamtabschlüssen (GA) für Schlüsselpositionen "
            "des Ergebnishaushalts."
        ),
        "key_positions": KEY_POSITIONS,
        "total_comparisons": len(comparisons),
        "comparisons": comparisons,
    }

    # Count matches
    hp_ja_comps = [c for c in comparisons if "hp_ja_match" in c]
    matches = sum(1 for c in hp_ja_comps if c.get("hp_ja_match") == "exact")
    close = sum(1 for c in hp_ja_comps if c.get("hp_ja_match") == "close")
    mismatches = sum(1 for c in hp_ja_comps if c.get("hp_ja_match") == "MISMATCH")
    single = sum(1 for c in hp_ja_comps if c.get("hp_ja_match") == "single_source")

    report["hp_ja_summary"] = {
        "exact_matches": matches,
        "close_matches": close,
        "mismatches": mismatches,
        "single_source_only": single,
    }

    # Save report
    out_path = out_dir / "cross_validation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info("Cross-validation report → %s", out_path)

    return report


def print_report(report: dict) -> None:
    """Print human-readable cross-validation report."""
    print("=" * 80)
    print("KREUZVALIDIERUNG: Haushaltsplan vs. Jahresabschluss")
    print("=" * 80)
    print()
    print(report["description"])
    print()

    # HP vs JA comparisons (where both sources exist)
    hp_ja = [c for c in report["comparisons"] if c.get("hp_ja_match") and c["hp_ja_match"] != "single_source"]
    if hp_ja:
        print("-" * 80)
        print("Haushaltsplan (Retrospektive) vs. Jahresabschluss (Ergebnis)")
        print("-" * 80)
        print(f"{'Jahr':>6} {'Nr':>5} {'Position':<35} {'HP':>15} {'JA':>15} {'Diff':>12} {'Status':<10}")
        print("-" * 80)
        for c in hp_ja:
            hp = f"{c['hp_value']:>14,.2f}" if c['hp_value'] is not None else f"{'—':>14}"
            ja = f"{c['ja_value']:>14,.2f}" if c['ja_value'] is not None else f"{'—':>14}"
            diff = f"{c['hp_ja_diff']:>11,.2f}" if c.get('hp_ja_diff') is not None else f"{'—':>11}"
            status = c.get('hp_ja_match', '')
            marker = "✓" if status == "exact" else ("≈" if status == "close" else "✗")
            print(f"{c['year']:>6} {c['nr']:>5} {c['position']:<35} {hp} {ja} {diff} {marker} {status}")

    # Single-source-only entries
    single = [c for c in report["comparisons"]
              if c.get("hp_ja_match") == "single_source" or "hp_ja_match" not in c]
    if single:
        print()
        print("-" * 80)
        print("Nur aus einer Quelle verfügbar (keine Kreuzvalidierung möglich)")
        print("-" * 80)
        print(f"{'Jahr':>6} {'Nr':>5} {'Position':<35} {'HP':>15} {'JA':>15} {'GA':>15}")
        print("-" * 80)
        for c in single:
            hp = f"{c['hp_value']:>14,.2f}" if c['hp_value'] is not None else f"{'—':>14}"
            ja = f"{c['ja_value']:>14,.2f}" if c['ja_value'] is not None else f"{'—':>14}"
            ga = f"{c['ga_value']:>14,.2f}" if c['ga_value'] is not None else f"{'—':>14}"
            print(f"{c['year']:>6} {c['nr']:>5} {c['position']:<35} {hp} {ja} {ga}")

    # Summary
    s = report.get("hp_ja_summary", {})
    print()
    print("=" * 80)
    print(f"HP↔JA Zusammenfassung: {s.get('exact_matches', 0)} exakt, "
          f"{s.get('close_matches', 0)} nahe, "
          f"{s.get('mismatches', 0)} Abweichungen, "
          f"{s.get('single_source_only', 0)} nur eine Quelle")
    print("=" * 80)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )

    report = cross_validate()
    print_report(report)


if __name__ == "__main__":
    main()
