import {
	loadLineItems,
	loadSummary,
	loadDocuments,
	overviewItems,
	financingItems,
	groupBy,
	sourceLinksFromItems,
	shortDocLabel
} from '$lib/data';
import type { LineItem, TimeSeriesPoint, SourceLink } from '$lib/types';
import type { PageLoad } from './$types';

export interface SchuldenstatistikEntry {
	year: number;
	schuldenstand: number;
	pro_kopf: number | null;
	source_document?: string;
	source_page?: number;
}

/**
 * Deduplicate line items: keep only the row from the most recent document
 * for each (nr, year, amount_type) combination.
 */
function dedup(items: LineItem[]): LineItem[] {
	const map = new Map<string, LineItem>();
	for (const item of items) {
		const key = `${item.nr}_${item.year}_${item.amount_type}`;
		const existing = map.get(key);
		if (!existing || item.document_id > existing.document_id) {
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

export const load: PageLoad = async ({ fetch }) => {
	const [allItems, summary, schuldenstatistikRaw, documents] = await Promise.all([
		loadLineItems(fetch),
		loadSummary(fetch),
		fetch('/data/schuldenstatistik.json').then((r) => r.json()) as Promise<SchuldenstatistikEntry[]>,
		loadDocuments(fetch)
	]);

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
		kpis: {
			lastIstYear: lastIstYear,
			kreditaufnahme: kreditIst,
			tilgung: tilgungIst,
			nettoNeuverschuldung,
			zinsen: zinsenIst,
			schuldenstandAktuell,
			proKopfAktuell
		},
		sourceLinks: {
			kreditTilgung: kreditTilgungSourceLinks,
			zinsen: zinsenSourceLinks,
			schuldenstatistik: schuldenSourceLinks
		}
	};
};
