import {
	loadPageItems,
	loadSummary,
	loadDocuments,
	loadSchuldenstatistik,
	currentItems,
	overviewItems,
	financingItems,
	groupBy,
	sourceLinksFromItems,
	shortDocLabel
} from '$lib/data';
import type { LineItem, TimeSeriesPoint, SourceLink } from '$lib/types';
import type { PageServerLoad } from './$types';

export interface KassenkreditRahmenEntry {
	year: number;
	hoechstbetrag: number | null;
	status: 'festgesetzt' | 'nicht_beansprucht' | 'scan_nicht_lesbar';
	begriff: string;
	document_id: string;
	page: number;
	ist_entwurf: boolean;
}

interface KassenkreditRahmenFile {
	beschreibung: string;
	einheit: string;
	hinweis_2026_entwurf: string;
	entries: KassenkreditRahmenEntry[];
}

/** Display-ready row for the §4 Kreditrahmen overview. */
export interface KassenkreditRahmenRow {
	year: number;
	/** Formatted ceiling text, e.g. "37 Mio. €", "5 Mio. €", "0 € (nicht beansprucht)", "k. A. (Scan)". */
	display: string;
	status: KassenkreditRahmenEntry['status'];
	begriff: string;
	ist_entwurf: boolean;
	source: SourceLink | null;
}

/**
 * Deduplicate line items for each (nr, year, amount_type) combination.
 *
 * Welche Fassung gilt, entscheidet die Pipeline über superseded_by – ein Vergleich
 * der document_id wäre alphabetisch und würde "..._entwurf" über "..._beschluss"
 * stellen. Hier bleibt nur der Fall übrig, dass mehrere Positionen desselben
 * Dokuments auf denselben Schlüssel fallen; da gewinnt die erste, stabil.
 */
function dedup(items: LineItem[]): LineItem[] {
	const map = new Map<string, LineItem>();
	for (const item of currentItems(items)) {
		const key = `${item.nr}_${item.year}_${item.amount_type}`;
		if (!map.has(key)) {
			map.set(key, item);
		}
	}
	return [...map.values()];
}

/** Convert line items to TimeSeriesPoint with a custom label */
function toSeries(items: LineItem[], label: string): TimeSeriesPoint[] {
	return items.map((i) => ({
		year: i.year,
		amount_type: i.amount_type,
		amount: i.amount,
		label,
		document_id: i.document_id,
		page: i.page
	}));
}

/**
 * Prefer Ist value, fall back to Plan.
 * Returns the best available value for a given year from a list of items.
 */
function bestValueForYear(items: LineItem[], year: number): number {
	const ist = items.find((i) => i.year === year && i.amount_type === 'ist');
	if (ist) return ist.amount;
	const plan = items.find((i) => i.year === year && i.amount_type === 'plan');
	return plan?.amount ?? 0;
}

export const load: PageServerLoad = async ({ fetch }) => {
	const [fh, investitionen, summary, schuldenstatistikRaw, documents] = await Promise.all([
		// Zinsen, Kassenkredite, Kreditaufnahme und Tilgung
		loadPageItems('schulden'),
		// Die Kredit- und Darlehensprojekte stehen im Investitionsprogramm
		loadPageItems('investitionen'),
		loadSummary(),
		loadSchuldenstatistik(fetch),
		loadDocuments()
	]);
	const allItems = [...fh, ...investitionen];

	// Der Kreditrahmen nach §4 der Haushaltssatzung stammt aus einem eigenen Skript
	// und liegt weiterhin in static/ – hier per fetch geholt, da die Seite komplett
	// prerendert ist.
	const kassenkreditRahmenRaw = (await (
		await fetch('/data/kassenkredit_rahmen.json')
	).json()) as KassenkreditRahmenFile;

	const fhOverview = overviewItems(allItems).filter((i) => i.haushalt_type === 'finanzhaushalt');

	// Deduplicate per year/type (use most recent document)
	// Note: Nr.310 and Nr.320 had inconsistent content in the 2017_2018 document
	// (Nr.310 contained "Tilgung" in 2015/2016, Nr.320 contained "Zahlungsmittelüberschuss").
	// From 2017+ documents the numbering is consistent:
	// Nr.310 = Kreditaufnahme, Nr.320 = Tilgung.
	// We filter out 2015/2016 for Kredit/Tilgung to avoid wrong data.
	const kredit310 = dedup(fhOverview.filter((i) => i.nr === '310' && i.year >= 2017));
	const tilgung320 = dedup(fhOverview.filter((i) => i.nr === '320' && i.year >= 2017));
	const zinsen160 = dedup(fhOverview.filter((i) => i.nr === '160'));

	// Build chart series – use labels that don't trigger semantic green/red coloring,
	// because 'Einzahlungen' (= new debt) should NOT be green on a debt page.
	const kreditSeries = toSeries(kredit310, 'Kreditaufnahme');
	const tilgungSeries = toSeries(tilgung320, 'Tilgung');
	const kreditTilgungSeries = [...kreditSeries, ...tilgungSeries].sort(
		(a, b) => a.year - b.year || a.amount_type.localeCompare(b.amount_type)
	);

	const zinsSeries = toSeries(zinsen160, 'Zinsen')
		.map((p) => ({ ...p, amount: Math.abs(p.amount) }))
		.sort((a, b) => a.year - b.year || a.amount_type.localeCompare(b.amount_type));

	// ─── Kassen-/Liquiditätskredite (kurzfristige Liquiditätssicherung) ───
	// Getrennt von den Investitionskrediten: Nr. 301 = Aufnahme von Kassenkrediten,
	// Nr. 361 = Tilgung/Rückzahlung. Rödermark hat diese kurzfristigen Kredite
	// 2017/2018 im Zuge des Hessenkasse-Beitritts abgebaut.
	const kassenAufnahme = dedup(fhOverview.filter((i) => i.nr === '301'));
	const kassenTilgung = dedup(fhOverview.filter((i) => i.nr === '361'));
	const kassenkreditSeries = [
		...toSeries(kassenAufnahme, 'Aufnahme'),
		...toSeries(kassenTilgung, 'Tilgung / Rückzahlung')
	].sort((a, b) => a.year - b.year || a.amount_type.localeCompare(b.amount_type));
	const kassenkreditSourceLinks = sourceLinksFromItems(
		[...kassenAufnahme, ...kassenTilgung],
		documents
	);
	const hasKassenkredite = kassenkreditSeries.length > 0;

	// ─── Hessenkasse-Eigenbeitrag (jährliche Rückzahlung an das Sondervermögen) ───
	// Mit dem Beitritt zur Hessenkasse (2018) hat das Land Hessen die Kassenkredite
	// der Stadt übernommen; im Gegenzug zahlt Rödermark einen festen jährlichen
	// Eigenbeitrag zurück. Diese Position liegt in den Detail-/Strukturtabellen
	// des Finanzhaushalts (nicht in der Übersicht), daher direkt aus allItems
	// selektiert. Es gibt nur Plan-Werte.
	const hessenkasseRaw = dedup(
		allItems.filter((i) => i.bezeichnung === 'AZ an das Sondervermögen Hessenkasse' && i.amount !== 0)
	);
	const hessenkasseSeries = toSeries(hessenkasseRaw, 'Hessenkasse-Eigenbeitrag')
		.map((p) => ({ ...p, amount: Math.abs(p.amount) }))
		.sort((a, b) => a.year - b.year);
	const hessenkasseSourceLinks = sourceLinksFromItems(hessenkasseRaw, documents);
	// Jüngster ausgewiesener Eigenbeitrag (höchstes Jahr) als KPI.
	const hessenkasseAktuell = hessenkasseSeries.length
		? hessenkasseSeries.reduce((a, b) => (b.year >= a.year ? b : a)).amount
		: 0;

	// ─── Kassen-/Liquiditätskredit-Höchstbeträge gemäß § 4 der Haushaltssatzung ───
	// Diese Werte sind KREDITRAHMEN (Ermächtigungen), nicht der tatsächliche Bestand.
	// Sie stehen im Satzungstext (§ 4) jedes Haushaltsplans, nicht in den
	// extrahierten Ergebnis-/Finanztabellen. Quelle: kassenkredit_rahmen.json.
	const eur = new Intl.NumberFormat('de-DE');
	const rahmenDisplay = (e: KassenkreditRahmenEntry): string => {
		if (e.status === 'scan_nicht_lesbar') return 'k.\u00a0A. (Satzungsseite nur als Scan)';
		if (e.status === 'nicht_beansprucht') return 'wird nicht beansprucht (0\u00a0\u20ac)';
		const v = e.hoechstbetrag ?? 0;
		const mio = v / 1_000_000;
		const nice = Number.isInteger(mio) ? `${mio}\u00a0Mio.\u00a0\u20ac` : `${eur.format(v)}\u00a0\u20ac`;
		return nice;
	};
	const kassenkreditRahmen: KassenkreditRahmenRow[] = kassenkreditRahmenRaw.entries
		.slice()
		.sort((a, b) => a.year - b.year)
		.map((e) => {
			const doc = documents.find((d) => d.document_id === e.document_id);
			const source: SourceLink | null =
				doc?.filename && e.status !== 'scan_nicht_lesbar'
					? {
							label: `${shortDocLabel(e.document_id)}, §\u00a04 / S.\u00a0${e.page}`,
							href: `/pdfs/${doc.filename}#page=${e.page}`,
							document_id: e.document_id,
							page: e.page
					  }
					: null;
			return {
				year: e.year,
				display: rahmenDisplay(e),
				status: e.status,
				begriff: e.begriff,
				ist_entwurf: e.ist_entwurf,
				source
			};
		});
	const kassenkreditRahmenHinweis = kassenkreditRahmenRaw.beschreibung;

	// TH14 financing items (Kredit/Tilgung/Darlehen projects)
	const financing = financingItems(allItems);

	// ─── Schuldenstatistik (real data from PDFs) ───
	// The Schuldenstatistik table in the Haushaltspläne contains the actual
	// Schuldenstand (inkl. KBR) per year, going back to 1986.
	const lastIstYear = summary.last_ist_year ?? 2024;

	const schuldenstandSeries: TimeSeriesPoint[] = schuldenstatistikRaw.map((entry) => ({
		year: entry.year,
		// Years beyond the last Ist year are plan values
		amount_type: entry.year <= lastIstYear ? 'ist' : 'plan',
		amount: entry.schuldenstand,
		label: 'Schuldenstand',
		document_id: ''
	}));

	const proKopfSeries: TimeSeriesPoint[] = schuldenstatistikRaw
		.filter((entry) => entry.pro_kopf !== null)
		.map((entry) => ({
			year: entry.year,
			amount_type: entry.year <= lastIstYear ? 'ist' : 'plan',
			amount: entry.pro_kopf!,
			label: 'Pro-Kopf-Verschuldung',
			document_id: ''
		}));

	// KPIs based on last Ist year
	const kreditIst = kredit310
		.filter((i) => i.year === lastIstYear && i.amount_type === 'ist')
		.reduce((s, i) => s + i.amount, 0);
	const tilgungIst = tilgung320
		.filter((i) => i.year === lastIstYear && i.amount_type === 'ist')
		.reduce((s, i) => s + i.amount, 0);
	const zinsenIst = zinsen160
		.filter((i) => i.year === lastIstYear && i.amount_type === 'ist')
		.reduce((s, i) => s + i.amount, 0);
	const nettoNeuverschuldung = kreditIst + tilgungIst; // Kredit is positive, Tilgung is negative

	// Actual Schuldenstand from Schuldenstatistik table
	const schuldenstandAktuell = schuldenstatistikRaw.find(
		(s) => s.year === lastIstYear
	)?.schuldenstand ?? 0;

	// Pro-Kopf-Verschuldung
	const proKopfAktuell = schuldenstatistikRaw.find(
		(s) => s.year === lastIstYear
	)?.pro_kopf ?? 0;

	// ─── Source links from provenance data ───
	const kreditTilgungSourceLinks = sourceLinksFromItems([...kredit310, ...tilgung320], documents);
	const zinsenSourceLinks = sourceLinksFromItems(zinsen160, documents);

	// Schuldenstatistik source links: build from the provenance fields in the JSON entries
	const schuldenSourceLinks: SourceLink[] = [];
	const seenSchuldenSources = new Set<string>();
	for (const entry of schuldenstatistikRaw) {
		if (!entry.source_document) continue;
		const key = `${entry.source_document}__${entry.source_page ?? 'x'}`;
		if (seenSchuldenSources.has(key)) continue;
		seenSchuldenSources.add(key);
		const doc = documents.find((d) => d.document_id === entry.source_document);
		if (!doc?.filename) continue;
		const page = entry.source_page ?? null;
		const base = `/pdfs/${doc.filename}`;
		const href = page ? `${base}#page=${page}` : base;
		// Use the shortDocLabel via sourceLinksFromItems pattern — here we build manually
		const docLabel = shortDocLabel(entry.source_document);
		schuldenSourceLinks.push({
			label: page ? `${docLabel}, S.\u00a0${page}` : docLabel,
			href,
			document_id: entry.source_document,
			page
		});
	}

	// Determine the last year that is Ist for the Schuldenstatistik
	// (independent of summary.last_ist_year which is for the Finanzhaushalt)
	const schuldenLastIstYear = lastIstYear;
	// Plan-only years for Schuldenstatistik: only years AFTER lastIstYear
	const schuldenPlanOnlyYears = schuldenstatistikRaw
		.filter((e) => e.year > lastIstYear)
		.map((e) => e.year);

	return {
		summary,
		kreditTilgungSeries,
		zinsSeries,
		schuldenstandSeries,
		proKopfSeries,
		financing,
		schuldenPlanOnlyYears,
		schuldenLastIstYear,
		kassenkreditSeries,
		hasKassenkredite,
		hessenkasseSeries,
		kassenkreditRahmen,
		kassenkreditRahmenHinweis,
		kpis: {
			lastIstYear: lastIstYear,
			kreditaufnahme: kreditIst,
			tilgung: tilgungIst,
			nettoNeuverschuldung,
			zinsen: zinsenIst,
			schuldenstandAktuell,
			proKopfAktuell,
			hessenkasseAktuell
		},
		sourceLinks: {
			kreditTilgung: kreditTilgungSourceLinks,
			zinsen: zinsenSourceLinks,
			schuldenstatistik: schuldenSourceLinks,
			kassenkredite: kassenkreditSourceLinks,
			hessenkasse: hessenkasseSourceLinks
		}
	};
};
