/** Data loading utilities – load published data at build time via server load functions. */

import type { Summary, LineItem, Document, HaushaltType, SourceLink } from './types';
import { formatDocumentName } from './format';

/** Load summary.json */
export async function loadSummary(fetch: typeof globalThis.fetch): Promise<Summary> {
	const res = await fetch('/data/summary.json');
	return res.json();
}

/** Load documents.json */
export async function loadDocuments(fetch: typeof globalThis.fetch): Promise<Document[]> {
	const res = await fetch('/data/documents.json');
	return res.json();
}

/** Load and parse line_items.csv into typed objects */
export async function loadLineItems(fetch: typeof globalThis.fetch): Promise<LineItem[]> {
	const res = await fetch('/data/line_items.csv');
	const text = await res.text();
	return parseCSV(text);
}

/** Parse a single CSV line respecting quoted fields (RFC 4180) */
function splitCSVLine(line: string): string[] {
	const fields: string[] = [];
	let current = '';
	let inQuotes = false;
	for (let i = 0; i < line.length; i++) {
		const ch = line[i];
		if (inQuotes) {
			if (ch === '"') {
				if (i + 1 < line.length && line[i + 1] === '"') {
					current += '"';
					i++; // skip escaped quote
				} else {
					inQuotes = false;
				}
			} else {
				current += ch;
			}
		} else if (ch === '"') {
			inQuotes = true;
		} else if (ch === ',') {
			fields.push(current);
			current = '';
		} else {
			current += ch;
		}
	}
	fields.push(current);
	return fields;
}

/** CSV parser with proper quote handling */
function parseCSV(csv: string): LineItem[] {
	const lines = csv.trim().split('\n');
	if (lines.length < 2) return [];

	const headers = lines[0].split(',');
	const items: LineItem[] = [];

	for (let i = 1; i < lines.length; i++) {
		const values = splitCSVLine(lines[i]);
		const row: Record<string, string> = {};
		headers.forEach((h, idx) => {
			row[h] = values[idx] || '';
		});

		items.push({
			line_item_key: row['line_item_key'],
			year: parseInt(row['year']),
			amount: parseFloat(row['amount']),
			amount_type: row['amount_type'] as 'ist' | 'plan',
			unit: row['unit'] || 'EUR',
			haushalt_type: row['haushalt_type'] as HaushaltType,
			nr: row['nr'],
			bezeichnung: row['bezeichnung'],
			document_id: row['document_id'],
			table_id: row['table_id'],
			page: row['page'] ? parseInt(row['page']) : null,
			row_idx: parseInt(row['row_idx']),
			confidence: parseFloat(row['confidence']),
			konto: row['konto'] || undefined,
			teilhaushalt_nr: row['teilhaushalt_nr'] || undefined,
			teilhaushalt_name: row['teilhaushalt_name'] || undefined,
			fachbereich_nr: row['fachbereich_nr'] || undefined,
			fachbereich_name: row['fachbereich_name'] || undefined,
			productgroup_nr: row['productgroup_nr'] || undefined,
			productgroup_name: row['productgroup_name'] || undefined
		});
	}

	return items;
}

/** Group line items by a key function */
export function groupBy<T>(items: T[], keyFn: (item: T) => string): Map<string, T[]> {
	const map = new Map<string, T[]>();
	for (const item of items) {
		const key = keyFn(item);
		if (!map.has(key)) map.set(key, []);
		map.get(key)!.push(item);
	}
	return map;
}

/** Get only overview items (non-struktur tables) */
export function overviewItems(items: LineItem[]): LineItem[] {
	return items.filter((i) => !i.table_id.startsWith('struktur_'));
}

/** Get unique sorted years */
export function uniqueYears(items: LineItem[]): number[] {
	return [...new Set(items.map((i) => i.year))].sort();
}

/** Build a time series for a specific position (nr) */
export function timeSeriesForNr(
	items: LineItem[],
	haushaltType: string,
	nr: string
): LineItem[] {
	return overviewItems(items)
		.filter((i) => i.haushalt_type === haushaltType && i.nr === nr)
		.sort((a, b) => a.year - b.year || a.amount_type.localeCompare(b.amount_type));
}

/** Keywords that identify financing (Kredit/Tilgung/Darlehen) items in the investment program */
const FINANCING_KEYWORDS = ['kredit', 'tilg', 'darleh'];

/** Check if an investment item is a financing item (Kredit/Tilgung/Darlehen) rather than a real investment */
export function isFinancingItem(item: LineItem): boolean {
	const bez = item.bezeichnung.toLowerCase();
	return FINANCING_KEYWORDS.some((kw) => bez.includes(kw));
}

/** Get investment items (excludes financing items like Kredit/Tilgung) */
export function investitionItems(items: LineItem[]): LineItem[] {
	return items.filter((i) => i.haushalt_type === 'investitionen' && !isFinancingItem(i));
}

/** Get financing items from the investment program (Kredit/Tilgung/Darlehen positions) */
export function financingItems(items: LineItem[]): LineItem[] {
	return items.filter((i) => i.haushalt_type === 'investitionen' && isFinancingItem(i));
}

/** Get Teilhaushalt items (both Teilergebnis and Teilfinanz) */
export function teilhaushaltItems(items: LineItem[]): LineItem[] {
	return items.filter(
		(i) => i.haushalt_type === 'teilergebnishaushalt' || i.haushalt_type === 'teilfinanzhaushalt'
	);
}

// ─── Budget Category Breakdown ───

/** Human-readable category definitions for Ergebnishaushalt positions */
export interface BudgetCategory {
	nr: string;
	label: string;
	shortLabel: string;
	side: 'einnahmen' | 'ausgaben';
	color: string;
	description: string;
}

/** Revenue categories (Erträge) – mapped from EH positions 10–90 */
export const REVENUE_CATEGORIES: BudgetCategory[] = [
	{ nr: '50', label: 'Steuern', shortLabel: 'Steuern', side: 'einnahmen', color: '#059669', description: 'Gewerbesteuer, Grundsteuer, Einkommensteueranteil und andere Steuern' },
	{ nr: '70', label: 'Zuweisungen & Zuschüsse', shortLabel: 'Zuweisungen', side: 'einnahmen', color: '#0891b2', description: 'Schlüsselzuweisungen vom Land, Zuschüsse für laufende Zwecke' },
	{ nr: '30', label: 'Kostenerstattungen', shortLabel: 'Erstattungen', side: 'einnahmen', color: '#2563eb', description: 'Rückerstattungen von Bund, Land oder Kreis für übernommene Aufgaben' },
	{ nr: '20', label: 'Gebühren & Beiträge', shortLabel: 'Gebühren', side: 'einnahmen', color: '#7c3aed', description: 'Kita-Beiträge, Wasser-/Abwassergebühren, Friedhofsgebühren u.a.' },
	{ nr: '60', label: 'Transfererträge', shortLabel: 'Transfers', side: 'einnahmen', color: '#c026d3', description: 'Erträge aus Transferleistungen (z.B. Sozialhilfe-Erstattungen)' },
	{ nr: '90', label: 'Sonstige Erträge', shortLabel: 'Sonstige', side: 'einnahmen', color: '#6b7280', description: 'Spenden, Versicherungsentschädigungen, Auflösungen von Rückstellungen' },
	{ nr: '10', label: 'Privatrechtliche Entgelte', shortLabel: 'Entgelte', side: 'einnahmen', color: '#9ca3af', description: 'Mieteinnahmen, Pachterlöse, Eintrittsgelder' },
	{ nr: '80', label: 'Auflösung Sonderposten', shortLabel: 'Sonderposten', side: 'einnahmen', color: '#d1d5db', description: 'Auflösung von Sonderposten aus Investitionszuweisungen' },
	{ nr: '40', label: 'Bestandsveränderungen', shortLabel: 'Bestände', side: 'einnahmen', color: '#e5e7eb', description: 'Bestandsveränderungen und aktivierte Eigenleistungen' },
];

/** Expense categories (Aufwendungen) – mapped from EH positions 110–180 */
export const EXPENSE_CATEGORIES: BudgetCategory[] = [
	{ nr: '160', label: 'Umlagen & Steueraufwand', shortLabel: 'Umlagen', side: 'ausgaben', color: '#dc2626', description: 'Kreisumlage, Schulumlage, Gewerbesteuerumlage an Bund/Land' },
	{ nr: '110', label: 'Personal', shortLabel: 'Personal', side: 'ausgaben', color: '#ea580c', description: 'Gehälter, Löhne und Sozialabgaben der städtischen Mitarbeiter' },
	{ nr: '130', label: 'Sach- & Dienstleistungen', shortLabel: 'Sachkosten', side: 'ausgaben', color: '#d97706', description: 'Strom, Heizung, Reinigung, IT, Reparaturen, externe Dienstleister' },
	{ nr: '150', label: 'Zuweisungen & Zuschüsse', shortLabel: 'Zuschüsse', side: 'ausgaben', color: '#ca8a04', description: 'Zuschüsse an Kita-Träger, Jugendhilfe, Sozialtransfers' },
	{ nr: '140', label: 'Abschreibungen', shortLabel: 'Abschreib.', side: 'ausgaben', color: '#65a30d', description: 'Wertminderung von Gebäuden, Straßen und Ausstattung' },
	{ nr: '120', label: 'Versorgung', shortLabel: 'Versorgung', side: 'ausgaben', color: '#0d9488', description: 'Pensionen und Beihilfen an ehemalige Beamte' },
	{ nr: '180', label: 'Sonstige Aufwendungen', shortLabel: 'Sonstige', side: 'ausgaben', color: '#6b7280', description: 'Versicherungen, Mitgliedsbeiträge, Schadenersatz' },
];

/** A single slice in a category breakdown (for charts/tables) */
export interface CategorySlice {
	category: BudgetCategory;
	amount: number;
	percent: number;
}

/** A single sub-item within a category (konto-level detail from struktur tables) */
export interface SubItem {
	konto: string;
	label: string;
	amount: number;
	percent: number;
}

/**
 * Build a sub-item breakdown for a specific category position.
 * Uses konto-level data from struktur_ergebnishaushalt tables.
 * Returns sub-items sorted by absolute amount descending.
 * Returns empty array if no konto-level detail is available.
 */
export function buildSubItems(
	items: LineItem[],
	nr: string,
	year: number
): SubItem[] {
	// Find struktur items that match this nr and year
	const strukturItems = items.filter(
		(i) =>
			i.haushalt_type === 'ergebnishaushalt' &&
			i.table_id.startsWith('struktur_') &&
			i.nr === nr &&
			i.year === year &&
			i.konto
	);

	if (strukturItems.length === 0) return [];

	// Aggregate by konto (there might be duplicates from different documents)
	const byKonto = new Map<string, { label: string; amount: number }>();
	for (const item of strukturItems) {
		const key = item.konto!;
		if (!byKonto.has(key)) {
			byKonto.set(key, { label: item.bezeichnung, amount: Math.abs(item.amount) });
		}
		// If duplicate, keep the one already there (first match wins)
	}

	const subItems: SubItem[] = [];
	let total = 0;

	for (const [konto, { label, amount }] of byKonto) {
		if (amount === 0) continue;
		subItems.push({ konto, label, amount, percent: 0 });
		total += amount;
	}

	// Calculate percentages
	for (const s of subItems) {
		s.percent = total > 0 ? s.amount / total : 0;
	}

	// Sort by amount descending
	subItems.sort((a, b) => b.amount - a.amount);
	return subItems;
}

/**
 * Get the years for which konto-level detail (struktur data) is available
 * for a specific category position.
 */
export function subItemYears(items: LineItem[], nr: string): number[] {
	const years = new Set<number>();
	for (const item of items) {
		if (
			item.haushalt_type === 'ergebnishaushalt' &&
			item.table_id.startsWith('struktur_') &&
			item.nr === nr &&
			item.konto
		) {
			years.add(item.year);
		}
	}
	return [...years].sort((a, b) => a - b);
}

/**
 * Build a breakdown of revenue or expense categories for a given year.
 * Picks the best data: Ist if available, otherwise latest Plan.
 * Returns slices sorted by absolute amount descending.
 */
export function buildCategoryBreakdown(
	items: LineItem[],
	year: number,
	side: 'einnahmen' | 'ausgaben',
	preferredType: 'ist' | 'plan' = 'ist'
): CategorySlice[] {
	const categories = side === 'einnahmen' ? REVENUE_CATEGORIES : EXPENSE_CATEGORIES;
	const ehItems = items.filter((i) => i.haushalt_type === 'ergebnishaushalt' && i.year === year && !i.table_id.startsWith('struktur_'));

	const slices: CategorySlice[] = [];
	let total = 0;

	for (const cat of categories) {
		// Find matching items for this position
		const matches = ehItems.filter((i) => i.nr === cat.nr);
		if (matches.length === 0) continue;

		// Prefer ist, fallback to plan
		const istMatch = matches.find((m) => m.amount_type === 'ist');
		const planMatch = matches.find((m) => m.amount_type === 'plan');
		const item = preferredType === 'ist' ? (istMatch ?? planMatch) : (planMatch ?? istMatch);
		if (!item) continue;

		const absAmount = Math.abs(item.amount);
		if (absAmount === 0) continue;

		slices.push({ category: cat, amount: absAmount, percent: 0 });
		total += absAmount;
	}

	// Calculate percentages
	for (const s of slices) {
		s.percent = total > 0 ? s.amount / total : 0;
	}

	// Sort by amount descending
	slices.sort((a, b) => b.amount - a.amount);
	return slices;
}

/**
 * Get the best available data type for a year.
 * Returns 'ist' if Ist data exists, otherwise 'plan'.
 */
export function bestDataType(items: LineItem[], year: number): 'ist' | 'plan' {
	const hasIst = items.some(
		(i) => i.haushalt_type === 'ergebnishaushalt' && i.year === year && i.amount_type === 'ist'
	);
	return hasIst ? 'ist' : 'plan';
}

/**
 * Get the total (sum position) for revenue or expenses in a given year.
 * Nr. 100 = Summe ordentliche Erträge, Nr. 190 = Summe ordentliche Aufwendungen
 */
export function getCategoryTotal(
	items: LineItem[],
	year: number,
	side: 'einnahmen' | 'ausgaben',
	preferredType: 'ist' | 'plan' = 'ist'
): number | null {
	const sumNr = side === 'einnahmen' ? '100' : '190';
	const matches = items.filter(
		(i) => i.haushalt_type === 'ergebnishaushalt' && i.year === year && i.nr === sumNr
	);
	const istMatch = matches.find((m) => m.amount_type === 'ist');
	const planMatch = matches.find((m) => m.amount_type === 'plan');
	const item = preferredType === 'ist' ? (istMatch ?? planMatch) : (planMatch ?? istMatch);
	return item ? Math.abs(item.amount) : null;
}

/** Short label for haushalt_type */
export function haushaltTypeLabel(type: HaushaltType): string {
	switch (type) {
		case 'ergebnishaushalt':
			return 'EH';
		case 'finanzhaushalt':
			return 'FH';
		case 'teilergebnishaushalt':
			return 'TEH';
		case 'teilfinanzhaushalt':
			return 'TFH';
		case 'investitionen':
			return 'Inv';
		default:
			return type;
	}
}

/** Long label for haushalt_type */
export function haushaltTypeLabelLong(type: HaushaltType): string {
	switch (type) {
		case 'ergebnishaushalt':
			return 'Ergebnishaushalt';
		case 'finanzhaushalt':
			return 'Finanzhaushalt';
		case 'teilergebnishaushalt':
			return 'Teilergebnishaushalt';
		case 'teilfinanzhaushalt':
			return 'Teilfinanzhaushalt';
		case 'investitionen':
			return 'Investitionen';
		default:
			return type;
	}
}

// ─── Investment Commentary from Jahresabschlüsse ───

import type { InvestmentCommentary, InvestmentClassification } from './types';

/** Load investment commentary extracted from Rechenschaftsberichte */
export async function loadInvestmentCommentary(
	fetchFn: typeof fetch = fetch
): Promise<InvestmentCommentary[]> {
	try {
		const res = await fetchFn('/data/investment_commentary.json');
		if (!res.ok) return [];
		return await res.json();
	} catch {
		return [];
	}
}

/** Load the semantically classified investment entries */
export async function loadInvestmentClassification(
	fetchFn: typeof fetch = fetch
): Promise<InvestmentClassification | null> {
	try {
		const res = await fetchFn('/data/investment_classification.json');
		if (!res.ok) return null;
		return await res.json();
	} catch {
		return null;
	}
}

// ─── Hebesatz Data ───

import type { HebesatzData } from './types';

/** Load Grundsteuer B Hebesätze for Kreis Offenbach */
export async function loadHebesaetzeGrundsteuerB(
	fetchFn: typeof fetch = fetch
): Promise<HebesatzData | null> {
	try {
		const res = await fetchFn('/data/hebesaetze_grundsteuer_b.json');
		if (!res.ok) return null;
		return await res.json();
	} catch {
		return null;
	}
}

/** Load Gewerbesteuer Hebesätze for Kreis Offenbach */
export async function loadHebesaetzeGewerbesteuer(
	fetchFn: typeof fetch = fetch
): Promise<HebesatzData | null> {
	try {
		const res = await fetchFn('/data/hebesaetze_gewerbesteuer.json');
		if (!res.ok) return null;
		return await res.json();
	} catch {
		return null;
	}
}

// ─── Provenance / Source Citation Utilities ───

/** Short label for a document, e.g. "HH 2026 Entwurf" */
export function shortDocLabel(documentId: string): string {
	const m =
		/^(haushaltsplan|jahresabschluss|gesamtabschluss|haushaltsrede|beteiligungsbericht|konsolidierung|praesentation|nachtragshaushalt|haushaltssatzung)_(\d{4})(?:_(\d{4}))?(?:_(beschluss|entwurf|anpassung))?$/.exec(
			documentId
		);
	if (!m) return formatDocumentName(documentId);

	const typeAbbrev: Record<string, string> = {
		haushaltsplan: 'HH',
		jahresabschluss: 'JA',
		gesamtabschluss: 'GA',
		haushaltsrede: 'HR',
		beteiligungsbericht: 'BB',
		konsolidierung: 'Kons.',
		praesentation: 'Präs.',
		nachtragshaushalt: 'NH',
		haushaltssatzung: 'HS'
	};
	const suffixLabel: Record<string, string> = {
		beschluss: 'Beschluss',
		entwurf: 'Entwurf',
		anpassung: 'Anpassung'
	};

	const prefix = typeAbbrev[m[1]] ?? m[1];
	const years = m[3] ? `${m[2]}/${m[3].slice(2)}` : m[2];
	const suffix = m[4] ? ` ${suffixLabel[m[4]] ?? m[4]}` : '';
	return `${prefix} ${years}${suffix}`;
}

/**
 * Build a PDF link URL for a document and page.
 * Returns null if the document has no local filename.
 */
function pdfUrl(doc: Document, page: number | null): string {
	const base = `/pdfs/${doc.filename}`;
	return page ? `${base}#page=${page}` : base;
}

/**
 * Build a Map of year → SourceLink[] for table column headers.
 * For each year, finds all unique (document_id, page) from overview items
 * of the given haushalt type.
 */
export function sourceLinksPerYear(
	items: LineItem[],
	documents: Document[],
	haushaltType: string
): Map<number, SourceLink[]> {
	const overview = overviewItems(items).filter((i) => i.haushalt_type === haushaltType);
	const byYear = groupBy(overview, (i) => String(i.year));
	const result = new Map<number, SourceLink[]>();
	for (const [yearStr, yearItems] of byYear) {
		const links = sourceLinksFromItems(yearItems, documents);
		if (links.length > 0) result.set(Number(yearStr), links);
	}
	return result;
}

/**
 * Extract unique source links from an array of LineItems.
 * Groups by (document_id, page) to avoid duplicate links.
 * Returns SourceLinks sorted by document_id descending (most recent first).
 */
export function sourceLinksFromItems(items: LineItem[], documents: Document[]): SourceLink[] {
	const docMap = new Map(documents.map((d) => [d.document_id, d]));
	const seen = new Map<string, { document_id: string; page: number | null }>();

	for (const item of items) {
		if (!item.document_id) continue;
		const key = `${item.document_id}__${item.page ?? 'x'}`;
		if (!seen.has(key)) {
			seen.set(key, { document_id: item.document_id, page: item.page });
		}
	}

	const links: SourceLink[] = [];
	for (const { document_id, page } of seen.values()) {
		const doc = docMap.get(document_id);
		if (!doc?.filename) continue;

		const label = page ? `${shortDocLabel(document_id)}, S.\u00a0${page}` : shortDocLabel(document_id);
		links.push({
			label,
			href: pdfUrl(doc, page),
			document_id,
			page
		});
	}

	// Sort: most recent document first (by document_id descending)
	links.sort((a, b) => b.document_id.localeCompare(a.document_id));
	return links;
}

/**
 * Build source links for a specific position (nr) from overview items.
 * Finds all unique (document_id, page) combinations for that position.
 */
export function sourceLinksForNr(
	items: LineItem[],
	documents: Document[],
	haushaltType: string,
	nr: string
): SourceLink[] {
	const filtered = overviewItems(items).filter(
		(i) => i.haushalt_type === haushaltType && i.nr === nr
	);
	return sourceLinksFromItems(filtered, documents);
}

/**
 * Build source links for the positions used in the summary (overview charts).
 * Takes the summary time series points and resolves the document_id → SourceLink.
 * Note: Summary points don't have page numbers, so we look up page from line_items.
 */
export function sourceLinksForSummaryChart(
	chartPoints: { document_id: string }[],
	allItems: LineItem[],
	documents: Document[],
	haushaltType: string,
	nr: string
): SourceLink[] {
	// Find the actual LineItems that correspond to these chart points
	const docIds = new Set(chartPoints.map((p) => p.document_id).filter(Boolean));
	const relevantItems = overviewItems(allItems).filter(
		(i) => i.haushalt_type === haushaltType && i.nr === nr && docIds.has(i.document_id)
	);
	return sourceLinksFromItems(relevantItems, documents);
}

// ─── Task-based Expense Categories (citizen-friendly, by Teilhaushalt) ───

/** Obligation type for a municipal task */
export type PflichtType = 'pflicht' | 'freiwillig' | 'misch';

/** A citizen-friendly expense category based on functional areas (Teilhaushalte) */
export interface TaskCategory {
	id: string;
	label: string;
	shortLabel: string;
	/** Teilhaushalt numbers that belong to this group */
	thNrs: string[];
	/** Fachbereich numbers from the Produktübersicht that belong to this group */
	fbNrs: string[];
	color: string;
	pflicht: PflichtType;
	pflichtLabel: string;
	description: string;
	/** Icon hint for the UI (Lucide icon name) */
	icon: string;
}

/** Citizen-friendly expense groups mapped from Teilhaushalte.
 *  TH 14 (Allgemeine Finanzmittel) is split: Nr. 160 → Umlagen, rest → Sonstige Finanzen.
 *  TH 6+7 are combined (TH 7 split from TH 6 in 2024).
 */
export const TASK_CATEGORIES: TaskCategory[] = [
	{
		id: 'kinder_soziales',
		label: 'Kinder, Jugend & Soziales',
		shortLabel: 'Kinder & Soziales',
		thNrs: ['4'],
		fbNrs: ['4'],
		color: '#e11d48',
		pflicht: 'pflicht',
		pflichtLabel: 'Pflichtaufgabe',
		description: 'Kinderbetreuung (KiTa-Zuschüsse), Jugendarbeit, Seniorenbetreuung, Sozialhilfe – größtenteils gesetzlich vorgeschrieben',
		icon: 'baby',
	},
	{
		id: 'umlagen',
		label: 'Umlagen an den Kreis',
		shortLabel: 'Kreis-Umlagen',
		thNrs: ['14_160'],  // special: only Nr. 160 from TH 14
		fbNrs: [],  // TH14 sub-split: use konto drilldown instead
		color: '#9333ea',
		pflicht: 'pflicht',
		pflichtLabel: 'Pflichtaufgabe',
		description: 'Rödermark zahlt als kreisangehörige Kommune Umlagen an den Kreis Offenbach – vor allem die Kreisumlage (finanziert Kreisaufgaben wie Sozialhilfe, Straßen, Gesundheitsamt), die Schulumlage (Schulbau und -betrieb) sowie die Gewerbesteuerumlage an Bund und Land. Die Höhe wird vom Kreis bzw. per Gesetz festgelegt – die Stadt hat darauf keinen Einfluss.',
		icon: 'landmark',
	},
	{
		id: 'bauen',
		label: 'Bauen & Infrastruktur',
		shortLabel: 'Bauen',
		thNrs: ['6', '7'],
		fbNrs: ['6', '7'],  // FB7 split from FB6 in 2024
		color: '#ea580c',
		pflicht: 'misch',
		pflichtLabel: 'Pflicht + freiwillig',
		description: 'Straßen, Gebäudeunterhaltung, Stadtentwicklung, Abwasser/Entsorgung – Pflichtaufgabe mit freiwilligen Anteilen',
		icon: 'hard-hat',
	},
	{
		id: 'ordnung',
		label: 'Ordnung & Sicherheit',
		shortLabel: 'Ordnung',
		thNrs: ['3'],
		fbNrs: ['3'],
		color: '#2563eb',
		pflicht: 'pflicht',
		pflichtLabel: 'Pflichtaufgabe',
		description: 'Ordnungsamt, Standesamt, Bürgerservice, Einwohnermeldeamt – hoheitliche Pflichtaufgaben',
		icon: 'shield',
	},
	{
		id: 'verwaltung',
		label: 'Verwaltung',
		shortLabel: 'Verwaltung',
		thNrs: ['1', '2', '10', '11', '12'],
		fbNrs: ['1', '2', '10', '11', '12'],
		color: '#64748b',
		pflicht: 'pflicht',
		pflichtLabel: 'Pflichtaufgabe',
		description: 'Rathaus, Personalverwaltung, Finanzen, Rechnungsprüfung, Wirtschaftsförderung – Organisation des laufenden Betriebs',
		icon: 'building-2',
	},
	{
		id: 'kultur_sport',
		label: 'Kultur, Sport & Vereine',
		shortLabel: 'Kultur & Sport',
		thNrs: ['5'],
		fbNrs: ['5'],
		color: '#0891b2',
		pflicht: 'freiwillig',
		pflichtLabel: 'Freiwillige Leistung',
		description: 'Kulturbüro, Sportanlagen, Schwimmbad, Vereinsförderung, Bücherei – freiwillige Aufgaben, die die Stadt jederzeit kürzen könnte',
		icon: 'music',
	},
	{
		id: 'integration',
		label: 'Integration & Teilhabe',
		shortLabel: 'Integration',
		thNrs: ['9'],
		fbNrs: ['9'],
		color: '#059669',
		pflicht: 'pflicht',
		pflichtLabel: 'Pflichtaufgabe',
		description: 'Unterbringung von Geflüchteten, Integration, Vielfalt – überwiegend durch Land/Bund refinanziert',
		icon: 'heart-handshake',
	},
	{
		id: 'feuerwehr',
		label: 'Feuerwehr & Brandschutz',
		shortLabel: 'Feuerwehr',
		thNrs: ['8'],
		fbNrs: ['8'],
		color: '#dc2626',
		pflicht: 'pflicht',
		pflichtLabel: 'Pflichtaufgabe',
		description: 'Freiwillige Feuerwehr, Brandschutz, Katastrophenschutz – gesetzliche Pflichtaufgabe',
		icon: 'flame',
	},
	{
		id: 'versorgung',
		label: 'Pensionen & Versorgung',
		shortLabel: 'Pensionen',
		thNrs: ['14_120'],  // special: only Nr. 120 from TH 14
		fbNrs: [],  // TH14 sub-split: use konto drilldown instead
		color: '#a855f7',
		pflicht: 'pflicht',
		pflichtLabel: 'Pflichtaufgabe',
		description: 'Beamtenpensionen und Beihilfen – gesetzliche Versorgungsverpflichtungen',
		icon: 'user-check',
	},
	{
		id: 'wald',
		label: 'Stadtwald & Natur',
		shortLabel: 'Wald',
		thNrs: ['13'],
		fbNrs: ['13'],  // FB13 exists through 2023; from 2024 merged into FB6 (→ bauen)
		color: '#16a34a',
		pflicht: 'misch',
		pflichtLabel: 'Pflicht + freiwillig',
		description: 'Forstwirtschaft, Naturschutz – teilweise gesetzlich, teilweise freiwillig',
		icon: 'trees',
	},
	{
		id: 'sonstige_finanzen',
		label: 'Sonstige Finanzen',
		shortLabel: 'Sonstige',
		thNrs: ['14_rest'],  // special: TH 14 minus Nr. 160 and Nr. 120
		fbNrs: [],  // TH14 sub-split: use konto drilldown instead
		color: '#94a3b8',
		pflicht: 'misch',
		pflichtLabel: 'Pflicht + freiwillig',
		description: 'Personal Kämmerei, Sachkosten, Abschreibungen und sonstige zentrale Finanzposten',
		icon: 'wallet',
	},
];

/** A single slice in a task breakdown (for charts/tables) */
export interface TaskSlice {
	task: TaskCategory;
	amount: number;
	percent: number;
}

/**
 * Build a citizen-friendly expense breakdown by functional area (Teilhaushalte).
 * Uses Nr. 190 (total expenses) from each Teilergebnishaushalt.
 * TH 14 is split into Umlagen (Nr. 160), Versorgung (Nr. 120), and rest.
 */
export function buildTaskBreakdown(
	items: LineItem[],
	year: number,
	preferredType: 'ist' | 'plan' = 'ist'
): TaskSlice[] {
	// All teilergebnishaushalt items for this year
	const tehItems = items.filter(
		(i) => i.haushalt_type === 'teilergebnishaushalt' && i.year === year
	);

	/** Get best amount for a specific TH and Nr */
	function getAmount(thNr: string, nr: string): number {
		const matches = tehItems.filter(
			(i) => {
				const iThNr = i.teilhaushalt_nr?.replace('.0', '') ?? '';
				return iThNr === thNr && i.nr === nr;
			}
		);
		const ist = matches.find((m) => m.amount_type === 'ist');
		const plan = matches.find((m) => m.amount_type === 'plan');
		const item = preferredType === 'ist' ? (ist ?? plan) : (plan ?? ist);
		return item ? Math.abs(item.amount) : 0;
	}

	const slices: TaskSlice[] = [];
	let total = 0;

	for (const task of TASK_CATEGORIES) {
		let amount = 0;

		for (const thRef of task.thNrs) {
			if (thRef === '14_160') {
				// Only Nr. 160 (Umlagen) from TH 14
				amount += getAmount('14', '160');
			} else if (thRef === '14_120') {
				// Only Nr. 120 (Versorgung) from TH 14
				amount += getAmount('14', '120');
			} else if (thRef === '14_rest') {
				// TH 14 total (Nr. 190) minus Nr. 160 and Nr. 120
				const th14Total = getAmount('14', '190');
				const umlagen = getAmount('14', '160');
				const versorgung = getAmount('14', '120');
				amount += Math.max(0, th14Total - umlagen - versorgung);
			} else {
				// Normal TH: use Nr. 190 (total expenses)
				amount += getAmount(thRef, '190');
			}
		}

		if (amount === 0) continue;
		slices.push({ task, amount, percent: 0 });
		total += amount;
	}

	// Calculate percentages
	for (const s of slices) {
		s.percent = total > 0 ? s.amount / total : 0;
	}

	// Sort by amount descending
	slices.sort((a, b) => b.amount - a.amount);
	return slices;
}

/**
 * Build a time series for a task category across all years.
 * Returns data points with year, amount (expenses Nr. 190 or sub-position),
 * amount_type, and document_id for source citations.
 */
export function taskTimeSeries(
	items: LineItem[],
	taskId: string
): { year: number; amount: number; amount_type: string; document_id: string }[] {
	const task = TASK_CATEGORIES.find((t) => t.id === taskId);
	if (!task) return [];

	const tehItems = items.filter(
		(i) => i.haushalt_type === 'teilergebnishaushalt'
	);

	// Gather all available years
	const years = [...new Set(tehItems.map((i) => i.year))].sort((a, b) => a - b);

	const results: { year: number; amount: number; amount_type: string; document_id: string }[] = [];

	for (const year of years) {
		const yearItems = tehItems.filter((i) => i.year === year);

		function getBest(thNr: string, nr: string): { amount: number; type: string; doc: string } | null {
			const matches = yearItems.filter((i) => {
				const iThNr = i.teilhaushalt_nr?.replace('.0', '') ?? '';
				return iThNr === thNr && i.nr === nr;
			});
			const ist = matches.find((m) => m.amount_type === 'ist');
			const plan = matches.find((m) => m.amount_type === 'plan');
			const item = ist ?? plan;
			if (!item) return null;
			return { amount: Math.abs(item.amount), type: item.amount_type, doc: item.document_id };
		}

		let totalAmount = 0;
		let bestType = 'plan';
		let bestDoc = '';

		for (const thRef of task.thNrs) {
			let result: { amount: number; type: string; doc: string } | null = null;
			if (thRef === '14_160') {
				result = getBest('14', '160');
			} else if (thRef === '14_120') {
				result = getBest('14', '120');
			} else if (thRef === '14_rest') {
				const total = getBest('14', '190');
				const umlagen = getBest('14', '160');
				const versorgung = getBest('14', '120');
				if (total) {
					const rest = Math.max(0, total.amount - (umlagen?.amount ?? 0) - (versorgung?.amount ?? 0));
					result = { amount: rest, type: total.type, doc: total.doc };
				}
			} else {
				result = getBest(thRef, '190');
			}
			if (result) {
				totalAmount += result.amount;
				if (result.type === 'ist') bestType = 'ist';
				if (!bestDoc) bestDoc = result.doc;
			}
		}

		if (totalAmount > 0) {
			results.push({ year, amount: totalAmount, amount_type: bestType, document_id: bestDoc });
		}
	}

	return results;
}

/**
 * Get source links for a task category from its constituent Teilhaushalte.
 */
export function taskSourceLinks(
	items: LineItem[],
	documents: Document[],
	taskId: string
): SourceLink[] {
	const task = TASK_CATEGORIES.find((t) => t.id === taskId);
	if (!task) return [];

	const relevant = items.filter((i) => {
		if (i.haushalt_type !== 'teilergebnishaushalt') return false;
		const thNr = i.teilhaushalt_nr?.replace('.0', '') ?? '';
		for (const ref of task.thNrs) {
			if (ref === '14_160' || ref === '14_120' || ref === '14_rest') {
				if (thNr === '14') return true;
			} else {
				if (thNr === ref) return true;
			}
		}
		return false;
	});

	return sourceLinksFromItems(relevant, documents);
}

/**
 * Convert TaskSlice[] → CategorySlice[] for use in DonutChart.
 * Maps TaskCategory fields to BudgetCategory shape.
 */
export function taskSlicesToCategorySlices(slices: TaskSlice[]): CategorySlice[] {
	return slices.map((s) => ({
		category: {
			nr: s.task.id,
			label: s.task.label,
			shortLabel: s.task.shortLabel,
			side: 'ausgaben' as const,
			color: s.task.color,
			description: s.task.description,
		},
		amount: s.amount,
		percent: s.percent,
	}));
}

/** A single sub-position within a task category drill-down */
export interface TaskDrilldownItem {
	nr: string;
	label: string;
	amount: number;
	percent: number;
}

/**
 * Drill down into konto-level detail for TH14 sub-splits (e.g. Kreisumlage, Schulumlage).
 * Uses ergebnishaushalt struktur data which has individual account lines.
 */
function buildKontoDrilldown(
	items: LineItem[],
	task: (typeof TASK_CATEGORIES)[number],
	year: number,
	preferredType: 'ist' | 'plan'
): TaskDrilldownItem[] {
	const specialNrs = new Set(
		task.thNrs.filter((r) => r.startsWith('14_')).map((r) => r.split('_')[1])
	);

	// Find konto-level items in the ergebnishaushalt for these Nrs
	const ehItems = items.filter(
		(i) =>
			i.haushalt_type === 'ergebnishaushalt' &&
			i.year === year &&
			specialNrs.has(i.nr) &&
			i.konto != null &&
			i.konto !== ''
	);

	if (ehItems.length === 0) return [];

	// Group by konto, prefer the requested amount_type
	const byKonto = new Map<string, { ist?: LineItem; plan?: LineItem }>();
	for (const item of ehItems) {
		const konto = String(item.konto).replace('.0', '');
		const entry = byKonto.get(konto) ?? {};
		if (item.amount_type === 'ist') entry.ist = item;
		else entry.plan = item;
		byKonto.set(konto, entry);
	}

	const rows: { nr: string; label: string; amount: number }[] = [];
	for (const [konto, entry] of byKonto) {
		const pick = preferredType === 'ist' ? (entry.ist ?? entry.plan) : (entry.plan ?? entry.ist);
		if (!pick || pick.amount === 0) continue;
		rows.push({ nr: konto, label: pick.bezeichnung || `Konto ${konto}`, amount: Math.abs(pick.amount) });
	}

	const total = rows.reduce((a, b) => a + b.amount, 0);
	if (total === 0) return [];

	return rows
		.map((r) => ({ ...r, percent: r.amount / total }))
		.sort((a, b) => b.amount - a.amount);
}

/**
 * Drill down into individual products (Produkte) for a task category.
 * Uses Produktübersicht data (Zuschussbedarf per product) matched via fachbereich_nr.
 * Shows citizen-friendly items like "Kindergärten", "Schwimmbad" instead of
 * bookkeeping categories like "Personalaufwendungen", "Sachkosten".
 */
function buildProductDrilldown(
	items: LineItem[],
	task: (typeof TASK_CATEGORIES)[number],
	year: number,
	preferredType: 'ist' | 'plan'
): TaskDrilldownItem[] {
	const fbNrSet = new Set(task.fbNrs);

	// Get all produktuebersicht items for this year and matching Fachbereiche
	const prodItems = items.filter(
		(i) =>
			i.haushalt_type === 'produktuebersicht' &&
			i.year === year &&
			i.fachbereich_nr != null &&
			fbNrSet.has(String(Math.trunc(Number(i.fachbereich_nr))))
	);

	if (prodItems.length === 0) return [];

	// Group by product nr, prefer the requested amount_type
	const byProduct = new Map<string, { ist?: LineItem; plan?: LineItem }>();
	for (const item of prodItems) {
		const key = item.nr;
		const entry = byProduct.get(key) ?? {};
		if (item.amount_type === 'ist') entry.ist = item;
		else entry.plan = item;
		byProduct.set(key, entry);
	}

	// Zuschussbedarf: negative = the city pays (deficit), positive = surplus.
	// For expense display we want amounts where city pays → use absolute values of negative amounts,
	// but also include positive amounts (both sides are relevant for the drilldown).
	const rows: { nr: string; label: string; amount: number }[] = [];
	for (const [nr, entry] of byProduct) {
		const pick = preferredType === 'ist' ? (entry.ist ?? entry.plan) : (entry.plan ?? entry.ist);
		if (!pick) continue;
		// Use absolute value – Zuschussbedarf sign just indicates surplus/deficit
		const amount = Math.abs(pick.amount);
		if (amount === 0) continue;
		rows.push({ nr, label: pick.bezeichnung || `Produkt ${nr}`, amount });
	}

	const total = rows.reduce((a, b) => a + b.amount, 0);
	if (total === 0) return [];

	return rows
		.map((r) => ({ ...r, percent: r.amount / total }))
		.sort((a, b) => b.amount - a.amount);
}

/**
 * Build a drill-down for a task category.
 * - TH14 sub-splits → konto-level detail from ergebnishaushalt
 * - All other categories → product-level detail from Produktübersicht (Zuschussbedarf per product)
 * Citizen-friendly: shows "Kindergärten", "Schwimmbad" instead of "Personalkosten", "Sachkosten".
 */
export function buildTaskDrilldown(
	items: LineItem[],
	taskId: string,
	year: number,
	preferredType: 'ist' | 'plan' = 'ist'
): TaskDrilldownItem[] {
	const task = TASK_CATEGORIES.find((t) => t.id === taskId);
	if (!task) return [];

	// For TH14 sub-splits (14_160, 14_120, 14_rest), drill down into konto-level detail
	// from the ergebnishaushalt (struktur) data
	const isSpecialTh14 = task.thNrs.some((r) => r.startsWith('14_'));
	if (isSpecialTh14) {
		return buildKontoDrilldown(items, task, year, preferredType);
	}

	// For all other categories: use product-level drilldown from Produktübersicht
	if (task.fbNrs.length > 0) {
		const productResult = buildProductDrilldown(items, task, year, preferredType);
		if (productResult.length > 0) return productResult;
	}

	// Fallback: no product data available for this year → return empty
	return [];
}

/**
 * Get source links for the drilldown of a task category.
 * Uses produktuebersicht sources for product drilldowns and ergebnishaushalt
 * sources for TH14 konto drilldowns – matching the same items shown in the table.
 */
export function drilldownSourceLinks(
	items: LineItem[],
	documents: Document[],
	taskId: string,
	year: number
): SourceLink[] {
	const task = TASK_CATEGORIES.find((t) => t.id === taskId);
	if (!task) return [];

	// TH14 sub-splits: source from ergebnishaushalt konto items
	const isSpecialTh14 = task.thNrs.some((r) => r.startsWith('14_'));
	if (isSpecialTh14) {
		const specialNrs = new Set(
			task.thNrs.filter((r) => r.startsWith('14_')).map((r) => r.split('_')[1])
		);
		const relevant = items.filter(
			(i) =>
				i.haushalt_type === 'ergebnishaushalt' &&
				i.year === year &&
				specialNrs.has(i.nr)
		);
		return sourceLinksFromItems(relevant, documents);
	}

	// Product drilldown: source from produktuebersicht items
	if (task.fbNrs.length > 0) {
		const fbNrSet = new Set(task.fbNrs);
		const relevant = items.filter(
			(i) =>
				i.haushalt_type === 'produktuebersicht' &&
				i.year === year &&
				i.fachbereich_nr != null &&
				fbNrSet.has(String(Math.trunc(Number(i.fachbereich_nr))))
		);
		return sourceLinksFromItems(relevant, documents);
	}

	return [];
}