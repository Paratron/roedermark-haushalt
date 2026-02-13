<script lang="ts">
	import type { PageData } from './$types';
	import { formatMio, formatAmount, formatChange, amountTypeLabel } from '$lib/format';
	import { sourceLinksFromItems, sourceLinksPerYear } from '$lib/data';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import HaushaltTable from '$lib/components/HaushaltTable.svelte';
	import { ClipboardList, Info, ChevronsDown } from '@lucide/svelte';
	import { browser } from '$app/environment';

	let { data }: { data: PageData } = $props();

	// Read initial selection from URL, fallback to '300'
	function initNr(): string {
		if (!browser) return '300';
		const nr = new URLSearchParams(window.location.search).get('nr');
		return nr && data.positions.some((p) => p.nr === nr) ? nr : '300';
	}

	let selectedNr = $state(initNr());

	// Sync selection to URL
	$effect(() => {
		if (!browser) return;
		const url = new URL(window.location.href);
		if (selectedNr === '300') {
			url.searchParams.delete('nr');
		} else {
			url.searchParams.set('nr', selectedNr);
		}
		history.replaceState(history.state, '', url);
	});

	let selectedItems = $derived(
		data.items.filter((i) => i.nr === selectedNr).sort((a, b) => a.year - b.year)
	);

	let chartSeries = $derived(
		selectedItems.map((i) => ({
			year: i.year,
			amount_type: i.amount_type,
			amount: i.amount,
			label: i.bezeichnung,
			document_id: i.document_id
		}))
	);

	let selectedLabel = $derived(
		data.positions.find((p) => p.nr === selectedNr)?.bezeichnung ?? ''
	);

	/** Human-readable explanations for Ergebnishaushalt positions */
	const positionInfo: Record<string, string> = {
		'10': 'Einnahmen aus privatrechtlichen Verträgen, z.\u00a0B. Mieten, Pachten, Eintrittsgelder für städtische Einrichtungen.',
		'20': 'Gebühren für öffentliche Leistungen wie Kindergartenbeiträge, Wasser-/Abwassergebühren oder Friedhofsgebühren.',
		'30': 'Erstattungen und Rückzahlungen, die die Stadt von anderen Stellen oder Privatpersonen erhält.',
		'50': 'Der größte Einnahmeposten: Gewerbesteuer, Grundsteuer A+B, Gemeindeanteil an der Einkommensteuer und Umsatzsteuer.',
		'60': 'Zuweisungen vom Land oder Bund für Sozialleistungen wie Unterkunftskosten (SGB II) oder Eingliederungshilfe.',
		'70': 'Allgemeine Zuweisungen und Zuschüsse, v.\u00a0a. Schlüsselzuweisungen aus dem Kommunalen Finanzausgleich (KFA).',
		'80': 'Buchhalterischer Ertrag: Anteilige Auflösung von Sonderposten aus früheren Investitionszuschüssen (Abschreibungs-Gegenstück).',
		'90': 'Diverse kleinere Erträge wie Bußgelder, Säumniszuschläge, Konzessionsabgaben, Spenden.',
		'100': 'Summe aller Ertragsarten (Nr.\u00a010–90). Zeigt die gesamten ordentlichen Einnahmen der Stadt.',
		'110': 'Gehälter, Löhne, Sozialversicherungsbeiträge und Beihilfen für alle städtischen Beschäftigten.',
		'120': 'Rückstellungen für Pensionen und Versorgungsansprüche ehemaliger Beamter der Stadt.',
		'125': 'Summe aus Personalaufwendungen und Versorgungsaufwendungen (Nr.\u00a0110 + 120).',
		'130': 'Material, Energie, Instandhaltung, Reinigung, IT-Kosten, externe Dienstleister – der laufende Betrieb.',
		'140': 'Planmäßiger Wertverlust des städtischen Vermögens (Gebäude, Straßen, Fahrzeuge, Ausstattung).',
		'150': 'Transfers an Vereine, Verbände, andere Kommunen – z.\u00a0B. Zuschüsse für Jugendhilfe oder Kulturförderung.',
		'160': 'Pflicht-Umlagen: Kreisumlage, Schulumlage, Gewerbesteuerumlage – die größten Ausgabeblöcke neben Personal.',
		'180': 'Versicherungen, Mitgliedsbeiträge, Wertberichtigungen und sonstige kleinere Aufwendungen.',
		'185': 'Summe aller Sachaufwendungen (Nr.\u00a0130–180).',
		'190': 'Summe aller Aufwandsarten (Nr.\u00a0110–180). Zeigt die gesamten ordentlichen Ausgaben der Stadt.',
		'200': 'Differenz zwischen ordentlichen Erträgen und Aufwendungen – das operative Ergebnis der Verwaltung.',
		'210': 'Zinserträge, Beteiligungserträge, Erträge aus Finanzanlagen.',
		'220': 'Zinsaufwendungen für Kredite, Verluste aus Finanzanlagen.',
		'230': 'Differenz aus Finanzerträgen und Finanzaufwendungen (Nr.\u00a0210 − 220).',
		'240': 'Gesamtbetrag der ordentlichen Erträge inkl. Finanzerträge.',
		'250': 'Gesamtbetrag der ordentlichen Aufwendungen inkl. Finanzaufwendungen.',
		'260': 'Gesamtergebnis: Verwaltungsergebnis plus Finanzergebnis. Positiv = Überschuss, negativ = Defizit.',
		'280': 'Ergebnis vor Verrechnung interner Leistungen zwischen den Fachbereichen.',
		'290': 'Verrechnungen für interne Dienstleistungen zwischen städtischen Abteilungen (z.\u00a0B. Bauhof für Grünflächen).',
		'300': 'Das Endergebnis des Haushaltsjahres. Positiv = die Stadt hat mehr eingenommen als ausgegeben.',
		'320': 'Entspricht dem Jahresergebnis – Gesamtbilanz des Haushaltsjahres.',
	};

	let selectedInfo = $derived(positionInfo[selectedNr] ?? '');

	let selectedSourceLinks = $derived(
		sourceLinksFromItems(
			data.items.filter((i) => i.nr === selectedNr),
			data.documents
		)
	);

	// Build pivot table: rows = positions, cols = years
	const years = data.summary.years;
	const planOnlySet = new Set(data.summary.plan_only_years);

	interface PivotRow {
		nr: string;
		bezeichnung: string;
		values: Map<string, number | null>; // key: `${year}_${amount_type}`
	}

	let pivotData = $derived.by(() => {
		const rows: PivotRow[] = [];
		for (const pos of data.positions) {
			const values = new Map<string, number | null>();
			for (const item of data.items) {
				if (item.nr === pos.nr) {
					values.set(`${item.year}_${item.amount_type}`, item.amount);
				}
			}
			rows.push({ nr: pos.nr, bezeichnung: pos.bezeichnung, values });
		}
		return rows;
	});

	let yearSourceLinks = $derived(sourceLinksPerYear(data.items, data.documents, 'ergebnishaushalt'));

	// Sticky scroll-hint button for the data table
	let tableEl: HTMLElement | undefined = $state();
	let tableVisible = $state(false);
	let hintDismissed = $state(true); // start dismissed, activate on dropdown change

	$effect(() => {
		if (!browser || !tableEl) {
			tableVisible = false;
			return;
		}
		const observer = new IntersectionObserver(
			([entry]) => {
				tableVisible = entry.isIntersecting;
				if (entry.isIntersecting) hintDismissed = true;
			},
			{ threshold: 0.05 }
		);
		observer.observe(tableEl);
		return () => observer.disconnect();
	});

	let showScrollHint = $derived(!tableVisible && !hintDismissed);

	function scrollToTable() {
		tableEl?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}
</script>

<h2 class="page-title"><ClipboardList class="page-icon" /> Ergebnishaushalt</h2>
<p class="page-intro">
	Der Ergebnishaushalt zeigt die ordentlichen Erträge (Steuern, Zuweisungen, Gebühren) und
	Aufwendungen (Personal, Sach-, Transferaufwendungen) der Stadt Rödermark.
</p>

<!-- Position Selector + Chart -->
<section class="section">
	<div class="selector-row">
		<div class="selector-field">
			<label for="position-select" class="field-label">Position auswählen</label>
			<select id="position-select" bind:value={selectedNr} class="form-select"
				onchange={() => { hintDismissed = false; }}>
				{#each data.positions as pos}
					<option value={pos.nr}>Nr. {pos.nr} – {pos.bezeichnung}</option>
				{/each}
			</select>
		</div>
	</div>

	<div class="card card-padded">
		<TimeSeriesChart
			title="Nr. {selectedNr} – {selectedLabel}"
			series={chartSeries}
			yLabel="Mio. €"
			planOnlyYears={data.summary.plan_only_years}
			lastIstYear={data.summary.last_ist_year}
			valueColoring={true}
		/>
	</div>

	<SourceCitation
		description="Ergebnishaushalt, Nr. {selectedNr}"
		links={selectedSourceLinks}
	/>

	{#if selectedInfo}
		<div class="info-box info-box-amber">
			<Info class="info-icon" />
			<div>
				<strong>{selectedLabel}</strong><br />
                {selectedInfo}
			</div>
		</div>
	{/if}
</section>

<!-- Data Table -->
<section bind:this={tableEl}>
	<h3 class="table-title">Alle Positionen im Überblick</h3>
	<HaushaltTable
		rows={pivotData}
		{years}
		planOnlyYears={data.summary.plan_only_years}
		sumNrs={['100', '200', '260', '300']}
		{yearSourceLinks}
		sourceLabel="Ergebnishaushalt"
		onRowClick={(nr) => { selectedNr = nr; hintDismissed = true; window.scrollTo({ top: 0, behavior: 'smooth' }); }}
	/>
</section>

<!-- Sticky scroll hint -->
{#if showScrollHint}
	<button class="scroll-hint-btn" onclick={scrollToTable}>
		<ChevronsDown size={18} />
		Tabelle anzeigen
	</button>
{/if}

<style>
	.page-title {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1.5rem;
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--gray-900);
	}
	:global(.page-icon) {
		width: 1.75rem;
		height: 1.75rem;
	}
	.page-intro {
		margin-bottom: 2rem;
		max-width: 48rem;
		color: var(--gray-600);
	}
	.section { margin-bottom: 2.5rem; }
	.selector-row {
		margin-bottom: 1rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
	@media (min-width: 640px) {
		.selector-row { flex-direction: row; align-items: flex-end; }
	}
	.selector-field { flex: 1; }
	.field-label {
		display: block;
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--gray-700);
	}
	.info-box :global(.info-icon) {
		margin-top: 0.125rem;
		width: 1.25rem;
		height: 1.25rem;
		flex-shrink: 0;
	}
	.table-title {
		margin-bottom: 1rem;
		font-size: 1.125rem;
		font-weight: 600;
		color: var(--gray-800);
	}

	/* Sticky scroll-to-table hint */
	.scroll-hint-btn {
		position: fixed;
		bottom: 1rem;
		left: 1rem;
		right: 1rem;
		z-index: 40;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.875rem 1.5rem;
		background: var(--brand-700);
		color: white;
		font-size: 0.9375rem;
		font-weight: 600;
		border: none;
		border-radius: 0.75rem;
		box-shadow: 0 4px 12px rgba(0,0,0,0.2);
		cursor: pointer;
		white-space: nowrap;
		-webkit-tap-highlight-color: transparent;
		animation: hint-enter 0.3s ease-out;
	}
	.scroll-hint-btn:active {
		background: var(--brand-800);
		transform: scale(0.98);
	}
	@keyframes hint-enter {
		from { opacity: 0; transform: translateY(1rem); }
		to   { opacity: 1; transform: translateY(0); }
	}
	@media (min-width: 768px) {
		.scroll-hint-btn { display: none; }
	}

</style>
