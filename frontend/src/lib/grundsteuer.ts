// Hessisches Flächen-Faktor-Modell: effektive Ansätze je m².
// Boden: 0,04 €/m² × Steuermesszahl 100 %. Wohnfläche: 0,50 €/m² × 70 %.
export const AEQ_BODEN = 0.04;
export const AEQ_WOHN = 0.5 * 0.7; // 0,35 €/m²

/**
 * Deutsche Zahleingabe robust parsen.
 * Unterstützt Tausenderpunkte ("1.234,56"), Komma-Dezimal ("75,76"),
 * Einheitensuffixe ("140 m²") und einfache Ganzzahlen ("750").
 * Gibt null zurück für leere, nicht-numerische oder nicht-positive Eingaben.
 */
export function parseGermanNumber(s: string): number | null {
	const c = s
		.replace(/[^0-9.,]/g, '')
		.replace(/\.(?=\d{3}(\D|$))/g, '')
		.replace(',', '.');
	const n = parseFloat(c);
	return Number.isFinite(n) && n > 0 ? n : null;
}

/**
 * Geschätzter Grundsteuermessbetrag nach dem hessischen Flächen-Faktor-Modell
 * (Lagefaktor pauschal 1,0).
 *
 * Beim Haus wird die Grundstücksfläche einbezogen (wenn bekannt).
 * Bei Wohnungen entfällt der Bodenanteil, weil Grundstücksfläche und
 * Miteigentumsanteil ohne Bescheid nicht bekannt sind – die Schätzung
 * fällt dadurch etwas zu niedrig aus.
 */
export function berechneMessbetragSchaetzung(
	wohnflaeche: number,
	grundflaeche: number | null,
	istHaus: boolean
): number {
	const boden = istHaus && grundflaeche !== null ? grundflaeche * AEQ_BODEN : 0;
	return wohnflaeche * AEQ_WOHN + boden;
}

export type Modus = 'schaetzen' | 'grundsteuer' | 'messbetrag';

export interface GrundsteuerErgebnis {
	/** Bisherige Jahres-Grundsteuer (oder Anteil davon). */
	alt: number;
	/** Neue Jahres-Grundsteuer ab neuem Hebesatz. */
	neu: number;
	/** Mehrbelastung pro Jahr. */
	mehrJahr: number;
	/** Mehrbelastung pro Monat. */
	mehrMonat: number;
	/** true, wenn der Wert auf einer Flächenschätzung beruht. */
	geschaetzt: boolean;
}

/**
 * Berechnet alte und neue Jahres-Grundsteuer sowie die Mehrbelastung.
 *
 * Gibt null zurück, wenn die notwendigen Eingaben für den gewählten Modus fehlen.
 */
export function berechneGrundsteuer(params: {
	modus: Modus;
	hebesatzAktuell: number;
	hebesatzNeu: number;
	/** Modus 'grundsteuer': bisherige Jahres-Grundsteuer in €. */
	grundsteuerBetrag?: number | null;
	/** Modus 'messbetrag': Grundsteuermessbetrag in €. */
	messbetrag?: number | null;
	/** Modus 'schaetzen': bereits berechneter Messbetrag aus berechneMessbetragSchaetzung(). */
	messbetragSchaetzung?: number | null;
}): GrundsteuerErgebnis | null {
	const { modus, hebesatzAktuell, hebesatzNeu } = params;
	let alt: number | null = null;
	let jetzt: number | null = null;

	if (modus === 'grundsteuer') {
		const g = params.grundsteuerBetrag ?? null;
		if (g !== null) {
			alt = g;
			jetzt = g * (hebesatzNeu / hebesatzAktuell);
		}
	} else if (modus === 'messbetrag') {
		const m = params.messbetrag ?? null;
		if (m !== null) {
			alt = (m * hebesatzAktuell) / 100;
			jetzt = (m * hebesatzNeu) / 100;
		}
	} else {
		const s = params.messbetragSchaetzung ?? null;
		if (s !== null) {
			alt = (s * hebesatzAktuell) / 100;
			jetzt = (s * hebesatzNeu) / 100;
		}
	}

	if (alt === null || jetzt === null) return null;
	return {
		alt,
		neu: jetzt,
		mehrJahr: jetzt - alt,
		mehrMonat: (jetzt - alt) / 12,
		geschaetzt: modus === 'schaetzen'
	};
}
