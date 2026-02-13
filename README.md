# Rödermark Haushalt – Offene Daten + Web-UI

Pipeline + Interface für die Haushaltspläne und Jahresabschlüsse der Stadt Rödermark.

**Ziel:** PDFs → strukturierte Daten → transparente, durchsuchbare Darstellung.

## Quickstart

```bash
# Umgebung einrichten
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"

# PDFs herunterladen
make fetch

# Pipeline ausführen (später)
make parse
make normalize
make validate
make publish
```

## Projektstruktur

```
data/raw/          # Heruntergeladene PDFs + documents.json
data/extracted/    # Zwischenformat (CSV/JSON pro Dokument)
data/published/    # Parquet/JSON für UI/API
pipeline/          # Python-Module für jeden Pipeline-Schritt
docs/              # Methodik, Datenwörterbuch, Einschränkungen
```

Weitere Details: [concept.md](concept.md) · [agents.md](agents.md) · [urls.md](urls.md)
