#!/usr/bin/env python3
"""
Extract investment commentary (Rechenschaftsbericht § 4.6.1) from Jahresabschluss PDFs.

Produces: data/published/investment_commentary.json

Each entry contains:
  - document_id: e.g. "jahresabschluss_2024"
  - year: fiscal year
  - category: investment category heading (e.g. "Auszahlungen für Baumaßnahmen")
  - text: full paragraph text for that category
  - items: list of parsed bullet items {project, amount_eur, reason}
  - page_start / page_end: PDF page numbers
"""

import json
import os
import re
import sys

import pdfplumber

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(ROOT, "data", "raw")
PUB_DIR = os.path.join(ROOT, "data", "published")

# Known section start/end markers
SECTION_START = "4.6.1 Plan-Ist-Vergleich der Investitionen"
SECTION_END_MARKERS = [
    "4.6.2 Entwicklungszahlen",
    "4.6.2Entwicklungszahlen",
    "4.7 ",
]

# Investment categories (headings used in the Rechenschaftsbericht)
CATEGORY_HEADINGS = [
    "Investitionszuweisungen, -zuschüsse und -beiträge",
    "Einzahlungen aus Abgängen des Sachanlagevermögens",
    "Einzahlungen aus Abgängen des Finanzanlagevermögens",
    "Einzahlungen aus der Gewährung von Krediten",
    "Auszahlungen für den Erwerb von Grundstücken und Gebäuden",
    "Auszahlungen für Baumaßnahmen",
    "Auszahlungen für Investitionen in das sonstige Sachanlagevermögen und immaterielle Anlagevermögen",
    "Auszahlungen für Investitionen in das sonstige Sachanlagevermögen und immaterielle An-\nlagevermögen",
    "Auszahlungen für aktivierte Investitionszuweisungen und -zuschüsse",
    "Auszahlungen für aktivierte Investitionszuweisungen",
    "Auszahlungen für Investitionen in das Finanzanlagevermögen",
    "Auszahlungen aus der Gewährung von Krediten",
]


def extract_section_text(pdf_path: str) -> tuple[str, int, int] | None:
    """Extract the full text of section 4.6.1 from a JA PDF, plus page range.

    Skips the table-of-contents pages (typically pages 1-10) and only looks
    for the actual section heading from page 50 onwards.
    """
    pdf = pdfplumber.open(pdf_path)
    pages_text = []
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        pages_text.append((i + 1, text))
    pdf.close()

    full_text = ""
    start_page = None
    end_page = None
    capturing = False

    # Skip early pages (TOC, balance sheet, etc.) — section 4.6.1 is always past page 50
    min_page = 50

    for page_num, text in pages_text:
        if page_num < min_page and not capturing:
            continue
        if not capturing:
            idx = text.find(SECTION_START)
            if idx >= 0:
                capturing = True
                start_page = page_num
                full_text += text[idx:] + "\n"
        else:
            # Check for end marker
            found_end = False
            for marker in SECTION_END_MARKERS:
                eidx = text.find(marker)
                if eidx >= 0:
                    full_text += text[:eidx]
                    end_page = page_num
                    found_end = True
                    break
            if found_end:
                break
            full_text += text + "\n"
            end_page = page_num

    if not capturing:
        return None

    return full_text, start_page, end_page


def clean_text(text: str) -> str:
    """Clean extracted PDF text: fix hyphenation, normalize whitespace."""
    # Fix mid-word line breaks from PDF (e.g. "Verzöge-\nrungen")
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
    # Remove page footer lines like "Seite 108 von 115" or "115 von 121"
    text = re.sub(r'\n?\s*(?:Seite\s+)?\d+\s+von\s+\d+\s*\n?', '\n', text)
    # Remove document header lines
    text = re.sub(r'Jahresabschluss \d{4} der Stadt Rödermark\n?', '', text)
    # Collapse multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def normalize_category(heading: str) -> str:
    """Normalize category heading to a canonical form."""
    h = heading.replace('\n', ' ').replace('  ', ' ').strip()
    # Collapse variations
    if 'sonstige Sachanlagevermögen' in h:
        return 'Auszahlungen für Investitionen in das sonstige Sachanlagevermögen und immaterielle Anlagevermögen'
    if 'aktivierte Investitionszuweisungen' in h:
        return 'Auszahlungen für aktivierte Investitionszuweisungen und -zuschüsse'
    return h


def parse_bullet_items(text: str) -> list[dict]:
    """Parse bullet-point investment items like ' Straßenbau (986.274 Euro)'."""
    items = []
    # Match lines starting with  (bullet char from PDF) or - or •
    for m in re.finditer(
        r'[•\-]\s*(.+?)(?:\((?:Plan:\s*)?(\d[\d.,]*)\s*Euro\))',
        text
    ):
        project = m.group(1).strip().rstrip('(').strip()
        amount_str = m.group(2).replace('.', '').replace(',', '.')
        try:
            amount = float(amount_str)
        except ValueError:
            amount = None
        items.append({
            "project": project,
            "amount_eur": amount,
        })

    # Also match "named lines" with Plan/Ist pattern
    for m in re.finditer(
        r'(?:Bei (?:der |den |dem )?|Für (?:die )?|Die |Das |Beim |Auch (?:das |die |beim )?)'
        r'[„"]([^""]+)["""].*?'
        r'(?:Plan:\s*(\d[\d.,]*)\s*Euro).*?'
        r'(?:Ist:\s*(\d[\d.,]*)\s*Euro)?',
        text,
        re.DOTALL
    ):
        project = m.group(1).strip()
        plan_str = m.group(2).replace('.', '').replace(',', '.') if m.group(2) else None
        ist_str = m.group(3).replace('.', '').replace(',', '.') if m.group(3) else None
        items.append({
            "project": project,
            "plan_eur": float(plan_str) if plan_str else None,
            "ist_eur": float(ist_str) if ist_str else None,
        })

    # Deduplicate by project name
    seen = set()
    unique = []
    for item in items:
        key = item["project"].lower()[:40]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def split_by_categories(section_text: str) -> list[dict]:
    """Split the section text by category headings, return list of {category, text, items}."""
    # Build regex to find category headings in text
    results = []

    # Find all category heading positions
    positions = []
    for heading in CATEGORY_HEADINGS:
        h_clean = heading.replace('\n', ' ')
        # Try to find the heading after the summary table
        # The first occurrence is in the table, the second is the narrative heading
        pattern = re.escape(h_clean)
        # Find all occurrences
        for m in re.finditer(pattern, section_text.replace('\n', ' ')):
            positions.append((m.start(), h_clean))

    # Sort by position
    positions.sort(key=lambda x: x[0])

    # Deduplicate: if same heading appears in summary table AND as narrative heading,
    # keep only the second occurrence (the narrative one)
    deduped = {}
    for pos, heading in positions:
        cat = normalize_category(heading)
        deduped[cat] = pos  # last occurrence wins (narrative heading comes after table)

    # Re-sort
    sorted_cats = sorted(deduped.items(), key=lambda x: x[1])

    # Now extract text between consecutive headings
    flat_text = section_text.replace('\n', ' ')
    for i, (cat, start_pos) in enumerate(sorted_cats):
        end_pos = sorted_cats[i + 1][1] if i + 1 < len(sorted_cats) else len(flat_text)
        chunk = flat_text[start_pos + len(cat):end_pos].strip()

        # Get the original text with newlines for bullet parsing
        # Approximate by using the original section_text
        orig_chunk = section_text[start_pos:end_pos] if start_pos < len(section_text) else chunk

        items = parse_bullet_items(orig_chunk)

        if chunk and len(chunk) > 20:  # skip empty/trivial chunks
            results.append({
                "category": cat,
                "text": clean_text(chunk),
                "items": items,
            })

    return results


def extract_year_from_doc_id(doc_id: str) -> int:
    """Extract the fiscal year from document_id like 'jahresabschluss_2024'."""
    m = re.search(r'(\d{4})', doc_id)
    return int(m.group(1)) if m else 0


def main():
    # Load documents.json
    docs_path = os.path.join(RAW_DIR, "documents.json")
    with open(docs_path) as f:
        documents = json.load(f)

    ja_docs = [d for d in documents if d["document_id"].startswith("jahresabschluss_")]

    # Also scan for JA PDFs on disk that might not be in documents.json yet
    for fn in sorted(os.listdir(RAW_DIR)):
        if fn.startswith("jahresabschluss_") and fn.endswith(".pdf"):
            doc_id = fn.replace(".pdf", "")
            if not any(d["document_id"] == doc_id for d in ja_docs):
                print(f"  Found unlisted PDF: {fn} → adding as {doc_id}")
                ja_docs.append({"document_id": doc_id, "filename": fn})

    all_commentary = []

    for doc in ja_docs:
        pdf_path = os.path.join(RAW_DIR, doc["filename"])
        if not os.path.exists(pdf_path):
            print(f"  SKIP {doc['document_id']}: PDF not found")
            continue

        print(f"  Processing {doc['document_id']}...")
        result = extract_section_text(pdf_path)
        if not result:
            print(f"    WARNING: Section 4.6.1 not found in {doc['filename']}")
            continue

        section_text, page_start, page_end = result
        section_text = clean_text(section_text)
        year = extract_year_from_doc_id(doc["document_id"])

        categories = split_by_categories(section_text)

        for cat in categories:
            entry = {
                "document_id": doc["document_id"],
                "year": year,
                "category": cat["category"],
                "text": cat["text"],
                "items": cat["items"],
                "page_start": page_start,
                "page_end": page_end,
            }
            all_commentary.append(entry)

        print(f"    Found {len(categories)} categories, pages {page_start}-{page_end}")

    # Write output
    os.makedirs(PUB_DIR, exist_ok=True)
    out_path = os.path.join(PUB_DIR, "investment_commentary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_commentary, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {len(all_commentary)} commentary entries to {out_path}")


if __name__ == "__main__":
    main()
