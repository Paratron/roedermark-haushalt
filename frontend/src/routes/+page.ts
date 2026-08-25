import { loadSummary, loadDocuments, loadHsk } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	const [summary, documents, hsk] = await Promise.all([
		loadSummary(),
		loadDocuments(),
		loadHsk()
	]);
	return { summary, documents, hsk };
};
