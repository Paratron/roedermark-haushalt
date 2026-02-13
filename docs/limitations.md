# Bekannte Einschränkungen

## Allgemein

- **Keine Vollständigkeitsgarantie**: Nicht alle Tabellen/Positionen aller Jahre sind vom ersten Tag an enthalten. Der Ausbau erfolgt inkrementell.
- **Keine politische Bewertung**: Die Darstellung ist neutral. Es werden keine Bewertungen oder Empfehlungen abgegeben.
- **Layoutwechsel**: Rödermarks PDFs haben über die Jahre unterschiedliche Layouts. Jeder Layoutwechsel kann Parser-Anpassungen erfordern.

## Datenqualität

- **Parsing-Fehler**: Automatische Tabellenextraktion kann Fehler enthalten (falsche Spalten-Zuordnung, fehlende Zeilen, Zahlendreher). Alle extrahierten Daten werden mit Summenchecks validiert.
- **Confidence**: Positionen mit niedriger Extraktionssicherheit (`confidence < 1.0`) sind gekennzeichnet.
- **Einheitenwechsel**: Manche Tabellen verwenden T€ (Tausend Euro), andere €. Die Normalisierung erfolgt nach Regeln in `mappings.yaml`.

## Zeitliche Abdeckung

- **MVP**: Ab Haushaltsjahr 2017/2018 bis aktuell.
- **Ältere Jahrgänge**: Nur verfügbar, wenn PDFs online vorliegen.
- **Ist-Daten**: Jahresabschlüsse liegen zeitlich versetzt vor (oft 1–2 Jahre Rückstand).

## Technik

- **OCR**: Wird nur bei gescannten PDFs eingesetzt (bislang nicht nötig). OCR-Ergebnisse haben generell niedrigere Confidence.
- **Große PDFs**: Einige Haushaltspläne sind >500 Seiten. Die Pipeline verarbeitet sie vollständig, aber der Parse-Schritt kann zeitintensiv sein.
