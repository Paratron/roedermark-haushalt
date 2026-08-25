import { loadPageItems, loadSummary, loadDocuments, pageDataKeys, defaultYear } from '$lib/data';
import type { PageServerLoad } from './$types';

/**
 * Diese Seite wird nicht vorgerendert, sondern bei Bedarf serverseitig gebaut.
 *
 * Beim Prerendering gibt es keine Anfrage, also auch kein ?year= – die Seite musste
 * alle fünfzehn Jahrgänge ausliefern und im Browser umschalten. Als Server-Load
 * bekommt sie den Parameter und lädt genau das Jahr, das sie zeigt.
 *
 * isr.allowQuery macht year zum Teil des Cache-Keys: jede Jahresvariante wird einmal
 * gebaut und liegt danach im Edge-Cache. Andere Parameter (task) stehen bewusst nicht
 * drin – sie ändern nur den Ausschnitt derselben Daten und würden den Cache zersplittern.
 */
export const prerender = false;
export const config = { isr: { expiration: false, allowQuery: ['year'] } };

/** Die Jahre, für die es einen Datensatz gibt */
function verfuegbareJahre(): number[] {
	return pageDataKeys('kategorien')
		.map(Number)
		.sort((a, b) => a - b);
}

export const load: PageServerLoad = async ({ url }) => {
	const summary = await loadSummary();
	const years = verfuegbareJahre();

	const gewuenscht = Number(url.searchParams.get('year'));
	const year = years.includes(gewuenscht) ? gewuenscht : defaultYear(years);

	const prevYear = years.includes(year - 1) ? year - 1 : null;

	const [current, previous, series, documents] = await Promise.all([
		loadPageItems('kategorien', year),
		prevYear ? loadPageItems('kategorien', prevYear) : Promise.resolve([]),
		// Die Zeitreihe je Aufgabenbereich läuft quer über alle Jahre, braucht aber
		// nur die drei Summenpositionen – das sind 135 KB statt fünfzehn Jahrgängen.
		loadPageItems('kategorien_serie'),
		loadDocuments()
	]);

	return {
		year,
		prevYear,
		years,
		// Ein Array: die Zeitreihen-Zeilen sind Teilergebnishaushalt, die Jahresdaten
		// Ergebnishaushalt und Produktübersicht – die Auswertungen filtern ohnehin
		// nach haushalt_type.
		items: [...current, ...previous, ...series],
		summary,
		documents
	};
};
