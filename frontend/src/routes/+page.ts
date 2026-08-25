import { loadSummary, loadDocuments } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	const [summary, documents] = await Promise.all([loadSummary(), loadDocuments()]);
	return { summary, documents };
};
