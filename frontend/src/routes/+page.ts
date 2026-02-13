import { loadSummary, loadDocuments } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [summary, documents] = await Promise.all([
		loadSummary(fetch),
		loadDocuments(fetch)
	]);
	return { summary, documents };
};
