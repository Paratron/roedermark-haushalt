/** Core data types matching the published data model. */

export type HaushaltType =
	| 'ergebnishaushalt'
	| 'finanzhaushalt'
	| 'teilergebnishaushalt'
	| 'teilfinanzhaushalt'
	| 'investitionen'
	| 'produktuebersicht';

export interface LineItem {
	line_item_key: string;
	year: number;
	amount: number;
	amount_type: 'ist' | 'plan';
	haushalt_type: HaushaltType;
	nr: string;
	bezeichnung: string;
	document_id: string;
	/** document_id der Fassung, die diesen Wert ersetzt – null, wenn dies der aktuelle Wert ist */
	superseded_by?: string | null;
	table_id: string;
	page: number | null;
	konto?: string;
	teilhaushalt_nr?: string;
	teilhaushalt_name?: string;
	fachbereich_nr?: string;
	fachbereich_name?: string;
	productgroup_nr?: string;
	productgroup_name?: string;
}

export interface Document {
	document_id: string;
	doc_type: string;
	years: number[];
	priority: number;
	source_url?: string;
	filename?: string;
	missing?: boolean;
	sha256?: string;
	size_bytes?: number;
	fetched_at?: string;
	local_path?: string;
	/** 'vorlage' = noch nicht beschlossen; Zahlen daraus sind vorläufig */
	status?: string;
	/** Erläuterung zum Status, z. B. Datum der Entscheidung */
	status_note?: string;
	/** Link auf die Vorlage im Ratsinformationssystem */
	status_url?: string;
}

export interface TimeSeriesPoint {
	year: number;
	amount_type: string;
	amount: number;
	label: string;
	document_id: string;
	/** PDF page number from pipeline provenance (1-based) */
	page?: number | null;
}

/** A resolved source link for citation display */
export interface SourceLink {
	/** Human-readable label, e.g. "HH 2026 Entwurf, S. 152" */
	label: string;
	/** URL to the PDF with page anchor, e.g. "/pdfs/haushaltsplan_2026_entwurf.pdf#page=152" */
	href: string;
	/** The document_id this link refers to */
	document_id: string;
	/** The page number in the PDF */
	page: number | null;
}

/** Commentary from a Jahresabschluss Rechenschaftsbericht about investment deviations */
export interface InvestmentCommentary {
	document_id: string;
	year: number;
	category: string;
	text: string;
	items: { project: string; amount_eur?: number | null; plan_eur?: number | null; ist_eur?: number | null }[];
	page_start: number;
	page_end: number;
}

/** A classified investment entry from the pipeline */
export interface ClassifiedInvestmentEntry {
	key: string;
	bezeichnung: string;
	th_nr: number;
	th_name: string;
	entry_type: string;
	thema: string;
	ist_total: number;
	plan_total: number;
	years: number[];
}

/** Aggregated theme summary */
export interface ThemaSummary {
	thema: string;
	label: string;
	ausgaben_ist: number;
	ausgaben_plan: number;
	einnahmen_ist: number;
	einnahmen_plan: number;
	count_ausgaben: number;
	count_einnahmen: number;
}

/** The full classification result */
export interface InvestmentClassification {
	meta: {
		total_entries: number;
		type_counts: Record<string, number>;
		thema_counts: Record<string, number>;
		type_labels: Record<string, string>;
		thema_labels: Record<string, string>;
	};
	themen: ThemaSummary[];
	entries: ClassifiedInvestmentEntry[];
}

export interface Summary {
	generated_at: string;
	total_line_items: number;
	overview_line_items: number;
	detail_line_items: number;
	years: number[];
	documents: string[];
	ergebnishaushalt: {
		ordentliche_ertraege: TimeSeriesPoint[];
		ordentliche_aufwendungen: TimeSeriesPoint[];
		ordentliches_ergebnis: TimeSeriesPoint[];
		jahresergebnis: TimeSeriesPoint[];
	};
	finanzhaushalt: {
		einzahlungen_lfd: TimeSeriesPoint[];
		auszahlungen_lfd: TimeSeriesPoint[];
		saldo_lfd: TimeSeriesPoint[];
	};
	coverage: Record<string, number>;
	/** Years with actual 'Ist' (Ergebnis) data from Jahresabschlüsse */
	ist_years: number[];
	/** Years that only have 'Plan' data (Ansatz/Finanzplanung) */
	plan_only_years: number[];
	/** The last year with Ist data – divider position for charts */
	last_ist_year: number | null;
}

/** A single Hebesatz entry for one municipality and year */
export interface HebesatzEntry {
	kommune: string;
	year: number;
	hebesatz: number;
	quelle: string;
	/** Adoption status for forward-looking (e.g. 2026) values */
	status?: 'beschlossen' | 'geplant' | 'abgelehnt';
	/** Optional public source URL backing this entry */
	quelle_url?: string;
}

/** Full Hebesatz dataset loaded from JSON */
export interface HebesatzData {
	meta: {
		description: string;
			note: string;
	};
	data: HebesatzEntry[];
}

// ─── Haushaltssicherungskonzept (HSK) 2026 ───

/** A single year on the consolidation path (Abbaupfad, Anlage 3) */
export interface HskAbbaupfadEntry {
	year: number;
	defizit_aliste: number | null;
	veraenderung_hsk: number | null;
	ergebnis_nach_hsk: number | null;
	liquiditaet: number | null;
	saldo_aliste: number | null;
	saldo_hsk: number | null;
	page: number;
}

/** A single consolidation measure (Anlage 1) */
export interface HskMassnahme {
	fb: string;
	fb_label: string;
	produkt: string | null;
	massnahme: string;
	kategorie: string;
	kategorie_label: string;
	art: 'einnahme' | 'ausgabe';
	gruppe_label: string;
	is_grundsteuer_b: boolean;
	hebesatzpunkte: number | null;
	werte: Record<string, number | null>;
	summe: number | null;
	page: number;
}

/** Aggregated citizen-facing category */
export interface HskKategorie {
	kategorie: string;
	label: string;
	summe: number;
	anzahl: number;
}

/** A group of measures within a pillar (revenue or expense side) */
export interface HskSaeuleGruppe {
	label: string;
	summe: number;
	anzahl: number;
	werte: Record<string, number>;
}

/** One pillar: the revenue side (einnahmen) or the expense side (ausgaben) */
export interface HskSaeule {
	summe: number;
	anzahl: number;
	werte: Record<string, number>;
	gruppen: HskSaeuleGruppe[];
}

/** Both pillars of the consolidation: where the city earns more vs. saves */
export interface HskSaeulen {
	einnahmen: HskSaeule;
	ausgaben: HskSaeule;
}

/** A single investment that was cut/shifted (Änderungsliste, page 10) */
export interface HskInvestition {
	fb: string;
	fb_label: string;
	code: string;
	name: string;
	werte: Record<string, number | null>;
	summe: number;
	page: number;
}

/** A narrative fact with a page reference back into the PDF */
export interface HskNarrativeFact {
	value: number | string;
	text: string;
	page: number;
}

/** The full HSK 2026 dataset loaded from hsk_2026.json */
export interface HskData {
	generated_at: string;
	source_document: string;
	source_file: string;
	laufzeit: [number, number];
	genehmigungsfaehig: boolean;
	narrative: Record<string, HskNarrativeFact>;
	kennzahlen: {
		konsolidierung_mit_grundsteuer_b: number | null;
		konsolidierung_ohne_grundsteuer_b: number | null;
		grundsteuer_b_summe: number | null;
		grundsteuer_b_anteil: number | null;
		eigene_massnahmen_anteil: number | null;
		anzahl_massnahmen: number;
	};
	abbaupfad: HskAbbaupfadEntry[];
	kategorien: HskKategorie[];
	saeulen: HskSaeulen;
	massnahmen: HskMassnahme[];
	totals: {
		verkaeufe?: { bezeichnung: string; values: (number | null)[]; summe: number | null; page: number }[];
		[key: string]: unknown;
	};
	investitionen: HskInvestition[];
}
