import { loadLineItems, loadSummary } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [items, summary] = await Promise.all([loadLineItems(fetch), loadSummary(fetch)]);
	return { items, planOnlyYears: summary.plan_only_years };
};
