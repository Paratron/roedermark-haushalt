import { loadHsk, loadDocuments } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [hsk, documents] = await Promise.all([loadHsk(fetch), loadDocuments()]);
	return { hsk, documents };
};
