"""Quick validation of normalized line_items."""
import pandas as pd

df = pd.read_csv("data/extracted/line_items_normalized.csv")

# Overview tables only
overview = df[~df["table_id"].str.startswith("struktur_")].copy()

print("=== EH Nr.10 (Steuern u. ähnl.) alle Jahre ===")
mask = (overview["haushalt_type"] == "ergebnishaushalt") & (overview["nr"] == 10.0)
sub = overview[mask].sort_values(["year", "amount_type"])
print(sub[["nr", "bezeichnung", "year", "amount_type", "amount", "document_id"]].to_string(index=False))

print()
print("=== EH Nr.100 (Summe ord. Erträge) alle Jahre ===")
mask2 = (overview["haushalt_type"] == "ergebnishaushalt") & (overview["nr"] == 100.0)
sub2 = overview[mask2].sort_values(["year", "amount_type"])
print(sub2[["nr", "bezeichnung", "year", "amount_type", "amount", "document_id"]].to_string(index=False))

print()
print("=== EH Nr.300 (Jahresergebnis) alle Jahre ===")
mask3 = (overview["haushalt_type"] == "ergebnishaushalt") & (overview["nr"] == 300.0)
sub3 = overview[mask3].sort_values(["year", "amount_type"])
print(sub3[["nr", "bezeichnung", "year", "amount_type", "amount", "document_id"]].to_string(index=False))

print()
print("=== Abdeckung: items pro (year, amount_type) ===")
pivot = overview.groupby(["year", "amount_type"])["line_item_key"].count().unstack(fill_value=0)
print(pivot.to_string())
