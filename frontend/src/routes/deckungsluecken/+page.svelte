<script lang="ts">
	import type { PageData } from './$types';
	import {
		bestDataType,
		TASK_CATEGORIES,
		buildDeckungslueckenBreakdown,
		deckungslueckeTimeSeries,
		buildTaskDrilldown,
		drilldownSourceLinks,
		taskSourceLinks,
	} from '$lib/data';
	import { formatAmount, formatMio } from '$lib/format';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';
	import SocialMeta from '$lib/components/SocialMeta.svelte';
	import Popover from '$lib/components/Popover.svelte';
	import { Scale, Info, ChevronDown, ChevronUp, HelpCircle } from '@lucide/svelte';
	import { browser } from '$app/environment';

	let { data }: { data: PageData } = $props();

	const { items, summary, documents } = data;

	// ─── State ───
	const allYears = summary.years;
	const istYears = summary.ist_years;

	function initYear(): number {
		if (!browser) return summary.last_ist_year ?? istYears[istYears.length - 1] ?? allYears[allYears.length - 1];
		const y = new URLSearchParams(window.location.search).get('year');
		if (y) {
			const yn = Number.parseInt(y);
			if (allYears.includes(yn)) return yn;
		}
		return summary.last_ist_year ?? istYears[istYears.length - 1] ?? allYears[allYears.length - 1];
	}

	let selectedYear = $state(initYear());
	let selectedTaskId = $state<string | null>(null);

	// Sync to URL
	$effect(() => {
		if (!browser) return;
		const url = new URL(window.location.href);
		const defaultYear = summary.last_ist_year ?? istYears[istYears.length - 1];
		if (selectedYear !== defaultYear) {
			url.searchParams.set('year', String(selectedYear));
		} else {
			url.searchParams.delete('year');
		}
		if (selectedTaskId) {
			url.searchParams.set('task', selectedTaskId);
		} else {
			url.searchParams.delete('task');
		}
		history.replaceState(history.state, '', url);
	});

	// ─── Derived data ───
	let dataType = $derived(bestDataType(items, selectedYear));
	let dataTypeLabel = $derived(dataType === 'ist' ? 'Ist (Jahresabschluss)' : 'Plan (Haushaltsansatz)');

	let slices = $derived(buildDeckungslueckenBreakdown(items, selectedYear, dataType));

	// Aggregate KPIs
	let totalExpense = $derived(slices.reduce((s, r) => s + r.expense, 0));
	let totalRevenue = $derived(slices.reduce((s, r) => s + r.revenue, 0));
	let totalGap = $derived(totalExpense - totalRevenue);
	let totalCoverage = $derived(totalExpense > 0 ? totalRevenue / totalExpense : 1);

	// Only pflicht tasks
	let pflichtSlices = $derived(slices.filter(s => s.task.pflicht === 'pflicht'));
	let pflichtExpense = $derived(pflichtSlices.reduce((s, r) => s + r.expense, 0));
	let pflichtRevenue = $derived(pflichtSlices.reduce((s, r) => s + r.revenue, 0));
	let pflichtGap = $derived(pflichtExpense - pflichtRevenue);
	let pflichtCoverage = $derived(pflichtExpense > 0 ? pflichtRevenue / pflichtExpense : 1);

	// Previous year for comparison
	let prevYear = $derived(allYears.includes(selectedYear - 1) ? selectedYear - 1 : null);
	let prevDataType = $derived(prevYear ? bestDataType(items, prevYear) : 'plan' as const);
	let prevSlices = $derived(prevYear ? buildDeckungslueckenBreakdown(items, prevYear, prevDataType) : []);
	let prevGapMap = $derived.by(() => {
		const map = new Map<string, number>();
		for (const s of prevSlices) map.set(s.task.id, s.gap);
		return map;
	});

	// Max expense for bar scaling
	let maxExpense = $derived(Math.max(...slices.map(s => s.expense), 1));

	// Selected task for drill-down
	let selectedTask = $derived.by(() => {
		if (!selectedTaskId) return null;
		return slices.find(s => s.task.id === selectedTaskId) ?? null;
	});

	// Time series for selected task
	let selectedTimeSeries = $derived.by(() => {
		if (!selectedTaskId) return { revenue: [], expense: [], gap: [] };
		const ts = deckungslueckeTimeSeries(items, selectedTaskId);
		const task = TASK_CATEGORIES.find(t => t.id === selectedTaskId);
		const label = task?.label ?? '';
		return {
			revenue: ts.map(p => ({ year: p.year, amount: p.revenue, amount_type: p.amount_type, label: `Erträge ${label}`, document_id: p.document_id })),
			expense: ts.map(p => ({ year: p.year, amount: p.expense, amount_type: p.amount_type, label: `Aufwendungen ${label}`, document_id: p.document_id })),
			gap: ts.map(p => ({ year: p.year, amount: p.gap, amount_type: p.amount_type, label: `Deckungslücke ${label}`, document_id: p.document_id })),
		};
	});

	let selectedSourceLinks = $derived(
		selectedTaskId ? taskSourceLinks(items, documents, selectedTaskId) : []
	);

	// Drill-down: product-level detail for selected task
	let drilldown = $derived.by(() => {
		if (!selectedTaskId) return [];
		return buildTaskDrilldown(items, selectedTaskId, selectedYear, dataType);
	});

	let selectedDrilldownSourceLinks = $derived(
		selectedTaskId ? drilldownSourceLinks(items, documents, selectedTaskId, selectedYear) : []
	);

	// Identify tasks that are "naturally tax-funded" (no meaningful own revenue)
	const TAX_FUNDED_TASKS = new Set(['verwaltung']);
	let isTaxFunded = $derived(selectedTaskId ? TAX_FUNDED_TASKS.has(selectedTaskId) : false);

	function handleTaskClick(id: string) {
		selectedTaskId = selectedTaskId === id ? null : id;
	}

	function pctFmt(ratio: number): string {
		return `${(ratio * 100).toFixed(0)} %`;
	}
</script>

<SocialMeta
	title="Deckungslücken der Aufgabenbereiche"
	description="Wie viel der kommunalen Aufwendungen wird durch eigene Erträge gedeckt – und wo muss Rödermark aus Steuern und Schlüsselzuweisungen zuschießen?"
	path="/deckungsluecken"
/>

<AnchorHeading level={2} id="deckungsluecken"><Scale /> Wer zahlt für was?</AnchorHeading>

<p class="page-intro">
	Jeder Aufgabenbereich der Stadt hat eigene Erträge – Gebühren, Zuweisungen vom Land oder Bund, Kostenerstattungen.
	Diese Seite zeigt, wie viel davon die Aufwendungen deckt und wie viel Rödermark aus allgemeinen Mitteln (Steuern, Schlüsselzuweisungen aus dem KFA) zuschießen muss.
</p>

<!-- Year Selector -->
<section class="section">
	<div class="year-selector">
		<label for="year-select" class="field-label">Jahr auswählen</label>
		<select id="year-select" bind:value={selectedYear} class="form-select form-select-compact"
			onchange={() => { selectedTaskId = null; }}>
			{#each [...allYears].reverse() as y}
				<option value={y}>
					{y} {istYears.includes(y) ? '(Ist)' : '(Plan)'}
				</option>
			{/each}
		</select>
		<span class="data-type-badge" class:is-ist={dataType === 'ist'} class:is-plan={dataType === 'plan'}>
			{dataTypeLabel}
		</span>
	</div>
</section>

<!-- KPI Cards -->
<section class="section">
	<div class="kpi-grid">
		<div class="kpi-card">
			<div class="kpi-label">
				Aufwendungen
				<Popover direction="down">
					{#snippet trigger()}
						<span class="kpi-help" title="Was ist hier enthalten?">
							<HelpCircle size={14} />
						</span>
					{/snippet}
					<p class="popover-text"><strong>Ohne Umlagen und Pensionen.</strong></p>
					<p class="popover-text"><strong>Umlagen</strong> (Kreisumlage, Schulumlage) sind Weiterleitungen an den Kreis – kein eigener Aufgabenvollzug der Stadt. Sie haben keine zuordenbare Ertragsseite pro Bereich.</p>
					<p class="popover-text"><strong>Pensionen</strong> sind Versorgungsverpflichtungen aus früherer Beschäftigung. Man könnte sie methodisch auch einbeziehen (sie sind Folgekosten von Pflichtaufgaben) – hier sind sie bewusst herausgerechnet, weil sie keinem aktuellen Aufgabenbereich direkt zuordenbar sind.</p>
				</Popover>
			</div>
			<div class="kpi-value">{formatMio(totalExpense)}</div>
		</div>
		<div class="kpi-card">
			<div class="kpi-label">Eigene Erträge der Bereiche</div>
			<div class="kpi-value kpi-green">{formatMio(totalRevenue)}</div>
		</div>
		<div class="kpi-card kpi-highlight">
			<div class="kpi-label">Deckungslücke gesamt</div>
			<div class="kpi-value kpi-red">{formatMio(totalGap)}</div>
		</div>
		<div class="kpi-card">
			<div class="kpi-label">Deckungsgrad</div>
			<div class="kpi-value">{pctFmt(totalCoverage)}</div>
		</div>
	</div>
</section>

<!-- Pflicht summary -->
{#if pflichtSlices.length > 0}
<section class="section">
	<div class="card card-padded">
		<div class="pflicht-kpi-row">
			<div>
				<span class="pflicht-badge pflicht-pflicht">Pflichtaufgaben</span>
				<span class="pflicht-kpi-sub">
					{formatMio(pflichtExpense)} Aufwand, davon {pctFmt(pflichtCoverage)} durch Erträge gedeckt
				</span>
			</div>
			<div class="pflicht-kpi-gap">
				Lücke: <strong>{formatMio(pflichtGap)}</strong>
			</div>
		</div>
	</div>
</section>
{/if}

<!-- Main Chart: Stacked Bars per Task -->
<section class="section">
	<div class="card card-padded">
		<h3 class="chart-section-title">Aufwand vs. Erträge nach Aufgabenbereich</h3>
		<p class="chart-section-desc">
			Klicken Sie auf einen Bereich für Details und Zeitverlauf.
		</p>

		<div class="bar-chart">
			{#each slices as slice (slice.task.id)}
				{@const prevGap = prevGapMap.get(slice.task.id)}
				{@const gapDiff = prevGap != null ? slice.gap - prevGap : null}
				{@const isSelected = selectedTaskId === slice.task.id}
				{@const isDimmed = TAX_FUNDED_TASKS.has(slice.task.id)}
				<button
					class="bar-row"
					class:bar-row-selected={isSelected}
					class:bar-row-dimmed={isDimmed}
					onclick={() => handleTaskClick(slice.task.id)}
					aria-expanded={isSelected}
				>
					<div class="bar-label">
						<span class="bar-dot" style="background: {slice.task.color}"></span>
						<span class="bar-name">{slice.task.shortLabel}</span>
						<span class="bar-pflicht pflicht-badge pflicht-{slice.task.pflicht}">{slice.task.pflichtLabel}</span>
					</div>
					<div class="bar-visual">
						<div class="bar-track">
							<div
								class="bar-fill bar-fill-green"
								style="width: {(slice.revenue / maxExpense) * 100}%"
								title="Erträge: {formatAmount(slice.revenue)}"
							></div>
							<div
								class="bar-fill bar-fill-red"
								style="width: {(slice.gap / maxExpense) * 100}%"
								title="Deckungslücke: {formatAmount(slice.gap)}"
							></div>
						</div>
					</div>
					<div class="bar-numbers">
						<span class="bar-coverage">{pctFmt(slice.coverageRatio)}</span>
						<span class="bar-gap">
							Lücke {formatAmount(slice.gap)}
							{#if gapDiff != null}
								<span class="bar-delta" class:is-up={gapDiff > 0} class:is-down={gapDiff < 0}>
									({gapDiff >= 0 ? '+' : ''}{formatAmount(gapDiff)})
								</span>
							{/if}
						</span>
					</div>
					<span class="bar-chevron">
						{#if isSelected}
							<ChevronUp size={16} />
						{:else}
							<ChevronDown size={16} />
						{/if}
					</span>
				</button>
			{/each}
		</div>

		<!-- Legend -->
		<div class="bar-legend">
			<span class="legend-item"><span class="legend-swatch legend-green"></span> Durch Erträge gedeckt</span>
			<span class="legend-item"><span class="legend-swatch legend-red"></span> Deckungslücke (aus Steuern/KFA)</span>
		</div>
	</div>
</section>

<!-- Detail: Selected Task -->
{#if selectedTask}
	{@const task = selectedTask.task}
	<section class="section">
		<div class="card card-padded">
			<h4 class="chart-section-title">
				<span class="cat-dot-lg" style="background: {task.color}"></span>
				{task.label}
			</h4>
			<p class="chart-section-desc">{task.description}</p>

			{#if isTaxFunded}
				<div class="info-box info-box-amber" style="margin-bottom: 1rem">
					<Info class="info-icon" />
					<div>
						<strong>Naturgemäß steuerfinanziert:</strong> Verwaltungskosten (Rathaus, Kämmerei, Personalverwaltung) erzeugen keine zuordenbaren Erträge.
						Der niedrige Deckungsgrad ist strukturell normal und kein Zeichen einer Unterfinanzierung durch Land oder Bund.
					</div>
				</div>
			{/if}

			<div class="detail-grid">
				<div class="detail-row">
					<span class="detail-label">Aufwendungen</span>
					<span class="detail-value">{formatAmount(selectedTask.expense)}</span>
				</div>
				<div class="detail-row">
					<span class="detail-label">Erträge (Zuweisungen, Gebühren, Erstattungen)</span>
					<span class="detail-value detail-green">{formatAmount(selectedTask.revenue)}</span>
				</div>
				<div class="detail-row detail-row-sum">
					<span class="detail-label">Deckungslücke</span>
					<span class="detail-value detail-red">{formatAmount(selectedTask.gap)}</span>
				</div>
				<div class="detail-row">
					<span class="detail-label">Deckungsgrad</span>
					<span class="detail-value">{pctFmt(selectedTask.coverageRatio)}</span>
				</div>
			</div>
		</div>
	</section>

	<!-- Product drill-down -->
	{#if drilldown.length > 0}
		<section class="section">
			<div class="card card-padded">
				<h4 class="chart-section-title">
					<span class="cat-dot-lg" style="background: {task.color}"></span>
					Was steckt in „{task.shortLabel}"?
				</h4>
				<div class="scroll-x">
				<table class="coverage-table">
					<thead>
						<tr>
							<th>Produkt</th>
							<th class="col-right">Zuschussbedarf</th>
							<th class="col-right">Anteil</th>
						</tr>
					</thead>
					<tbody>
						{#each drilldown as row (row.nr)}
							<tr>
								<td>{row.label}</td>
								<td class="col-right">{formatAmount(row.amount)}</td>
								<td class="col-right">{(row.percent * 100).toFixed(1)} %</td>
							</tr>
						{/each}
					</tbody>
				</table>
				</div>
			</div>
			{#if selectedDrilldownSourceLinks.length > 0}
				<SourceCitation
					description="Produktübersicht – {task.label}"
					links={selectedDrilldownSourceLinks}
				/>
			{/if}
		</section>
	{/if}

	<!-- Time Series: Revenue, Expense, Gap -->
	{#if selectedTimeSeries.expense.length > 0}
		<section class="section">
			<div class="card card-padded">
				<h4 class="chart-section-title">
					<span class="cat-dot-lg" style="background: {task.color}"></span>
					{task.shortLabel} – Aufwendungen über die Jahre
				</h4>
				<TimeSeriesChart
					title=""
					series={selectedTimeSeries.expense}
					yLabel="€"
					planOnlyYears={summary.plan_only_years}
					lastIstYear={summary.last_ist_year}
					fixedColor="red"
				/>
			</div>
		</section>
		<section class="section">
			<div class="card card-padded">
				<h4 class="chart-section-title">
					<span class="cat-dot-lg" style="background: {task.color}"></span>
					{task.shortLabel} – Erträge über die Jahre
				</h4>
				<TimeSeriesChart
					title=""
					series={selectedTimeSeries.revenue}
					yLabel="€"
					planOnlyYears={summary.plan_only_years}
					lastIstYear={summary.last_ist_year}
					fixedColor="green"
				/>
			</div>
		</section>
		<section class="section">
			<div class="card card-padded">
				<h4 class="chart-section-title">
					<span class="cat-dot-lg" style="background: {task.color}"></span>
					{task.shortLabel} – Deckungslücke über die Jahre
				</h4>
				<TimeSeriesChart
					title=""
					series={selectedTimeSeries.gap}
					yLabel="€"
					planOnlyYears={summary.plan_only_years}
					lastIstYear={summary.last_ist_year}
					fixedColor="red"
				/>
			</div>
			<SourceCitation
				description="Teilergebnishaushalt – {task.label}"
				links={selectedSourceLinks}
			/>
		</section>
	{/if}
{/if}

<!-- Coverage Overview Table -->
<section class="section">
	<div class="card card-padded">
		<h3 class="chart-section-title">Deckungsgrad aller Bereiche</h3>
		<p class="chart-section-desc">Wie viel Prozent der Kosten werden durch eigene Erträge des Bereichs gedeckt?</p>

		<div class="scroll-x">
		<table class="coverage-table">
			<thead>
				<tr>
					<th>Aufgabenbereich</th>
					<th class="col-right">Aufwand</th>
					<th class="col-right">Erträge</th>
					<th class="col-right">Lücke</th>
					<th>Deckungsgrad</th>
				</tr>
			</thead>
			<tbody>
				{#each slices as slice (slice.task.id)}
					<tr class:row-highlight={selectedTaskId === slice.task.id} class:row-dimmed={TAX_FUNDED_TASKS.has(slice.task.id)}>
						<td>
							<span class="cat-dot" style="background: {slice.task.color}"></span>
							{slice.task.shortLabel}
							<span class="pflicht-badge-sm pflicht-{slice.task.pflicht}">{slice.task.pflichtLabel}</span>
						</td>
						<td class="col-right">{formatAmount(slice.expense)}</td>
						<td class="col-right td-green">{formatAmount(slice.revenue)}</td>
						<td class="col-right td-red">{formatAmount(slice.gap)}</td>
						<td>
							<div class="coverage-bar-wrapper">
								<div class="coverage-bar">
									<div class="coverage-bar-fill" style="width: {Math.min(slice.coverageRatio * 100, 100)}%"></div>
								</div>
								<span class="coverage-pct">{pctFmt(slice.coverageRatio)}</span>
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
			<tfoot>
				<tr class="row-sum">
					<td><strong>Gesamt</strong></td>
					<td class="col-right"><strong>{formatAmount(totalExpense)}</strong></td>
					<td class="col-right td-green"><strong>{formatAmount(totalRevenue)}</strong></td>
					<td class="col-right td-red"><strong>{formatAmount(totalGap)}</strong></td>
					<td>
						<div class="coverage-bar-wrapper">
							<div class="coverage-bar">
								<div class="coverage-bar-fill" style="width: {Math.min(totalCoverage * 100, 100)}%"></div>
							</div>
							<span class="coverage-pct"><strong>{pctFmt(totalCoverage)}</strong></span>
						</div>
					</td>
				</tr>
			</tfoot>
		</table>
		</div>
	</div>
</section>

<!-- Context / Info Boxes -->
<section class="section">
	<div class="info-box info-box-blue">
		<Info class="info-icon" />
		<div>
			<strong>Was zeigt diese Seite?</strong><br />
			Pro Teilhaushalt werden die ordentlichen Erträge (Nr. 100: Gebühren, Zuweisungen, Erstattungen)
			den ordentlichen Aufwendungen (Nr. 190: Personal, Sach, Transfers) gegenübergestellt.
			Die Differenz – die „Deckungslücke" – finanziert Rödermark aus allgemeinen Mitteln (Steuern, Schlüsselzuweisungen aus dem KFA).
			<br /><br />
			Die Deckungslücke zeigt, wo die Stadt aus eigenen Steuermitteln zuschießen muss –
			sie ist aber <strong>nicht gleichbedeutend mit einer Konnexitätsverletzung</strong>.
			Das Konnexitätsprinzip (Art. 137 Abs. 6 Hessische Verfassung) greift nur bei Aufgaben,
			die das Land Hessen per Gesetz überträgt oder verschärft, und nur für den dadurch verursachten Mehraufwand.
		</div>
	</div>
</section>

<section class="section">
	<div class="info-box info-box-amber">
		<Info class="info-icon" />
		<div>
			<strong>Hinweise zur Einordnung</strong>
			<ul class="caveat-list">
				<li><strong>Umlagen</strong> (Kreisumlage, Schulumlage) und <strong>Pensionen</strong> sind in dieser Ansicht nicht enthalten – sie sind zentrale Finanzposten ohne eigene Ertragsseite pro Aufgabenbereich.</li>
				<li><strong>Verwaltung</strong> erscheint mit sehr niedrigem Deckungsgrad – das ist strukturell normal, weil Rathaus und Kämmerei keine eigenen Gebühren oder Zuweisungen erhalten.</li>
				<li><strong>Freiwillige Leistungen</strong> (Kultur, Sport) haben keine gesetzliche Erstattungspflicht durch Land oder Bund. Eine Lücke dort ist kein Finanzierungsproblem höherer Ebenen, sondern kommunale Entscheidung.</li>
				<li>Viele Pflichtaufgaben basieren auf <strong>Bundesrecht</strong> (SGB VIII, Ganztagsanspruch), das über die Länder auf Kommunen durchgereicht wird. Das Land argumentiert dann, es sei nicht der Verursacher – juristisch ein Dauerstreit.</li>
			</ul>
		</div>
	</div>
</section>

<style>
	.page-intro { margin-bottom: 2rem; max-width: 48rem; color: var(--gray-600); }
	.section { margin-bottom: 2.5rem; }

	/* Year selector */
	.year-selector {
		display: flex; flex-direction: column; gap: 0.5rem;
	}
	@media (min-width: 640px) {
		.year-selector { flex-direction: row; align-items: center; gap: 1rem; }
	}
	.field-label { font-size: 0.875rem; font-weight: 500; color: var(--gray-700); }
	.form-select-compact { width: auto; min-width: 8rem; }
	.data-type-badge {
		font-size: 0.75rem; font-weight: 500; padding: 0.25rem 0.75rem;
		border-radius: 999px;
	}
	.data-type-badge.is-ist { background: var(--green-100); color: var(--green-700); }
	.data-type-badge.is-plan { background: var(--blue-50); color: var(--blue-700); }

	/* KPI cards */
	.kpi-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}
	@media (min-width: 768px) {
		.kpi-grid { grid-template-columns: repeat(4, 1fr); }
	}
	.kpi-card {
		background: white;
		padding: 1rem;
		border-radius: 0.5rem;
		box-shadow: var(--shadow-sm);
		outline: 1px solid var(--gray-100);
	}
	.kpi-highlight {
		outline: 2px solid var(--red-400);
		background: #fef2f2;
	}
	.kpi-label { font-size: 0.75rem; color: var(--gray-500); margin-bottom: 0.25rem; }
	.kpi-value { font-size: 1.25rem; font-weight: 700; color: var(--gray-800); }
	.kpi-green { color: var(--emerald-600); }
	.kpi-red { color: var(--red-600); }

	/* Pflicht summary row */
	.pflicht-kpi-row {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	@media (min-width: 640px) {
		.pflicht-kpi-row {
			flex-direction: row;
			align-items: center;
			justify-content: space-between;
		}
	}
	.pflicht-kpi-sub { font-size: 0.8125rem; color: var(--gray-500); margin-left: 0.5rem; }
	.pflicht-kpi-gap { font-size: 0.9375rem; color: var(--red-600); white-space: nowrap; }

	/* Pflicht badges */
	.pflicht-badge {
		display: inline-block;
		font-size: 0.6875rem; font-weight: 600;
		padding: 0.125rem 0.5rem;
		border-radius: 999px;
		white-space: nowrap;
		line-height: 1.4;
	}
	.pflicht-badge-sm {
		display: inline-block;
		font-size: 0.625rem; font-weight: 600;
		padding: 0.0625rem 0.375rem;
		border-radius: 999px;
		white-space: nowrap;
		line-height: 1.4;
	}
	.pflicht-pflicht {
		background: #fef2f2; color: var(--red-700);
	}
	.pflicht-freiwillig {
		background: #f0fdf4; color: var(--green-700);
	}
	.pflicht-misch {
		background: #fffbeb; color: var(--amber-700);
	}

	/* Chart section titles */
	.chart-section-title {
		display: flex; align-items: center; gap: 0.5rem;
		font-size: 1rem; font-weight: 600; color: var(--gray-800);
		margin-bottom: 0.25rem;
	}
	.chart-section-desc {
		font-size: 0.8125rem; color: var(--gray-500); margin-bottom: 1rem;
	}

	/* Bar chart */
	.bar-chart {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.bar-row {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.25rem;
		padding: 0.625rem 0.75rem;
		border: 1px solid transparent;
		border-radius: 0.375rem;
		cursor: pointer;
		transition: all 0.15s;
		background: none;
		text-align: left;
		width: 100%;
		font: inherit;
		color: inherit;
	}
	@media (min-width: 768px) {
		.bar-row {
			grid-template-columns: 12rem 1fr auto 1.25rem;
			align-items: center;
			gap: 0.75rem;
		}
	}
	.bar-row:hover { background: var(--gray-50); }
	.bar-row-selected {
		background: var(--brand-50, #eff6ff);
		border-color: var(--brand-200, #bfdbfe);
	}
	.bar-row-dimmed {
		opacity: 0.5;
	}
	.bar-row-dimmed:hover, .bar-row-dimmed.bar-row-selected {
		opacity: 0.8;
	}

	.bar-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.8125rem;
		flex-wrap: wrap;
	}
	.bar-dot {
		width: 0.625rem; height: 0.625rem; border-radius: 2px; flex-shrink: 0;
	}
	.bar-name { font-weight: 600; color: var(--gray-800); }
	.bar-pflicht { flex-shrink: 0; }

	.bar-visual { min-width: 0; }
	.bar-track {
		display: flex;
		height: 1.25rem;
		border-radius: 0.25rem;
		overflow: hidden;
		background: var(--gray-100);
	}
	.bar-fill {
		height: 100%;
		transition: width 0.3s ease;
		min-width: 0;
	}
	.bar-fill-green { background: var(--emerald-500); }
	.bar-fill-red { background: var(--red-400); opacity: 0.7; }

	.bar-numbers {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.75rem;
		white-space: nowrap;
	}
	.bar-coverage { font-weight: 700; color: var(--gray-700); min-width: 2.5rem; }
	.bar-gap { color: var(--gray-500); }
	.bar-delta { font-size: 0.6875rem; }
	.bar-delta.is-up { color: var(--red-600); }
	.bar-delta.is-down { color: var(--green-700); }
	.bar-chevron { color: var(--gray-400); display: none; }
	@media (min-width: 768px) {
		.bar-chevron { display: flex; align-items: center; }
	}

	.bar-legend {
		display: flex;
		gap: 1.5rem;
		margin-top: 1rem;
		font-size: 0.75rem;
		color: var(--gray-500);
	}
	.legend-item { display: flex; align-items: center; gap: 0.375rem; }
	.legend-swatch {
		display: inline-block;
		width: 0.75rem; height: 0.75rem;
		border-radius: 2px;
	}
	.legend-green { background: var(--emerald-500); }
	.legend-red { background: var(--red-400); opacity: 0.7; }

	/* Detail grid */
	.detail-grid {
		display: flex; flex-direction: column; gap: 0.375rem;
		margin-top: 0.75rem;
	}
	.detail-row {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		padding: 0.375rem 0;
		border-bottom: 1px solid var(--gray-50);
		font-size: 0.875rem;
	}
	.detail-row-sum {
		border-bottom: 2px solid var(--gray-200);
		padding-top: 0.5rem;
		font-weight: 600;
	}
	.detail-label { color: var(--gray-600); }
	.detail-value { font-weight: 600; color: var(--gray-800); }
	.detail-green { color: var(--emerald-600); }
	.detail-red { color: var(--red-600); }

	/* Dot for table/headers */
	.cat-dot-lg {
		display: inline-block; width: 1rem; height: 1rem;
		border-radius: 0.25rem; vertical-align: middle;
	}
	.cat-dot {
		display: inline-block; width: 0.625rem; height: 0.625rem;
		border-radius: 2px; vertical-align: middle; margin-right: 0.25rem;
	}

	/* Coverage table */
	.coverage-table {
		width: 100%; border-collapse: collapse; font-size: 0.8125rem;
	}
	.coverage-table th {
		text-align: left; font-weight: 500; color: var(--gray-500);
		padding: 0.375rem 0.5rem; border-bottom: 1px solid var(--gray-100);
		font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.025em;
	}
	.coverage-table th.col-right { text-align: right; }
	.coverage-table td {
		padding: 0.5rem 0.5rem; border-bottom: 1px solid var(--gray-50);
		white-space: nowrap;
	}
	.coverage-table td:first-child {
		white-space: normal;
	}
	.coverage-table tbody tr:hover td { background: var(--gray-50); }
	.col-right { text-align: right; }
	.td-green { color: var(--emerald-600); }
	.td-red { color: var(--red-600); }
	.row-highlight td { background: var(--brand-50, #eff6ff); }
	.row-dimmed td { opacity: 0.5; }
	.row-dimmed:hover td { opacity: 0.8; }
	.row-sum td {
		background: var(--gray-50);
		border-top: 2px solid var(--gray-200);
		padding-top: 0.625rem;
	}

	/* Coverage progress bar */
	.coverage-bar-wrapper {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.coverage-bar {
		flex: 1;
		height: 0.5rem;
		background: var(--gray-100);
		border-radius: 0.25rem;
		overflow: hidden;
		min-width: 3rem;
	}
	.coverage-bar-fill {
		height: 100%;
		background: var(--emerald-500);
		border-radius: 0.25rem;
		transition: width 0.3s ease;
	}
	.coverage-pct {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--gray-700);
		min-width: 2.5rem;
		text-align: right;
	}

	/* Info icon */
	:global(.info-icon) {
		margin-top: 0.125rem; width: 1.25rem; height: 1.25rem; flex-shrink: 0;
	}

	/* Caveat list */
	.caveat-list {
		margin-top: 0.5rem;
		padding-left: 1.25rem;
		font-size: 0.8125rem;
		line-height: 1.6;
	}
	.caveat-list li { margin-bottom: 0.25rem; }

	/* KPI help icon */
	.kpi-help {
		display: inline-flex;
		align-items: center;
		color: var(--gray-400);
		cursor: help;
		vertical-align: middle;
		margin-left: 0.25rem;
	}

	/* Popover text */
	.popover-text {
		font-size: 0.8125rem;
		line-height: 1.5;
		color: var(--gray-700);
		margin-bottom: 0.5rem;
	}
	.popover-text:last-child { margin-bottom: 0; }

	/* Mobile helpers */
	.scroll-x {
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
		margin-left: -1rem;
		margin-right: -1rem;
	}
	@media (min-width: 640px) {
		.scroll-x { margin-left: 0; margin-right: 0; }
	}
</style>
