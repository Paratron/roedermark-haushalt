import { loadSummary, loadPageItems, loadDocuments, overviewItems } from '$lib/data';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const [summary, allItems, documents] = await Promise.all([
		loadSummary(),
		loadPageItems('finanzhaushalt'),
		loadDocuments()
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
