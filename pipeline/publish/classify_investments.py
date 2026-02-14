#!/usr/bin/env python3
"""
Semantische Klassifizierung aller Investitionseinträge.

Dieses Skript klassifiziert die 765 Einträge aus dem Investitionsprogramm in:

1. entry_type: Was IST das?
   - "ausgabe_projekt"    → echtes Investitionsprojekt (Geld fließt raus)
   - "ausgabe_edv"        → EDV/Software-Anschaffung (Geld fließt raus, kleinteilig)
   - "ausgabe_ausstattung"→ Büroausstattung, bewegl. Anlagevermögen
   - "ausgabe_tilgung"    → Tilgung von Krediten
   - "ausgabe_beteiligung"→ Kapitaleinlagen, Beteiligungen, Sonderposten
   - "einnahme_zuwendung" → Zuschüsse/Zuweisungen/Spenden (Geld kommt rein)
   - "einnahme_kredit"    → Kreditaufnahme (Geld kommt rein)
   - "einnahme_veraeusserung" → Verkauf/Veräußerung/Erlöse
   - "einnahme_beitrag"   → Beiträge, Erstattungen, Kostenbeteiligungen
   - "einnahme_sonstige"  → Sonstige Einnahmen

2. thema: Welches inhaltliche Thema?
   - "feuerwehr", "kita", "schule", "strasse", "radweg", "kanal",
   - "gebaude", "spielplatz", "edv_it", "friedhof", "wald",
   - "stadtumbau", "kulturhalle", "sport", "buecherei",
   - "betriebshof", "finanzen", "leitbild", "umwelt", "sonstiges"

3. linked_project: Verknüpfung Einnahme→Projekt (wo erkennbar)

Die Klassifizierung basiert auf Musterabgleich der Bezeichnungen –
genau das, was ein LLM semantisch versteht.
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "published"


# ── Regeln für entry_type ──────────────────────────────────────────────────

def classify_type(bezeichnung: str, key: str) -> str:
    b = bezeichnung.lower()

    # ── EINNAHMEN ──
    # Kredit
    if any(w in b for w in ["kreditaufnahme"]):
        return "einnahme_kredit"

    # Zuwendungen / Zuschüsse / Zuweisungen / Spenden / Förderung
    if any(w in b for w in [
        "zuwendung", "zuwendungen", "zuweisung", "zuweisungen",
        "zuschuss", "zuschüsse", "zuschusse",
        "spenden", "spendeneinnahmen",
        "förderung", "forderung",
        "investitionszuweisung", "investitionszuschüsse", "investitionszuschusse",
        "investitionskostenzuschuss", "investitionskostenzuschusse",
        "inv.-kostenzuschüsse", "inv.kostenzuschuss", "invkostenzuschusse",
        "investitionserlöse", "investitionserlose",
        "rückerstattung", "ruckerstattung",
        "starke heimat hessen: zuwendung",
        "sopo ",  # Sonderposten = Einnahme-Gegenbuchung
    ]):
        return "einnahme_zuwendung"

    # Verkauf / Veräußerung / Erlöse
    if any(w in b for w in [
        "verkauf", "veräußerung", "veraeußerung", "veraußerung",
        "einnahmen aus dem verkauf",
        "einnahme wegertüchtigung", "einnahme wegertuchtigung",
    ]):
        return "einnahme_veraeusserung"

    # Beiträge / Erstattungen / Refinanzierung / Kostenbeteiligung
    if any(w in b for w in [
        "erschließungsbeiträge", "erschließungsbeitrage",
        "straßenbeiträge", "straßenbeitrage",
        "erstattung", "refinanzierung",
        "kostenbeteiligung", "kostenbeteiligungen",
        "kostenerstattungen",
        "stellplatzablöse", "stellplatzablose",
    ]):
        return "einnahme_beitrag"

    # ── AUSGABEN ──
    # Tilgung
    if any(w in b for w in [
        "tilgung",
    ]):
        return "ausgabe_tilgung"

    # Beteiligungen / Kapitaleinlagen
    if any(w in b for w in [
        "beteiligung", "kapitaleinlage", "stammeinlage",
        "eigenbeitrag hessenkasse",
        "versorgungsrücklage", "versorgungsrucklage",
        "finanzbeitr", "finanz.beitr",
        "darlehen konjunkturpaket",
        "baukostenzuschuss",
    ]):
        return "ausgabe_beteiligung"

    # EDV / Software / Lizenzen
    if any(w in b for w in [
        "edv-anschaffungen", "edvanschaffungen",
        "lizenzen/software", "lizenzensoftware",
        "lizenzen-software",
    ]):
        return "ausgabe_edv"

    # Büroausstattung / Bewegl. Anlagevermögen (Pauschale/Klein)
    if any(w in b for w in [
        "büroausstattung", "buroausstattung",
        "ausstattung besprechungsräume", "ausstattung besprechungsraume",
    ]):
        return "ausgabe_ausstattung"

    # Alles andere = echtes Projekt
    return "ausgabe_projekt"


# ── Regeln für Thema ───────────────────────────────────────────────────────

THEMA_PATTERNS = [
    # Spezifisch → allgemein (Reihenfolge wichtig: spezifisch zuerst!)
    ("feuerwehr",    [r"feuerwehr", r"\bfw\b", r"digitalfunk", r"sirene",
                      r"schlauchpflege", r"notstromversorgung.*feuerwehr",
                      r"tlf.4000"]),
    ("kita",         [r"\bkita\b", r"kinderbetreuung", r"kitabau", r"kita.bau",
                      r"taubhaus", r"regenbogen", r"amselstraße", r"pestalozzi",
                      r"villa kunterbunt", r"liebigstraße", r"potsdamer",
                      r"zwickauer", r"waldkobolde", r"waldmeister", r"sonnenschein",
                      r"motzenbruch", r"lessingstraße", r"gruppenräume.*kita",
                      r"neuausstattungen gruppenräume",
                      r"bethanien"]),
    ("schule",       [r"schule", r"schillerhaus", r"mensa", r"helene.lange",
                      r"grundschulsozialarbeit", r"schulkindbetreuung",
                      r"linden"]),
    ("radweg",       [r"radweg", r"radroute", r"kreisradroute", r"radverkehr",
                      r"eulerweg", r"rad.*fußgänger"]),
    ("kanal",        [r"kanal", r"kläranlage", r"klaranlage", r"abwasser",
                      r"sandfang", r"vorklärung", r"filtratwasser",
                      r"gasbehälter", r"gasbehalter", r"bhkw",
                      r"schalt.*steuer", r"e.msr", r"hausanschlüsse",
                      r"drainage"]),
    ("spielplatz",   [r"spielplatz", r"spielpark", r"bolzplatz",
                      r"jugendpl", r"freizeitanl", r"jugendfarm", r"farmhaus"]),
    ("stadtumbau",   [r"stadtumbau", r"isek", r"ortskern", r"bahnhofs",
                      r"rennwiesen", r"marktplatz", r"pfarrgarten",
                      r"kirchumfeld", r"machbarkeit", r"nutzungskonzept",
                      r"gestaltungsrichtlinie", r"beleuchtungskonzept",
                      r"öffentlichkeitsarbeit.*partizipation",
                      r"mobilitätskonzept", r"anreizprogramm",
                      r"pflanzkübel", r"trinkbrunnen", r"initiative wertvoller",
                      r"entenweiher", r"grünstrukturen", r"grunstrukturen",
                      r"freifl.chen", r"videoüberwachung.*bahnhö",
                      r"p\+r.*anlage", r"erweiterung.*p\+r",
                      r"kompetenzzentrum", r"kompetenz",
                      r"städteplanung", r"stadteplanung", r"bauleitplanung"]),
    ("strasse",      [r"straßen(?!beleuchtung|mobiliar)", r"straße(?!nmobiliar|nbeleuchtung)",
                      r"gehweg",
                      r"ortsdurchfahrt", r"durchgangsweg", r"\bring\b",
                      r"endausbau", r"bonhoeffer", r"ricarda.huch",
                      r"donaustraße", r"mainstraße", r"rodaustraße",
                      r"friedhofstraße", r"bruchwiesenstraße",
                      r"dieburger(?!.*machbarkeit)", r"grundh.*erneuerung",
                      r"straßenbau", r"beschilderung", r"bushaltestelle",
                      r"kreuzungsbereich", r"einmündung",
                      r"brücke.*zillig", r"brückenneubau", r"bruckenneubau",
                      r"bw \d{3}"]),
    ("gebaude",      [r"rathaus", r"schließanlage", r"notstromversorgung(?!.*feuerwehr)",
                      r"öffentliche gebäude", r"gebäudebestand", r"wertstoffhof",
                      r"energet.*kompletterneuerung", r"elisabethenstr",
                      r"jahnstr", r"mainzerstr", r"wohnungsbau",
                      r"sozialwohnungen", r"alte wache", r"jägerhaus",
                      r"st\. gallus", r"gemeindezentrum", r"haus morija",
                      r"notunterkünfte", r"notunterkunfte",
                      r"erwerb von grundstücken", r"erwerb von grundstucken",
                      r"grunderwerb"]),
    ("kulturhalle",  [r"kulturhalle", r"tiefgarage", r"lüftungsanlage.*kultur",
                      r"alarmierungsanlage.*kultur", r"beleuchtungssystem.*kultur",
                      r"kassensystem.*badehaus", r"kelterscheune", r"töpfermuseum",
                      r"topfermuseum"]),
    ("sport",        [r"sporthalle", r"halle urberach", r"gaststätte.*halle",
                      r"sauna", r"badehaus(?!.*spiel)", r"schwimmbad"]),
    ("buecherei",    [r"bücherei", r"bucherei", r"stadtbücherei", r"stadtbucherei"]),
    ("umwelt",       [r"rodau.*renaturierung", r"100 wilde", r"wasserläufe",
                      r"flachwasserteich", r"naturschutz", r"stadtgrün", r"stadtgrun",
                      r"klimaschutz", r"nachhaltig", r"umwelt(?:fr)?",
                      r"pieta", r"baumstandort",
                      r"städtepartnerschaft", r"stadtepartnerschaft",
                      r"förderprogramm klimaschutz",
                      r"starkregen", r"informationsbrücke.*rodau"]),
    ("friedhof",     [r"friedhof", r"grabnutzungsrechte"]),
    ("wald",         [r"waldweg", r"waldumbau", r"stadtwald", r"holzvermarktung",
                      r"anhänger(?!.*feuerwehr)"]),
    ("betriebshof",  [r"betriebshof", r"fahrzeug.*betriebshof",
                      r"abfall(?!.*edv|.*lizenz)", r"straßenmobiliar",
                      r"straßenbeleuchtung", r"hundekotstationen",
                      r"ersatzbeschaffung", r"vermögensgegenstände.*betriebshof"]),
    ("leitbild",     [r"leitbild"]),
    ("finanzen",     [r"kreditaufnahme", r"tilgung", r"versorgungsrücklage",
                      r"hessenkasse", r"investitionspauschale",
                      r"darlehen", r"umschuldung", r"kip\b", r"konjunkturpaket",
                      r"veräußerung von grundstücken", r"veraeußerung",
                      r"sopo\b"]),
    ("verkehr",      [r"verkehr(?!sinfra)", r"geschwindigkeitsüber",
                      r"dienst.*schutzkleidung", r"baukostenzuschuss.*bahn",
                      r"s.bahn", r"dreieich.bahn", r"schrankenschließ",
                      r"schrankschließ", r"lichtsignal",
                      r"hopper", r"\bast\b", r"parkplatz", r"parkplätze"]),
    ("soziales",     [r"flüchtlinge", r"fluchtlinge", r"integration",
                      r"vielfalt.*teilhabe", r"senioren.*sozial",
                      r"soziale stadt", r"jugendpflege", r"jugendsozial",
                      r"ehrenamt(?!.*edv|.*lizenz)", r"bürgertreff",
                      r"quartiersgrupp", r"quartierstreff",
                      r"frauenbeauftr", r"\bjuz\b", r"jugendpfl",
                      r"außengelände.*juz", r"bürgerservice"]),
    ("edv_it",       [r"edv", r"lizenzen", r"software", r"digitalisierung",
                      r"breitband", r"e.bikes?"]),
    ("feld_wirtschaftswege", [r"feld.*wirtschaftswege", r"feldwege",
                             r"\bweg\b.*germania", r"\bweg\b.*lerchenberg",
                             r"\bweg\b.*offenthal", r"\bweg\b.*b486",
                             r"alter seeweg"]),
    ("erschliessung", [r"erschließung", r"baugebiet", r"neubaugebiet",
                       r"bodenordnung"]),
    ("wasserbau",    [r"überfüh?rung.*rodau", r"kanalisierung.*rodau"]),
    ("grundstuecke", [r"ankauf.*liegenschaften"]),
    ("zweckverband", [r"zweckverband", r"entega"]),
]


def classify_thema(bezeichnung: str) -> str:
    b = bezeichnung.lower()
    for thema, patterns in THEMA_PATTERNS:
        for p in patterns:
            if re.search(p, b):
                return thema
    return "sonstiges"


# ── Thema-Gruppen für das Frontend ─────────────────────────────────────────

THEMA_LABELS = {
    "feuerwehr": "Feuerwehr",
    "kita": "Kita & Kinderbetreuung",
    "schule": "Schulen & Bildung",
    "strasse": "Straßenbau",
    "radweg": "Radwege",
    "kanal": "Kanal & Kläranlage",
    "spielplatz": "Spielplätze & Freizeitanlagen",
    "gebaude": "Gebäude & Liegenschaften",
    "stadtumbau": "Stadtumbau & Ortskern",
    "kulturhalle": "Kulturhalle & Veranstaltungen",
    "sport": "Sport & Bäder",
    "buecherei": "Büchereien",
    "umwelt": "Umwelt & Naturschutz",
    "friedhof": "Friedhöfe",
    "wald": "Wald & Forstwirtschaft",
    "betriebshof": "Betriebshof & Infrastruktur",
    "leitbild": "Leitbildprojekte",
    "finanzen": "Finanzierung & Kredite",
    "edv_it": "EDV & Digitalisierung",
    "feld_wirtschaftswege": "Feld- & Wirtschaftswege",
    "erschliessung": "Erschließung Baugebiete",
    "verkehr": "Verkehr & Ordnung",
    "soziales": "Soziales & Integration",
    "wasserbau": "Wasserbau",
    "grundstuecke": "Grundstücke",
    "zweckverband": "Zweckverbände & Beteiligungen",
    "sonstiges": "Sonstiges",
}

TYPE_LABELS = {
    "ausgabe_projekt": "Investitionsprojekt",
    "ausgabe_edv": "EDV & Software",
    "ausgabe_ausstattung": "Büroausstattung",
    "ausgabe_tilgung": "Tilgung",
    "ausgabe_beteiligung": "Beteiligung & Einlage",
    "einnahme_zuwendung": "Zuwendung & Zuschuss",
    "einnahme_kredit": "Kreditaufnahme",
    "einnahme_veraeusserung": "Verkauf & Erlöse",
    "einnahme_beitrag": "Beiträge & Erstattungen",
    "einnahme_sonstige": "Sonstige Einnahmen",
}


def is_ausgabe(entry_type: str) -> bool:
    return entry_type.startswith("ausgabe_")


def is_einnahme(entry_type: str) -> bool:
    return entry_type.startswith("einnahme_")


# ── Hauptlogik ─────────────────────────────────────────────────────────────

def classify_all():
    infile = DATA_DIR / "investment_entries_for_classification.json"
    raw = json.loads(infile.read_text(encoding="utf-8"))

    entries = raw["entries"]
    classified = []

    for e in entries:
        bez = e["bezeichnung"]
        entry_type = classify_type(bez, e["key"])
        thema = classify_thema(bez)

        classified.append({
            "key": e["key"],
            "bezeichnung": bez,
            "th_nr": e["th_nr"],
            "th_name": e["th_name"],
            "entry_type": entry_type,
            "thema": thema,
            "ist_total": e["ist_total"],
            "plan_total": e["plan_total"],
            "years": e["years"],
        })

    # ── Statistiken ────────────────────────────────────────────────────
    type_counts = {}
    thema_counts = {}
    for c in classified:
        type_counts[c["entry_type"]] = type_counts.get(c["entry_type"], 0) + 1
        thema_counts[c["thema"]] = thema_counts.get(c["thema"], 0) + 1

    # ── Themen-Aggregation für Frontend ─────────────────────────────────
    # Pro Thema: Summe Ausgaben (Ist) + Summe Einnahmen (Ist)
    thema_sums = {}
    for c in classified:
        t = c["thema"]
        if t not in thema_sums:
            thema_sums[t] = {
                "thema": t,
                "label": THEMA_LABELS.get(t, t),
                "ausgaben_ist": 0,
                "ausgaben_plan": 0,
                "einnahmen_ist": 0,
                "einnahmen_plan": 0,
                "count_ausgaben": 0,
                "count_einnahmen": 0,
            }
        if is_ausgabe(c["entry_type"]):
            thema_sums[t]["ausgaben_ist"] += c["ist_total"]
            thema_sums[t]["ausgaben_plan"] += c["plan_total"]
            thema_sums[t]["count_ausgaben"] += 1
        elif is_einnahme(c["entry_type"]):
            thema_sums[t]["einnahmen_ist"] += c["ist_total"]
            thema_sums[t]["einnahmen_plan"] += c["plan_total"]
            thema_sums[t]["count_einnahmen"] += 1

    # Sort themes by total ist volume
    thema_list = sorted(
        thema_sums.values(),
        key=lambda x: abs(x["ausgaben_ist"]) + abs(x["einnahmen_ist"]),
        reverse=True,
    )

    result = {
        "meta": {
            "total_entries": len(classified),
            "type_counts": type_counts,
            "thema_counts": thema_counts,
            "type_labels": TYPE_LABELS,
            "thema_labels": THEMA_LABELS,
        },
        "themen": thema_list,
        "entries": classified,
    }

    outfile = DATA_DIR / "investment_classification.json"
    outfile.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ── Report ─────────────────────────────────────────────────────────
    print(f"Klassifiziert: {len(classified)} Einträge")
    print()
    print("=== Entry Types ===")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        label = TYPE_LABELS.get(t, t)
        print(f"  {label:30s}  {c:4d}")
    print()
    print("=== Themen ===")
    for t, c in sorted(thema_counts.items(), key=lambda x: -x[1]):
        label = THEMA_LABELS.get(t, t)
        print(f"  {label:35s}  {c:4d}")
    print()
    print("=== Top Themen nach Ist-Volumen ===")
    for ts in thema_list[:15]:
        aus = ts["ausgaben_ist"]
        ein = ts["einnahmen_ist"]
        print(f"  {ts['label']:35s}  Ausg: {aus/1e6:8.2f}M  Einn: {ein/1e6:8.2f}M")

    print(f"\nGeschrieben: {outfile}")


if __name__ == "__main__":
    classify_all()
