import {
	loadPageItems,
	loadPageIndex,
	loadSummary,
	loadDocuments,
	hasPageItems,
	teilhaushaltItems
} from '$lib/data';
import type { PageServerLoad } from './$types';

/**
 * Diese Seite wird nicht vorgerendert, sondern bei Bedarf serverseitig gebaut.
 *
 * Beim Prerendering gibt es keine Anfrage, also auch kein ?th= – die Seite musste
 * alle vierzehn Teilhaushalte ausliefern und im Browser umschalten. Als Server-Load
 * bekommt sie den Parameter und lädt genau den einen, den sie zeigt.
 *
 * isr.allowQuery macht th zum Teil des Cache-Keys. typ und nr stehen bewusst nicht
 * drin – sie wechseln nur den Ausschnitt derselben Daten.
 */
export const prerender = false;
export const config = { isr: { expiration: false, allowQuery: ['th'] } };

export const load: PageServerLoad = async ({ url }) => {
	const index = await loadPageIndex('teilhaushalte');
	const teilhaushalte = index
		.map((e) => ({
			nr: e.key,
			name: e.name,
			countTE: e.counts.teilergebnishaushalt ?? 0,
			countTF: e.counts.teilfinanzhaushalt ?? 0
		}))
		.sort((a, b) => Number.parseFloat(a.nr) - Number.parseFloat(b.nr));

	// Unbekannte Nummer führt auf den ersten Teilhaushalt statt auf einen Fehler –
	// so verhielt sich die Auswahl im Browser vorher auch.
	const gewuenscht = url.searchParams.get('th') ?? '';
	const th = hasPageItems('teilhaushalte', gewuenscht) ? gewuenscht : teilhaushalte[0].nr;

	const [items, summary, documents] = await Promise.all([
		loadPageItems('teilhaushalte', th),
		loadSummary(),
		loadDocuments()
	]);

	return { th, items: teilhaushaltItems(items), teilhaushalte, summary, documents };
};
