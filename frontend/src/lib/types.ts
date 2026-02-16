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
	unit: string;
	haushalt_type: HaushaltType;
	nr: string;
	bezeichnung: string;
	document_id: string;
	table_id: string;
	page: number | null;
	row_idx: number;
	confidence: number;
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
}

/** Full Hebesatz dataset loaded from JSON */
export interface HebesatzData {
	meta: {
		description: string;
		unit: string;
		note: string;
	};
	data: HebesatzEntry[];
}
