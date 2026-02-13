"""Quick inspection: extract table headers from candidate pages."""
import pdfplumber
from pathlib import Path

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"

# Pages to inspect – based on find_missing_tables.py output
# The Erläuterungen pages contain the overview tables
TARGETS = [
    # (pdf_filename, page_numbers_to_check, label)
    ("haushaltsplan_2019.pdf",               [145, 146, 149, 150], "2019"),
    ("haushaltsplan_2020_2021_beschluss.pdf", [154, 155, 158, 159], "2020/21 Beschluss"),
    ("haushaltsplan_2020_2021_anpassung.pdf", [168, 169, 172, 173], "2020/21 Anpassung"),
    ("haushaltsplan_2022_entwurf.pdf",        [145, 146, 149, 150], "2022 Entwurf"),
    ("haushaltsplan_2023_entwurf.pdf",        [143, 144, 147, 148], "2023 Entwurf"),
    ("haushaltsplan_2024_2025_entwurf.pdf",   [171, 172, 174],      "2024/25 Entwurf"),
    # 2017/2018 – older format, scan beyond 175
    ("haushaltsplan_2017_2018.pdf",           [162, 163, 173, 174], "2017/18 Struktur"),
]

for pdf_name, pages, label in TARGETS:
    pdf_path = RAW / pdf_name
    if not pdf_path.exists():
        print(f"SKIP {pdf_name} (not found)")
        continue
    print(f"\n{'='*60}")
    print(f"  {label} – {pdf_name}")
    print(f"{'='*60}")
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pages:
            if pg > len(pdf.pages):
                print(f"  Page {pg}: OUT OF RANGE")
                continue
            page = pdf.pages[pg - 1]
            tables = page.extract_tables()
            if not tables:
                print(f"  Page {pg}: NO TABLES")
                continue
            for ti, table in enumerate(tables):
                if not table or len(table) < 2:
                    continue
                # Show first 3 rows (header + first data rows)
                print(f"  Page {pg}, Table {ti} ({len(table)} rows x {len(table[0])} cols):")
                for ri, row in enumerate(table[:4]):
                    cells = [str(c or "")[:25] for c in row]
                    print(f"    Row {ri}: {cells}")
                print()
