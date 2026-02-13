# Datenwörterbuch (Data Dictionary)

## Kernobjekte

### Document

| Feld          | Typ      | Beschreibung                                      |
|---------------|----------|---------------------------------------------------|
| document_id   | string   | Eindeutiger Schlüssel, z.B. `haushaltsplan_2023_beschluss` |
| doc_type      | string   | Dokumenttyp (s. unten)                            |
| years         | int[]    | Haushaltsjahr(e), z.B. `[2024, 2025]`            |
| source_url    | string   | Original-Download-URL                             |
| filename      | string   | Lokaler Dateiname unter `data/raw/`               |
| sha256        | string   | SHA-256-Hash der Datei                            |
| size_bytes    | int      | Dateigröße in Bytes                               |
| fetched_at    | datetime | Download-Zeitpunkt (UTC, ISO 8601)                |
| priority      | string   | `primary` (Zahlenquelle) oder `secondary` (Kontext) |

### doc_type Werte

- `haushaltsplan_entwurf` – Entwurf eines Haushaltsplans
- `haushaltsplan_beschluss` – Beschlossener Haushaltsplan
- `anpassungsbeschluss` – Anpassungsbeschluss zu einem Haushalt
- `nachtragshaushalt` – Nachtragshaushalt
- `jahresabschluss` – Jahresabschluss (Ist-Daten)
- `gesamtabschluss` – Konsolidierter Gesamtabschluss
- `beteiligungsbericht` – Bericht über Beteiligungen
- `konsolidierung` – Konsolidierungsbericht
- `haushaltsrede` – Rede zum Haushalt
- `praesentation` – Präsentation
- `haushaltssatzung` – Haushaltssatzung/Bekanntmachung

### LineItem (später)

| Feld           | Typ     | Beschreibung                                    |
|----------------|---------|-------------------------------------------------|
| line_item_id   | string  | Stabiler Schlüssel (Komposition)                |
| year           | int     | Haushaltsjahr                                   |
| amount         | decimal | Betrag in EUR                                   |
| amount_type    | string  | `plan`, `ist`, `prognose`                       |
| unit           | string  | Immer `EUR`                                     |
| section        | string  | Teilhaushalt                                    |
| product_area   | string  | Produktbereich                                  |
| product_group  | string  | Produktgruppe                                   |
| product        | string  | Produkt                                         |
| konto          | string  | Konto-/Sachkontonummer                          |
| label          | string  | Originalbezeichnung aus dem PDF                 |

### Provenance (später)

| Feld           | Typ    | Beschreibung                                     |
|----------------|--------|--------------------------------------------------|
| document_id    | string | Referenz auf Document                            |
| page           | int    | Seitennummer im PDF                              |
| table_id       | string | Tabellen-Identifikation                          |
| row_idx        | int    | Zeilenindex in der Tabelle                       |
| raw_text       | string | Kurzer Textauszug (Beleg)                        |
| confidence     | float  | Vertrauen in die Extraktion (0.0 – 1.0)         |
