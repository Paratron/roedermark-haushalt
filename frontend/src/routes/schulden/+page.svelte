<script lang="ts">
	import type { PageData } from './$types';
	import { formatAmount, formatEur } from '$lib/format';
	import { groupBy } from '$lib/data';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import { Landmark, Info, ChevronDown, ChevronRight, HandCoins, ExternalLink } from '@lucide/svelte';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';
	import SocialMeta from '$lib/components/SocialMeta.svelte';
	import { SvelteSet, SvelteMap } from 'svelte/reactivity';

	let { data }: { data: PageData } = $props();

	const { kpis, summary } = data;

	// ─── TH14 detail expand/collapse ───
	let expandedProjects = $state<SvelteSet<string>>(new SvelteSet());

	function toggleProject(key: string) {
		if (expandedProjects.has(key)) {
			expandedProjects.delete(key);
		} else {
			expandedProjects.add(key);
		}
	}

	// ─── Build project-level summary from TH14 financing items ───
	interface ProjectSummary {
		key: string;
		bezeichnung: string;
		thNr: string;
		thName: string;
		totalIst: number;
		totalPlan: number;
		yearData: SvelteMap<number, { ist: number | null; plan: number | null }>;
		allYears: number[];
		hasIst: boolean;
		hasPlan: boolean;
	}

	let projects = $derived.by(() => {
		const byKey = groupBy(data.financing, (i) => i.line_item_key);
		const result: ProjectSummary[] = [];

		for (const [key, items] of byKey) {
			const yearData = new SvelteMap<number, { ist: number | null; plan: number | null }>();
			let totalIst = 0;
			let totalPlan = 0;
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
				}
			}

			result.push({
				key,
				bezeichnung: items[0].bezeichnung,
				thNr: items[0].teilhaushalt_nr ?? '',
				thName: items[0].teilhaushalt_name ?? '',
				totalIst,
				totalPlan,
				yearData,
				allYears: [...yearData.keys()].sort((a, b) => a - b),
				hasIst,
				hasPlan
			});
		}

		result.sort((a, b) => Math.abs(b.totalPlan) - Math.abs(a.totalPlan));
		return result;
	});

	let planOnlySet = $derived(new Set(summary.plan_only_years));
</script>

<SocialMeta
	title="Schulden & Zinsen"
	description="Verschuldung der Stadt Rödermark – Kreditaufnahme, Tilgung und Zinsbelastung im Zeitverlauf seit 1986."
	path="/schulden"
/>

<AnchorHeading level={2} id="schulden-zinsen">
	<HandCoins /> Schulden &amp; Zinsen
</AnchorHeading>
<p class="page-intro">
	Wie hoch ist die Verschuldung der Stadt Rödermark? Diese Seite zeigt Kreditaufnahme, Tilgung
	und Zinsbelastung im Zeitverlauf – basierend auf den Finanzhaushaltsdaten.
</p>

<!-- KPI Cards -->
<section class="kpi-grid section">
	<div class="kpi-card">
		<p class="kpi-label">Schuldenstand</p>
		<p class="kpi-value">
			{formatAmount(kpis.schuldenstandAktuell)}
		</p>
		<p class="kpi-sub">Ist {kpis.lastIstYear} · inkl. Investitionskredite KBR</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Pro-Kopf-Verschuldung</p>
		<p class="kpi-value">
			{kpis.proKopfAktuell.toLocaleString('de-DE', { style: 'currency', currency: 'EUR' })}
		</p>
		<p class="kpi-sub">Ist {kpis.lastIstYear} · Schulden je Einwohner</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Netto-Neuverschuldung</p>
		<p class="kpi-value">
			{formatAmount(kpis.nettoNeuverschuldung)}
		</p>
		<p class="kpi-sub">Ist {kpis.lastIstYear} · Kredit − Tilgung</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Zinsbelastung</p>
		<p class="kpi-value">
			{formatAmount(Math.abs(kpis.zinsen))}
		</p>
		<p class="kpi-sub">Ist {kpis.lastIstYear} · Zinszahlungen gesamt</p>
	</div>
</section>

<!-- Info Box -->
<div class="info-box info-box-amber section-lg">
	<Info class="info-icon" />
	<div>
		<strong>Zur Einordnung:</strong> Der Schuldenstand umfasst nur <em>Investitionskredite</em> (inkl. KBR)
		und stammt aus der offiziellen Schuldenstatistik der Haushaltspläne.
		Rödermark hat 2013 den <a href="https://finanzen.hessen.de/kommunen/kommunaler-schutzschirm" target="_blank"><em>Schutzschirmvertrag</em> mit dem Land Hessen <ExternalLink style="display: inline-block" size={12} /></a> geschlossen,
		der die Stadt zu Haushaltskonsolidierung verpflichtet und Entschuldungshilfen gewährt.
		Der Schuldenabbau 2012–2017 ist Folge dieses Vertrags.
		Die Plan-Werte ab {summary.plan_only_years?.[0] ?? 2025} spiegeln geplante Kreditaufnahmen für Großprojekte wider
		(u.&thinsp;a. Schulneubauten), deren Finanzierung teils noch nicht abschließend gesichert ist.
	</div>
</div>

<!-- Chart 2: Schuldenstand historisch -->
<section class="chart-section">
	<div class="chart-card">
		<TimeSeriesChart
			title="Schuldenstand seit 1986"
			series={data.schuldenstandSeries}
			yLabel="Mio. €"
			planOnlyYears={data.schuldenPlanOnlyYears}
			lastIstYear={data.schuldenLastIstYear}
			fixedColor="red"
		/>
	</div>
	<p class="chart-note">
		Schuldenstand inkl. KBR (nur Investitionskredite) zum 31.12. des jeweiligen Jahres.
		Gut sichtbar: der Schuldenabbau 2012–2017 im Rahmen des Schutzschirmvertrags und der starke Anstieg nach 2023.
	</p>
	<SourceCitation
		description="Schuldenstatistik (inkl. KBR)"
		links={data.sourceLinks.schuldenstatistik}
	/>
</section>

<!-- Chart 1: Kreditaufnahme vs Tilgung -->
<section class="chart-section">
	<div class="chart-card">
		<TimeSeriesChart
			title="Kreditaufnahme vs. Tilgung"
			series={data.kreditTilgungSeries}
			yLabel="Mio. €"
			planOnlyYears={summary.plan_only_years}
			lastIstYear={summary.last_ist_year}
			multiSeries={true}
		/>
	</div>
	<p class="chart-note">
		Kreditaufnahme = neue Kredite, die die Stadt aufnimmt (positiv, erhöht den Schuldenstand).
		Tilgung = Rückzahlung bestehender Kredite (negativ, senkt den Schuldenstand).
		Die Differenz ergibt die Netto-Neuverschuldung.
	</p>
	<SourceCitation
		description="Finanzhaushalt, Nr. 310 (Kreditaufnahme) und Nr. 320 (Tilgung)"
		links={data.sourceLinks.kreditTilgung}
	/>
</section>

<!-- Chart 3: Zinsbelastung -->
<section class="chart-section">
	<div class="chart-card">
		<TimeSeriesChart
			title="Zinsbelastung"
			series={data.zinsSeries}
			yLabel="Mio. €"
			planOnlyYears={summary.plan_only_years}
			lastIstYear={summary.last_ist_year}
			fixedColor="amber"
		/>
	</div>
	<p class="chart-note">
		Zinsen und ähnliche Auszahlungen (FH Nr. 160). Zeigt die jährliche Zinsbelastung für alle kommunalen Kredite.
	</p>
	<SourceCitation
		description="Finanzhaushalt, Nr. 160 (Zinsen und ähnliche Auszahlungen)"
		links={data.sourceLinks.zinsen}
	/>
</section>

<!-- Detail Table: TH14 Financing Projects -->
<section>
	<AnchorHeading level={3} id="einzelpositionen">Einzelpositionen im Investitionsprogramm</AnchorHeading>
	<p class="section-sub">
		{projects.length} Positionen aus dem Investitionsprogramm, die sich auf Kreditaufnahme, Tilgung und Darlehen beziehen.
		Aufklappen für die Jahresdetails.
	</p>

	<div class="project-list">
		{#each projects as project (project.key)}
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
									<span class="dot" style="background:{project.totalIst >= 0 ? 'var(--red-500)' : 'var(--emerald-500)'}"></span>
									Ist: {formatAmount(project.totalIst)}
								</span>
							{/if}
							{#if project.hasPlan}
								<span class="meta-item">
									<span class="dot" style="background:{project.totalPlan >= 0 ? 'var(--red-300)' : 'var(--emerald-300)'}"></span>
									Plan: {formatAmount(project.totalPlan)}
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
										<th style="text-align:left">Jahr</th>
										<th style="text-align:right">Plan</th>
										<th style="text-align:right">Ist</th>
										<th style="text-align:right">Δ (Ist − Plan)</th>
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
											<td class="col-number"
												style="color: {yd?.plan !== null && yd?.plan !== undefined ? (yd.plan >= 0 ? 'var(--red-500)' : 'var(--emerald-600)') : 'var(--gray-300)'}">
												{yd?.plan !== null && yd?.plan !== undefined ? formatEur(yd.plan) : '–'}
											</td>
											<td class="col-number"
												style="color: {yd?.ist !== null && yd?.ist !== undefined ? (yd.ist >= 0 ? 'var(--red-600)' : 'var(--emerald-700)') : 'var(--gray-300)'}">
												{yd?.ist !== null && yd?.ist !== undefined ? formatEur(yd.ist) : '–'}
											</td>
											<td class="col-number"
												style="color: {delta !== null ? (Math.abs(delta) > 100 ? (delta < 0 ? 'var(--red-600)' : 'var(--amber-600)') : 'var(--gray-500)') : 'var(--gray-300)'}; {delta !== null && Math.abs(delta) > 100 && delta < 0 ? 'font-weight:500' : ''}">
												{#if delta !== null}
													{delta > 0 ? '+' : ''}{formatEur(delta)}
												{:else}
													–
												{/if}
											</td>
										</tr>
									{/each}
								</tbody>
								{#if project.allYears.length > 1}
									{@const totalDelta = project.hasIst && project.hasPlan ? project.totalIst - project.totalPlan : null}
									<tfoot>
										<tr>
											<td>Summe</td>
											<td class="col-number"
												style="color: {project.hasPlan ? (project.totalPlan >= 0 ? 'var(--red-500)' : 'var(--emerald-600)') : 'var(--gray-300)'}">{project.hasPlan ? formatEur(project.totalPlan) : '–'}</td>
											<td class="col-number"
												style="color: {project.hasIst ? (project.totalIst >= 0 ? 'var(--red-700)' : 'var(--emerald-800)') : 'var(--gray-300)'}">{project.hasIst ? formatEur(project.totalIst) : '–'}</td>
											<td class="col-number"
												style="color: {totalDelta !== null ? (totalDelta < -100 ? 'var(--red-700)' : totalDelta > 100 ? 'var(--amber-600)' : 'var(--gray-600)') : 'var(--gray-300)'}">
												{#if totalDelta !== null}
													{totalDelta > 0 ? '+' : ''}{formatEur(totalDelta)}
												{:else}
													–
												{/if}
											</td>
										</tr>
									</tfoot>
								{/if}
							</table>
						</div>
					</div>
				{/if}
			</div>
		{/each}
	</div>
</section>

<style>
	.page-intro { margin-bottom: 2rem; max-width: 48rem; color: var(--gray-600); }
	.section { margin-bottom: 2rem; }
	.section-lg { margin-bottom: 2.5rem; }
	:global(.info-icon) { width: 1.25rem; height: 1.25rem; margin-top: 0.125rem; flex-shrink: 0; }
	.chart-section { margin-bottom: 2.5rem; }
	.chart-card {
		background: #fff; border-radius: 0.75rem; padding: 1.5rem;
		box-shadow: var(--shadow-sm); border: 1px solid var(--gray-100);
	}
	.chart-note { margin-top: 0.5rem; font-size: 0.75rem; color: var(--gray-400); }
	.section-sub { margin-bottom: 1rem; font-size: 0.875rem; color: var(--gray-500); }
	.project-list { display: flex; flex-direction: column; gap: 0.5rem; }
	.chevron { margin-top: 0.125rem; flex-shrink: 0; color: var(--gray-400); }
	:global(.chevron-icon) { width: 1rem; height: 1rem; }
	.project-info { min-width: 0; flex: 1; }
	.project-name-row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; }
	.project-name { font-weight: 500; color: var(--gray-900); }
	.project-meta {
		margin-top: 0.25rem; display: flex; flex-wrap: wrap;
		align-items: center; gap: 0.75rem; font-size: 0.75rem; color: var(--gray-500);
	}
	.meta-item { display: flex; align-items: center; gap: 0.25rem; }
</style>
