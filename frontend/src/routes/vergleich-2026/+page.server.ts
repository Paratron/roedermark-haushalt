import {
	loadVergleich2026,
	loadDocuments,
	shortDocLabel,
	REVENUE_CATEGORIES,
	EXPENSE_CATEGORIES
} from '$lib/data';
import type { BudgetCategory } from '$lib/data';
import type { VergleichPosition, VergleichKonto, SourceLink } from '$lib/types';
import type { PageServerLoad } from './$types';

/** Eine Zeile der Aufschlüsselung: ein Konto oder ein Fachbereich. */
export interface VergleichDetail {
	/** Kontonummer, wenn die Aufschlüsselung über Konten läuft. */
	konto: string | null;
	label: string;
	/** Wert in der Neufassung, als Betrag. */
	amount: number;
	/** Wert im Entwurf, als Betrag. */
	alt: number;
	percent: number;
	diff: number;
	ratio: number | null;
}

/**
 * Eine Kategorie im Donut und in der Tabelle daneben.
 *
 * Aufgebaut wie die CategorySlice der Seite "Einnahmen & Ausgaben", damit der
 * DonutChart sie unverändert nimmt - nur dass die Vergleichsspalte nicht aufs
 * Vorjahr zeigt, sondern auf den Entwurf.
 */
export interface VergleichSlice {
	category: BudgetCategory;
	amount: number;
	percent: number;
	alt: number;
	diff: number;
	ratio: number | null;
	detail: VergleichDetail[];
	detailArt: 'konten' | 'fachbereiche' | null;
}

export interface Seite {
	side: 'einnahmen' | 'ausgaben';
	titel: string;
	slices: VergleichSlice[];
	summe: number;
	summeAlt: number;
}

/** Beträge statt Vorzeichen: im Plan stehen Aufwendungen negativ. */
const betrag = (n: number) => Math.abs(n);

const anteil = (teil: number, ganzes: number) => (ganzes > 0 ? teil / ganzes : 0);
const verhaeltnis = (diff: number, alt: number) => (alt > 0 ? diff / alt : null);

/**
 * Die Aufschlüsselung einer Kategorie - Konten, wenn die Pipeline sie
 * vollständig hergibt, sonst die Fachbereiche.
 *
 * Eine einzige Zeile wiederholt nur die Summe darüber und wird verworfen; das
 * gilt für beide Arten gleichermaßen.
 */
function baueDetail(
	nr: string,
	konten: VergleichKonto[] | undefined,
	teh: VergleichPosition[]
): { detail: VergleichDetail[]; art: 'konten' | 'fachbereiche' | null } {
	if (konten && konten.length >= 2) {
		const ganzes = konten.reduce((s, k) => s + k.neu, 0);
		return {
			art: 'konten',
			detail: konten
				.map((k) => ({
					konto: k.konto,
					label: k.bezeichnung,
					amount: k.neu,
					alt: k.alt,
					percent: anteil(k.neu, ganzes),
					diff: k.diff,
					ratio: verhaeltnis(k.diff, k.alt)
				}))
				.sort((a, b) => b.amount - a.amount)
		};
	}

	const fb = teh
		.filter((p) => String(p.nr) === nr && p.teilhaushalt_name)
		.map((p) => {
			const amount = betrag(p.neu);
			const alt = betrag(p.alt);
			return {
				konto: null,
				label: p.teilhaushalt_name as string,
				amount,
				alt,
				percent: 0,
				diff: amount - alt,
				ratio: verhaeltnis(amount - alt, alt)
			};
		})
		.sort((a, b) => b.amount - a.amount);

	if (fb.length < 2) return { detail: [], art: null };
	const ganzes = fb.reduce((s, f) => s + f.amount, 0);
	return {
		art: 'fachbereiche',
		detail: fb.map((f) => ({ ...f, percent: anteil(f.amount, ganzes) }))
	};
}

export const load: PageServerLoad = async () => {
	const [vergleich, documents] = await Promise.all([loadVergleich2026(), loadDocuments()]);

	const eh = new Map<string, VergleichPosition>();
	for (const p of vergleich.positionen) {
		if (p.haushalt_type === 'ergebnishaushalt' && p.nr) eh.set(String(p.nr), p);
	}
	const teh = vergleich.positionen.filter((p) => p.haushalt_type === 'teilergebnishaushalt');
	const alleKonten = vergleich.konten ?? {};

	function baueSeite(
		cats: BudgetCategory[],
		side: 'einnahmen' | 'ausgaben',
		titel: string
	): Seite {
		const roh = cats
			.map((category) => {
				const top = eh.get(category.nr);
				if (!top) return null;
				const amount = betrag(top.neu);
				const alt = betrag(top.alt);
				const { detail, art } = baueDetail(category.nr, alleKonten[category.nr], teh);
				return {
					category,
					amount,
					alt,
					percent: 0,
					diff: amount - alt,
					ratio: verhaeltnis(amount - alt, alt),
					detail,
					detailArt: art
				};
			})
			.filter((s): s is VergleichSlice => s !== null)
			.sort((a, b) => b.amount - a.amount);

		const summe = roh.reduce((s, x) => s + x.amount, 0);
		return {
			side,
			titel,
			slices: roh.map((s) => ({ ...s, percent: anteil(s.amount, summe) })),
			summe,
			summeAlt: roh.reduce((s, x) => s + x.alt, 0)
		};
	}

	const seiten = [
		baueSeite(REVENUE_CATEGORIES, 'einnahmen', 'Einnahmen'),
		baueSeite(EXPENSE_CATEGORIES, 'ausgaben', 'Ausgaben')
	];

	const zeile = (frag: string) =>
		vergleich.positionen.find(
			(p) => p.haushalt_type === 'ergebnishaushalt' && p.bezeichnung.startsWith(frag)
		) ?? null;

	const doc = (id: string, page: number | null): SourceLink | null => {
		const d = documents.find((x) => x.document_id === id);
		if (!d?.filename) return null;
		return {
			label: page ? `${shortDocLabel(id)}, S. ${page}` : shortDocLabel(id),
			href: page ? `/pdfs/${d.filename}#page=${page}` : `/pdfs/${d.filename}`,
			document_id: id,
			page
		};
	};

	const ergebnis = zeile('Ordentliches Ergebnis');
	const quellen = [
		doc(vergleich.alt_document_id, ergebnis?.seite_alt ?? null),
		doc(vergleich.neu_document_id, ergebnis?.seite_neu ?? null)
	].filter((x): x is SourceLink => x !== null);

	return {
		jahr: vergleich.jahr,
		altLabel: shortDocLabel(vergleich.alt_document_id),
		neuLabel: shortDocLabel(vergleich.neu_document_id),
		seiten,
		ergebnis,
		quellen
	};
};
