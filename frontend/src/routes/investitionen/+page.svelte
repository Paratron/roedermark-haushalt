<script lang="ts">
	import { tick, onMount } from 'svelte';
	import { browser } from '$app/environment';
	import type { PageData } from './$types';
	import type { SourceLink, InvestmentCommentary, ThemaSummary } from '$lib/types';
	import { formatAmount, formatEur, formatMio, formatNumber } from '$lib/format';
	import { groupBy, sourceLinksFromItems, shortDocLabel } from '$lib/data';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import { Coins, TrendingUp, TrendingDown, AlertTriangle, ChevronDown, ChevronRight, Info, BookOpen } from '@lucide/svelte';
	import { SvelteSet, SvelteMap } from 'svelte/reactivity';

	let { data }: { data: PageData } = $props();

	const cl = data.classification;

	// ─── Tab state ───
	type Tab = 'themen' | 'projekte';
	let activeTab = $state<Tab>('themen');

	// ─── Theme state ───
	let selectedThema = $state<string | null>(null);

	// ─── URL hash ↔ state sync ───
	function parseHash(hash: string) {
		const h = hash.replace(/^#/, '');
		if (h.startsWith('projekt/')) {
			return { tab: 'projekte' as Tab, projectKey: decodeURIComponent(h.slice('projekt/'.length)) };
		}
		if (h === 'projekte') {
			return { tab: 'projekte' as Tab, projectKey: null };
		}
		return { tab: 'themen' as Tab, projectKey: null };
	}

	function buildHash(tab: Tab, projectKey: string | null): string {
		if (projectKey) return `#projekt/${encodeURIComponent(projectKey)}`;
		if (tab === 'projekte') return '#projekte';
		return '#themen';
	}

	function pushHash(tab: Tab, projectKey: string | null = null) {
		if (!browser) return;
		const hash = buildHash(tab, projectKey);
		if (location.hash !== hash) {
			history.pushState(null, '', hash);
		}
	}

	function replaceHash(tab: Tab, projectKey: string | null = null) {
		if (!browser) return;
		const hash = buildHash(tab, projectKey);
		if (location.hash !== hash) {
			history.replaceState(null, '', hash);
		}
	}

	async function applyHash(hash: string) {
		const { tab, projectKey } = parseHash(hash);
		activeTab = tab;
		if (projectKey) {
			selectedThema = null;
			selectedTh = 'all';
			searchQuery = '';
			showOnlyDiscrepancies = false;
			pageNum = 0;
			await tick();
			const idx = projects.findIndex(p => p.key === projectKey);
			if (idx >= 0) {
				pageNum = Math.floor(idx / pageSize);
			}
			expandedProjects.clear();
			expandedProjects.add(projectKey);
			await tick();
			document.getElementById(`project-${projectKey}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
		} else if (tab === 'themen') {
			selectedThema = null;
		}
	}

	onMount(() => {
		if (location.hash) {
			applyHash(location.hash);
		}
		const onPopState = () => applyHash(location.hash);
		window.addEventListener('popstate', onPopState);
		return () => window.removeEventListener('popstate', onPopState);
	});

	// ─── Project view state ───
	let selectedTh = $state<string>('all');
	let searchQuery = $state('');
	let showOnlyDiscrepancies = $state(false);
	let expandedProjects = $state<SvelteSet<string>>(new SvelteSet());

	// ─── Classification data ───
	let typeLabels = $derived(cl?.meta.type_labels ?? {});
	let themaLabels = $derived(cl?.meta.thema_labels ?? {});

	// ─── Per-entry volume: ist if available, otherwise plan ───
	function entryVolume(e: { ist_total: number; plan_total: number }): number {
		return Math.abs(e.ist_total) > 0 ? Math.abs(e.ist_total) : Math.abs(e.plan_total);
	}

	// ─── Per-theme aggregation from entries (not from thema sums) ───
	interface ThemaAgg {
		thema: string;
		label: string;
		istVolume: number;    // sum of abs(ist) for ausgabe entries
		planVolume: number;   // sum of abs(plan) for plan-only ausgabe entries
		totalVolume: number;  // istVolume + planVolume
		countAusgaben: number;
	}

	let themaAgg = $derived.by(() => {
		if (!cl) return [] as ThemaAgg[];
		const map = new Map<string, ThemaAgg>();
		for (const e of cl.entries) {
			if (!e.entry_type.startsWith('ausgabe_')) continue;
			if (!map.has(e.thema)) {
				map.set(e.thema, {
					thema: e.thema,
					label: themaLabels[e.thema] ?? e.thema,
					istVolume: 0,
					planVolume: 0,
					totalVolume: 0,
					countAusgaben: 0,
				});
			}
			const agg = map.get(e.thema)!;
			const ist = Math.abs(e.ist_total);
			const plan = Math.abs(e.plan_total);
			if (ist > 0) {
				agg.istVolume += ist;
			} else if (plan > 0) {
				agg.planVolume += plan;
			}
			agg.countAusgaben++;
		}
		for (const agg of map.values()) {
			agg.totalVolume = agg.istVolume + agg.planVolume;
		}
		return [...map.values()];
	});

	// ─── Max value for bar scaling ───
	let maxThemaVolume = $derived(
		Math.max(...themaAgg.map(t => t.totalVolume), 1)
	);

	// ─── Entries by thema (for detail view) ───
	let themaEntries = $derived.by(() => {
		if (!selectedThema || !cl) return [];
		return cl.entries
			.filter(e => e.thema === selectedThema)
			.sort((a, b) => entryVolume(b) - entryVolume(a));
	});

	// ─── Aggregate totals ───
	let totals = $derived.by(() => {
		if (!cl) return { istAusgaben: 0, planOnlyAusgaben: 0, totalAusgaben: 0, einnahmen: 0, projekte: 0 };
		let istAusgaben = 0, planOnlyAusgaben = 0, einnahmen = 0, projekte = 0;
		for (const e of cl.entries) {
			if (e.entry_type.startsWith('ausgabe_')) {
				const ist = Math.abs(e.ist_total);
				const plan = Math.abs(e.plan_total);
				if (ist > 0) {
					istAusgaben += ist;
				} else if (plan > 0) {
					planOnlyAusgaben += plan;
				}
				projekte++;
			} else {
				// Einnahmen: use ist if available, else plan
				const eIst = Math.abs(e.ist_total);
				const ePlan = Math.abs(e.plan_total);
				einnahmen += eIst > 0 ? eIst : ePlan;
			}
		}
		return { istAusgaben, planOnlyAusgaben, totalAusgaben: istAusgaben + planOnlyAusgaben, einnahmen, projekte };
	});

	// ─── Themen sorted by totalVolume, exclude sonstiges/finanzen ───
	let investmentThemen = $derived(
		themaAgg.filter(t => t.thema !== 'finanzen' && t.thema !== 'sonstiges' && t.totalVolume > 0)
			.sort((a, b) => b.totalVolume - a.totalVolume)
	);

	// ─── Type aggregation for "Woher kommt das Geld?" ───
	let financeBreakdown = $derived.by(() => {
		if (!cl) return [];
		const byType = new Map<string, { type: string; label: string; total: number; count: number }>();
		for (const e of cl.entries) {
			if (!e.entry_type.startsWith('einnahme_')) continue;
			const t = e.entry_type;
			if (!byType.has(t)) {
				byType.set(t, { type: t, label: typeLabels[t] ?? t, total: 0, count: 0 });
			}
			const b = byType.get(t)!;
			// Use ist if available, otherwise plan (mirrors entryVolume logic)
			const vol = Math.abs(e.ist_total) > 0 ? Math.abs(e.ist_total) : Math.abs(e.plan_total);
			b.total += vol;
			b.count++;
		}
		return [...byType.values()].sort((a, b) => b.total - a.total);
	});



	// ─── Lookup: line_item_key → raw LineItems (for source links) ───
	let investmentsByKey = $derived.by(() => {
		const map = new Map<string, typeof data.investments>();
		for (const item of data.investments) {
			const k = item.line_item_key;
			if (!map.has(k)) map.set(k, []);
			map.get(k)!.push(item);
		}
		return map;
	});

	function sourceLinksForEntry(key: string) {
		const items = investmentsByKey.get(key) ?? [];
		return sourceLinksFromItems(items, data.documents);
	}

	// ──── Project detail view (existing logic, but refactored) ────
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

	let istYearsSet = $derived(new Set(data.summary.ist_years));

	interface ProjectSummary {
		key: string;
		bezeichnung: string;
		thNr: string;
		thName: string;
		sourceLinks: SourceLink[];
		totalIst: number;
		totalPlan: number;
		comparablePlan: number;
		comparableIst: number;
		discrepancy: number;
		discrepancyPct: number;
		yearData: SvelteMap<number, { ist: number | null; plan: number | null }>;
		allYears: number[];
		hasIst: boolean;
		hasPlan: boolean;
		hasComparableData: boolean;
	}

	let projects = $derived.by(() => {
		const byKey = groupBy(filteredInvestments, (i) => i.line_item_key);
		const result: ProjectSummary[] = [];

		for (const [key, items] of byKey) {
			const sourceLinks = sourceLinksFromItems(items, data.documents);
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
					if (istYearsSet.has(item.year)) {
						comparablePlan += item.amount;
					}
				}
			}

			comparableIst = totalIst;
			const hasComparableData = hasIst || (hasPlan && comparablePlan !== 0);
			const discrepancy = hasComparableData && comparablePlan !== 0 ? comparableIst - comparablePlan : 0;
			const discrepancyPct = comparablePlan !== 0 ? (discrepancy / Math.abs(comparablePlan)) * 100 : 0;

			result.push({
				key, bezeichnung: items[0].bezeichnung,
				thNr: items[0].teilhaushalt_nr ?? '', thName: items[0].teilhaushalt_name ?? '',
				sourceLinks, totalIst, totalPlan, comparableIst, comparablePlan,
				discrepancy, discrepancyPct, yearData,
				allYears: [...yearData.keys()].sort((a, b) => a - b),
				hasIst, hasPlan, hasComparableData
			});
		}

		let filtered = result;
		if (showOnlyDiscrepancies) {
			filtered = result.filter(
				(p) => p.hasComparableData && p.comparablePlan !== 0 && Math.abs(p.discrepancyPct) > 20
			);
		}
		filtered.sort((a, b) => Math.abs(b.discrepancy) - Math.abs(a.discrepancy));
		return filtered;
	});

	// ─── Pagination ───
	let pageNum = $state(0);
	const pageSize = 30;
	let totalPages = $derived(Math.ceil(projects.length / pageSize));
	let pagedProjects = $derived(projects.slice(pageNum * pageSize, (pageNum + 1) * pageSize));

	$effect(() => {
		void selectedTh; void searchQuery; void showOnlyDiscrepancies;
		pageNum = 0;
	});

	function toggleProject(key: string) {
		if (expandedProjects.has(key)) expandedProjects.delete(key);
		else expandedProjects.add(key);
	}

	let planOnlySet = $derived(new Set(data.summary.plan_only_years));

	// ─── Commentary matching ───
	const STOP_WORDS = new Set([
		'allgemein', 'ausbau', 'ober', 'roden', 'urberach', 'unter', 'straße',
		'dienst', 'anlage', 'halle', 'haus', 'stadt', 'feuerwehr', 'kinder',
		'anschaffung', 'anschaffungen', 'ausstattung', 'erweiterung', 'maßnahmen',
		'bewegliches', 'bewegl', 'investitionen', 'auszahlungen', 'einzahlungen',
		'zuwendung', 'zuwendungen', 'erstattung', 'tilgung', 'lizenzen',
		'darlehen', 'krediten', 'verkauf', 'friedhof', 'softwareanschaffungen',
	]);

	function findCommentary(bezeichnung: string): InvestmentCommentary[] {
		if (!data.commentary?.length) return [];
		const norm = (s: string) => s.toLowerCase().replace(/[„""'\-–.]/g, ' ').replace(/\s+/g, ' ').trim();
		const projName = norm(bezeichnung);
		if (projName.length < 5) return [];
		const words = projName.split(' ').filter(w => w.length > 4 && !STOP_WORDS.has(w));
		return data.commentary.filter(c => {
			const cText = norm(c.text);
			if (cText.includes(projName)) return true;
			if (words.length >= 2) {
				const hits = words.filter(w => cText.includes(w)).length;
				if (hits >= 2 && hits / words.length >= 0.8) return true;
			}
			return false;
		}).sort((a, b) => b.year - a.year);
	}

	function commentaryPdfLink(c: InvestmentCommentary): string | null {
		const doc = data.documents.find(d => d.document_id === c.document_id);
		if (!doc?.filename) return null;
		return `/pdfs/${doc.filename}#page=${c.page_start}`;
	}

	function barWidth(value: number, max: number): string {
		if (max === 0) return '0%';
		return `${Math.min(100, (Math.abs(value) / max) * 100)}%`;
	}

	function selectThema(thema: string) {
		if (selectedThema === thema) {
			selectedThema = null;
		} else {
			selectedThema = thema;
		}
		replaceHash('themen');
	}

	async function goToProject(key: string) {
		pushHash('projekte', key);
		selectedThema = null;
		activeTab = 'projekte';
		selectedTh = 'all';
		searchQuery = '';
		showOnlyDiscrepancies = false;
		pageNum = 0;
		await tick();
		const idx = projects.findIndex(p => p.key === key);
		if (idx >= 0) {
			pageNum = Math.floor(idx / pageSize);
		}
		expandedProjects.clear();
		expandedProjects.add(key);
		await tick();
		document.getElementById(`project-${key}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}
</script>

<h2 class="page-title">
	<Coins class="page-icon" /> Investitionen
</h2>
<p class="page-intro">
	Wo investiert Rödermark – und woher kommt das Geld dafür?
	Die Übersicht zeigt das gesamte Investitionsvolumen: Was bereits ausgegeben wurde (Ist bis {data.summary.last_ist_year})
	und was noch geplant ist (bis {Math.max(...(cl?.entries.flatMap(e => e.years) ?? [2029]))}).
</p>

{#if cl}
<!-- KPI Cards -->
<section class="kpi-grid section">
	<div class="kpi-card">
		<p class="kpi-label">Bereits investiert</p>
		<p class="kpi-value text-brand-700">{formatMio(totals.istAusgaben)}</p>
		<p class="kpi-sub">Ist-Ausgaben bis {data.summary.last_ist_year}</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Noch geplant</p>
		<p class="kpi-value text-blue-600">{formatMio(totals.planOnlyAusgaben)}</p>
		<p class="kpi-sub">Projekte ohne bisherige Ausgaben</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Gesamt</p>
		<p class="kpi-value text-brand-700">{formatMio(totals.totalAusgaben)}</p>
		<p class="kpi-sub">{formatNumber(totals.projekte)} Projekte in {investmentThemen.length} Themen</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Einnahmen</p>
		<p class="kpi-value text-green-600">{formatMio(totals.einnahmen)}</p>
		<p class="kpi-sub">Zuschüsse, Kredite, Erlöse</p>
	</div>
</section>

<!-- Tab Navigation -->
<div class="tab-bar section">
	<button class="tab-btn" class:active={activeTab === 'themen'} onclick={() => { activeTab = 'themen'; pushHash('themen'); }}>
		Themenübersicht
	</button>
	<button class="tab-btn" class:active={activeTab === 'projekte'} onclick={() => { activeTab = 'projekte'; pushHash('projekte'); }}>
		Einzelprojekte
	</button>
</div>

{#if activeTab === 'themen'}
<!-- ═══════════ THEMEN VIEW ═══════════ -->

<!-- Wo wird investiert? -->
<section class="section">
	<h3 class="section-title">
		Wo wird investiert?
	</h3>
	<p class="section-sub">
		Investitionsausgaben nach Thema – Klick für Details.
		<span class="legend"><span class="legend-dot legend-ist"></span> bereits ausgegeben <span class="legend-dot legend-plan"></span> noch geplant</span>
	</p>

	<div class="theme-list">
		{#each investmentThemen as t (t.thema)}
			{@const istPct = maxThemaVolume > 0 ? (t.istVolume / maxThemaVolume) * 100 : 0}
			{@const planPct = maxThemaVolume > 0 ? (t.planVolume / maxThemaVolume) * 100 : 0}
			{@const isSelected = selectedThema === t.thema}
			<button
				class="theme-row"
				class:selected={isSelected}
				onclick={() => selectThema(t.thema)}
			>
				<div class="theme-left">
					<div class="theme-label">{t.label}</div>
					<div class="theme-count">{t.countAusgaben} Projekte</div>
				</div>
				<div class="theme-bar-area">
					<div class="bar-track">
						<div class="bar bar-ist" style="width: {istPct}%{planPct === 0 ? '; border-radius: 0.25rem' : ''}"></div>
						<div class="bar bar-plan" style="width: {planPct}%; left: {istPct}%"></div>
					</div>
				</div>
				<div class="theme-amounts">
					{#if t.istVolume > 0}
						<span class="amount-ist">{formatAmount(t.istVolume)}</span>
					{/if}
					{#if t.planVolume > 0}
						<span class="amount-plan">{formatAmount(t.planVolume)}</span>
					{/if}
				</div>
			</button>

			<!-- Detail inline below the clicked theme -->
			{#if isSelected && themaEntries.length > 0}
				<div class="theme-detail">
						<table class="data-table">
							<thead>
								<tr>
									<th>Bezeichnung</th>
									<th class="col-number">Ist</th>
									<th class="col-number">Plan</th>
									<th>Zeitraum</th>
								</tr>
							</thead>
							<tbody>
								{#each themaEntries as entry (entry.key)}
									{@const ist = Math.abs(entry.ist_total)}
									{@const plan = Math.abs(entry.plan_total)}
									{@const hasIst = ist > 0}
									{@const hasPlan = plan > 0}
									{@const isAusgabe = entry.entry_type.startsWith('ausgabe_')}
									{@const entrySourceLinks = sourceLinksForEntry(entry.key)}
									<tr>
										<td class="entry-name">
											<button class="entry-link" onclick={() => goToProject(entry.key)} title="Details anzeigen">
												{entry.bezeichnung}
											</button>
											<span class="entry-type-hint">
												{isAusgabe ? 'Ausgabe' : 'Einnahme'}
												<SourceCitation description={entry.bezeichnung} links={entrySourceLinks} />
											</span>
										</td>
										<td class="col-number">
											{#if hasIst}
												{formatEur(ist)}
											{:else}
												<span class="text-gray-300">–</span>
											{/if}
										</td>
										<td class="col-number">
											{#if hasPlan}
												{formatEur(plan)}
											{:else}
												<span class="text-gray-300" title="Kein Planwert verfügbar">k.A.</span>
											{/if}
										</td>
										<td class="text-gray-400 entry-years">
											{entry.years.length > 0 ? `${Math.min(...entry.years)}–${Math.max(...entry.years)}` : '–'}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
				</div>
			{/if}
		{/each}
	</div>
</section>

<!-- Woher kommt das Geld? -->
<section class="section">
	<h3 class="section-title">
		Woher kommt das Geld?
	</h3>
	<p class="section-sub">Wie Investitionen finanziert werden – aus Zuschüssen, Krediten, Verkäufen oder Beiträgen.</p>

	<div class="finance-grid">
		{#each financeBreakdown as fb (fb.type)}
			<div class="finance-card">
				<div class="finance-value text-green-700">{formatAmount(fb.total)}</div>
				<div class="finance-label">{fb.label}</div>
				<div class="finance-count">{fb.count} Posten</div>
			</div>
		{/each}
	</div>
</section>

{:else}
<!-- ═══════════ PROJEKTE VIEW (existing detail) ═══════════ -->

<!-- Filters -->
<div class="card filter-bar cols-4 section">
	<div>
		<label for="search-inv" class="filter-label">Suche</label>
		<input
			id="search-inv" type="search" placeholder="Projektbezeichnung…"
			bind:value={searchQuery} class="form-input"
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
			Nur mit &gt;&nbsp;20 % Abweichung
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
		<div class="project-card" id="project-{project.key}">
			<div
				role="button" tabindex="0" class="project-header"
				onclick={() => toggleProject(project.key)}
				onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleProject(project.key); } }}
			>
				<span class="chevron">
					{#if isExpanded}<ChevronDown class="chevron-icon" />{:else}<ChevronRight class="chevron-icon" />{/if}
				</span>
				<div class="project-info">
					<div class="project-name-row">
						<span class="project-name">{project.bezeichnung}</span>
						{#if project.thNr}
							<span class="badge badge-gray" title="Teilhaushalt {project.thNr}">TH {project.thNr}</span>
						{/if}
						<SourceCitation description={`Investitionsprojekt: ${project.bezeichnung}`} links={project.sourceLinks} />
					</div>
					<div class="project-meta">
						{#if project.hasIst}
							<span class="meta-item"><span class="dot bg-green-500"></span> Ist: {formatAmount(project.totalIst)}</span>
						{/if}
						{#if project.hasPlan}
							<span class="meta-item"><span class="dot bg-blue-500"></span> Plan: {formatAmount(project.comparablePlan)}
								{#if project.totalPlan !== project.comparablePlan}
									<span class="text-gray-400" title="Gesamtplan inkl. Folgejahre: {formatAmount(project.totalPlan)}">(ges. {formatAmount(project.totalPlan)})</span>
								{/if}
							</span>
						{/if}
						{#if project.hasComparableData && project.comparablePlan !== 0 && Math.abs(project.discrepancyPct) > 5}
							{@const pct = Math.abs(project.discrepancyPct).toFixed(0)}
							{@const lessInvested = project.discrepancy > 0}
							<span class="meta-item discrepancy {lessInvested ? 'text-amber-600' : 'text-red-600'}">
								{#if lessInvested}
									<TrendingDown class="disc-icon" /> {pct} % weniger investiert
								{:else}
									<TrendingUp class="disc-icon" /> {pct} % teurer als geplant
								{/if}
							</span>
						{/if}
						{#if !project.hasIst && !project.hasComparableData && project.hasPlan}
							<span class="meta-item text-gray-400"><AlertTriangle class="disc-icon" /> Nur Planung (Folgejahre)</span>
						{:else if !project.hasIst && project.hasComparableData}
							<span class="meta-item text-amber-600"><AlertTriangle class="disc-icon" /> Geplant, nicht umgesetzt</span>
						{/if}
					</div>
				</div>
			</div>

			{#if isExpanded}
				<div class="project-detail">
					<div class="scroll-x">
						<table>
							<thead>
								<tr>
									<th>Jahr</th>
									<th class="col-number">Plan</th>
									<th class="col-number">Ist</th>
									<th class="col-number">Umsetzung</th>
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
										<td class="col-number text-blue-600">{yd?.plan !== null && yd?.plan !== undefined ? formatEur(yd.plan) : '–'}</td>
										<td class="col-number text-green-700">{yd?.ist !== null && yd?.ist !== undefined ? formatEur(yd.ist) : '–'}</td>
										<td class="col-number"
											style="color: {delta !== null ? (delta > 100 ? 'var(--amber-600)' : delta < -100 ? 'var(--red-600)' : 'var(--gray-500)') : 'var(--gray-300)'}; {delta !== null && Math.abs(delta) > 100 ? 'font-weight:500' : ''}">
											{#if delta !== null}
												{@const absDelta = Math.abs(delta)}
												{#if delta > 100}{formatEur(absDelta)} weniger
												{:else if delta < -100}{formatEur(absDelta)} mehr
												{:else}≈ Plan{/if}
											{:else}–{/if}
										</td>
									</tr>
								{/each}
							</tbody>
							{#if project.allYears.length > 1}
								<tfoot>
									{#if project.totalPlan !== project.comparablePlan}
										<tr class="comparable-row">
											<td>Bisherige Jahre</td>
											<td class="col-number text-blue-700">{project.comparablePlan !== 0 ? formatEur(project.comparablePlan) : '–'}</td>
											<td class="col-number text-green-800">{project.hasIst ? formatEur(project.comparableIst) : '–'}</td>
											<td class="col-number"
												style="color: {project.discrepancy > 100 ? 'var(--amber-600)' : project.discrepancy < -100 ? 'var(--red-700)' : 'var(--gray-600)'}">
												{#if project.hasComparableData && project.comparablePlan !== 0}
													{@const absPct = Math.abs(project.discrepancyPct).toFixed(0)}
													{#if project.discrepancy > 100}{absPct} % weniger investiert
													{:else if project.discrepancy < -100}{absPct} % teurer
													{:else}≈ wie geplant{/if}
												{:else}–{/if}
											</td>
										</tr>
										<tr>
											<td>Gesamt (inkl. Planung)</td>
											<td class="col-number" style="color:var(--gray-500)">{project.hasPlan ? formatEur(project.totalPlan) : '–'}</td>
											<td class="col-number" style="color:var(--gray-500)">{project.hasIst ? formatEur(project.totalIst) : '–'}</td>
											<td class="col-number" style="color:var(--gray-400)">–</td>
										</tr>
									{:else}
										<tr>
											<td>Summe</td>
											<td class="col-number text-blue-700">{project.hasPlan ? formatEur(project.totalPlan) : '–'}</td>
											<td class="col-number text-green-800">{project.hasIst ? formatEur(project.totalIst) : '–'}</td>
											<td class="col-number"
												style="color: {project.discrepancy > 100 ? 'var(--amber-600)' : project.discrepancy < -100 ? 'var(--red-700)' : 'var(--gray-600)'}">
												{#if project.hasComparableData && project.comparablePlan !== 0}
													{@const absPct = Math.abs(project.discrepancyPct).toFixed(0)}
													{#if project.discrepancy > 100}{absPct} % weniger investiert
													{:else if project.discrepancy < -100}{absPct} % teurer
													{:else}≈ wie geplant{/if}
												{:else}–{/if}
											</td>
										</tr>
									{/if}
								</tfoot>
							{/if}
						</table>
					</div>

					{#each [findCommentary(project.bezeichnung)] as comments}
						{#if comments.length > 0}
							<div class="commentary-section">
								<h4 class="commentary-title">
									<BookOpen class="commentary-icon" /> Anmerkungen aus Jahresabschlüssen
								</h4>
								{#each comments as comment (comment.document_id + comment.category)}
									{@const pdfLink = commentaryPdfLink(comment)}
									<div class="commentary-entry">
										<div class="commentary-header">
											<span class="commentary-year">{shortDocLabel(comment.document_id)}</span>
											<span class="commentary-cat">{comment.category}</span>
											{#if pdfLink}
												<a href={pdfLink} target="_blank" class="commentary-pdf-link" title="Im PDF nachlesen">
													S.&nbsp;{comment.page_start}–{comment.page_end}
												</a>
											{/if}
										</div>
										<p class="commentary-text">{comment.text}</p>
									</div>
								{/each}
							</div>
						{/if}
					{/each}
				</div>
			{/if}
		</div>
	{/each}
</div>

{#if totalPages > 1}
	<div class="pagination">
		<button disabled={pageNum === 0} onclick={() => { pageNum = Math.max(0, pageNum - 1); }}>← Zurück</button>
		<span class="page-info">Seite {pageNum + 1} von {totalPages}</span>
		<button disabled={pageNum >= totalPages - 1} onclick={() => { pageNum = Math.min(totalPages - 1, pageNum + 1); }}>Weiter →</button>
	</div>
{/if}

{/if}

{:else}
	<div class="info-box info-box-blue section">
		<Info class="info-icon" />
		<div>
			Klassifizierungsdaten nicht verfügbar. Bitte <code>classify_investments.py</code> ausführen.
		</div>
	</div>
{/if}

<style>
	/* Page layout */
	.page-title {
		display: flex; align-items: center; gap: 0.75rem;
		margin-bottom: 1.5rem; font-size: 1.5rem; font-weight: 700; color: var(--gray-900);
	}
	:global(.page-icon) { width: 1.75rem; height: 1.75rem; }
	.page-intro { margin-bottom: 2rem; max-width: 48rem; color: var(--gray-600); }
	.section { margin-bottom: 2rem; }

	/* Section titles */
	.section-title {
		display: flex; align-items: center; gap: 0.5rem;
		font-size: 1.125rem; font-weight: 600; color: var(--gray-800);
		margin-bottom: 1rem;
	}
	:global(.section-icon) { width: 1.25rem; height: 1.25rem; }

	/* Tab bar */
	.tab-bar {
		display: flex; gap: 0.25rem;
		border-bottom: 2px solid var(--gray-200);
		padding-bottom: 0;
	}
	.tab-btn {
		padding: 0.5rem 1.25rem;
		font-size: 0.875rem; font-weight: 500;
		color: var(--gray-500);
		border: none; background: none;
		cursor: pointer;
		border-bottom: 2px solid transparent;
		margin-bottom: -2px;
		transition: all 0.15s;
	}
	.tab-btn:hover { color: var(--gray-700); }
	.tab-btn.active {
		color: var(--brand-700);
		border-bottom-color: var(--brand-600);
	}

	/* Section subtitle */
	.section-sub {
		margin-top: -0.5rem; margin-bottom: 1rem;
		font-size: 0.8125rem; color: var(--gray-500); max-width: 40rem;
	}

	/* Theme list */
	.theme-list {
		display: flex; flex-direction: column; gap: 0.375rem;
	}
	.theme-row {
		display: grid;
		grid-template-columns: 12rem 1fr 6rem;
		align-items: center;
		gap: 0.75rem;
		padding: 0.625rem 0.875rem;
		border-radius: 0.5rem;
		background: var(--gray-50);
		border: 1px solid var(--gray-100);
		cursor: pointer;
		transition: all 0.15s;
		text-align: left;
		width: 100%;
	}
	.theme-row:hover { background: var(--brand-50, #f0f9ff); border-color: var(--brand-200, #bae6fd); }
	.theme-row.selected { background: var(--brand-50, #f0f9ff); border-color: var(--brand-400, #38bdf8); box-shadow: 0 0 0 1px var(--brand-400, #38bdf8); }
	.theme-left { min-width: 0; }
	.theme-label {
		font-size: 0.875rem; font-weight: 600; color: var(--gray-800);
	}
	.theme-count {
		font-size: 0.6875rem; color: var(--gray-400);
		margin-top: 0.125rem;
	}
	.theme-bar-area { min-width: 0; }
	.bar-track {
		height: 0.5rem; background: var(--gray-100); border-radius: 0.25rem;
		position: relative;
	}
	.bar {
		height: 100%;
		transition: width 0.3s ease;
		position: absolute; top: 0;
	}
	.bar-ist { background: var(--brand-500, #3b82f6); left: 0; border-radius: 0.25rem 0 0 0.25rem; }
	.bar-plan { background: var(--brand-200, #bfdbfe); border-radius: 0 0.25rem 0.25rem 0; }
	.legend {
		display: inline-flex; align-items: center; gap: 0.35rem;
		font-size: 0.8125rem; color: var(--gray-500); margin-left: 0.5rem;
	}
	.legend-dot {
		display: inline-block; width: 0.625rem; height: 0.625rem; border-radius: 2px;
	}
	.legend-ist { background: var(--brand-500, #3b82f6); }
	.legend-plan { background: var(--brand-200, #bfdbfe); }
	.theme-amounts {
		text-align: right; white-space: nowrap;
		display: flex; flex-direction: column; gap: 0.125rem;
		min-width: 5.5rem;
	}
	.amount-ist {
		font-size: 0.875rem; font-weight: 600; color: var(--brand-700, #1d4ed8);
	}
	.amount-plan {
		font-size: 0.75rem; font-weight: 500; color: var(--brand-400, #60a5fa);
	}

	/* Theme detail table */
	.theme-detail {
		padding: 0.25rem 0 0.5rem;
		border-left: 3px solid var(--brand-300, #93c5fd);
		margin-left: 0.5rem;
		padding-left: 0.5rem;
		overflow-x: auto;
	}
	.entry-name {
		font-size: 0.8125rem; color: var(--gray-700);
		max-width: 22rem;
	}
	.entry-link {
		background: none; border: none; padding: 0; cursor: pointer;
		font: inherit; color: var(--brand-700, #1d4ed8); text-align: left;
		text-decoration: none;
	}
	.entry-link:hover { text-decoration: underline; }
	.entry-type-hint {
		display: flex; align-items: center; gap: 0.25rem;
		font-size: 0.6875rem; color: var(--gray-400); font-weight: 400;
	}
	.entry-years { font-size: 0.75rem; }
	.badge-gray {
		background: var(--gray-50); color: var(--gray-500);
		border: 1px solid var(--gray-200);
	}

	/* Finance breakdown */
	.finance-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
		gap: 0.75rem;
	}
	.finance-card {
		padding: 1rem;
		background: var(--gray-50);
		border: 1px solid var(--gray-200);
		border-radius: 0.5rem;
	}
	.finance-label {
		font-size: 0.8125rem; font-weight: 500; color: var(--gray-600);
		margin-bottom: 0.25rem;
	}
	.finance-value {
		font-size: 1.125rem; font-weight: 700;
	}
	.finance-count {
		font-size: 0.75rem; color: var(--gray-400); margin-top: 0.125rem;
	}

	/* Filter bar */
	.filter-label { display: block; font-size: 0.75rem; font-weight: 500; color: var(--gray-500); }
	.filter-checkbox-wrap { display: flex; align-items: flex-end; }
	.filter-checkbox { display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem; color: var(--gray-600); }
	.filter-count { display: flex; align-items: flex-end; font-size: 0.875rem; color: var(--gray-500); }

	/* Project list */
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

	/* Commentary */
	.commentary-section { margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--gray-200); }
	.commentary-title {
		display: flex; align-items: center; gap: 0.5rem;
		font-size: 0.8125rem; font-weight: 600; color: var(--gray-700); margin-bottom: 0.75rem;
	}
	:global(.commentary-icon) { width: 0.875rem; height: 0.875rem; color: var(--amber-600); }
	.commentary-entry {
		padding: 0.5rem 0.75rem;
		background: var(--amber-50, #fffbeb); border-radius: 0.375rem;
		border-left: 3px solid var(--amber-400, #fbbf24); margin-bottom: 0.5rem;
	}
	.commentary-header { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem; }
	.commentary-year { font-weight: 600; font-size: 0.75rem; color: var(--gray-700); }
	.commentary-cat { font-size: 0.6875rem; color: var(--gray-500); }
	.commentary-pdf-link { margin-left: auto; font-size: 0.6875rem; color: var(--brand-600); text-decoration: underline; }
	.commentary-text { font-size: 0.8125rem; line-height: 1.5; color: var(--gray-700); }

	/* Responsive: collapse grid on small screens */
	@media (max-width: 640px) {
		.theme-row {
			grid-template-columns: 1fr auto;
			grid-template-rows: auto auto;
			gap: 0.25rem 0.5rem;
		}
		.theme-bar-area {
			grid-column: 1 / -1;
			grid-row: 2;
		}
		.theme-amounts { min-width: auto; }
		.amount-ist { font-size: 0.8125rem; }
		.amount-plan { font-size: 0.6875rem; }
		.kpi-grid { grid-template-columns: 1fr 1fr; }
		.finance-grid { grid-template-columns: 1fr; }
	}
</style>
