import { loadHebesaetzeGrundsteuerB, loadLineItems } from '$lib/data';
import { berechneMessbetragSchaetzung } from '$lib/grundsteuer';
import type { LineItem } from '$lib/types';
import type { PageLoad } from './$types';

export interface KommuneVergleich {
	kommune: string;
	ist_2024: {
		jahr: number;
		hebesatz: number;
		einnahmen_eur: number;
		einwohner: number;
		einnahmen_pro_kopf_eur: number;
		bemessungsgrundlage_pro_kopf_eur: number;
		gewerbesteuer: { jahr: number; einnahmen_eur: number; pro_kopf_eur: number } | null;
		quelle: string;
		anmerkung: string | null;
	} | null;
	hebesatz_2026: {
		jahr: number;
		hebesatz: number;
		status?: 'beschlossen' | 'geplant' | 'abgelehnt';
		quelle?: string;
		quelle_url?: string;
	} | null;
	plan_2026_grundsteuer_b: {
		betrag_eur: number;
		betrag_eur_angepasst?: number;
		quelle: string;
		document: string;
		page: number;
		hebesatz_basis?: number | null;
		hebesatz_aktuell?: number;
		anmerkung?: string;
	} | null;
}

interface KreisvergleichFile {
	meta: { beschreibung: string; methodik_pro_kopf: string; methodik_plan_2026: string };
	kommunen: KommuneVergleich[];
}

/** Steuerquellen-Mix einer Kommune (Plan 2026) für das Stapel-Chart. */
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
	meta: { beschreibung: string; fehlend: { kommune: string; grund: string }[]; hinweis: string };
	kommunen: SteuermixRow[];
}

/** Minimaler Ausschnitt aus hsk_2026.json, den diese Seite braucht. */
interface HskFile {
	narrative: Record<string, { value: number | string; text: string; page: number }>;
	abbaupfad: { year: number; ergebnis_nach_hsk: number }[];
	massnahmen: { is_grundsteuer_b?: boolean; werte: Record<string, number> }[];
}

// Hebesätze für die Ableitung der zweiten HSK-Stufe (gleiche Methode wie auf
// /hsk2026): Die Grundsteuer ist linear im Hebesatz, also liefert Schritt 1
// (990 → 1.327 % = bekannte Mehreinnahme) den €-Wert je Hebesatzpunkt.
const GRST_B_VOR_HSK = 990;
const GRST_B_SCHRITT_1 = 1327;

/** Row for the Musterhaus comparison chart. */
export interface MusterhausRow {
	kommune: string;
	hebesatz: number;
	status?: 'beschlossen' | 'geplant' | 'abgelehnt';
	/** Jahres-Grundsteuer des Musterhauses bei diesem Hebesatz. */
	grundsteuer_eur: number;
}

/** Format a Hebesatz value: German locale. If forceDecimals is true, always show 2 decimal places. */
function fmtHS(v: number, forceDecimals = false): string {
	if (forceDecimals || !Number.isInteger(v)) {
		return v.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
	}
	return v.toLocaleString('de-DE');
}

// Musterhaus: durchschnittliches Einfamilienhaus in mittlerer Lage.
// Lagefaktor ≈ 1,0, weil er das Grundstück relativ zum GEMEINDE-Durchschnitt
// bewertet – ein durchschnittlich gelegenes Haus hat in jeder Kommune ~1,0.
// Dadurch ist der Vergleich über Kommunen hinweg innerhalb Hessens sauber.
// (Kein Modul-Export: SvelteKit erlaubt in +page.ts nur bestimmte Exporte,
// daher wird das Objekt über load() ans Frontend gereicht.)
const MUSTERHAUS = { grundflaeche: 500, wohnflaeche: 140 };

/** Keep only the row from the most recent document per (bezeichnung, year). */
function dedupLatest(items: LineItem[]): LineItem[] {
	const map = new Map<string, LineItem>();
	for (const item of items) {
		const key = `${item.bezeichnung}_${item.year}`;
		const existing = map.get(key);
		if (!existing || item.document_id > existing.document_id) {
			map.set(key, item);
		}
	}
	return [...map.values()];
}

export const load: PageLoad = async ({ fetch }) => {
	const [hebesaetze, kreisvergleichRaw, steuermixRaw, hskRaw, allItems] = await Promise.all([
		loadHebesaetzeGrundsteuerB(),
		fetch('/data/grundsteuer_kreisvergleich.json').then((r) => r.json()) as Promise<KreisvergleichFile>,
		fetch('/data/steuermix_2026.json').then((r) => r.json()) as Promise<SteuermixFile>,
		fetch('/data/hsk_2026.json').then((r) => r.json()) as Promise<HskFile>,
		loadLineItems(fetch)
	]);

	// Rödermark Hebesatz-Historie (für den Entwicklungs-Chart)
	const roedermarkHistory = (hebesaetze?.data ?? [])
		.filter((d) => d.kommune === 'Rödermark')
		.sort((a, b) => a.year - b.year);

	const hasDecimals = (hebesaetze?.data ?? []).some((d) => !Number.isInteger(d.hebesatz));

	const kommunen = kreisvergleichRaw.kommunen
		.slice()
		.sort((a, b) => a.kommune.localeCompare(b.kommune, 'de'));

	const mitHebesatz2026 = kommunen.filter((k) => k.hebesatz_2026 !== null);

	// Musterhaus-Vergleich: gleiche Formel (hessenweit einheitlich), nur der
	// Hebesatz unterscheidet sich → Jahres-Grundsteuer je Kommune.
	const messbetrag = berechneMessbetragSchaetzung(
		MUSTERHAUS.wohnflaeche,
		MUSTERHAUS.grundflaeche,
		true
	);
	const musterhaus: MusterhausRow[] = mitHebesatz2026
		.map((k) => ({
			kommune: k.kommune,
			hebesatz: k.hebesatz_2026!.hebesatz,
			status: k.hebesatz_2026!.status,
			grundsteuer_eur: (messbetrag * k.hebesatz_2026!.hebesatz) / 100
		}))
		.sort((a, b) => b.grundsteuer_eur - a.grundsteuer_eur);
	const maxMusterhaus = Math.max(...musterhaus.map((m) => m.grundsteuer_eur));

	// Durchschnitts-Hebesätze für die "Hochsteuer-Kreis"-Einordnung
	// (ungewichtete Mittel, wie sie auch in der öffentlichen Debatte kursieren).
	const avgHebesatz2026 =
		mitHebesatz2026.reduce((s, k) => s + k.hebesatz_2026!.hebesatz, 0) / mitHebesatz2026.length;
	const mitIst = kommunen.filter((k) => k.ist_2024 !== null);
	const avgHebesatzVorReform =
		mitIst.reduce((s, k) => s + k.ist_2024!.hebesatz, 0) / mitIst.length;

	// Steuerquellen-Mix (Plan 2026), hier nur für den Gewerbesteuer-Faktor in
	// #was-tun genutzt; das Stapel-Chart dazu lebt auf /kreisvergleich.
	const steuermix = steuermixRaw.kommunen
		.slice()
		.sort((a, b) => b.summe_pro_kopf - a.summe_pro_kopf);

	// "Wohin fließt das Geld": Rödermarks Kreis- und Schulumlage sowie die
	// geplante Grundsteuer B aus den eigenen Haushaltsdaten (Beträge negativ
	// gebucht → abs). Jüngstes Planjahr mit beiden Umlagen.
	const umlageItems = dedupLatest(
		allItems.filter(
			(i) =>
				(i.bezeichnung === 'Kreisumlage' || i.bezeichnung === 'Schulumlage') &&
				i.amount_type === 'plan'
		)
	);
	const grundsteuerBItems = dedupLatest(
		allItems.filter((i) => i.bezeichnung === 'Grundsteuer B' && i.amount_type === 'plan')
	);
	const umlageYears = [...new Set(umlageItems.map((i) => i.year))].sort((a, b) => a - b);
	const umlagenJahr = umlageYears[umlageYears.length - 1];
	const kreisumlage = Math.abs(
		umlageItems.find((i) => i.year === umlagenJahr && i.bezeichnung === 'Kreisumlage')?.amount ?? 0
	);
	const schulumlage = Math.abs(
		umlageItems.find((i) => i.year === umlagenJahr && i.bezeichnung === 'Schulumlage')?.amount ?? 0
	);
	const grundsteuerBPlan = Math.abs(
		grundsteuerBItems.find((i) => i.year === umlagenJahr)?.amount ?? 0
	);
	// Für die "Gab es 2025 nicht schon eine Erhöhung"-Antwort: Ist-Einnahme 2024
	// (alter Satz 715 %) als Vergleichsbasis zum 2026er-Ansatz beim 990er-Satz.
	const roedermarkIst2024GrundsteuerB =
		kreisvergleichRaw.kommunen.find((k) => k.kommune === 'Rödermark')?.ist_2024?.einnahmen_eur ?? 0;

	// Rödermarks größte Steuerquellen im Planjahr (Nr. 50, Detailtabellen) – die
	// Einkommensteuer-Anteile übertreffen Gewerbe- und Grundsteuer deutlich.
	const steuerDetail = dedupLatest(
		allItems.filter(
			(i) =>
				i.nr === '50' &&
				i.table_id.startsWith('struktur_') &&
				i.amount_type === 'plan' &&
				i.year === umlagenJahr
		)
	);
	const einkommensteuerPlan = Math.abs(
		steuerDetail.find((i) => i.bezeichnung.includes('Einkommensteuer'))?.amount ?? 0
	);
	const gewerbesteuerPlan = Math.abs(
		steuerDetail.find((i) => i.bezeichnung.includes('Gewerbesteuer'))?.amount ?? 0
	);
	// Gesamte Steuererträge (Nr.-50-Übersichtszeile des Ergebnishaushalts) –
	// Bezugsgröße für "wie viel davon geht als Umlage an den Kreis".
	const steuernGesamtPlan = Math.abs(
		allItems.find(
			(i) =>
				i.nr === '50' &&
				i.amount_type === 'plan' &&
				i.year === umlagenJahr &&
				i.haushalt_type === 'ergebnishaushalt' &&
				!i.table_id.startsWith('struktur_') &&
				i.document_id === 'haushaltsplan_2026_entwurf'
		)?.amount ?? 0
	);
	const umlagenErstesJahr = umlageYears[0];
	const umlagenErstesJahrSumme =
		Math.abs(umlageItems.find((i) => i.year === umlagenErstesJahr && i.bezeichnung === 'Kreisumlage')?.amount ?? 0) +
		Math.abs(umlageItems.find((i) => i.year === umlagenErstesJahr && i.bezeichnung === 'Schulumlage')?.amount ?? 0);

	// HSK-Abbaupfad (Restdefizite nach allen Maßnahmen) und die im Konzept
	// eingeplante zweite Grundsteuer-Stufe: Die Grundsteuer-B-Maßnahme springt
	// ab einem Jahr auf eine deutlich höhere Mehreinnahme; den zugehörigen
	// Hebesatz leiten wir linear ab (Näherung, wie auf /hsk2026 erklärt).
	const grstBMassnahme = hskRaw.massnahmen.find((m) => m.is_grundsteuer_b);
	const stufe1Mehr = Math.abs(grstBMassnahme?.werte['2026'] ?? 0);
	let stufe2Jahr: number | null = null;
	let stufe2Mehr = 0;
	for (const [jahr, wert] of Object.entries(grstBMassnahme?.werte ?? {}).sort()) {
		const v = Math.abs(wert);
		if (stufe1Mehr > 0 && v > stufe1Mehr * 1.05) {
			stufe2Jahr = Number(jahr);
			stufe2Mehr = v;
			break;
		}
	}
	const stufe2Hebesatz =
		stufe2Jahr !== null
			? Math.round(
					GRST_B_VOR_HSK + stufe2Mehr / (stufe1Mehr / (GRST_B_SCHRITT_1 - GRST_B_VOR_HSK))
				)
			: null;
	const hsk = {
		abbaupfad: hskRaw.abbaupfad.map((r) => ({ jahr: r.year, rest: r.ergebnis_nach_hsk })),
		ausgleichJahr: Number(hskRaw.narrative?.ausgleich_ab_jahr?.value ?? 0) || null,
		stufe1Mehr,
		stufe2Jahr,
		stufe2Mehr,
		stufe2Hebesatz
	};

	return {
		hsk,
		roedermarkHistory,
		hasDecimals,
		fmtHS,
		kommunen,
		musterhausSpec: MUSTERHAUS,
		musterhaus,
		maxMusterhaus,
		musterhausMessbetrag: messbetrag,
		steuermix,
		avgHebesatz2026,
		avgHebesatzVorReform,
		umlagen: {
			jahr: umlagenJahr,
			kreisumlage,
			schulumlage,
			summe: kreisumlage + schulumlage,
			grundsteuerBPlan,
			erstesJahr: umlagenErstesJahr,
			erstesJahrSumme: umlagenErstesJahrSumme
		},
		roedermarkIst2024GrundsteuerB,
		steuerquellen: {
			jahr: umlagenJahr,
			einkommensteuer: einkommensteuerPlan,
			gewerbesteuer: gewerbesteuerPlan,
			gesamt: steuernGesamtPlan
		}
	};
};
