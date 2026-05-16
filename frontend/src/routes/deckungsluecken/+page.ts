import { loadLineItems, loadSummary, loadDocuments } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [items, summary, documents] = await Promise.all([
		loadLineItems(fetch),
		loadSummary(fetch),
		loadDocuments(fetch)
	]);

	// Need teilergebnishaushalt for revenue/expense per TH,
	// ergebnishaushalt for konto-level detail (struktur tables),
	// and produktuebersicht for product-level drill-down
	const relevantItems = items.filter(
		(i) =>
			i.haushalt_type === 'teilergebnishaushalt' ||
			i.haushalt_type === 'ergebnishaushalt' ||
			i.haushalt_type === 'produktuebersicht'
	);

	return { items: relevantItems, summary, documents };
};
