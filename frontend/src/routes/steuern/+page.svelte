<script lang="ts">
	import type { PageData } from './$types';
	import type { TaxItem, TaxTimeSeries } from './+page.ts';
	import type { CategorySlice } from '$lib/data';
	import type { SourceLink } from '$lib/types';
	import { formatAmount } from '$lib/format';
	import DonutChart from '$lib/components/DonutChart.svelte';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';
	import SocialMeta from '$lib/components/SocialMeta.svelte';
	import HebesatzHistoryChart from '$lib/components/HebesatzHistoryChart.svelte';
	import { Receipt, Info, SlidersHorizontal, ShieldCheck, ArrowRight } from '@lucide/svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

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
	// Initialize from query param or default to latest year
	$effect(() => {
		if (selectedYear !== 0) return;
		const qYear = Number($page.url.searchParams.get('jahr'));
		selectedYear = qYear && taxYears.includes(qYear) ? qYear : latestYear;
	});

	function setYear(y: number) {
		selectedYear = y;
		const url = new URL($page.url);
		if (y === latestYear) {
			url.searchParams.delete('jahr');
		} else {
			url.searchParams.set('jahr', String(y));
		}
		goto(url, { replaceState: true, noScroll: true, keepFocus: true });
	}

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
	interface CompEntry {
		kommune: string;
		hebesatz: number;
		actualYear: number;
		carried: boolean;
		status?: 'beschlossen' | 'geplant' | 'abgelehnt';
		quelle?: string;
		quelle_url?: string;
	}

	function fillComparison(
		data: {
			kommune: string;
			year: number;
			hebesatz: number;
			status?: 'beschlossen' | 'geplant' | 'abgelehnt';
			quelle?: string;
			quelle_url?: string;
		}[],
		targetYear: number
	): CompEntry[] {
		// Group by kommune, pick best entry ≤ targetYear
		const byKommune = new Map<
			string,
			{
				hebesatz: number;
				year: number;
				status?: 'beschlossen' | 'geplant' | 'abgelehnt';
				quelle?: string;
				quelle_url?: string;
			}
		>();
		for (const d of data) {
			if (d.year > targetYear) continue;
			const prev = byKommune.get(d.kommune);
			if (!prev || d.year > prev.year) {
				byKommune.set(d.kommune, {
					hebesatz: d.hebesatz,
					year: d.year,
					status: d.status,
					quelle: d.quelle,
					quelle_url: d.quelle_url
				});
			}
		}
		return [...byKommune.entries()]
			.map(([kommune, v]) => ({
				kommune,
				hebesatz: v.hebesatz,
				actualYear: v.year,
				carried: v.year !== targetYear,
				status: v.status,
				quelle: v.quelle,
				quelle_url: v.quelle_url
			}))
			.sort((a, b) => b.hebesatz - a.hebesatz);
	}

	// Build the source link(s) for a comparison entry, for the Quelle popover.
	function sourceLinks(entry: CompEntry): SourceLink[] {
		if (!entry.quelle_url) return [];
		return [
			{
				label: entry.quelle ?? 'Quelle',
				href: entry.quelle_url,
				document_id: '',
				page: null
			}
		];
	}

	let gewerbesteuerComparison = $derived.by(() => {
		if (!hebesaetzeGewerbesteuer) return [] as CompEntry[];
		return fillComparison(hebesaetzeGewerbesteuer.data, selectedYear);
	});

	let maxGewerbesteuer = $derived(
		gewerbesteuerComparison.length > 0
			? Math.max(...gewerbesteuerComparison.map((d) => d.hebesatz))
			: 1
	);

	// ─── Hebesatz-Slider "Was wäre wenn?" ───
	// Grundsteuer B
	// Basis für den Simulator ist der aktuell GÜLTIGE Hebesatz (nicht ein
	// geplanter, noch nicht beschlossener Wert), denn die ausgewiesenen
	// Einnahmen beruhen auf dem gültigen Satz. Daher geplante Einträge
	// ausblenden und den jüngsten beschlossenen Satz ≤ Auswahljahr nehmen.
	let roedermarkGrundsteuerB = $derived.by(() => {
		if (!hebesaetzeGrundsteuerB) return 650;
		const enacted = hebesaetzeGrundsteuerB.data
			.filter((d) => d.kommune === 'Rödermark' && d.year <= selectedYear && d.status !== 'geplant')
			.sort((a, b) => b.year - a.year);
		return enacted[0]?.hebesatz ?? 650;
	});
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
	let roedermarkGewerbesteuerHistory = $derived(
		hebesaetzeGewerbesteuer
			? hebesaetzeGewerbesteuer.data
					.filter((d) => d.kommune === 'Rödermark')
					.sort((a, b) => a.year - b.year)
			: []
	);

	let roedermarkGrundsteuerBHistory = $derived(
		hebesaetzeGrundsteuerB
			? hebesaetzeGrundsteuerB.data
					.filter((d) => d.kommune === 'Rödermark')
					.sort((a, b) => a.year - b.year)
			: []
	);
</script>

<SocialMeta
	title="Steuereinnahmen"
	description="Steuereinnahmen der Stadt Rödermark – Zusammensetzung, Hebesätze im Vergleich mit dem Kreis Offenbach und Entwicklung über die Jahre."
	path="/steuern"
	image="share-steuer.jpg"
/>

<AnchorHeading level={2} id="steuereinnahmen"><Receipt /> Steuereinnahmen</AnchorHeading>
<p class="page-intro">
	Steuereinnahmen sind die wichtigste Einnahmequelle der Stadt Rödermark.
	Hier siehst du die Zusammensetzung, Entwicklung und den Vergleich der Hebesätze mit anderen Kommunen im Kreis Offenbach.
</p>

<!--
<a href="/hsk2026" class="hsk-link-box">
	<ShieldCheck class="hsk-link-icon" />
	<div class="hsk-link-body">
		<strong>Haushaltssicherungskonzept 2026</strong>
		Die Grundsteuer B ist eine von 97 Maßnahmen. Sie macht rund 44 % des
		Konsolidierungsvolumens aus, 56 % entfallen auf andere Maßnahmen. Wo die Stadt
		mehr einnimmt und wo sie spart, zeigt die HSK-Seite.
	</div>
	<ArrowRight class="hsk-link-arrow" />
</a>-->

<!-- Year Selector -->
<section class="section">
	<div class="year-selector">
		<label for="year-select" class="field-label">Jahr auswählen</label>
		<select id="year-select" value={selectedYear} onchange={(e) => setYear(Number(e.currentTarget.value))} class="form-select form-select-compact">
			{#each [...taxYears].reverse() as y (y)}
				<option value={y}>{y}</option>
			{/each}
		</select>
	</div>
</section>

<!-- Tax Composition: Donut + Table -->
<section class="section">
	<AnchorHeading level={3} id="zusammensetzung">Zusammensetzung der Steuereinnahmen {selectedYear}</AnchorHeading>
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

<!-- Grundsteuer B: Vertiefung auf /grundsteuer -->
<section class="section">
	<a href="/grundsteuer" class="hsk-link-box">
		<Info class="hsk-link-icon" />
		<div class="hsk-link-body">
			<strong>Grundsteuer B: die ganze Geschichte</strong>
			Warum der Hebesatz so hoch ist, wie er im Kreis dasteht und warum er allein wenig über die
			tatsächliche Belastung aussagt – ausführlich auf der Grundsteuer-Seite.
		</div>
		<ArrowRight class="hsk-link-arrow" />
	</a>
</section>

<!-- Hebesatz Development Rödermark: Grundsteuer B + Gewerbesteuer -->
<section class="section">
	<AnchorHeading level={3} id="hebesatz-entwicklung">Hebesatz-Entwicklung Rödermark</AnchorHeading>
	<div class="hebesatz-history-grid">
		<div class="card card-padded">
			<h4 class="card-subtitle">Grundsteuer B</h4>
			<HebesatzHistoryChart
				history={roedermarkGrundsteuerBHistory}
				split={{ year: 2025, neutral: 800 }}
				newSystemFrom={2025}
			/>
		</div>
		<div class="card card-padded">
			<h4 class="card-subtitle">Gewerbesteuer</h4>
			<HebesatzHistoryChart
				history={roedermarkGewerbesteuerHistory}
			/>
		</div>
	</div>
</section>

<!-- Hebesatz Comparison: Gewerbesteuer -->
<section class="section">
	<AnchorHeading level={3} id="hebesaetze-vergleich">Gewerbesteuer im Vergleich – Kreis Offenbach</AnchorHeading>
	<div class="card card-padded">
		<div class="bar-chart">
			{#each gewerbesteuerComparison as entry (entry.kommune)}
				{@const isRoedermark = entry.kommune === 'Rödermark'}
				<div class="bar-row" class:bar-row-highlight={isRoedermark}>
					<span class="bar-label">{entry.kommune}{#if entry.carried}<span class="carried-year"> ({entry.actualYear})</span>{/if}{#if entry.status === 'geplant'}<span class="status-geplant"> (geplant)</span>{/if}</span>
					<div class="bar-track-h">
						<div
							class="bar-fill"
							class:bar-fill-highlight={isRoedermark}
							style="width: {(entry.hebesatz / maxGewerbesteuer) * 100}%"
						></div>
					</div>
				<span class="bar-value">{fmtHS(entry.hebesatz, gewerbesteuerHasDecimals)} %</span>
					<span class="bar-source">
						{#if entry.quelle_url}
							<SourceCitation condensed description={`${entry.kommune} ${entry.actualYear}`} links={sourceLinks(entry)} />
						{/if}
					</span>
				</div>
			{/each}
		</div>
	</div>
	<p class="comparison-legend">
		<span class="legend-item"><span class="legend-swatch legend-swatch-carried"></span> (Jahr) = letzter bekannter Wert aus einem früheren Jahr, fortgeschrieben</span>
		<span class="legend-item">(geplant) = vorgeschlagener, vom Stadtparlament noch nicht beschlossener Wert</span>
	</p>
</section>

<!-- Simulator: What-if Slider -->
<section class="section">
	<AnchorHeading level={3} id="was-waere-wenn"><SlidersHorizontal /> Was wäre wenn?</AnchorHeading>
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
	<AnchorHeading level={3} id="zeitverlauf">Steuereinnahmen im Zeitverlauf</AnchorHeading>
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
	.page-intro { margin-bottom: 2rem; max-width: 48rem; color: var(--gray-600); }

	.hsk-link-box {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 2rem;
		padding: 1rem 1.25rem;
		border-radius: 0.625rem;
		background: var(--brand-50, #eff6ff);
		border: 1px solid var(--brand-200, #bfdbfe);
		color: var(--gray-700);
		text-decoration: none;
		font-size: 0.9rem;
		line-height: 1.5;
		transition: background 0.15s, border-color 0.15s;
	}
	.hsk-link-box:hover {
		background: var(--brand-100, #dbeafe);
		border-color: var(--brand-300, #93c5fd);
	}
	:global(.hsk-link-icon) {
		flex-shrink: 0;
		width: 1.75rem;
		height: 1.75rem;
		color: var(--brand-700);
	}
	.hsk-link-body strong {
		color: var(--gray-900);
	}
	:global(.hsk-link-arrow) {
		flex-shrink: 0;
		width: 1.25rem;
		height: 1.25rem;
		color: var(--brand-700);
		transition: transform 0.15s;
	}
	.hsk-link-box:hover :global(.hsk-link-arrow) {
		transform: translateX(3px);
	}
	.section { margin-bottom: 2.5rem; }
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
	.col-right { text-align: right !important; }
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
		min-width: 0;
	}
	@media (min-width: 640px) {
		.hebesatz-history-grid { grid-template-columns: 1fr 1fr; }
	}

	/* Comparison bars */
	.bar-chart {
		display: flex; flex-direction: column; gap: 0.375rem;
	}
	.bar-row {
		display: grid; grid-template-columns: 6rem 1fr 4rem auto; gap: 0.25rem; align-items: center;
	}
	@media (min-width: 640px) {
		.bar-row { grid-template-columns: 10rem 1fr 5rem auto; gap: 0.5rem; }
	}
	.bar-row-highlight { font-weight: 600; }
	.bar-label {
		font-size: 0.6875rem; color: var(--gray-600);
		overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
	}
	@media (min-width: 640px) {
		.bar-label { font-size: 0.8125rem; }
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
		font-size: 0.6875rem; color: var(--gray-600); text-align: right; white-space: nowrap;
	}
	@media (min-width: 640px) {
		.bar-value { font-size: 0.8125rem; }
	}
	.bar-row-highlight .bar-value { color: var(--brand-700); font-weight: 700; }
	.bar-source {
		display: inline-flex; align-items: center; min-width: 1rem;
	}
	.carried-year {
		font-size: 0.6875rem; font-weight: 400; color: var(--gray-400);
	}
	.status-geplant {
		font-size: 0.6875rem; font-weight: 600; color: var(--amber-600, #d97706);
	}
	.comparison-legend {
		display: flex; flex-wrap: wrap; gap: 0.25rem 1.25rem;
		margin-top: 1rem; font-size: 0.75rem; color: var(--gray-500);
	}
	.legend-item { display: flex; align-items: center; gap: 0.375rem; }
	.legend-swatch {
		width: 0.75rem; height: 0.75rem; border-radius: 0.1875rem; flex-shrink: 0;
	}
	.legend-swatch-carried { background: var(--gray-200); }

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
