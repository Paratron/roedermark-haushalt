import type { PageLoad } from './$types';
import svgRaw from '$lib/assets/kreisvergleich-map.svg?raw';

export interface KommuneData {
	kommune: string;
	einwohner: number;
	plan_jahr: number;
	gesamteinnahmen_eur: number | null;
	gesamtausgaben_eur: number | null;
	jahresergebnis_eur: number | null;
	jahresergebnis_ordentlich_eur?: number | null;
	jahresergebnis_pro_kopf_eur: number | null;
	url: string;
	quelle: string | null;
	anmerkung: string | null;
}

export interface SteuermixRow {
	kommune: string;
	jahr: number;
	einwohner: number;
	einkommensteuer: number;
	gewerbesteuer: number;
	grundsteuer: number;
	sonstige: number;
	einkommensteuer_pro_kopf: number;
	gewerbesteuer_pro_kopf: number;
	grundsteuer_pro_kopf: number;
	sonstige_pro_kopf: number;
	summe: number;
	summe_pro_kopf: number;
	quelle: string;
	anmerkung?: string;
}
interface SteuermixFile {
	meta: { fehlend: { kommune: string; grund: string }[] };
	kommunen: SteuermixRow[];
}

const SVG_ID: Record<string, string> = {
	'Dietzenbach':      'dietzenbach',
	'Dreieich':         'dreieich',
	'Egelsbach':        'egelsbach',
	'Hainburg':         'hainburg',
	'Heusenstamm':      'heusenstamm',
	'Langen':           'langen',
	'Mainhausen':       'mainhausen',
	'Mühlheim am Main': 'm__hlheim',
	'Neu-Isenburg':     'neu-isenburg',
	'Obertshausen':     'obertshausen',
	'Rodgau':           'rodgau',
	'Rödermark':        'r__dermark',
	'Seligenstadt':     'seligenstadt',
};

export const load: PageLoad = async ({ fetch }) => {
	const [kommunen, steuermixRaw, grstRaw] = await Promise.all([
		fetch('/data/kreisvergleich_2026.json').then((r) => r.json()) as Promise<KommuneData[]>,
		fetch('/data/steuermix_2026.json').then((r) => r.json()) as Promise<SteuermixFile>,
		fetch('/data/grundsteuer_kreisvergleich.json').then((r) => r.json()) as Promise<{
			kommunen: { kommune: string; hebesatz_2026: { hebesatz: number } | null }[];
		}>,
	]);

	// Steuer-Mix (Plan 2026), absteigend nach Steuerkraft je Einwohner.
	const steuermix = steuermixRaw.kommunen
		.slice()
		.sort((a, b) => b.summe_pro_kopf - a.summe_pro_kopf);
	const maxSteuermixProKopf = Math.max(...steuermix.map((r) => r.summe_pro_kopf));
	const steuermixFehlend = steuermixRaw.meta.fehlend;

	// Grundsteuer-B-Hebesatz je Kommune (fürs Popover-Label).
	const grstHebesatz: Record<string, number> = {};
	for (const k of grstRaw.kommunen) {
		if (k.hebesatz_2026) grstHebesatz[k.kommune] = k.hebesatz_2026.hebesatz;
	}

	// Color municipality polygons by inserting a fill attribute.
	// The elements inherit fill="#ccc" from parent <g>, so adding fill= directly overrides it.
	let mapSvg = svgRaw;
	for (const k of kommunen) {
		const id = SVG_ID[k.kommune];
		if (!id) continue;
		const fill =
			k.jahresergebnis_eur == null ? '#cccccc' :
			k.jahresergebnis_eur < 0     ? '#fca5a5' :
			                               '#86efac';
		mapSvg = mapSvg.replace(`id="${id}"`, `id="${id}" fill="${fill}"`);
	}

	return { kommunen, mapSvg, steuermix, maxSteuermixProKopf, steuermixFehlend, grstHebesatz };
};
