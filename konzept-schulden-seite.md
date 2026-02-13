# Konzept: Seite "Schulden & Zinsen"

## Ziel

Eine eigene Seite, die die **Verschuldung** der Stadt Rödermark transparent darstellt:
Kreditaufnahme, Tilgung, Netto-Neuverschuldung und Zinsbelastung.

## Verfügbare Datenquellen

### 1. Finanzhaushalt (Hauptquelle)
Die verlässlichsten aggregierten Daten:
- **Kreditaufnahme**: `EZ Kreditaufnahme`, `Einzahlungen aus der Aufnahme von Krediten für Investitionen` → Einzahlungen (positiv)
- **Tilgung**: `AZ f. Tilgung v.Krediten f. Kreditmarkt/Land`, `Auszahlung für die Tilgung von Krediten` → Auszahlungen (negativ)
- **Zinsen**: `AZ Zinszahlungen an Kreditmarkt`, `Zinsen und ähnliche Auszahlungen` → Auszahlungen (negativ)

Zeitraum: 2015–2029, Ist + Plan
Umfang: ~28 Zeilen Kredit, ~61 Tilgung, ~62 Zinsen

### 2. Investitionsprogramm TH14 (Detaildaten)
17 Positionen mit Kredit/Tilgung/Darlehen im Namen — zeigen die **Einzelprojekte** hinter den Aggregaten:
- Kreditaufnahme vom Kreditmarkt, vom Land, KIP Bund/Land
- Tilgung nach Darlehenstyp (Konjunkturpaket, KIP, Haus Morija, Kita Lessingstraße, ...)
- Erstattung Tilgung (Rückzahlungen von Beteiligungen)

### 3. Ergebnishaushalt (Zinsposten)
58 Zeilen mit Einzel-Zinsposten (Zinsausgaben Kreditmarkt, Schutzschirm, Bankzinsen, Zinseinnahmen, ...). 
Detaillierter als der Finanzhaushalt, aber für die Übersichtsseite reichen die FH-Aggregate.

## Seitenstruktur

### KPI-Karten (oben)
| KPI | Beschreibung | Quelle |
|-----|-------------|--------|
| **Netto-Neuverschuldung** (letztes Ist-Jahr) | Kreditaufnahme − Tilgung | FH |
| **Zinsbelastung** (letztes Ist-Jahr) | Summe Zinszahlungen | FH |
| **Kreditaufnahme** (letztes Ist-Jahr) | Summe neue Kredite | FH |
| **Geplante Tilgung** (kumuliert Plan) | Gesamte geplante Tilgungen der Planjahre | FH |

### Chart 1: Kreditaufnahme vs. Tilgung (Zeitreihe)
- **Bar-Chart**, multiSeries
- Grün: Kreditaufnahme (Einnahmen)
- Rot: Tilgung (Ausgaben, negativ dargestellt)
- Optional: Linie für Netto-Neuverschuldung (Differenz)
- Ist-/Plan-Trennung wie auf anderen Seiten

### Chart 2: Zinsbelastung (Zeitreihe)
- **Bar-Chart**, valueColoring
- Zinszahlungen pro Jahr
- Zeigt den Trend: steigt oder sinkt die Zinsbelastung?

### Detail-Tabelle: Einzelprojekte (TH14)
- Aufklappbare Projekte wie auf der Investitionsseite
- Nur die 17 Kredit/Tilgung-Positionen aus TH14
- Plan vs. Ist pro Jahr

### Info-Box
Kurze Erklärung was Kommunalverschuldung bedeutet, was der Schutzschirmvertrag ist, etc.

## Daten-Aufbereitung (Data Loader)

Der Page-Loader sammelt:
1. **FH-Aggregate**: Kreditaufnahme, Tilgung, Zinsen pro Jahr (dedupliziert nach neuestem Dokument)
2. **TH14-Details**: Die 17 Kredit/Tilgung-Projekte aus dem Investitionsprogramm
3. **Netto-Berechnung**: Kreditaufnahme + Tilgung = Netto-Neuverschuldung

### Filterung / Klassifizierung
Kredit-Positionen aus TH14 erkennen per Keyword-Match:
```
kredit, tilg, darleh
```
→ Diese Positionen werden auf der Investitionsseite **ausgeblendet** und stattdessen hier gezeigt.

## Technische Umsetzung

- Route: `/schulden`
- Komponenten: `TimeSeriesChart` (multiSeries + valueColoring), bestehende expand/collapse-Logik
- Nav-Link: Lucide-Icon `Landmark` (Bankgebäude) 
- Daten: Keine Pipeline-Änderung nötig — alles wird im Frontend-Loader aus line_items.csv gefiltert

## Abgrenzung zur Investitionsseite

Auf der Investitionsseite werden Positionen mit Keyword `kredit|tilg|darleh` in der Bezeichnung **nicht** mehr angezeigt. Die echten TH14-Investitionen (Fahrzeuge, EDV, Grundstücke, ...) bleiben dort.
