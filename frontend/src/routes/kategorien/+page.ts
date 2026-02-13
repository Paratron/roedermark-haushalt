import { loadLineItems, loadSummary, loadDocuments } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [items, summary, documents] = await Promise.all([
		loadLineItems(fetch),
		loadSummary(fetch),
		loadDocuments(fetch)
	]);

	// Aufgabenbereich view: needs teilergebnishaushalt items (TH breakdown)
	// plus ergebnishaushalt items for konto-level drill-down (e.g. Umlagen)
	// plus produktuebersicht items for product-level drill-down
	const relevantItems = items.filter(
		(i) => i.haushalt_type === 'teilergebnishaushalt' || i.haushalt_type === 'ergebnishaushalt' || i.haushalt_type === 'produktuebersicht'
	);

	return { items: relevantItems, summary, documents };
};
