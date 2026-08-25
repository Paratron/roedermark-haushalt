import {
	loadPageItems,
	loadSummary,
	loadDocuments,
	loadInvestmentCommentary,
	loadInvestmentClassification,
	investitionItems,
	groupBy,
	sourceLinksFromItems
} from '$lib/data';
import type { Document, InvestmentClassification, LineItem } from '$lib/types';
import type { PageServerLoad } from './$types';

/**
 * Ein klassifizierter Eintrag, auf die Felder eingedampft, die die Seite zeigt.
 *
 * Die Klassifikationsdatei führt Teilhaushaltsname und die vollständige Jahresliste
 * je Eintrag; angezeigt wird davon nur die Spanne von–bis. Bei 765 Einträgen ist das
 * der Unterschied zwischen einem Drittel und einem Zehntel des Seitenpayloads.
 */
export interface ThemaEntry {
	key: string;
	bezeichnung: string;
	entry_type: string;
	thema: string;
	ist_total: number;
	plan_total: number;
	yearFrom: number | null;
	yearTo: number | null;
}

export interface Classification {
	typeLabels: Record<string, string>;
	themaLabels: Record<string, string>;
	entries: ThemaEntry[];
	/** Letztes Jahr, für das überhaupt etwas eingeplant ist */
	lastYear: number;
}

function slimClassification(cl: InvestmentClassification | null): Classification | null {
	if (!cl) return null;
	let lastYear = 0;
	const entries = cl.entries.map((e) => {
		const years = e.years ?? [];
		if (years.length) lastYear = Math.max(lastYear, ...years);
		return {
			key: e.key,
			bezeichnung: e.bezeichnung,
			entry_type: e.entry_type,
			thema: e.thema,
			ist_total: e.ist_total,
			plan_total: e.plan_total,
			yearFrom: years.length ? Math.min(...years) : null,
			yearTo: years.length ? Math.max(...years) : null
		};
	});
	return {
		typeLabels: cl.meta.type_labels,
		themaLabels: cl.meta.thema_labels,
		entries,
		lastYear: lastYear || 0
	};
}

/**
 * Ein Investitionsprojekt über alle Jahre und Haushaltspläne hinweg.
 *
 * Die Seite zeigt nie einzelne Zeilen, sondern immer diese Zusammenfassung – 8.337
 * Positionen fallen auf 771 Projekte zusammen. Projektname, Teilhaushalt und
 * Quellenlink stehen in jeder Zeile erneut; gruppiert stehen sie einmal.
 */
export interface ProjectSummary {
	key: string;
	bezeichnung: string;
	thNr: string;
	thName: string;
	/**
	 * Quellen als [Index in documents, Seite].
	 *
	 * Ausgeschriebene Links – Beschriftung, PDF-Pfad, document_id je Eintrag – waren
	 * bei 2.230 Stellenangaben rund 400 KB der Seite. Beschriftung und Pfad stehen
	 * schon in documents, die Komponente setzt sie beim Rendern zusammen.
	 */
	sources: [number, number | null][];
	totalIst: number;
	totalPlan: number;
	/** Plan der Jahre, für die es schon Ist-Zahlen gibt – nur das ist vergleichbar */
	comparablePlan: number;
	comparableIst: number;
	discrepancy: number;
	discrepancyPct: number;
	/** [Jahr, Ist, Plan] – als Objekte je Zeile kostete das Feld doppelt so viel */
	years: [number, number | null, number | null][];
	hasIst: boolean;
	hasPlan: boolean;
	hasComparableData: boolean;
}

function buildProjects(
	investments: LineItem[],
	documents: Document[],
	istYears: number[]
): ProjectSummary[] {
	const istYearsSet = new Set(istYears);
	const documentIndex = new Map(documents.map((d, i) => [d.document_id, i]));
	const projects: ProjectSummary[] = [];

	for (const [key, items] of groupBy(investments, (i) => i.line_item_key)) {
		const byYear = new Map<number, { year: number; ist: number | null; plan: number | null }>();
		let totalIst = 0;
		let totalPlan = 0;
		let comparablePlan = 0;
		let hasIst = false;
		let hasPlan = false;

		for (const item of items) {
			let yd = byYear.get(item.year);
			if (!yd) {
				yd = { year: item.year, ist: null, plan: null };
				byYear.set(item.year, yd);
			}
			if (item.amount_type === 'ist') {
				yd.ist = item.amount;
				totalIst += item.amount;
				hasIst = true;
			} else {
				yd.plan = item.amount;
				totalPlan += item.amount;
				hasPlan = true;
				if (istYearsSet.has(item.year)) comparablePlan += item.amount;
			}
		}

		const comparableIst = totalIst;
		const hasComparableData = hasIst || (hasPlan && comparablePlan !== 0);
		const discrepancy =
			hasComparableData && comparablePlan !== 0 ? comparableIst - comparablePlan : 0;

		projects.push({
			key,
			bezeichnung: items[0].bezeichnung,
			thNr: items[0].teilhaushalt_nr ?? '',
			thName: items[0].teilhaushalt_name ?? '',
			sources: sourceLinksFromItems(items, documents)
				.map((l): [number, number | null] => [documentIndex.get(l.document_id) ?? -1, l.page])
				.filter(([i]) => i >= 0),
			totalIst,
			totalPlan,
			comparableIst,
			comparablePlan,
			discrepancy,
			discrepancyPct: comparablePlan !== 0 ? (discrepancy / Math.abs(comparablePlan)) * 100 : 0,
			years: [...byYear.values()]
				.sort((a, b) => a.year - b.year)
				.map((y): [number, number | null, number | null] => [y.year, y.ist, y.plan]),
			hasIst,
			hasPlan,
			hasComparableData
		});
	}

	return projects.sort((a, b) => Math.abs(b.discrepancy) - Math.abs(a.discrepancy));
}

/** Die Teilhaushalte, in denen investiert wird – Auswahlliste des Filters */
function buildTeilhaushalte(projects: ProjectSummary[]) {
	const thMap = new Map<string, { nr: string; name: string; count: number }>();
	for (const project of projects) {
		if (!project.thNr || project.thNr === 'nan') continue;
		const existing = thMap.get(project.thNr);
		if (!existing) {
			thMap.set(project.thNr, { nr: project.thNr, name: project.thName, count: 1 });
			continue;
		}
		existing.count++;
		// Ältere Pläne kürzen den Namen ab – der längste ist der aussagekräftigste
		if (project.thName.length > existing.name.length) existing.name = project.thName;
	}
	return [...thMap.values()].sort((a, b) => Number.parseFloat(a.nr) - Number.parseFloat(b.nr));
}

export const load: PageServerLoad = async ({ fetch }) => {
	const [allItems, summary, documents, commentary, classification] = await Promise.all([
		loadPageItems('investitionen'),
		loadSummary(),
		loadDocuments(),
		loadInvestmentCommentary(fetch),
		loadInvestmentClassification(fetch)
	]);

	const projects = buildProjects(investitionItems(allItems), documents, summary.ist_years ?? []);

	return {
		projects,
		summary,
		teilhaushalte: buildTeilhaushalte(projects),
		documents,
		commentary,
		classification: slimClassification(classification)
	};
};
