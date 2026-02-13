import { loadDocuments, loadSummary } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [documents, summary] = await Promise.all([
		loadDocuments(fetch),
		loadSummary(fetch)
	]);
	return { documents, summary };
};
