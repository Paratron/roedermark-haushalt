import { loadLineItems, loadSummary, loadDocuments, teilhaushaltItems } from '$lib/data';
import type { LineItem } from '$lib/types';
import type { PageLoad } from './$types';

function buildTeilhaushalte(thItems: LineItem[]) {
	const thMap = new Map<string, { nr: string; name: string; countTE: number; countTF: number }>();
	for (const item of thItems) {
		const nr = item.teilhaushalt_nr ?? '';
		if (!nr || nr === 'nan') continue;
		const existing = thMap.get(nr);
		if (existing) {
			if (item.haushalt_type === 'teilergebnishaushalt') existing.countTE++;
			else existing.countTF++;
			if ((item.teilhaushalt_name ?? '').length > existing.name.length) {
				existing.name = item.teilhaushalt_name ?? '';
			}
		} else {
			thMap.set(nr, {
				nr,
				name: item.teilhaushalt_name ?? '',
				countTE: item.haushalt_type === 'teilergebnishaushalt' ? 1 : 0,
				countTF: item.haushalt_type === 'teilfinanzhaushalt' ? 1 : 0
			});
		}
	}
	return [...thMap.values()].sort(
		(a, b) => Number.parseFloat(a.nr) - Number.parseFloat(b.nr)
	);
}

export const load: PageLoad = async ({ fetch }) => {
	const [allItems, summary, documents] = await Promise.all([
		loadLineItems(fetch),
		loadSummary(fetch),
		loadDocuments(fetch)
	]);
	const thItems = teilhaushaltItems(allItems);
	const teilhaushalte = buildTeilhaushalte(thItems);
	return { items: thItems, summary, teilhaushalte, documents };
};
