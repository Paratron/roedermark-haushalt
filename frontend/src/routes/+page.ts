import { loadSummary, loadDocuments, loadHsk } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [summary, documents, hsk] = await Promise.all([
		loadSummary(),
		loadDocuments(),
		loadHsk(fetch)
	]);
	return { summary, documents, hsk };
};
