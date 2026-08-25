import { loadPageItems, loadSummary, loadDocuments, defaultYear } from '$lib/data';
import type { PageServerLoad } from './$types';

/**
 * Anders als die Aufgabenbereiche zeigt diese Seite Zeitreihen über alle Jahre –
 * das Jahr in die Route zu ziehen würde hier nichts sparen. Geladen wird nur noch
 * die Übersicht des Ergebnishaushalts; Teilhaushalte und Produktübersicht wurden
 * bisher mitgeliefert und sofort weggefiltert, und die Konto-Ebene holt die
 * Komponente erst nach, wenn jemand eine Ertragsart aufklappt.
 */
export const load: PageServerLoad = async () => {
	const [items, summary, documents] = await Promise.all([
		loadPageItems('ergebnishaushalt'),
		loadSummary(),
		loadDocuments()
	]);
	// Ohne ?year= zeigt die Seite das laufende Jahr. Sie wird vorgerendert, das Jahr
	// stammt also aus dem Build – ein Deploy pro Jahr genügt, um das aktuell zu halten.
	return { items, summary, documents, defaultYear: defaultYear(summary.years) };
};
