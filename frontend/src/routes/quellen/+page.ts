import { loadDocuments, loadSummary } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	const [documents, summary] = await Promise.all([loadDocuments(), loadSummary()]);
	return { documents, summary };
};
