<script lang="ts">
	import type { PageData } from './$types';
	import { formatAmount, formatNumber, amountTypeLabel } from '$lib/format';
	import { groupBy, haushaltTypeLabelLong, sourceLinksFromItems, sourceLinksPerYear } from '$lib/data';
	import type { LineItem, HaushaltType } from '$lib/types';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import HaushaltTable from '$lib/components/HaushaltTable.svelte';
	import { Building2 } from '@lucide/svelte';
	import { browser } from '$app/environment';

	let { data }: { data: PageData } = $props();

	// Read initial selections from URL
	function initParams() {
		if (!browser) return { th: data.teilhaushalte[0]?.nr ?? '', typ: 'teilergebnishaushalt' as HaushaltType, nr: '' };
		const params = new URLSearchParams(window.location.search);
		const th = params.get('th');
		const typ = params.get('typ');
		const nr = params.get('nr');
		return {
			th: th && data.teilhaushalte.some((t) => t.nr === th) ? th : (data.teilhaushalte[0]?.nr ?? ''),
			typ: (typ === 'teilergebnishaushalt' || typ === 'teilfinanzhaushalt') ? typ : 'teilergebnishaushalt' as HaushaltType,
			nr: nr ?? '',
		};
	}

	const _init = initParams();

	// ─── State ───
	let selectedTh = $state<string>(_init.th);
	let selectedSubType = $state<HaushaltType>(_init.typ);

	// Sync selections to URL
	$effect(() => {
		if (!browser) return;
		const url = new URL(window.location.href);
		url.searchParams.set('th', selectedTh);
		if (selectedSubType !== 'teilergebnishaushalt') {
			url.searchParams.set('typ', selectedSubType);
		} else {
			url.searchParams.delete('typ');
		}
		if (selectedNr) {
			url.searchParams.set('nr', selectedNr);
		} else {
			url.searchParams.delete('nr');
		}
		history.replaceState(history.state, '', url);
	});

	// ─── Derived ───
	let selectedThName = $derived(
		data.teilhaushalte.find((t) => t.nr === selectedTh)?.name ?? ''
	);

	let filteredItems = $derived(
		data.items.filter(
			(i) =>
				i.teilhaushalt_nr === selectedTh &&
				i.haushalt_type === selectedSubType
		)
	);

	// Build positions list (unique nr + bezeichnung)
	let positions = $derived.by(() => {
		const posMap = new Map<string, { nr: string; bezeichnung: string }>();
		for (const item of filteredItems) {
			if (!posMap.has(item.nr)) {
				posMap.set(item.nr, { nr: item.nr, bezeichnung: item.bezeichnung });
			}
		}
		return [...posMap.values()].sort(
			(a, b) => Number.parseInt(a.nr) - Number.parseInt(b.nr)
		);
	});

	let selectedNr = $state(_init.nr);

	// Auto-select first position when TH/type changes (but not on initial load if URL had a nr)
	let _initialized = false;
	$effect(() => {
		if (positions.length > 0 && (!_initialized || !positions.some((p) => p.nr === selectedNr))) {
			if (_initialized || !selectedNr) {
				selectedNr = positions[0].nr;
			}
			_initialized = true;
		}
	});

	let chartSeries = $derived(
		filteredItems
			.filter((i) => i.nr === selectedNr)
			.sort((a, b) => a.year - b.year)
			.map((i) => ({
				year: i.year,
				amount_type: i.amount_type,
				amount: i.amount,
				label: i.bezeichnung,
				document_id: i.document_id
			}))
	);

	let selectedLabel = $derived(
		positions.find((p) => p.nr === selectedNr)?.bezeichnung ?? ''
	);

	let selectedSourceLinks = $derived(
		sourceLinksFromItems(
			filteredItems.filter((i) => i.nr === selectedNr),
			data.documents
		)
	);

	// Pivot table data
	let years = $derived(data.summary.years);
	let planOnlySet = $derived(new Set(data.summary.plan_only_years));

	interface PivotRow {
		nr: string;
		bezeichnung: string;
		values: Map<string, number | null>;
	}

	let pivotData = $derived.by(() => {
		const rows: PivotRow[] = [];
		for (const pos of positions) {
			const values = new Map<string, number | null>();
			for (const item of filteredItems) {
				if (item.nr === pos.nr) {
					values.set(`${item.year}_${item.amount_type}`, item.amount);
				}
			}
			rows.push({ nr: pos.nr, bezeichnung: pos.bezeichnung, values });
		}
		return rows;
	});

	let yearSourceLinks = $derived(sourceLinksPerYear(data.items, data.documents, selectedSubType));
	let thSummary = $derived.by(() => {
		const byTh = groupBy(data.items, (i) => i.teilhaushalt_nr ?? '');
		const result: { nr: string; name: string; countTE: number; countTF: number }[] = [];
		for (const th of data.teilhaushalte) {
			result.push(th);
		}
		return result;
	});
</script>

<h2 class="page-title">
	<Building2 class="page-icon" /> Teilhaushalte
</h2>
<p class="page-intro">
	Teilergebnis- und Teilfinanzhaushalte nach Fachbereichen der Stadt Rödermark.
	Jeder Teilhaushalt zeigt die budgetierten und tatsächlichen Erträge/Aufwendungen bzw. Ein-/Auszahlungen
	für einen Verwaltungsbereich.
</p>

<!-- Teilhaushalt Overview Cards -->
<section class="section">
	<div class="th-grid">
		{#each data.teilhaushalte as th (th.nr)}
			<button
				type="button"
				class="th-card {selectedTh === th.nr ? 'th-card-active' : ''}"
				onclick={() => { selectedTh = th.nr; }}
			>
				<p class="th-card-nr">Teilhaushalt {th.nr}</p>
				<p class="th-card-name">{th.name}</p>
				<div class="th-card-counts">
					<span>{formatNumber(th.countTE)} TEH</span>
					<span>{formatNumber(th.countTF)} TFH</span>
				</div>
			</button>
		{/each}
	</div>
</section>

<!-- Detail Section -->
<section class="card card-padded">
	<div class="detail-header">
		<div>
			<h3 class="detail-title">
				TH {selectedTh} – {selectedThName}
			</h3>
		</div>
		<div class="toggle-group">
			<button
				type="button"
				class="toggle-btn {selectedSubType === 'teilergebnishaushalt' ? 'toggle-btn-active' : 'toggle-btn-inactive'}"
				onclick={() => { selectedSubType = 'teilergebnishaushalt'; }}
			>
				Teilergebnishaushalt
			</button>
			<button
				type="button"
				class="toggle-btn {selectedSubType === 'teilfinanzhaushalt' ? 'toggle-btn-active' : 'toggle-btn-inactive'}"
				onclick={() => { selectedSubType = 'teilfinanzhaushalt'; }}
			>
				Teilfinanzhaushalt
			</button>
		</div>
	</div>

	{#if positions.length === 0}
		<p class="empty-msg">Keine Daten für diese Auswahl vorhanden.</p>
	{:else}
		<!-- Position Selector + Chart -->
		<div class="selector-row">
			<label for="pos-select" class="field-label">Position</label>
			<select id="pos-select" bind:value={selectedNr} class="form-select">
				{#each positions as pos}
					<option value={pos.nr}>Nr. {pos.nr} – {pos.bezeichnung}</option>
				{/each}
			</select>
		</div>

		{#if chartSeries.length > 0}
			<div class="chart-box">
				<TimeSeriesChart
					title="Nr. {selectedNr} – {selectedLabel}"
					series={chartSeries}
					yLabel="Mio. €"
					planOnlyYears={data.summary.plan_only_years}
				/>
			</div>
			<SourceCitation
				description="TH {selectedTh}, {haushaltTypeLabelLong(selectedSubType)}, Nr. {selectedNr}"
				links={selectedSourceLinks}
			/>
		{/if}

		<!-- Data Table -->
		<h4 class="sub-table-title">Alle Positionen – {haushaltTypeLabelLong(selectedSubType)}</h4>
		<HaushaltTable
			rows={pivotData}
			{years}
			planOnlyYears={data.summary.plan_only_years}
			{yearSourceLinks}
			sourceLabel={haushaltTypeLabelLong(selectedSubType)}
			invertColors={selectedSubType === 'teilfinanzhaushalt'}
		/>
	{/if}
</section>

<style>
	.page-title {
		display: flex; align-items: center; gap: 0.75rem;
		margin-bottom: 1.5rem; font-size: 1.5rem; font-weight: 700; color: var(--gray-900);
	}
	:global(.page-icon) { width: 1.75rem; height: 1.75rem; }
	.page-intro { margin-bottom: 2rem; max-width: 48rem; color: var(--gray-600); }
	.section { margin-bottom: 2rem; }
	.th-card {
		padding: 1rem; text-align: left; border-radius: 0.75rem;
		box-shadow: var(--shadow-sm); border: none; cursor: pointer;
		outline: 1px solid var(--gray-100); outline-offset: -1px;
		background: white; transition: box-shadow 0.15s;
	}
	.th-card:hover { box-shadow: var(--shadow-md); }
	.th-card-active { background: var(--brand-50); outline-color: var(--brand-300); }
	.th-card-nr { font-size: 0.75rem; font-weight: 500; color: var(--gray-400); }
	.th-card-name { margin-top: 0.25rem; font-weight: 600; color: var(--gray-900); line-height: 1.3; }
	.th-card-counts { margin-top: 0.5rem; display: flex; gap: 0.75rem; font-size: 0.75rem; color: var(--gray-500); }
	.detail-header {
		margin-bottom: 1.5rem; display: flex; flex-direction: column; gap: 1rem;
	}
	@media (min-width: 640px) { .detail-header { flex-direction: row; align-items: flex-end; } }
	.detail-title { font-size: 1.125rem; font-weight: 600; color: var(--gray-800); }
	.toggle-group { display: flex; gap: 0.5rem; }
	.selector-row { margin-bottom: 1.5rem; }
	.field-label { display: block; font-size: 0.875rem; font-weight: 500; color: var(--gray-700); }
	.chart-box {
		margin-bottom: 1rem; padding: 1rem;
		border: 1px solid var(--gray-100); border-radius: 0.5rem;
	}
	.sub-table-title {
		margin-bottom: 0.75rem; font-size: 0.875rem; font-weight: 600; color: var(--gray-700);
	}
	.empty-msg { color: var(--gray-400); font-style: italic; }

</style>
