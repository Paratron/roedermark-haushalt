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
	const kommunen: KommuneData[] = await fetch('/data/kreisvergleich_2026.json').then((r) => r.json());

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

	return { kommunen, mapSvg };
};
