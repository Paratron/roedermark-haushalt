# Methodik

## Datenerhebung

Die Daten stammen ausschließlich aus öffentlich zugänglichen PDF-Dokumenten der Stadt Rödermark (Haushaltspläne, Jahresabschlüsse, Bekanntmachungen). Alle Quelldokumente sind in [sources.yaml](../sources.yaml) und [urls.md](../urls.md) dokumentiert.

## Pipeline-Schritte

1. **Fetch** – PDFs herunterladen, SHA-256-Hash berechnen, Metadaten in `documents.json` speichern.
2. **Parse** – Tabellen und Text mit `pdfplumber` extrahieren (keine semantische Interpretation).
3. **Normalize** – Spalten/Zeilen interpretieren, Hierarchien erkennen, Zahlen bereinigen.
4. **Validate** – Summenchecks, Plausibilitätsprüfungen, Duplikaterkennung.
5. **Publish** – Strukturierte Daten als Parquet/JSON exportieren.

## Rückverfolgbarkeit

Jede extrahierte Zahl (`LineItem`) enthält eine Provenance-Referenz:
- `document_id` → Quelldokument
- `page` → Seitennummer im PDF
- `table_id` → Identifikation der Tabelle
- `row_idx` → Zeilenposition

## Einschränkungen

Siehe [limitations.md](limitations.md).
