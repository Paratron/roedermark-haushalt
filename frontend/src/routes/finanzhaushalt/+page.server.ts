import { loadSummary, loadLineItems, loadDocuments, overviewItems } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [summary, allItems, documents] = await Promise.all([
		loadSummary(fetch),
		loadLineItems(fetch),
		loadDocuments(fetch)
	]);

	const overview = overviewItems(allItems).filter((i) => i.haushalt_type === 'finanzhaushalt');

	const positions = new Map<string, { nr: string; bezeichnung: string }>();
	for (const item of overview) {
		if (!positions.has(item.nr)) {
			positions.set(item.nr, { nr: item.nr, bezeichnung: item.bezeichnung });
		}
	}
	const sortedPositions = [...positions.values()].sort(
		(a, b) => Number.parseInt(a.nr) - Number.parseInt(b.nr)
	);

	return { summary, items: overview, positions: sortedPositions, documents };
};
