<script lang="ts">
	import type { PageData } from './$types';
	import { formatAmount, formatEur, formatNumber } from '$lib/format';
	import { groupBy, sourceLinksFromItems } from '$lib/data';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import { Coins, TrendingUp, TrendingDown, AlertTriangle, ChevronDown, ChevronRight, Info } from '@lucide/svelte';
	import { SvelteSet, SvelteMap } from 'svelte/reactivity';

	let { data }: { data: PageData } = $props();

	// ─── State ───
	let selectedTh = $state<string>('all');
	let searchQuery = $state('');
	let showOnlyDiscrepancies = $state(false);
	let expandedProjects = $state<SvelteSet<string>>(new SvelteSet());

	// ─── Derived: filter investments ───
	let filteredInvestments = $derived.by(() => {
		let items = data.investments;

		if (selectedTh !== 'all') {
			items = items.filter((i) => i.teilhaushalt_nr === selectedTh);
		}

		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase().trim();
			items = items.filter((i) => i.bezeichnung.toLowerCase().includes(q));
		}

		return items;
	});

	// ─── Derived: build project-level summary ───
	// Only compute deviation for years where ist data exists (past years).
	// Future plan-only years are shown but excluded from deviation calculation.
	let istYearsSet = $derived(new Set(data.summary.ist_years));

	interface ProjectSummary {
		key: string;
		bezeichnung: string;
		thNr: string;
		thName: string;
		totalIst: number;
		totalPlan: number;
		/** Plan sum only for years that have ist data globally (= past years) */
		comparablePlan: number;
		/** Ist sum only for those same years */
		comparableIst: number;
		/** ist - plan for comparable years only */
		discrepancy: number;
		discrepancyPct: number;
		yearData: SvelteMap<number, { ist: number | null; plan: number | null }>;
		allYears: number[];
		hasIst: boolean;
		hasPlan: boolean;
		/** Does this project have plan data in comparable (past) years? */
		hasComparableData: boolean;
	}

	let projects = $derived.by(() => {
		const byKey = groupBy(filteredInvestments, (i) => i.line_item_key);
		const result: ProjectSummary[] = [];

		for (const [key, items] of byKey) {
			const yearData = new SvelteMap<number, { ist: number | null; plan: number | null }>();
			let totalIst = 0;
			let totalPlan = 0;
			let comparableIst = 0;
			let comparablePlan = 0;
			let hasIst = false;
			let hasPlan = false;

			for (const item of items) {
				if (!yearData.has(item.year)) {
					yearData.set(item.year, { ist: null, plan: null });
				}
				const yd = yearData.get(item.year)!;
				if (item.amount_type === 'ist') {
					yd.ist = item.amount;
					totalIst += item.amount;
					hasIst = true;
				} else {
					yd.plan = item.amount;
					totalPlan += item.amount;
					hasPlan = true;
					// Only count plan towards comparable if this year has ist data globally
					if (istYearsSet.has(item.year)) {
						comparablePlan += item.amount;
					}
				}
			}

			// Ist data only exists in ist years, so comparableIst = totalIst
			comparableIst = totalIst;

			const hasComparableData = hasIst || (hasPlan && comparablePlan !== 0);
			const discrepancy = hasComparableData && comparablePlan !== 0 ? comparableIst - comparablePlan : 0;
			const discrepancyPct = comparablePlan !== 0 ? (discrepancy / Math.abs(comparablePlan)) * 100 : 0;

			result.push({
				key,
				bezeichnung: items[0].bezeichnung,
				thNr: items[0].teilhaushalt_nr ?? '',
				thName: items[0].teilhaushalt_name ?? '',
				totalIst,
				totalPlan,
				comparableIst,
				comparablePlan,
				discrepancy,
				discrepancyPct,
				yearData,
				allYears: [...yearData.keys()].sort((a, b) => a - b),
				hasIst,
				hasPlan,
				hasComparableData
			});
		}

		// Optionally filter to only projects with significant discrepancies
		let filtered = result;
		if (showOnlyDiscrepancies) {
			filtered = result.filter(
				(p) => p.hasComparableData && p.comparablePlan !== 0 && Math.abs(p.discrepancyPct) > 20
			);
		}

		// Sort by absolute discrepancy (most interesting first)
		filtered.sort((a, b) => Math.abs(b.discrepancy) - Math.abs(a.discrepancy));

		return filtered;
	});

	// ─── Derived: global stats ───
	let stats = $derived.by(() => {
		const allProjects = groupBy(data.investments, (i) => i.line_item_key);
		let totalIst = 0;
		let totalPlan = 0;
		let countWithBothTypes = 0;
		let overBudgetCount = 0;
		let underBudgetCount = 0;
		let notStartedCount = 0;
		let futureOnlyCount = 0;

		for (const [, items] of allProjects) {
			let pIst = 0;
			let pComparablePlan = 0;
			let hIst = false;
			let hPlan = false;
			let hComparablePlan = false;

			for (const item of items) {
				if (item.amount_type === 'ist') {
					pIst += item.amount;
					totalIst += item.amount;
					hIst = true;
				} else {
					totalPlan += item.amount;
					hPlan = true;
					if (istYearsSet.has(item.year)) {
						pComparablePlan += item.amount;
						hComparablePlan = true;
					}
				}
			}

			// Only compare deviation for years where ist data could exist
			if (hIst && hComparablePlan) {
				countWithBothTypes++;
				const diff = pIst - pComparablePlan;
				if (Math.abs(diff) > 1000 && Math.abs(pComparablePlan) > 0) {
					if (diff < -1000) overBudgetCount++;
					if (diff > 1000) underBudgetCount++;
				}
			}

			// Only plan in future years, no ist and no comparable plan
			if (hPlan && !hIst && !hComparablePlan) {
				futureOnlyCount++;
			} else if (hPlan && !hIst && hComparablePlan) {
				notStartedCount++;
			}
		}

		return {
			totalProjects: allProjects.size,
			totalIst,
			totalPlan,
			countWithBothTypes,
			overBudgetCount,
			underBudgetCount,
			notStartedCount,
			futureOnlyCount
		};
	});

	// ─── Pagination ───
	let pageNum = $state(0);
	const pageSize = 30;
	let totalPages = $derived(Math.ceil(projects.length / pageSize));
	let pagedProjects = $derived(projects.slice(pageNum * pageSize, (pageNum + 1) * pageSize));

	// Reset page on filter change
	$effect(() => {
		void selectedTh;
		void searchQuery;
		void showOnlyDiscrepancies;
		pageNum = 0;
	});

	function toggleProject(key: string) {
		if (expandedProjects.has(key)) {
			expandedProjects.delete(key);
		} else {
			expandedProjects.add(key);
		}
	}

	let planOnlySet = $derived(new Set(data.summary.plan_only_years));

	let investSourceLinks = $derived(
		sourceLinksFromItems(data.investments, data.documents)
	);
</script>

<h2 class="page-title">
	<Coins class="page-icon" /> Investitionsprogramm
</h2>
<p class="page-intro">
	Einzelne Investitionsprojekte der Stadt Rödermark – gruppiert nach Teilhaushalten.
	Abweichungen zwischen Plan und Ist werden nur für vergangene Jahre berechnet,
	in denen bereits Ist-Daten vorliegen.
</p>
<SourceCitation
	description="Investitionsprogramm"
	links={investSourceLinks}
/>

<!-- KPI Cards -->
<section class="kpi-grid section">
	<div class="kpi-card">
		<p class="kpi-label">Investitionsprojekte</p>
		<p class="kpi-value text-brand-700">{formatNumber(stats.totalProjects)}</p>
		<p class="kpi-sub">über alle Teilhaushalte</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Vergleichbar</p>
		<p class="kpi-value text-brand-700">{formatNumber(stats.countWithBothTypes)}</p>
		<p class="kpi-sub">Projekte mit Ist- &amp; Plan-Daten</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Teurer als geplant</p>
		<p class="kpi-value text-red-600">{formatNumber(stats.overBudgetCount)}</p>
		<p class="kpi-sub">Ist-Ausgaben &gt; Plan (vergangene Jahre)</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Nur Zukunftsplanung</p>
		<p class="kpi-value text-gray-500">{formatNumber(stats.futureOnlyCount)}</p>
		<p class="kpi-sub">Noch keine Ist-Daten möglich</p>
	</div>
</section>

<div class="info-box info-box-blue section">
	<Info class="info-icon" />
	<div>
		<strong>Datenstand:</strong> Ist-Ergebnisse liegen bis einschließlich {data.summary.last_ist_year} vor.
		Der Jahresabschluss {(data.summary.last_ist_year ?? 0) + 1} ist noch nicht veröffentlicht –
		ab {(data.summary.last_ist_year ?? 0) + 1} sind nur Planwerte verfügbar.
		Abweichungen werden daher nur für vergangene Jahre berechnet.
	</div>
</div>

<!-- Filters -->
<div class="card filter-bar cols-4 section">
	<div>
		<label for="search-inv" class="filter-label">Suche</label>
		<input
			id="search-inv"
			type="search"
			placeholder="Projektbezeichnung…"
			bind:value={searchQuery}
			class="form-input"
		/>
	</div>
	<div>
		<label for="filter-th" class="filter-label">Teilhaushalt</label>
		<select id="filter-th" bind:value={selectedTh} class="form-select">
			<option value="all">Alle Teilhaushalte</option>
			{#each data.teilhaushalte as th}
				<option value={th.nr}>TH {th.nr} – {th.name}</option>
			{/each}
		</select>
	</div>
	<div class="filter-checkbox-wrap">
		<label class="filter-checkbox">
			<input type="checkbox" bind:checked={showOnlyDiscrepancies} />
			Nur Abweichungen &gt;&nbsp;20 %
		</label>
	</div>
	<div class="filter-count">
		{projects.length.toLocaleString('de-DE')} Projekte
	</div>
</div>

<!-- Project List -->
<div class="project-list">
	{#each pagedProjects as project (project.key)}
		{@const isExpanded = expandedProjects.has(project.key)}
		<div class="project-card">
			<!-- Project Header -->
			<div
				role="button"
				tabindex="0"
				class="project-header"
				onclick={() => toggleProject(project.key)}
				onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleProject(project.key); } }}
			>
				<span class="chevron">
					{#if isExpanded}
						<ChevronDown class="chevron-icon" />
					{:else}
						<ChevronRight class="chevron-icon" />
					{/if}
				</span>

				<div class="project-info">
					<div class="project-name-row">
						<span class="project-name">{project.bezeichnung}</span>
						{#if project.thNr}
							<span class="badge badge-gray">TH {project.thNr}</span>
						{/if}
					</div>
					<div class="project-meta">
						{#if project.hasIst}
							<span class="meta-item">
								<span class="dot bg-green-500"></span>
								Ist: {formatAmount(project.totalIst)}
							</span>
						{/if}
						{#if project.hasPlan}
							<span class="meta-item">
								<span class="dot bg-blue-500"></span>
								Plan: {formatAmount(project.comparablePlan)}
								{#if project.totalPlan !== project.comparablePlan}
									<span class="text-gray-400" title="Gesamtplan inkl. Folgejahre: {formatAmount(project.totalPlan)}">(ges. {formatAmount(project.totalPlan)})</span>
								{/if}
							</span>
						{/if}
						{#if project.hasComparableData && project.comparablePlan !== 0 && Math.abs(project.discrepancyPct) > 5}
							{@const overBudget = project.discrepancy < 0}
							<span class="meta-item discrepancy {overBudget ? 'text-red-600' : 'text-amber-600'}">
								{#if overBudget}
									<TrendingUp class="disc-icon" />
								{:else}
									<TrendingDown class="disc-icon" />
								{/if}
								{overBudget ? '+' : ''}{Math.abs(project.discrepancyPct).toFixed(0)} % Abw.
							</span>
						{/if}
						{#if !project.hasIst && !project.hasComparableData && project.hasPlan}
							<span class="meta-item text-gray-400">
								<AlertTriangle class="disc-icon" />
								Nur Planung (Folgejahre)
							</span>
						{:else if !project.hasIst && project.hasComparableData}
							<span class="meta-item text-amber-600">
								<AlertTriangle class="disc-icon" />
								Geplant, nicht umgesetzt
							</span>
						{/if}
					</div>
				</div>
			</div>

			<!-- Expanded: Year-by-Year Detail -->
			{#if isExpanded}
				<div class="project-detail">
					<div class="scroll-x">
						<table>
							<thead>
								<tr>
									<th>Jahr</th>
									<th class="col-number">Plan</th>
									<th class="col-number">Ist</th>
									<th class="col-number">Δ (Ist − Plan)</th>
								</tr>
							</thead>
							<tbody>
								{#each project.allYears as year (year)}
									{@const yd = project.yearData.get(year)}
									{@const delta = yd && yd.ist !== null && yd.plan !== null ? yd.ist - yd.plan : null}
									<tr class="{planOnlySet.has(year) ? 'plan-only' : ''}">
										<td class="tabular-nums" style="font-weight:500">
											{year}
											{#if planOnlySet.has(year)}<span class="plan-marker">P</span>{/if}
										</td>
										<td class="col-number text-blue-600">
											{yd?.plan !== null && yd?.plan !== undefined ? formatEur(yd.plan) : '–'}
										</td>
										<td class="col-number text-green-700">
											{yd?.ist !== null && yd?.ist !== undefined ? formatEur(yd.ist) : '–'}
										</td>
										<td class="col-number"
											style="color: {delta !== null ? (delta < -100 ? 'var(--red-600)' : delta > 100 ? 'var(--amber-600)' : 'var(--gray-500)') : 'var(--gray-300)'}; {delta !== null && Math.abs(delta) > 100 ? 'font-weight:500' : ''}">
											{#if delta !== null}
												{delta > 0 ? '+' : ''}{formatEur(delta)}
											{:else}
												–
											{/if}
										</td>
									</tr>
								{/each}
							</tbody>
							<!-- Totals -->
							{#if project.allYears.length > 1}
								<tfoot>
									{#if project.totalPlan !== project.comparablePlan}
										<!-- Subtotal for comparable (past) years -->
										<tr class="comparable-row">
											<td>Bisherige Jahre</td>
											<td class="col-number text-blue-700">{project.comparablePlan !== 0 ? formatEur(project.comparablePlan) : '–'}</td>
											<td class="col-number text-green-800">{project.hasIst ? formatEur(project.comparableIst) : '–'}</td>
											<td class="col-number"
												style="color: {project.discrepancy < -100 ? 'var(--red-700)' : project.discrepancy > 100 ? 'var(--amber-600)' : 'var(--gray-600)'}">
												{#if project.hasComparableData && project.comparablePlan !== 0}
													{project.discrepancy > 0 ? '+' : ''}{formatEur(project.discrepancy)}
													<span style="color:var(--gray-400)">({project.discrepancyPct > 0 ? '+' : ''}{project.discrepancyPct.toFixed(0)} %)</span>
												{:else}
													–
												{/if}
											</td>
										</tr>
										<!-- Grand total -->
										<tr>
											<td>Gesamt (inkl. Planung)</td>
											<td class="col-number text-blue-600" style="color:var(--gray-500)">{project.hasPlan ? formatEur(project.totalPlan) : '–'}</td>
											<td class="col-number text-green-700" style="color:var(--gray-500)">{project.hasIst ? formatEur(project.totalIst) : '–'}</td>
											<td class="col-number" style="color:var(--gray-400)">–</td>
										</tr>
									{:else}
										<tr>
											<td>Summe</td>
											<td class="col-number text-blue-700">{project.hasPlan ? formatEur(project.totalPlan) : '–'}</td>
											<td class="col-number text-green-800">{project.hasIst ? formatEur(project.totalIst) : '–'}</td>
											<td class="col-number"
												style="color: {project.discrepancy < -100 ? 'var(--red-700)' : project.discrepancy > 100 ? 'var(--amber-600)' : 'var(--gray-600)'}">
												{#if project.hasComparableData && project.comparablePlan !== 0}
													{project.discrepancy > 0 ? '+' : ''}{formatEur(project.discrepancy)}
													<span style="color:var(--gray-400)">({project.discrepancyPct > 0 ? '+' : ''}{project.discrepancyPct.toFixed(0)} %)</span>
												{:else}
													–
												{/if}
											</td>
										</tr>
									{/if}
								</tfoot>
							{/if}
						</table>
					</div>
				</div>
			{/if}
		</div>
	{/each}
</div>

<!-- Pagination -->
{#if totalPages > 1}
	<div class="pagination">
		<button disabled={pageNum === 0} onclick={() => { pageNum = Math.max(0, pageNum - 1); }}>← Zurück</button>
		<span class="page-info">Seite {pageNum + 1} von {totalPages}</span>
		<button disabled={pageNum >= totalPages - 1} onclick={() => { pageNum = Math.min(totalPages - 1, pageNum + 1); }}>Weiter →</button>
	</div>
{/if}

<style>
	.page-title {
		display: flex; align-items: center; gap: 0.75rem;
		margin-bottom: 1.5rem; font-size: 1.5rem; font-weight: 700; color: var(--gray-900);
	}
	:global(.page-icon) { width: 1.75rem; height: 1.75rem; }
	.page-intro { margin-bottom: 2rem; max-width: 48rem; color: var(--gray-600); }
	.section { margin-bottom: 2rem; }
	.filter-label { display: block; font-size: 0.75rem; font-weight: 500; color: var(--gray-500); }
	.filter-checkbox-wrap { display: flex; align-items: flex-end; }
	.filter-checkbox { display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem; color: var(--gray-600); }
	.filter-count { display: flex; align-items: flex-end; font-size: 0.875rem; color: var(--gray-500); }
	.project-list { display: flex; flex-direction: column; gap: 0.5rem; }
	.chevron { margin-top: 0.125rem; flex-shrink: 0; color: var(--gray-400); }
	:global(.chevron-icon) { width: 1rem; height: 1rem; }
	:global(.disc-icon) { width: 0.875rem; height: 0.875rem; }
	.project-info { min-width: 0; flex: 1; }
	.project-name-row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; }
	.project-name { font-weight: 500; color: var(--gray-900); }
	.project-meta {
		margin-top: 0.25rem; display: flex; flex-wrap: wrap;
		align-items: center; gap: 0.75rem; font-size: 0.75rem; color: var(--gray-500);
	}
	.meta-item { display: flex; align-items: center; gap: 0.25rem; }
	.discrepancy { font-weight: 500; }
	.page-info { font-size: 0.875rem; color: var(--gray-500); }
	.comparable-row td { font-weight: 600; }
</style>
