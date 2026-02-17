<script lang="ts">
	import type { PageData } from './$types';
	import {
		bestDataType,
		TASK_CATEGORIES,
		buildTaskBreakdown,
		buildTaskDrilldown,
		drilldownSourceLinks,
		taskTimeSeries,
		taskSourceLinks,
		taskSlicesToCategorySlices,
	} from '$lib/data';
	import { formatAmount } from '$lib/format';
	import DonutChart from '$lib/components/DonutChart.svelte';
	import TaskLegend from '$lib/components/TaskLegend.svelte';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import { PieChart, Info, LayoutGrid, Columns3, ChartPie, ChevronsDown } from '@lucide/svelte';
	import { browser } from '$app/environment';
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';

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

	let taskSlices = $derived(buildTaskBreakdown(items, selectedYear, dataType));
	let taskDonutSlices = $derived(taskSlicesToCategorySlices(taskSlices));

	// ─── Pflicht border colors for donut segments ───
	const PFLICHT_BORDER: Record<string, string> = {
		pflicht: '#ef4444',
		freiwillig: '#22c55e',
		misch: '#f59e0b',
	};

	let pflichtRingColors = $derived(
		taskSlices.map(s => PFLICHT_BORDER[s.task.pflicht] ?? '#fff')
	);

	// ─── Pflicht summary: aggregate by obligation type ───
	let pflichtSummary = $derived.by(() => {
		const totalAmount = taskSlices.reduce((sum, s) => sum + s.amount, 0);
		const groups: { type: string; label: string; color: string; amount: number; percent: number }[] = [
			{ type: 'pflicht', label: 'Pflichtaufgaben', color: 'var(--red-500, #ef4444)', amount: 0, percent: 0 },
			{ type: 'misch', label: 'Pflicht + freiwillig', color: 'var(--amber-500, #f59e0b)', amount: 0, percent: 0 },
			{ type: 'freiwillig', label: 'Freiwillige Leistungen', color: 'var(--green-500, #22c55e)', amount: 0, percent: 0 },
		];
		for (const s of taskSlices) {
			const g = groups.find(g => g.type === s.task.pflicht);
			if (g) g.amount += s.amount;
		}
		for (const g of groups) {
			g.percent = totalAmount > 0 ? g.amount / totalAmount : 0;
		}
		return groups.filter(g => g.amount > 0);
	});

	// Previous year for comparison
	let prevYear = $derived(allYears.includes(selectedYear - 1) ? selectedYear - 1 : null);
	let prevDataType = $derived(prevYear ? bestDataType(items, prevYear) : 'plan' as const);
	let prevTaskSlices = $derived(prevYear ? buildTaskBreakdown(items, prevYear, prevDataType) : []);
	let prevAmountMap = $derived.by(() => {
		const map = new Map<string, number>();
		for (const s of prevTaskSlices) map.set(s.task.id, s.amount);
		return map;
	});

	let selectedTask = $derived.by(() => {
		if (!selectedTaskId) return null;
		return TASK_CATEGORIES.find((t) => t.id === selectedTaskId) ?? null;
	});

	let drilldown = $derived.by(() => {
		if (!selectedTaskId) return [];
		return buildTaskDrilldown(items, selectedTaskId, selectedYear, dataType);
	});

	let prevDrilldownMap = $derived.by(() => {
		if (!selectedTaskId || !prevYear) return new Map<string, number>();
		const prev = buildTaskDrilldown(items, selectedTaskId, prevYear, prevDataType);
		const map = new Map<string, number>();
		for (const row of prev) map.set(row.nr, row.amount);
		return map;
	});

	let selectedTaskTimeSeries = $derived.by(() => {
		if (!selectedTaskId) return [];
		return taskTimeSeries(items, selectedTaskId).map((p) => ({
			year: p.year,
			amount_type: p.amount_type,
			amount: p.amount,
			label: TASK_CATEGORIES.find((t) => t.id === selectedTaskId)?.label ?? '',
			document_id: p.document_id,
		}));
	});

	let selectedTaskSourceLinks = $derived(
		selectedTaskId ? taskSourceLinks(items, documents, selectedTaskId) : []
	);

	let selectedDrilldownSourceLinks = $derived(
		selectedTaskId ? drilldownSourceLinks(items, documents, selectedTaskId, selectedYear) : []
	);

	// Total expenses across all task categories (for computing Gesamthaushalt percentage)
	let totalExpenses = $derived(taskSlices.reduce((sum, s) => sum + s.amount, 0));

	// Sticky "show details" button: visible when task selected but drilldown not in viewport
	let drilldownEl: HTMLElement | undefined = $state();
	let drilldownVisible = $state(false);
	let hintDismissed = $state(false);

	$effect(() => {
		if (!browser || !drilldownEl) {
			drilldownVisible = false;
			return;
		}
		const observer = new IntersectionObserver(
			([entry]) => {
				drilldownVisible = entry.isIntersecting;
				if (entry.isIntersecting) hintDismissed = true;
			},
			{ threshold: 0.05 }
		);
		observer.observe(drilldownEl);
		return () => observer.disconnect();
	});

	let showScrollHint = $derived(!!selectedTaskId && !!selectedTask && !drilldownVisible && !hintDismissed);

	function scrollToDrilldown() {
		drilldownEl?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}

	function handleTaskClick(id: string) {
		if (id !== selectedTaskId) hintDismissed = false;
		selectedTaskId = selectedTaskId === id ? null : id;
	}
</script> <AnchorHeading level={2} id="einnahmen-ausgaben"><ChartPie /> Einnahmen & Ausgaben</AnchorHeading> <p class="page-intro"> Wofür gibt die Stadt Rödermark Geld aus? Die Aufschlüsselung zeigt die Ausgaben nach Aufgabenbereichen – von Kinderbetreuung bis Feuerwehr. </p>
<!-- View Toggle (navigation) -->
<section class="section">
	<div class="view-toggle">
		<span class="view-toggle-btn view-toggle-active">
			<LayoutGrid class="view-toggle-icon" />
			Nach Aufgabenbereich
		</span>
		<a href="/kategorien/ertrag" class="view-toggle-btn">
			<Columns3 class="view-toggle-icon" />
			Nach Ertragsart
		</a>
	</div>
</section>

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

<!-- Task Donut + Legend -->
<section class="section">
	<div class="card card-padded">
		<div class="donut-legend-layout">
			<div class="donut-with-pflicht">
				<DonutChart
					title="Ausgaben nach Aufgabenbereich {selectedYear}"
					slices={taskDonutSlices}
					onSliceClick={(id) => handleTaskClick(id)}
					hideLegend
					outerRingColors={pflichtRingColors}
					outerRingLabels={taskSlices.map(s => s.task.pflichtLabel)}
				/>
				<div class="pflicht-summary">
					{#each pflichtSummary as g (g.type)}
						<div class="pflicht-row">
							<span class="pflicht-dot" style="background: {g.color}"></span>
							<span class="pflicht-label">{g.label}</span>
							<span class="pflicht-pct">{(g.percent * 100).toFixed(0)} %</span>
							<span class="pflicht-amount">{formatAmount(g.amount)}</span>
						</div>
					{/each}
				</div>
			</div>
			<TaskLegend
				slices={taskSlices}
				selectedId={selectedTaskId}
				onSelect={(id) => handleTaskClick(id)}
				prevAmounts={prevAmountMap}
				{prevYear}
			/>
		</div>
	</div>
</section>

<!-- Drill-down: what's inside the selected task category -->
{#if selectedTaskId && selectedTask}
	{@const task = selectedTask}
	<section class="section" bind:this={drilldownEl}>
		<div class="card card-padded">
			<h4 class="chart-section-title">
				<span class="cat-dot-lg" style="background: {task.color}"></span>
				Was steckt in „{task.shortLabel}"?
			</h4>
			<p class="chart-section-desc">{task.description}</p>

			{#if drilldown.length > 0}
				<div class="scroll-x">
				<table class="drilldown-table">
					<thead>
						<tr>
							<th>Produkt</th>
							<th class="col-right">Betrag</th>
							<th class="col-right">Anteil</th>
							{#if prevYear}
								<th class="col-right hide-mobile">ggü. {prevYear}</th>
							{/if}
						</tr>
					</thead>
					<tbody>
						{#each drilldown as row (row.nr)}
							{@const prevAmt = prevDrilldownMap.get(row.nr)}
							{@const diff = prevAmt != null ? row.amount - prevAmt : null}
							{@const globalPct = totalExpenses > 0 ? (row.amount / totalExpenses * 100) : 0}
							<tr>
								<td>{row.label}</td>
								<td class="col-right">{formatAmount(row.amount)}</td>
								<td class="col-right" title="{globalPct.toFixed(1)} % vom Gesamthaushalt">{(row.percent * 100).toFixed(1)} %</td>
								{#if prevYear}
									<td class="col-right dd-delta hide-mobile" class:is-up={diff != null && diff > 0} class:is-down={diff != null && diff < 0}>
										{#if diff != null}
											{diff >= 0 ? '+' : ''}{formatAmount(diff)}
										{:else}
											–
										{/if}
									</td>
								{/if}
							</tr>
						{/each}
					</tbody>
				</table>
				</div>
			{:else}
				<p class="drilldown-empty">Für diesen Aufgabenbereich liegen keine Produktdaten für {selectedYear} vor.</p>
			{/if}
		</div>
		{#if selectedDrilldownSourceLinks.length > 0}
			<SourceCitation
				description="Produktübersicht – {task.label}"
				links={selectedDrilldownSourceLinks}
			/>
		{/if}
	</section>

	<!-- Task Time Series -->
	<section class="section" id="zeitreihe">
		<div class="card card-padded">
			<h4 class="chart-section-title">
				<span class="cat-dot-lg" style="background: {task.color}"></span>
				{task.label} – Entwicklung über die Jahre
			</h4>
			<TimeSeriesChart
				title=""
				series={selectedTaskTimeSeries}
				yLabel="€"
				planOnlyYears={summary.plan_only_years}
				lastIstYear={summary.last_ist_year}
				fixedColor="red"
			/>
		</div>
		<SourceCitation
			description="Teilergebnishaushalt – {task.label}"
			links={selectedTaskSourceLinks}
		/>
	</section>
{/if}

<!-- Sticky scroll hint -->
{#if showScrollHint}
	<button class="scroll-hint-btn" onclick={scrollToDrilldown}>
		<ChevronsDown size={18} />
		Weitere Details anzeigen
	</button>
{/if}

<!-- Info Box -->
<section class="section">
	<div class="info-box info-box-blue">
		<Info class="info-icon" />
		<div>
			<strong>Hinweis:</strong> Diese Ansicht zeigt, wofür die Stadt Geld ausgibt – gruppiert nach den 14 Teilhaushalten des Doppelhaushalts.
			<span class="pflicht-badge pflicht-pflicht">Pflichtaufgabe</span> = gesetzlich verpflichtend,
			<span class="pflicht-badge pflicht-freiwillig">Freiwillige Leistung</span> = kann gekürzt werden,
			<span class="pflicht-badge pflicht-misch">Pflicht + freiwillig</span> = enthält beides.
			<br />Für Jahre ohne Jahresabschluss werden Planwerte aus dem Haushaltsplan verwendet.
		</div>
	</div>
</section>

<style>
	.page-intro { margin-bottom: 2rem; max-width: 48rem; color: var(--gray-600); }
	.section { margin-bottom: 2.5rem; }
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
	.data-type-badge.is-ist { background: var(--green-50); color: var(--green-700); }
	.data-type-badge.is-plan { background: var(--blue-50); color: var(--blue-700); }

	/* View toggle as navigation */
	.view-toggle {
		display: flex;
		flex-direction: column;
		background: var(--gray-100);
		border-radius: 0.5rem;
		padding: 0.25rem;
		gap: 0.25rem;
	}
	@media (min-width: 640px) {
		.view-toggle {
			display: inline-flex;
			flex-direction: row;
		}
	}
	.view-toggle-btn {
		display: inline-flex; align-items: center; gap: 0.5rem;
		padding: 0.5rem 1rem;
		border: none; border-radius: 0.375rem;
		font-size: 0.875rem; font-weight: 500;
		background: transparent; color: var(--gray-600);
		cursor: pointer; transition: all 0.15s;
		text-decoration: none;
	}
	.view-toggle-btn:hover { color: var(--gray-900); }
	.view-toggle-active {
		background: white; color: var(--gray-900);
		box-shadow: 0 1px 3px rgba(0,0,0,0.1);
	}
	:global(.view-toggle-icon) { width: 1rem; height: 1rem; }

	/* Donut + Legend side-by-side layout */
	.donut-legend-layout {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}
	@media (min-width: 768px) {
		.donut-legend-layout {
			flex-direction: row;
			align-items: flex-start;
		}
	}

	/* Donut with pflicht summary */
	.donut-with-pflicht {
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.pflicht-summary {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.pflicht-row {
		display: grid;
		grid-template-columns: 0.625rem 1fr auto auto;
		gap: 0.5rem;
		align-items: center;
		font-size: 0.8125rem;
	}
	.pflicht-dot {
		width: 0.625rem;
		height: 0.625rem;
		border-radius: 2px;
	}
	.pflicht-label {
		color: var(--gray-600);
	}
	.pflicht-pct {
		font-weight: 600;
		color: var(--gray-800);
		text-align: right;
		min-width: 2.5rem;
	}
	.pflicht-amount {
		color: var(--gray-400);
		text-align: right;
		font-size: 0.75rem;
		min-width: 5rem;
	}

	.col-right { text-align: right; }
	.cat-dot-lg {
		display: inline-block; width: 1rem; height: 1rem;
		border-radius: 0.25rem; vertical-align: middle;
	}

	.chart-section-title {
		display: flex; align-items: center; gap: 0.5rem;
		font-size: 1rem; font-weight: 600; color: var(--gray-800);
		margin-bottom: 0.25rem;
	}
	.chart-section-desc {
		font-size: 0.8125rem; color: var(--gray-500); margin-bottom: 1rem;
	}

	/* Drill-down table */
	.drilldown-table {
		width: 100%; border-collapse: collapse; font-size: 0.8125rem;
		margin-top: 0.75rem;
	}
	.drilldown-table th {
		text-align: left; font-weight: 500; color: var(--gray-500);
		padding: 0.375rem 0.5rem; border-bottom: 1px solid var(--gray-100);
		font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.025em;
	}
	.drilldown-table th.col-right {
		text-align: right;
	}
	.drilldown-table td {
		padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--gray-50);
		white-space: nowrap;
		transition: background 0.1s;
	}
	.drilldown-table tbody tr:hover td {
		background: var(--gray-50);
	}
	.drilldown-table td:first-child,
	.drilldown-table th:first-child {
		width: 100%;
		white-space: normal;
	}
	.dd-delta { color: var(--gray-400); font-size: 0.75rem; }
	.dd-delta.is-up { color: var(--red-600, #dc2626); }
	.dd-delta.is-down { color: var(--green-600, #16a34a); }
	.drilldown-empty {
		font-size: 0.8125rem; color: var(--gray-400); font-style: italic;
		margin-top: 0.5rem;
	}

	/* Mobile helpers */
	.scroll-x {
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
		margin-left: -1rem;
		margin-right: -1rem;
	}
	@media (min-width: 640px) {
		.scroll-x {
			margin-left: 0;
			margin-right: 0;
		}
	}
	@media (max-width: 767px) {
		.hide-mobile { display: none; }
		.drilldown-table td {
			padding: 0.625rem 0.5rem;
		}
		.view-toggle-btn {
			padding: 0.625rem 1rem;
		}
	}

	/* Pflicht badges */
	.pflicht-badge {
		display: inline-block;
		font-size: 0.6875rem; font-weight: 600;
		padding: 0.125rem 0.5rem;
		border-radius: 999px;
		white-space: nowrap;
		line-height: 1.4;
	}
	.pflicht-pflicht {
		background: var(--red-50, #fef2f2); color: var(--red-700, #b91c1c);
	}
	.pflicht-freiwillig {
		background: var(--green-50, #f0fdf4); color: var(--green-700, #15803d);
	}
	.pflicht-misch {
		background: var(--amber-50, #fffbeb); color: var(--amber-700, #b45309);
	}

	:global(.info-icon) {
		margin-top: 0.125rem; width: 1.25rem; height: 1.25rem; flex-shrink: 0;
	}

	/* Sticky scroll-to-drilldown hint */
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
