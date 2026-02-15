import { loadLineItems, loadSummary, loadDocuments } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [items, summary, documents] = await Promise.all([
		loadLineItems(fetch),
		loadSummary(fetch),
		loadDocuments(fetch),
	]);
	return { items, documents, planOnlyYears: summary.plan_only_years };
};
