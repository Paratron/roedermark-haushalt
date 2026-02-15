<script lang="ts">
	import type { PageData } from './$types';
	import {
		buildCategoryBreakdown,
		bestDataType,
		REVENUE_CATEGORIES,
		EXPENSE_CATEGORIES,
		sourceLinksFromItems,
		buildSubItems,
		subItemYears,
	} from '$lib/data';
	import { formatAmount } from '$lib/format';
	import DonutChart from '$lib/components/DonutChart.svelte';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import { PieChart, Info, TrendingUp, TrendingDown, Minus, List, LayoutGrid, Columns3 } from '@lucide/svelte';
	import { browser } from '$app/environment';

	let { data }: { data: PageData } = $props();

	const { items, summary, documents } = data;

	// ─── State ───
	const istYears = summary.ist_years.filter(
		(y) => items.some((i) => i.year === y && i.amount_type === 'ist' && i.nr === '100')
	);
	const allYears = summary.years;

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
	let selectedNr = $state<string | null>(null);
	let selectedSide = $state<'einnahmen' | 'ausgaben'>('einnahmen');

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
		if (selectedNr) {
			url.searchParams.set('nr', selectedNr);
			url.searchParams.set('side', selectedSide);
		} else {
			url.searchParams.delete('nr');
			url.searchParams.delete('side');
		}
		history.replaceState(history.state, '', url);
	});

	// ─── Derived data ───
	let dataType = $derived(bestDataType(items, selectedYear));
	let revenueSlices = $derived(buildCategoryBreakdown(items, selectedYear, 'einnahmen', dataType));
	let expenseSlices = $derived(buildCategoryBreakdown(items, selectedYear, 'ausgaben', dataType));
	let dataTypeLabel = $derived(dataType === 'ist' ? 'Ist (Jahresabschluss)' : 'Plan (Haushaltsansatz)');

	// ─── Time series for selected category ───
	let selectedCategory = $derived.by(() => {
		if (!selectedNr) return null;
		const cats = selectedSide === 'einnahmen' ? REVENUE_CATEGORIES : EXPENSE_CATEGORIES;
		return cats.find((c) => c.nr === selectedNr) ?? null;
	});

	let selectedTimeSeries = $derived.by(() => {
		if (!selectedNr) return [];
		return items
			.filter((i) => i.nr === selectedNr && !i.table_id.startsWith('struktur_'))
			.sort((a, b) => a.year - b.year)
			.map((i) => ({
				year: i.year,
				amount_type: i.amount_type,
				amount: Math.abs(i.amount),
				label: i.bezeichnung,
				document_id: i.document_id,
			}));
	});

	let selectedSourceLinks = $derived(
		selectedNr
			? sourceLinksFromItems(
					items.filter((i) => i.nr === selectedNr && !i.table_id.startsWith('struktur_')),
					documents
				)
			: []
	);

	// ─── Sub-items drill-down ───
	let availableSubItemYears = $derived(
		selectedNr ? subItemYears(items, selectedNr) : []
	);

	let subItemYear = $state<number | null>(null);

	$effect(() => {
		if (availableSubItemYears.length > 0) {
			if (availableSubItemYears.includes(selectedYear)) {
				subItemYear = selectedYear;
			} else {
				subItemYear = availableSubItemYears[availableSubItemYears.length - 1];
			}
		} else {
			subItemYear = null;
		}
	});

	let selectedSubItems = $derived(
		selectedNr && subItemYear ? buildSubItems(items, selectedNr, subItemYear) : []
	);

	let subItemSourceLinks = $derived(
		selectedNr && subItemYear
			? sourceLinksFromItems(
					items.filter(
						(i) => i.table_id.startsWith('struktur_') && i.nr === selectedNr && i.year === subItemYear
					),
					documents
				)
			: []
	);

	// YoY change helper
	function getYoYChange(nr: string, year: number): { diff: number; ratio: number } | null {
		const prevYear = year - 1;
		const currItems = items.filter((i) => i.nr === nr && i.year === year);
		const prevItems = items.filter((i) => i.nr === nr && i.year === prevYear);

		const curr = currItems.find((i) => i.amount_type === 'ist') ?? currItems.find((i) => i.amount_type === 'plan');
		const prev = prevItems.find((i) => i.amount_type === 'ist') ?? prevItems.find((i) => i.amount_type === 'plan');

		if (!curr || !prev || prev.amount === 0) return null;

		const absCurr = Math.abs(curr.amount);
		const absPrev = Math.abs(prev.amount);
		const diff = absCurr - absPrev;
		const ratio = diff / absPrev;
		return { diff, ratio };
	}

	function handleSliceClick(side: 'einnahmen' | 'ausgaben', nr: string) {
		if (selectedNr === nr && selectedSide === side) {
			selectedNr = null;
		} else {
			selectedNr = nr;
			selectedSide = side;
		}
	}
</script>

<h2 class="page-title"><PieChart class="page-icon" /> Einnahmen & Ausgaben</h2>
<p class="page-intro">
	Die buchhalterische Aufschlüsselung nach den Positionen des Ergebnishaushalts.
</p>

<!-- View Toggle (navigation) -->
<section class="section">
	<div class="view-toggle">
		<a href="/kategorien" class="view-toggle-btn">
			<LayoutGrid class="view-toggle-icon" />
			Nach Aufgabenbereich
		</a>
		<span class="view-toggle-btn view-toggle-active">
			<Columns3 class="view-toggle-icon" />
			Nach Ertragsart
		</span>
	</div>
</section>

<!-- Year Selector -->
<section class="section">
	<div class="year-selector">
		<label for="year-select" class="field-label">Jahr auswählen</label>
		<select id="year-select" bind:value={selectedYear} class="form-select form-select-compact"
			onchange={() => { selectedNr = null; }}>
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

<!-- Einnahmen: Donut + Detail -->
<section class="section">
	<h4 class="detail-title einnahmen-title">Einnahmen {selectedYear}</h4>
	<div class="card card-padded donut-detail-row">
		<div class="donut-col">
			<DonutChart
				title="Einnahmen {selectedYear}"
				slices={revenueSlices}
				onSliceClick={(nr) => handleSliceClick('einnahmen', nr)}
				hideLegend
			/>
		</div>
		<div class="detail-col">
			<div class="detail-table-wrap">
				<table class="detail-table">
					<thead>
						<tr>
							<th>Kategorie</th>
							<th class="col-right">Betrag</th>
							<th class="col-right">Anteil</th>
							<th class="col-right hide-mobile">ggü. Vorjahr</th>
						</tr>
					</thead>
					<tbody>
						{#each revenueSlices as slice}
							{@const change = getYoYChange(slice.category.nr, selectedYear)}
							<tr
								class="detail-row {selectedNr === slice.category.nr && selectedSide === 'einnahmen' ? 'detail-row-active' : ''}"
								onclick={() => handleSliceClick('einnahmen', slice.category.nr)}
							>
								<td>
									<span class="cat-dot" style="background: {slice.category.color}"></span>
									{slice.category.label}
								</td>
								<td class="col-right">{formatAmount(slice.amount)}</td>
								<td class="col-right">{(slice.percent * 100).toFixed(1)} %</td>
								<td class="col-right hide-mobile">
									{#if change}
										<span class="change {change.diff > 0 ? 'change-up' : change.diff < 0 ? 'change-down' : ''}">
											{#if change.diff > 0}
												<TrendingUp class="change-icon" />
											{:else if change.diff < 0}
												<TrendingDown class="change-icon" />
											{:else}
												<Minus class="change-icon" />
											{/if}
											{change.diff > 0 ? '+' : ''}{(change.ratio * 100).toFixed(1)} %
										</span>
									{:else}
										<span class="change-na">–</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	</div>
</section>

<!-- Ausgaben: Donut + Detail -->
<section class="section">
	<h4 class="detail-title ausgaben-title">Ausgaben {selectedYear}</h4>
	<div class="card card-padded donut-detail-row">
		<div class="donut-col">
			<DonutChart
				title="Ausgaben {selectedYear}"
				slices={expenseSlices}
				onSliceClick={(nr) => handleSliceClick('ausgaben', nr)}
				hideLegend
			/>
		</div>
		<div class="detail-col">
			<div class="detail-table-wrap">
				<table class="detail-table">
					<thead>
						<tr>
							<th>Kategorie</th>
							<th class="col-right">Betrag</th>
							<th class="col-right">Anteil</th>
							<th class="col-right hide-mobile">ggü. Vorjahr</th>
						</tr>
					</thead>
					<tbody>
						{#each expenseSlices as slice}
							{@const change = getYoYChange(slice.category.nr, selectedYear)}
							<tr
								class="detail-row {selectedNr === slice.category.nr && selectedSide === 'ausgaben' ? 'detail-row-active' : ''}"
								onclick={() => handleSliceClick('ausgaben', slice.category.nr)}
							>
								<td>
									<span class="cat-dot" style="background: {slice.category.color}"></span>
									{slice.category.label}
								</td>
								<td class="col-right">{formatAmount(slice.amount)}</td>
								<td class="col-right">{(slice.percent * 100).toFixed(1)} %</td>
								<td class="col-right hide-mobile">
									{#if change}
										<span class="change {change.diff > 0 ? 'change-up' : change.diff < 0 ? 'change-down' : ''}">
											{#if change.diff > 0}
												<TrendingUp class="change-icon" />
											{:else if change.diff < 0}
												<TrendingDown class="change-icon" />
											{:else}
												<Minus class="change-icon" />
											{/if}
											{change.diff > 0 ? '+' : ''}{(change.ratio * 100).toFixed(1)} %
										</span>
									{:else}
										<span class="change-na">–</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	</div>
</section>

<!-- Time Series for Selected Category -->
{#if selectedNr && selectedCategory}
	{@const cat = selectedCategory}
	<section class="section" id="zeitreihe">
		<div class="card card-padded">
			<h4 class="chart-section-title">
				<span class="cat-dot-lg" style="background: {cat.color}"></span>
				{cat.label} – Entwicklung über die Jahre
			</h4>
			<p class="chart-section-desc">{cat.description}</p>
			<TimeSeriesChart
				title=""
				series={selectedTimeSeries}
				yLabel="€"
				planOnlyYears={summary.plan_only_years}
				lastIstYear={summary.last_ist_year}
				fixedColor={selectedSide === 'einnahmen' ? 'green' : 'red'}
			/>
		</div>
		<SourceCitation
			description="Ergebnishaushalt, Nr. {selectedNr} ({cat.label})"
			links={selectedSourceLinks}
		/>

		<!-- Sub-items drill-down -->
		{#if selectedSubItems.length > 0}
			<div class="card card-padded sub-items-card">
				<h4 class="sub-items-title">
					<List class="sub-items-icon" />
					{cat.label} – Aufschlüsselung nach Konten
				</h4>
				{#if availableSubItemYears.length > 1}
					<div class="sub-items-year-select">
						<label for="sub-year" class="field-label">Jahr:</label>
						<select id="sub-year" bind:value={subItemYear} class="form-select form-select-compact">
							{#each availableSubItemYears as y}
								<option value={y}>{y}</option>
							{/each}
						</select>
						<span class="data-type-badge is-plan">Plan</span>
					</div>
				{:else if subItemYear}
					<p class="sub-items-hint">Detaildaten für {subItemYear} (Planwerte)</p>
				{/if}
				<div class="sub-items-table-wrap">
					<table class="sub-items-table">
						<thead>
							<tr>
								<th>Position</th>
								<th class="col-right">Betrag</th>
								<th class="col-right">Anteil</th>
							</tr>
						</thead>
						<tbody>
							{#each selectedSubItems as sub}
								<tr>
									<td class="sub-item-label">
										<span class="sub-item-konto">{sub.konto}</span>
										{sub.label}
									</td>
									<td class="col-right">{formatAmount(sub.amount)}</td>
									<td class="col-right">{(sub.percent * 100).toFixed(1)} %</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
			<SourceCitation
				description="Struktur Ergebnishaushalt, Nr. {selectedNr} ({cat.label}) – {subItemYear}"
				links={subItemSourceLinks}
			/>
		{/if}
	</section>
{/if}

<!-- Info Box -->
<section class="section">
	<div class="info-box info-box-blue">
		<Info class="info-icon" />
		<div>
			<strong>Hinweis:</strong> Die Kategorien entsprechen den Positionen des Ergebnishaushalts (Nr. 10–90 für Erträge, Nr. 110–180 für Aufwendungen).
			Klicke auf eine Kategorie, um die Entwicklung über alle Jahre und – falls verfügbar – die Aufschlüsselung nach einzelnen Konten zu sehen.
			<br />Für Jahre ohne Jahresabschluss werden Planwerte aus dem Haushaltsplan verwendet.
		</div>
	</div>
</section>

<style>
	.page-title {
		display: flex; align-items: center; gap: 0.75rem;
		margin-bottom: 1.5rem; font-size: 1.5rem; font-weight: 700; color: var(--gray-900);
	}
	:global(.page-icon) { width: 1.75rem; height: 1.75rem; }
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

	.donut-detail-row {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}
	@media (min-width: 900px) {
		.donut-detail-row {
			flex-direction: row;
			align-items: flex-start;
		}
	}
	.donut-col {
		flex-shrink: 0;
	}
	.detail-col {
		flex: 1;
		min-width: 0;
	}

	.detail-title {
		margin-bottom: 0.75rem; font-size: 0.875rem; font-weight: 600;
		padding-bottom: 0.5rem; border-bottom: 2px solid var(--gray-100);
	}
	.einnahmen-title { border-color: var(--green-200); color: var(--green-700); }
	.ausgaben-title { border-color: var(--red-200); color: var(--red-700); }

	.detail-table-wrap {
		overflow-x: auto;
		margin-left: -1rem;
		margin-right: -1rem;
	}
	@media (min-width: 640px) {
		.detail-table-wrap {
			margin-left: 0;
			margin-right: 0;
		}
	}
	.detail-table { width: 100%; border-collapse: collapse; font-size: 0.8125rem; }
	.detail-table th {
		text-align: left; font-weight: 500; color: var(--gray-500);
		padding: 0.375rem 0.5rem; border-bottom: 1px solid var(--gray-100);
		font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.025em;
	}
	.detail-table td {
		padding: 0.5rem; border-bottom: 1px solid var(--gray-50);
	}
	.detail-row { cursor: pointer; transition: background 0.1s; }
	.detail-row:hover { background: var(--gray-50); }
	.detail-row-active { background: var(--brand-50); }
	.col-right { text-align: right; }
	.cat-dot {
		display: inline-block; width: 0.625rem; height: 0.625rem;
		border-radius: 0.125rem; margin-right: 0.375rem; vertical-align: middle;
	}
	.cat-dot-lg {
		display: inline-block; width: 1rem; height: 1rem;
		border-radius: 0.25rem; vertical-align: middle;
	}

	.change { display: inline-flex; align-items: center; gap: 0.25rem; font-size: 0.75rem; font-weight: 500; }
	.change-up { color: var(--green-600); }
	.change-down { color: var(--red-600); }
	:global(.change-icon) { width: 0.875rem; height: 0.875rem; }
	.change-na { color: var(--gray-300); }

	.chart-section-title {
		display: flex; align-items: center; gap: 0.5rem;
		font-size: 1rem; font-weight: 600; color: var(--gray-800);
		margin-bottom: 0.25rem;
	}
	.chart-section-desc {
		font-size: 0.8125rem; color: var(--gray-500); margin-bottom: 1rem;
	}

	/* Sub-items drill-down */
	.sub-items-card { margin-top: 1rem; }
	.sub-items-title {
		display: flex; align-items: center; gap: 0.5rem;
		font-size: 0.9375rem; font-weight: 600; color: var(--gray-800);
		margin-bottom: 0.75rem;
	}
	:global(.sub-items-icon) { width: 1rem; height: 1rem; color: var(--gray-400); }
	.sub-items-year-select {
		display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;
	}
	.sub-items-hint {
		font-size: 0.8125rem; color: var(--gray-500); margin-bottom: 0.75rem;
	}
	.sub-items-table-wrap {
		overflow-x: auto;
		margin-left: -1rem;
		margin-right: -1rem;
	}
	@media (min-width: 640px) {
		.sub-items-table-wrap {
			margin-left: 0;
			margin-right: 0;
		}
	}
	.sub-items-table { width: 100%; border-collapse: collapse; font-size: 0.8125rem; }
	.sub-items-table th {
		text-align: left; font-weight: 500; color: var(--gray-500);
		padding: 0.375rem 0.5rem; border-bottom: 1px solid var(--gray-100);
		font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.025em;
	}
	.sub-items-table td {
		padding: 0.5rem; border-bottom: 1px solid var(--gray-50);
	}
	.sub-item-label { max-width: 24rem; }
	.sub-item-konto {
		display: inline-block; font-size: 0.6875rem; font-family: var(--font-mono, monospace);
		color: var(--gray-400); margin-right: 0.5rem; min-width: 4rem;
	}

	:global(.info-icon) {
		margin-top: 0.125rem; width: 1.25rem; height: 1.25rem; flex-shrink: 0;
	}

	@media (max-width: 767px) {
		.hide-mobile { display: none; }
		.detail-table td { padding: 0.625rem 0.5rem; }
		.sub-items-table td { padding: 0.625rem 0.5rem; }
	}
</style>
