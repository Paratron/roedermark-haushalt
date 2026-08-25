import { loadHsk, loadDocuments } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	const [hsk, documents] = await Promise.all([loadHsk(), loadDocuments()]);
	return { hsk, documents };
};
