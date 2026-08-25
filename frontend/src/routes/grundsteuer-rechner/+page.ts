import { loadHebesaetzeGrundsteuerB } from '$lib/data';
import type { PageLoad } from './$types';

/**
 * Liefert den aktuellen (Vorjahr) und den neuen (jüngstes Jahr) Grundsteuer-B-
 * Hebesatz für Rödermark aus dem Hebesatz-Datensatz – damit der Rechner keine
 * Werte hartcodiert, sondern der Datenquelle folgt.
 */
export const load: PageLoad = async () => {
	const hebesaetze = await loadHebesaetzeGrundsteuerB();
	const roe = (hebesaetze?.data ?? [])
		.filter((e) => e.kommune === 'Rödermark')
		.sort((a, b) => a.year - b.year);

	const neu = roe.at(-1) ?? null;
	const aktuell = roe.at(-2) ?? null;

	return {
		aktuell: aktuell?.hebesatz ?? 990,
		neu: neu?.hebesatz ?? 1327,
		aktuellJahr: aktuell?.year ?? 2025,
		neuJahr: neu?.year ?? 2026,
		quelle: neu?.quelle ?? null,
		quelleUrl: neu?.quelle_url ?? null
	};
};
