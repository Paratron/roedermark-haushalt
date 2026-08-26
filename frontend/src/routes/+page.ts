import { loadSummary, loadDocuments } from '$lib/data';
import type { PageLoad } from './$types';

// loadHsk ist hier bewusst nicht mehr dabei: solange der HSK-Banner ausgeblendet
// ist, rendert die Startseite nichts daraus – die Datei landete aber weiterhin
// vollständig im Seitenquelltext (88 von 151 KB), mit Zahlen aus einer überholten
// Fassung. Wieder aufnehmen, wenn der Banner zurückkommt.
export const load: PageLoad = async () => {
	const [summary, documents] = await Promise.all([loadSummary(), loadDocuments()]);
	return { summary, documents };
};
