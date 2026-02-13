import { loadLineItems, loadSummary, loadDocuments } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [items, summary, documents] = await Promise.all([
		loadLineItems(fetch),
		loadSummary(fetch),
		loadDocuments(fetch)
	]);

	// Ertragsart view: ergebnishaushalt items (EH positions 10-90, 110-180)
	// Plus struktur items for sub-item drill-down
	const relevantItems = items.filter(
		(i) => i.haushalt_type === 'ergebnishaushalt' || i.table_id.startsWith('struktur_')
	);

	return { items: relevantItems, summary, documents };
};
