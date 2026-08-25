import { loadSummary, loadDocuments } from '$lib/data';
import type { PageLoad } from './$types';

/**
 * Der Explorer bekommt die Positionen nicht aus dem Load, sondern lädt sie im
 * Browser nach – er ist die einzige Seite, die tatsächlich alle durchsucht.
 *
 * Vorher bettete SvelteKit die 9,4 MB große CSV in die vorgerenderte Seite ein: der
 * Browser musste 9,7 MB HTML parsen, bevor irgendetwas zu sehen war. Die Seite wird
 * weiterhin vorgerendert – Navigation, Kopfzeile und Filter stehen also sofort da,
 * nur die Tabelle füllt sich, sobald die Daten da sind.
 */
export const load: PageLoad = async () => {
	const [summary, documents] = await Promise.all([loadSummary(), loadDocuments()]);
	return { documents, planOnlyYears: summary.plan_only_years };
};
