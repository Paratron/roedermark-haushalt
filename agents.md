# agents.md – Projektagenten & Verantwortlichkeiten

Dieses Dokument beschreibt, wie autonome Coding-Agents (Codex, Claude Code, GitHub Copilot o. ä.) in diesem Projekt eingesetzt werden sollen.

Ziel: Der Agent soll **selbstständig, reproduzierbar und nachvollziehbar** arbeiten, ohne implizite Annahmen zu treffen.

---

## 1. Generalregeln für alle Agenten

* Arbeite strikt nach den Vorgaben in `concept.md`.
* Verändere niemals Rohdaten (`data/raw/*.pdf`).
* Jede Zahl muss auf ein konkretes Dokument + Seite referenzierbar sein.
* Bevor neue Heuristiken eingeführt werden: bestehende Regeln prüfen.
* Lieber unvollständig, aber korrekt, als vollständig mit Fehlern.
* **Keine automatischen Builds** (`npm run build`) ausführen, es sei denn der User fordert es explizit an.

---

## 2. Agent: Fetch & Index

**Aufgabe**

* PDFs aus `urls.md` herunterladen
* Zusätzliche PDFs über die Übersichtsseiten finden

**Output**

* `data/raw/*.pdf`
* `data/raw/documents.json`

**Regeln**

* Keine aggressiven Requests (Rate-Limit)
* Jede Datei mit Hash + Download-Datum versehen
* Doppelte Dateien erkennen (Hash)

---

## 3. Agent: PDF-Parsing (Roh-Extraktion)

**Aufgabe**

* Text und Tabellen aus PDFs extrahieren
* Seitenstruktur erkennen (Überschriften, Tabellenblöcke)

**Tools**

* `pdfplumber`
* `camelot` oder `tabula-py`

**Output**

* `data/extracted/{document_id}/tables/*.csv`
* `data/extracted/{document_id}/text/*.txt`

**Regeln**

* Keine semantische Interpretation
* Layout-Artefakte (Header/Footer) entfernen, aber Rohdaten erhalten

---

## 4. Agent: Normalisierung & Semantik

**Aufgabe**

* Roh-Tabellen in `line_items` überführen
* Hierarchien (Teilhaushalt → Produkt → Konto) erkennen
* Zahlen bereinigen (€, T€, Mio€)

**Input**

* `data/extracted/**`
* `mappings.yaml`

**Output**

* SQLite: `line_items`, `nodes`

**Regeln**

* Jede Zeile braucht Provenance (Seite, Tabelle, Zeilenindex)
* Unsichere Matches markieren (`confidence < 1.0`)

---

## 5. Agent: Kategorien & Aggregation

**Aufgabe**

* `line_items` gemäß `categories.yaml` aggregieren
* Summen je Kategorie/Jahr berechnen

**Output**

* `category_sums`
* `category_breakdowns`

**Regeln**

* Kategorien dürfen sich überlappen **nur wenn explizit erlaubt**
* Jede Kategorie muss erklärbar sein

---

## 6. Agent: Validierung

**Aufgabe**

* Summenprüfungen (Teil ↔ Gesamt)
* Auffällige Abweichungen markieren

**Output**

* `validation_report.json`

**Regeln**

* Keine stillen Korrekturen
* Abweichungen dokumentieren, nicht „glattbügeln"

---

## 7. Agent: Publish

**Aufgabe**

* Daten für Weiterverwendung bereitstellen

**Output**

* `data/published/line_items.parquet`
* `data/published/category_sums.parquet`
* `data/published/documents.json`

---

## 8. Agent: Frontend (später)

**Aufgabe**

* Read-only UI auf Basis der publizierten Daten

**Regeln**

* Nutzerfreundlichkeit vor Vollständigkeit
* Kategorien zuerst, Details optional
* Quellen sichtbar, aber nicht dominant

---

## 9. Fehlerkultur

* Wenn ein Dokument nicht zuverlässig extrahiert werden kann:

  * Abbrechen
  * Problem dokumentieren
* Keine Annahmen über fehlende Zahlen treffen

---

## 10. Definition of Done (MVP)

* Mindestens 1 Haushaltsjahr vollständig extrahiert
* Kategorien-Summen reproduzierbar
* Jede Kategorie auf PDF-Seiten zurückführbar
* Keine ungeklärten Validierungsfehler
