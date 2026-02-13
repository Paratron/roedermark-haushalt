import { loadLineItems, loadSummary, loadDocuments, investitionItems } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [allItems, summary, documents] = await Promise.all([
		loadLineItems(fetch),
		loadSummary(fetch),
		loadDocuments(fetch)
	]);

	const investments = investitionItems(allItems);

	// Build unique Teilhaushalte list (by nr, pick most recent name)
	const thMap = new Map<string, { nr: string; name: string; count: number }>();
	for (const item of investments) {
		const nr = item.teilhaushalt_nr ?? '';
		if (!nr || nr === 'nan') continue;
		const existing = thMap.get(nr);
		if (existing) {
			existing.count++;
			// Use longest name (most descriptive, usually the most recent)
			if ((item.teilhaushalt_name ?? '').length > existing.name.length) {
				existing.name = item.teilhaushalt_name ?? '';
			}
		} else {
			thMap.set(nr, { nr, name: item.teilhaushalt_name ?? '', count: 1 });
		}
	}
	const teilhaushalte = [...thMap.values()].sort(
		(a, b) => Number.parseFloat(a.nr) - Number.parseFloat(b.nr)
	);

	return { investments, summary, teilhaushalte, documents };
};
