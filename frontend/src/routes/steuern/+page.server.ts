import {
	loadLineItems,
	loadSummary,
	loadDocuments,
	loadHebesaetzeGrundsteuerB,
	loadHebesaetzeGewerbesteuer,
	overviewItems,
	sourceLinksFromItems,
} from '$lib/data';
import type { LineItem } from '$lib/types';
import type { PageLoad } from './$types';

/** Tax categories we extract from position Nr. 50 (struktur) */
const TAX_KEYS = [
	{ match: 'Grundsteuer B', key: 'grundsteuer_b', label: 'Grundsteuer B', color: '#3b82f6' },
	{ match: 'Grundsteuer A', key: 'grundsteuer_a', label: 'Grundsteuer A', color: '#93c5fd' },
	{ match: 'Grundsteuer C', key: 'grundsteuer_c', label: 'Grundsteuer C', color: '#bfdbfe' },
	{ match: 'Gewerbesteuer', key: 'gewerbesteuer', label: 'Gewerbesteuer', color: '#f59e0b' },
	{ match: 'Einkommensteuer', key: 'einkommensteuer', label: 'Gemeindeanteil Einkommensteuer', color: '#10b981' },
	{ match: 'Umsatzsteuer', key: 'umsatzsteuer', label: 'Gemeindeanteil Umsatzsteuer', color: '#6ee7b7' },
	{ match: 'Hundesteuer', key: 'hundesteuer', label: 'Hundesteuer', color: '#8b5cf6' },
	{ match: 'Spielapparat', key: 'spielapparate', label: 'Spielapparatesteuer', color: '#a78bfa' },
	{ match: 'Vergnügungssteuer', key: 'vergnuegungssteuer', label: 'Vergnügungssteuer', color: '#c4b5fd' },
	{ match: 'Wettbüro', key: 'wettbuero', label: 'Wettbürosteuer', color: '#ddd6fe' },
];

export interface TaxItem {
	key: string;
	label: string;
	color: string;
	amount: number;
	percent: number;
}

export interface TaxTimeSeries {
	key: string;
	label: string;
	color: string;
	points: { year: number; amount: number }[];
}

/**
 * Deduplicate: keep only the row from the most recent document
 * for each (bezeichnung, year) combination.
 */
function dedup(items: LineItem[]): LineItem[] {
	const map = new Map<string, LineItem>();
	for (const item of items) {
		const key = `${item.bezeichnung}_${item.year}`;
		const existing = map.get(key);
		if (!existing || item.document_id > existing.document_id) {
			map.set(key, item);
		}
	}
	return [...map.values()];
}

export const load: PageLoad = async ({ fetch }) => {
	const [allItems, summary, documents, hebesaetzeGrundsteuerB, hebesaetzeGewerbesteuer] =
		await Promise.all([
			loadLineItems(fetch),
			loadSummary(fetch),
			loadDocuments(fetch),
			loadHebesaetzeGrundsteuerB(fetch),
			loadHebesaetzeGewerbesteuer(fetch),
		]);

	// Get detail tax items (Nr. 50, struktur_ tables contain the breakdown)
	const taxDetailItems = dedup(
		allItems.filter(
			(i) =>
				i.nr === '50' &&
				i.table_id.startsWith('struktur_') &&
				i.amount_type === 'plan'
		)
	);

	// Also get overview-level items for the total
	const overviewTaxItems = overviewItems(allItems).filter(
		(i) => i.nr === '50' && i.amount_type === 'plan'
	);

	// Available years from tax detail items
	const taxYears = [...new Set(taxDetailItems.map((i) => i.year))].sort((a, b) => a - b);

	// Build time series for each tax type
	const taxTimeSeries: TaxTimeSeries[] = TAX_KEYS.map((tk) => {
		const matching = taxDetailItems.filter((i) =>
			i.bezeichnung.includes(tk.match)
		);
		const points = taxYears.map((year) => {
			const item = matching.find((i) => i.year === year);
			return { year, amount: item ? Math.abs(item.amount) : 0 };
		}).filter((p) => p.amount > 0);
		return { key: tk.key, label: tk.label, color: tk.color, points };
	}).filter((ts) => ts.points.length > 0);

	// Source links for tax items
	const taxSourceLinks = sourceLinksFromItems(taxDetailItems, documents);

	return {
		summary,
		documents,
		taxDetailItems,
		overviewTaxItems,
		taxYears,
		taxTimeSeries,
		taxSourceLinks,
		hebesaetzeGrundsteuerB,
		hebesaetzeGewerbesteuer,
		taxKeys: TAX_KEYS,
	};
};
