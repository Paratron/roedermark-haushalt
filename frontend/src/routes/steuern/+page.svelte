<script lang="ts">
	import type { PageData } from './$types';
	import type { TaxItem, TaxTimeSeries } from './+page.ts';
	import type { CategorySlice } from '$lib/data';
	import { formatAmount } from '$lib/format';
	import DonutChart from '$lib/components/DonutChart.svelte';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import { Receipt, Info, SlidersHorizontal } from '@lucide/svelte';

	/** Format a Hebesatz value: German locale. If forceDecimals is true, always show 2 decimal places. */
	function fmtHS(v: number, forceDecimals = false): string {
		if (forceDecimals || !Number.isInteger(v)) {
			return v.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
		}
		return v.toLocaleString('de-DE');
	}

	let { data }: { data: PageData } = $props();

	let taxDetailItems = $derived(data.taxDetailItems);
	let taxYears = $derived(data.taxYears);
	let taxTimeSeries = $derived(data.taxTimeSeries);
	let taxSourceLinks = $derived(data.taxSourceLinks);
	let hebesaetzeGrundsteuerB = $derived(data.hebesaetzeGrundsteuerB);
	let hebesaetzeGewerbesteuer = $derived(data.hebesaetzeGewerbesteuer);
	let taxKeys = $derived(data.taxKeys);

	// ─── State ───
	let latestYear = $derived(taxYears[taxYears.length - 1] ?? 2026);
	let selectedYear = $state(0);
	// Initialize selectedYear once
	$effect(() => {
		if (selectedYear === 0 && latestYear > 0) selectedYear = latestYear;
	});

	// ─── Tax composition for selected year ───
	let taxItems = $derived.by((): TaxItem[] => {
		const yearItems = taxDetailItems.filter((i) => i.year === selectedYear);
		const mapped: TaxItem[] = [];
		for (const tk of taxKeys) {
			const match = yearItems.find((i) => i.bezeichnung.includes(tk.match));
			if (match && Math.abs(match.amount) > 0) {
				mapped.push({
					key: tk.key,
					label: tk.label,
					color: tk.color,
					amount: Math.abs(match.amount),
					percent: 0,
				});
			}
		}
		// Collect unmatched items as "Sonstige"
		const matchedBez = new Set(mapped.map((m) => {
			const yearItem = yearItems.find((i) => i.bezeichnung.includes(
				taxKeys.find((tk) => tk.key === m.key)!.match
			));
			return yearItem?.bezeichnung;
		}).filter(Boolean));
		const unmatched = yearItems.filter(
			(i) => !matchedBez.has(i.bezeichnung) && Math.abs(i.amount) > 100
		);
		if (unmatched.length > 0) {
			const sonstigeAmount = unmatched.reduce((s, i) => s + Math.abs(i.amount), 0);
			if (sonstigeAmount > 0) {
				mapped.push({
					key: 'sonstige',
					label: 'Sonstige',
					color: '#d1d5db',
					amount: sonstigeAmount,
					percent: 0,
				});
			}
		}
		const total = mapped.reduce((s, m) => s + m.amount, 0);
		for (const m of mapped) {
			m.percent = total > 0 ? m.amount / total : 0;
		}
		return mapped.sort((a, b) => b.amount - a.amount);
	});

	let totalTaxRevenue = $derived(taxItems.reduce((s, t) => s + t.amount, 0));

	// Convert to DonutChart slices
	let donutSlices = $derived<CategorySlice[]>(
		taxItems.map((t) => ({
			category: { nr: t.key, label: t.label, shortLabel: t.label, color: t.color, side: 'einnahmen' as const, description: '' },
			amount: t.amount,
			percent: t.percent,
		}))
	);

	// ─── Check if any Hebesatz value has decimals (→ force 2 decimal places for ALL values) ───
	let grundsteuerBHasDecimals = $derived(
		hebesaetzeGrundsteuerB?.data.some((d) => !Number.isInteger(d.hebesatz)) ?? false
	);
	let gewerbesteuerHasDecimals = $derived(
		hebesaetzeGewerbesteuer?.data.some((d) => !Number.isInteger(d.hebesatz)) ?? false
	);

	// ─── Hebesatz comparison ───
	// For each municipality, use the selected year's value if available,
	// otherwise carry forward the latest prior year and tag it.
	interface CompEntry { kommune: string; hebesatz: number; actualYear: number; carried: boolean }

	function fillComparison(
		data: { kommune: string; year: number; hebesatz: number }[],
		targetYear: number
	): CompEntry[] {
		// Group by kommune, pick best entry ≤ targetYear
		const byKommune = new Map<string, { hebesatz: number; year: number }>();
		for (const d of data) {
			if (d.year > targetYear) continue;
			const prev = byKommune.get(d.kommune);
			if (!prev || d.year > prev.year) {
				byKommune.set(d.kommune, { hebesatz: d.hebesatz, year: d.year });
			}
		}
		return [...byKommune.entries()]
			.map(([kommune, v]) => ({
				kommune,
				hebesatz: v.hebesatz,
				actualYear: v.year,
				carried: v.year !== targetYear,
			}))
			.sort((a, b) => b.hebesatz - a.hebesatz);
	}

	let grundsteuerBComparison = $derived.by(() => {
		if (!hebesaetzeGrundsteuerB) return [] as CompEntry[];
		return fillComparison(hebesaetzeGrundsteuerB.data, selectedYear);
	});

	let gewerbesteuerComparison = $derived.by(() => {
		if (!hebesaetzeGewerbesteuer) return [] as CompEntry[];
		return fillComparison(hebesaetzeGewerbesteuer.data, selectedYear);
	});

	let maxGrundsteuerB = $derived(
		grundsteuerBComparison.length > 0
			? Math.max(...grundsteuerBComparison.map((d) => d.hebesatz))
			: 1
	);
	let maxGewerbesteuer = $derived(
		gewerbesteuerComparison.length > 0
			? Math.max(...gewerbesteuerComparison.map((d) => d.hebesatz))
			: 1
	);

	// ─── Hebesatz-Slider "Was wäre wenn?" ───
	// Grundsteuer B
	let roedermarkGrundsteuerB = $derived(
		grundsteuerBComparison.find((d) => d.kommune === 'Rödermark')?.hebesatz ?? 650
	);
	let grundsteuerBRevenue = $derived(
		taxItems.find((t) => t.key === 'grundsteuer_b')?.amount ?? 0
	);
	let sliderGrundsteuerB = $state(0); // will be initialized via effect
	let grundsteuerBInitialized = $state(false);
	$effect(() => {
		if (!grundsteuerBInitialized && roedermarkGrundsteuerB > 0) {
			sliderGrundsteuerB = roedermarkGrundsteuerB;
			grundsteuerBInitialized = true;
		}
	});
	let simulatedGrundsteuerB = $derived(
		roedermarkGrundsteuerB > 0
			? (grundsteuerBRevenue / roedermarkGrundsteuerB) * sliderGrundsteuerB
			: 0
	);
	let grundsteuerBDiff = $derived(simulatedGrundsteuerB - grundsteuerBRevenue);

	// Gewerbesteuer
	let roedermarkGewerbesteuer = $derived(
		gewerbesteuerComparison.find((d) => d.kommune === 'Rödermark')?.hebesatz ?? 365
	);
	let gewerbesteuerRevenue = $derived(
		taxItems.find((t) => t.key === 'gewerbesteuer')?.amount ?? 0
	);
	let sliderGewerbesteuer = $state(0);
	let gewerbesteuerInitialized = $state(false);
	$effect(() => {
		if (!gewerbesteuerInitialized && roedermarkGewerbesteuer > 0) {
			sliderGewerbesteuer = roedermarkGewerbesteuer;
			gewerbesteuerInitialized = true;
		}
	});
	let simulatedGewerbesteuer = $derived(
		roedermarkGewerbesteuer > 0
			? (gewerbesteuerRevenue / roedermarkGewerbesteuer) * sliderGewerbesteuer
			: 0
	);
	let gewerbesteuerDiff = $derived(simulatedGewerbesteuer - gewerbesteuerRevenue);

	// ─── Time series: Rödermark Hebesatz history ───
	let roedermarkGrundsteuerBHistory = $derived(
		hebesaetzeGrundsteuerB
			? hebesaetzeGrundsteuerB.data
					.filter((d) => d.kommune === 'Rödermark')
					.sort((a, b) => a.year - b.year)
			: []
	);
	let roedermarkGewerbesteuerHistory = $derived(
		hebesaetzeGewerbesteuer
			? hebesaetzeGewerbesteuer.data
					.filter((d) => d.kommune === 'Rödermark')
					.sort((a, b) => a.year - b.year)
			: []
	);

	let maxHistGrundsteuerB = $derived(
		roedermarkGrundsteuerBHistory.length > 0
			? Math.max(...roedermarkGrundsteuerBHistory.map((d) => d.hebesatz))
			: 1
	);
	let maxHistGewerbesteuer = $derived(
		roedermarkGewerbesteuerHistory.length > 0
			? Math.max(...roedermarkGewerbesteuerHistory.map((d) => d.hebesatz))
			: 1
	);
</script>

<h2 class="page-title"><Receipt class="page-icon" /> Steuereinnahmen</h2>
<p class="page-intro">
	Steuereinnahmen sind die wichtigste Einnahmequelle der Stadt Rödermark.
	Hier siehst du die Zusammensetzung, Entwicklung und den Vergleich der Hebesätze mit anderen Kommunen im Kreis Offenbach.
</p>

<!-- Year Selector -->
<section class="section">
	<div class="year-selector">
		<label for="year-select" class="field-label">Jahr auswählen</label>
		<select id="year-select" bind:value={selectedYear} class="form-select form-select-compact">
			{#each [...taxYears].reverse() as y (y)}
				<option value={y}>{y}</option>
			{/each}
		</select>
	</div>
</section>

<!-- Tax Composition: Donut + Table -->
<section class="section">
	<h3 class="section-title">Zusammensetzung der Steuereinnahmen {selectedYear}</h3>
	<div class="card card-padded donut-detail-row">
		<div class="donut-col">
			<DonutChart
				title="Steuereinnahmen {selectedYear}"
				slices={donutSlices}
				hideLegend
			/>
		</div>
		<div class="detail-col">
			<div class="kpi-total">
				<span class="kpi-total-label">Steuereinnahmen gesamt</span>
				<span class="kpi-total-value">{formatAmount(totalTaxRevenue)}</span>
			</div>
			<div class="detail-table-wrap">
				<table class="detail-table">
					<thead>
						<tr>
							<th>Steuerart</th>
							<th class="col-right">Betrag</th>
							<th class="col-right">Anteil</th>
						</tr>
					</thead>
					<tbody>
						{#each taxItems as t (t.key)}
							<tr>
								<td>
									<span class="cat-dot" style="background: {t.color}"></span>
									{t.label}
								</td>
								<td class="col-right">{formatAmount(t.amount)}</td>
								<td class="col-right">{(t.percent * 100).toFixed(1)} %</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<SourceCitation description="Steuereinnahmen (Ergebnishaushalt Nr. 50)" links={taxSourceLinks} />
		</div>
	</div>
</section>

<!-- Hebesatz Development Rödermark -->
<section class="section">
	<h3 class="section-title">Hebesatz-Entwicklung Rödermark</h3>
	<div class="hebesatz-history-grid">
		<!-- Grundsteuer B History -->
		<div class="card card-padded">
			<h4 class="card-subtitle">Grundsteuer B</h4>
			<div class="vbar-chart">
				{#each roedermarkGrundsteuerBHistory as entry, i (entry.year)}
					{@const prev = i > 0 ? roedermarkGrundsteuerBHistory[i - 1] : null}
					{@const changed = prev && prev.hebesatz !== entry.hebesatz}
					{@const went_up = changed && entry.hebesatz > (prev?.hebesatz ?? 0)}
					{@const went_down = changed && entry.hebesatz < (prev?.hebesatz ?? 0)}
					<div class="vbar-col">
						{#if changed}
							<span class="vbar-delta" class:vbar-delta-up={went_up} class:vbar-delta-down={went_down}>
								{went_up ? '▲' : '▼'}{Math.abs(entry.hebesatz - (prev?.hebesatz ?? 0))}
							</span>
						{/if}
						<span class="vbar-label" class:vbar-label-up={went_up} class:vbar-label-down={went_down}>
							{fmtHS(entry.hebesatz, grundsteuerBHasDecimals)}
						</span>
						<div class="vbar-track">
							<div
								class="vbar-fill"
								class:vbar-fill-up={went_up}
								class:vbar-fill-down={went_down}
								style="height: {(entry.hebesatz / maxHistGrundsteuerB) * 100}%"
							></div>
						</div>
						<span class="vbar-year">{entry.year}</span>
					</div>
				{/each}
			</div>
		</div>
		<!-- Gewerbesteuer History -->
		<div class="card card-padded">
			<h4 class="card-subtitle">Gewerbesteuer</h4>
			<div class="vbar-chart">
				{#each roedermarkGewerbesteuerHistory as entry, i (entry.year)}
					{@const prev = i > 0 ? roedermarkGewerbesteuerHistory[i - 1] : null}
					{@const changed = prev && prev.hebesatz !== entry.hebesatz}
					{@const went_up = changed && entry.hebesatz > (prev?.hebesatz ?? 0)}
					{@const went_down = changed && entry.hebesatz < (prev?.hebesatz ?? 0)}
					<div class="vbar-col">
						{#if changed}
							<span class="vbar-delta" class:vbar-delta-up={went_up} class:vbar-delta-down={went_down}>
								{went_up ? '▲' : '▼'}{Math.abs(entry.hebesatz - (prev?.hebesatz ?? 0))}
							</span>
						{/if}
						<span class="vbar-label" class:vbar-label-up={went_up} class:vbar-label-down={went_down}>
							{fmtHS(entry.hebesatz, gewerbesteuerHasDecimals)}
						</span>
						<div class="vbar-track">
							<div
								class="vbar-fill"
								class:vbar-fill-up={went_up}
								class:vbar-fill-down={went_down}
								style="height: {(entry.hebesatz / maxHistGewerbesteuer) * 100}%"
							></div>
						</div>
						<span class="vbar-year">{entry.year}</span>
					</div>
				{/each}
			</div>
		</div>
	</div>
</section>

<!-- Hebesatz Comparison -->
<section class="section">
	<h3 class="section-title">Hebesätze im Vergleich – Kreis Offenbach</h3>
	<div class="comparison-grid">
		<!-- Grundsteuer B -->
		<div class="card card-padded">
			<h4 class="card-subtitle">Grundsteuer B</h4>
			<div class="bar-chart">
				{#each grundsteuerBComparison as entry (entry.kommune)}
					{@const isRoedermark = entry.kommune === 'Rödermark'}
					<div class="bar-row" class:bar-row-highlight={isRoedermark} class:bar-row-carried={entry.carried}>
						<span class="bar-label">{entry.kommune}{#if entry.carried}<span class="carried-year"> ({entry.actualYear})</span>{/if}</span>
						<div class="bar-track-h">
							<div
								class="bar-fill"
								class:bar-fill-highlight={isRoedermark}
								class:bar-fill-carried={entry.carried}
								style="width: {(entry.hebesatz / maxGrundsteuerB) * 100}%"
							></div>
						</div>
					<span class="bar-value">{fmtHS(entry.hebesatz, grundsteuerBHasDecimals)} %</span>
					</div>
				{/each}
			</div>
		</div>

		<!-- Gewerbesteuer -->
		<div class="card card-padded">
			<h4 class="card-subtitle">Gewerbesteuer</h4>
			<div class="bar-chart">
				{#each gewerbesteuerComparison as entry (entry.kommune)}
					{@const isRoedermark = entry.kommune === 'Rödermark'}
					<div class="bar-row" class:bar-row-highlight={isRoedermark} class:bar-row-carried={entry.carried}>
						<span class="bar-label">{entry.kommune}{#if entry.carried}<span class="carried-year"> ({entry.actualYear})</span>{/if}</span>
						<div class="bar-track-h">
							<div
								class="bar-fill"
								class:bar-fill-highlight={isRoedermark}
								class:bar-fill-carried={entry.carried}
								style="width: {(entry.hebesatz / maxGewerbesteuer) * 100}%"
							></div>
						</div>
					<span class="bar-value">{fmtHS(entry.hebesatz, gewerbesteuerHasDecimals)} %</span>
					</div>
				{/each}
			</div>
		</div>
	</div>
	<p class="data-note"><Info size={14} /> Datenquellen: <a href="https://www.offenbach.ihk.de/standortpolitik/region-offenbach/zahlen-daten-fakten/gemeindesteckbriefe/">IHK Offenbach Gemeindesteckbriefe</a> (Umfrage der IHK, alle Kommunen im Kreis Offenbach) sowie Haushaltssatzungen der Stadt Rödermark.</p>
</section>

<!-- Simulator: What-if Slider -->
<section class="section">
	<h3 class="section-title"><SlidersHorizontal size={20} /> Was wäre wenn?</h3>
	<p class="section-desc">
		Verschiebe die Hebesätze, um zu sehen, wie sich die Steuereinnahmen {selectedYear} verändern würden.
	</p>

	<div class="simulator-grid">
		<!-- Grundsteuer B Slider -->
		<div class="card card-padded simulator-card">
			<h4 class="card-subtitle">Grundsteuer B</h4>
			<div class="slider-row">
				<label class="slider-label" for="slider-grundsteuer">Hebesatz</label>
				<input
					id="slider-grundsteuer"
					type="range"
					min="200"
					max={roedermarkGrundsteuerB * 3}
					step="10"
					bind:value={sliderGrundsteuerB}
					class="slider-input"
				/>
				<span class="slider-value">{fmtHS(sliderGrundsteuerB, grundsteuerBHasDecimals)} %</span>
			</div>
			<div class="slider-result">
				<div class="slider-result-row">
					<span>Aktuell ({fmtHS(roedermarkGrundsteuerB, grundsteuerBHasDecimals)} %)</span>
					<span class="slider-amount">{formatAmount(grundsteuerBRevenue)}</span>
				</div>
				<div class="slider-result-row">
					<span>Simuliert ({fmtHS(sliderGrundsteuerB, grundsteuerBHasDecimals)} %)</span>
					<span class="slider-amount">{formatAmount(simulatedGrundsteuerB)}</span>
				</div>
				<div class="slider-result-row slider-diff" class:is-positive={grundsteuerBDiff > 0} class:is-negative={grundsteuerBDiff < 0}>
					<span>Differenz</span>
					<span class="slider-amount">
						{grundsteuerBDiff > 0 ? '+' : ''}{formatAmount(grundsteuerBDiff)}
					</span>
				</div>
			</div>
		</div>

		<!-- Gewerbesteuer Slider -->
		<div class="card card-padded simulator-card">
			<h4 class="card-subtitle">Gewerbesteuer</h4>
			<div class="slider-row">
				<label class="slider-label" for="slider-gewerbe">Hebesatz</label>
				<input
					id="slider-gewerbe"
					type="range"
					min="200"
					max={roedermarkGewerbesteuer * 3}
					step="5"
					bind:value={sliderGewerbesteuer}
					class="slider-input"
				/>
				<span class="slider-value">{fmtHS(sliderGewerbesteuer, gewerbesteuerHasDecimals)} %</span>
			</div>
			<div class="slider-result">
				<div class="slider-result-row">
					<span>Aktuell ({fmtHS(roedermarkGewerbesteuer, gewerbesteuerHasDecimals)} %)</span>
					<span class="slider-amount">{formatAmount(gewerbesteuerRevenue)}</span>
				</div>
				<div class="slider-result-row">
					<span>Simuliert ({fmtHS(sliderGewerbesteuer, gewerbesteuerHasDecimals)} %)</span>
					<span class="slider-amount">{formatAmount(simulatedGewerbesteuer)}</span>
				</div>
				<div class="slider-result-row slider-diff" class:is-positive={gewerbesteuerDiff > 0} class:is-negative={gewerbesteuerDiff < 0}>
					<span>Differenz</span>
					<span class="slider-amount">
						{gewerbesteuerDiff > 0 ? '+' : ''}{formatAmount(gewerbesteuerDiff)}
					</span>
				</div>
			</div>
		</div>
	</div>

	<div class="info-box info-box-amber">
		<Info class="info-icon" />
		<div>
			<strong>Hinweis:</strong> Die Simulation ist eine vereinfachte Hochrechnung (linearer Dreisatz).
			In der Realität beeinflusst der Hebesatz auch das Steueraufkommen selbst – ein höherer Satz kann
			Unternehmen/Einwohner abwandern lassen, ein niedrigerer kann Zuzug fördern. Die tatsächliche
			Wirkung hängt von vielen Faktoren ab.
		</div>
	</div>
</section>

<!-- Tax Revenue Time Series -->
<section class="section">
	<h3 class="section-title">Steuereinnahmen im Zeitverlauf</h3>
	<div class="card card-padded">
		<div class="stacked-table-wrap">
			<table class="detail-table">
				<thead>
					<tr>
						<th>Steuerart</th>
						{#each taxYears as y (y)}
							<th class="col-right">{y}</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each taxTimeSeries as ts (ts.key)}
						<tr>
							<td>
								<span class="cat-dot" style="background: {ts.color}"></span>
								{ts.label}
							</td>
							{#each taxYears as y (y)}
								{@const point = ts.points.find((p) => p.year === y)}
								<td class="col-right">
									{#if point && point.amount > 0}
										{formatAmount(point.amount)}
									{:else}
										<span class="text-gray-300">–</span>
									{/if}
								</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
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
	.section-title {
		display: flex; align-items: center; gap: 0.5rem;
		font-size: 1.125rem; font-weight: 700; color: var(--gray-800);
		margin-bottom: 1rem;
	}
	.section-desc {
		font-size: 0.875rem; color: var(--gray-500); margin-bottom: 1rem; max-width: 48rem;
	}
	.year-selector {
		display: flex; flex-direction: column; gap: 0.5rem;
	}
	@media (min-width: 640px) {
		.year-selector { flex-direction: row; align-items: center; gap: 1rem; }
	}
	.field-label { font-size: 0.875rem; font-weight: 500; color: var(--gray-700); }
	.form-select-compact { width: auto; min-width: 8rem; }
	.form-select-sm { min-width: 5rem; font-size: 0.8125rem; padding: 0.25rem 0.5rem; }

	/* Donut + detail row */
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
	.donut-col { flex-shrink: 0; }
	.detail-col { flex: 1; min-width: 0; }

	.kpi-total {
		display: flex; justify-content: space-between; align-items: baseline;
		padding: 0.75rem 0; margin-bottom: 0.75rem;
		border-bottom: 2px solid var(--brand-100, #dbeafe);
	}
	.kpi-total-label { font-size: 0.875rem; font-weight: 500; color: var(--gray-500); }
	.kpi-total-value { font-size: 1.25rem; font-weight: 700; color: var(--brand-700, #1d4ed8); }

	/* Detail table */
	.detail-table-wrap { overflow-x: auto; }
	.detail-table { width: 100%; border-collapse: collapse; font-size: 0.8125rem; }
	.detail-table th {
		text-align: left; font-weight: 500; color: var(--gray-500);
		padding: 0.375rem 0.5rem; border-bottom: 1px solid var(--gray-100);
		font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.025em;
		white-space: nowrap;
	}
	.detail-table td {
		padding: 0.5rem; border-bottom: 1px solid var(--gray-50); white-space: nowrap;
	}
	.col-right { text-align: right; }
	.cat-dot {
		display: inline-block; width: 0.625rem; height: 0.625rem;
		border-radius: 0.125rem; margin-right: 0.375rem; vertical-align: middle;
	}
	.stacked-table-wrap { overflow-x: auto; }

	.card-subtitle {
		font-size: 0.9375rem; font-weight: 600; color: var(--gray-800); margin-bottom: 0.75rem;
	}

	/* Hebesatz history vertical bar chart */
	.hebesatz-history-grid {
		display: grid; gap: 1.5rem; grid-template-columns: 1fr;
	}
	@media (min-width: 768px) {
		.hebesatz-history-grid { grid-template-columns: 1fr 1fr; }
	}
	.vbar-chart {
		display: flex; align-items: flex-end; gap: 0.125rem;
		overflow-x: auto; padding-bottom: 0.25rem;
	}
	.vbar-col {
		display: flex; flex-direction: column; align-items: center;
		flex: 1; min-width: 2rem;
	}
	.vbar-label {
		font-size: 0.625rem; font-weight: 600; color: var(--gray-500);
		margin-bottom: 0.125rem; white-space: nowrap;
	}
	.vbar-label-up { color: var(--red-600, #dc2626); }
	.vbar-label-down { color: var(--green-600, #16a34a); }
	.vbar-delta {
		font-size: 0.5625rem; font-weight: 600; margin-bottom: 0.125rem;
		white-space: nowrap;
	}
	.vbar-delta-up { color: var(--red-500, #ef4444); }
	.vbar-delta-down { color: var(--green-500, #22c55e); }
	.vbar-track {
		width: 100%; max-width: 2.5rem; height: 8rem;
		background: var(--gray-50); border-radius: 0.25rem 0.25rem 0 0;
		display: flex; align-items: flex-end;
	}
	.vbar-fill {
		width: 100%; background: var(--brand-400, #60a5fa);
		border-radius: 0.25rem 0.25rem 0 0;
		transition: height 0.3s ease;
		min-height: 2px;
	}
	.vbar-fill-up { background: var(--red-400, #f87171); }
	.vbar-fill-down { background: var(--green-400, #4ade80); }
	.vbar-year {
		font-size: 0.625rem; color: var(--gray-400);
		margin-top: 0.25rem; white-space: nowrap;
	}

	/* Comparison bars */
	.comparison-grid {
		display: grid; gap: 1.5rem; grid-template-columns: 1fr;
	}
	@media (min-width: 900px) {
		.comparison-grid { grid-template-columns: 1fr 1fr; }
	}
	.bar-chart {
		display: flex; flex-direction: column; gap: 0.375rem;
	}
	.bar-row {
		display: grid; grid-template-columns: 10rem 1fr 5rem; gap: 0.5rem; align-items: center;
	}
	.bar-row-highlight { font-weight: 600; }
	.bar-label {
		font-size: 0.8125rem; color: var(--gray-600);
		overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
	}
	.bar-row-highlight .bar-label { color: var(--brand-700, #1d4ed8); }
	.bar-track-h {
		height: 1.25rem; background: var(--gray-100); border-radius: 0.25rem;
		position: relative; overflow: hidden;
	}
	.bar-fill {
		height: 100%; background: var(--gray-300);
		border-radius: 0.25rem; transition: width 0.3s ease;
	}
	.bar-fill-highlight { background: var(--brand-500, #3b82f6); }
	.bar-value {
		font-size: 0.8125rem; color: var(--gray-600); text-align: right; white-space: nowrap;
	}
	.bar-row-highlight .bar-value { color: var(--brand-700); font-weight: 700; }
	.carried-year {
		font-size: 0.6875rem; font-weight: 400; color: var(--gray-400);
	}
	.bar-row-carried { opacity: 0.7; }
	.bar-fill-carried { background: var(--gray-200); }
	.data-note {
		display: flex; align-items: center; gap: 0.375rem;
		margin-top: 0.75rem; font-size: 0.75rem; color: var(--gray-400); font-style: italic;
	}

	/* Simulator */
	.simulator-grid {
		display: grid; gap: 1.5rem; grid-template-columns: 1fr;
	}
	@media (min-width: 768px) {
		.simulator-grid { grid-template-columns: 1fr 1fr; }
	}
	.simulator-card { }
	.slider-row {
		display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;
	}
	.slider-label { font-size: 0.8125rem; color: var(--gray-500); white-space: nowrap; }
	.slider-input {
		flex: 1; accent-color: var(--brand-500, #3b82f6);
		height: 0.375rem; cursor: pointer;
	}
	.slider-value {
		font-size: 0.9375rem; font-weight: 700; color: var(--brand-700);
		min-width: 4rem; text-align: right;
	}
	.slider-result {
		display: flex; flex-direction: column; gap: 0.25rem;
		padding: 0.75rem; background: var(--gray-50); border-radius: 0.5rem;
	}
	.slider-result-row {
		display: flex; justify-content: space-between; align-items: baseline;
		font-size: 0.8125rem; color: var(--gray-600);
	}
	.slider-amount { font-weight: 600; font-variant-numeric: tabular-nums; }
	.slider-diff {
		border-top: 1px solid var(--gray-200); padding-top: 0.375rem; margin-top: 0.25rem;
		font-weight: 600;
	}
	.slider-diff.is-positive { color: var(--green-600, #16a34a); }
	.slider-diff.is-negative { color: var(--red-600, #dc2626); }

	:global(.info-icon) {
		margin-top: 0.125rem; width: 1.25rem; height: 1.25rem; flex-shrink: 0;
	}
</style>
