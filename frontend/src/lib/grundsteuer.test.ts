import { describe, it, expect } from 'vitest';
import {
	parseGermanNumber,
	berechneMessbetragSchaetzung,
	berechneGrundsteuer,
	AEQ_BODEN,
	AEQ_WOHN
} from './grundsteuer';

describe('parseGermanNumber', () => {
	it('parst eine einfache Ganzzahl', () => {
		expect(parseGermanNumber('750')).toBe(750);
	});

	it('parst einen Dezimalwert mit Komma', () => {
		expect(parseGermanNumber('75,76')).toBe(75.76);
	});

	it('parst einen Wert mit Tausenderpunkt', () => {
		expect(parseGermanNumber('1.234')).toBe(1234);
	});

	it('parst einen Wert mit Tausenderpunkt und Komma-Dezimal', () => {
		expect(parseGermanNumber('1.234,56')).toBe(1234.56);
	});

	it('ignoriert Einheitensuffixe wie m²', () => {
		expect(parseGermanNumber('140 m²')).toBe(140);
	});

	it('gibt null für leere Eingabe zurück', () => {
		expect(parseGermanNumber('')).toBeNull();
	});

	it('gibt null für reine Buchstaben zurück', () => {
		expect(parseGermanNumber('abc')).toBeNull();
	});

	it('gibt null für null zurück', () => {
		expect(parseGermanNumber('0')).toBeNull();
	});

	it('ignoriert ein Minuszeichen und parst den Zahlenwert', () => {
		// Minus wird wie ein ungültiges Zeichen behandelt und gestripped – sinnvoll für Formulareingaben
		expect(parseGermanNumber('-5')).toBe(5);
	});

	it('parst Dezimalwert ohne führende Null', () => {
		expect(parseGermanNumber(',5')).toBe(0.5);
	});
});

describe('berechneMessbetragSchaetzung', () => {
	it('berechnet Messbetrag für Wohnung (nur Wohnfläche)', () => {
		// 80 m² × 0,35 = 28 €
		expect(berechneMessbetragSchaetzung(80, null, false)).toBeCloseTo(28, 5);
	});

	it('berechnet Messbetrag für Haus mit Grundstück', () => {
		// 120 m² × 0,35 + 400 m² × 0,04 = 42 + 16 = 58 €
		expect(berechneMessbetragSchaetzung(120, 400, true)).toBeCloseTo(58, 5);
	});

	it('ignoriert Grundstücksfläche wenn Wohnung (istHaus = false)', () => {
		expect(berechneMessbetragSchaetzung(80, 500, false)).toBeCloseTo(28, 5);
	});

	it('berechnet Haus ohne Grundstücksfläche (null)', () => {
		// nur Wohnfläche, kein Boden
		expect(berechneMessbetragSchaetzung(100, null, true)).toBeCloseTo(35, 5);
	});

	it('AEQ_WOHN ist 0,35 (0,50 × 0,70)', () => {
		expect(AEQ_WOHN).toBeCloseTo(0.35, 10);
	});

	it('AEQ_BODEN ist 0,04', () => {
		expect(AEQ_BODEN).toBe(0.04);
	});
});

describe('berechneGrundsteuer – Modus grundsteuer', () => {
	const basis = { modus: 'grundsteuer' as const, hebesatzAktuell: 990, hebesatzNeu: 1327 };

	it('skaliert die bisherige Grundsteuer korrekt', () => {
		const r = berechneGrundsteuer({ ...basis, grundsteuerBetrag: 600 });
		expect(r).not.toBeNull();
		expect(r!.alt).toBe(600);
		expect(r!.neu).toBeCloseTo(600 * (1327 / 990), 5);
	});

	it('berechnet Mehrbelastung pro Jahr und Monat', () => {
		const r = berechneGrundsteuer({ ...basis, grundsteuerBetrag: 600 });
		expect(r!.mehrJahr).toBeCloseTo(r!.neu - r!.alt, 5);
		expect(r!.mehrMonat).toBeCloseTo(r!.mehrJahr / 12, 5);
	});

	it('geschaetzt ist false', () => {
		const r = berechneGrundsteuer({ ...basis, grundsteuerBetrag: 600 });
		expect(r!.geschaetzt).toBe(false);
	});

	it('gibt null zurück wenn kein Betrag übergeben', () => {
		expect(berechneGrundsteuer({ ...basis })).toBeNull();
	});

	it('gibt null zurück bei grundsteuerBetrag = null', () => {
		expect(berechneGrundsteuer({ ...basis, grundsteuerBetrag: null })).toBeNull();
	});
});

describe('berechneGrundsteuer – Modus messbetrag', () => {
	const basis = { modus: 'messbetrag' as const, hebesatzAktuell: 990, hebesatzNeu: 1327 };

	it('berechnet Grundsteuer aus Messbetrag × Hebesatz', () => {
		// alt: 75,76 × 990/100 = 750,024 €; neu: 75,76 × 1327/100 = 1005,333 €
		const r = berechneGrundsteuer({ ...basis, messbetrag: 75.76 });
		expect(r!.alt).toBeCloseTo(75.76 * 990 / 100, 2);
		expect(r!.neu).toBeCloseTo(75.76 * 1327 / 100, 2);
	});

	it('geschaetzt ist false', () => {
		const r = berechneGrundsteuer({ ...basis, messbetrag: 50 });
		expect(r!.geschaetzt).toBe(false);
	});

	it('gibt null zurück wenn kein Messbetrag', () => {
		expect(berechneGrundsteuer({ ...basis })).toBeNull();
	});
});

describe('berechneGrundsteuer – Modus schaetzen', () => {
	const basis = { modus: 'schaetzen' as const, hebesatzAktuell: 990, hebesatzNeu: 1327 };

	it('berechnet Grundsteuer aus vorberechnetem Messbetrag', () => {
		// Messbetrag für ETW 80 m²: 28 €; alt: 28 × 990/100 = 277,20 €
		const schaetzung = berechneMessbetragSchaetzung(80, null, false);
		const r = berechneGrundsteuer({ ...basis, messbetragSchaetzung: schaetzung });
		expect(r!.alt).toBeCloseTo(277.2, 2);
		expect(r!.neu).toBeCloseTo(28 * 1327 / 100, 2);
	});

	it('geschaetzt ist true', () => {
		const r = berechneGrundsteuer({ ...basis, messbetragSchaetzung: 28 });
		expect(r!.geschaetzt).toBe(true);
	});

	it('gibt null zurück wenn keine Schätzung', () => {
		expect(berechneGrundsteuer({ ...basis })).toBeNull();
	});

	it('kombiniert Wohnfläche + Grundstück für Haus korrekt', () => {
		// 120 m² Wohn + 400 m² Grund → Messbetrag 58 €; alt: 58 × 990/100 = 574,20 €
		const schaetzung = berechneMessbetragSchaetzung(120, 400, true);
		const r = berechneGrundsteuer({ ...basis, messbetragSchaetzung: schaetzung });
		expect(r!.alt).toBeCloseTo(574.2, 2);
	});
});
