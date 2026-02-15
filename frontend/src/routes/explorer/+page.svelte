<script lang="ts">
	import type { PageData } from './$types';
	import { formatAmount, amountTypeLabel, formatDocumentName } from '$lib/format';
	import { haushaltTypeLabel, shortDocLabel } from '$lib/data';
	import type { SourceLink } from '$lib/types';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import { Search } from '@lucide/svelte';

	let { data }: { data: PageData } = $props();

	const docMap = new Map(data.documents.map(d => [d.document_id, d]));

	function itemSourceLinks(item: { document_id: string; page: number | null }): SourceLink[] {
		const doc = docMap.get(item.document_id);
		if (!doc?.filename) return [];
		const label = item.page
			? `${shortDocLabel(item.document_id)}, S.\u00a0${item.page}`
			: shortDocLabel(item.document_id);
		const base = `/pdfs/${doc.filename}`;
		const href = item.page ? `${base}#page=${item.page}` : base;
		return [{ label, href, document_id: item.document_id, page: item.page }];
	}

	// Filters
	let search = $state('');
	let filterType = $state<string>('all');
	let filterAmountType = $state<string>('all');
	let filterYear = $state<string>('all');
	let showDetail = $state(false);
	let sortCol = $state<string>('nr');
	let sortDir = $state<'asc' | 'desc'>('asc');

	// Available years
	const allYears = [...new Set(data.items.map((i) => i.year))].sort((a, b) => a - b);
	const planOnlySet = new Set(data.planOnlyYears ?? []);

	let filtered = $derived.by(() => {
		let items = data.items;

		// Filter detail/overview
		if (!showDetail) {
			items = items.filter((i) => !i.table_id.startsWith('struktur_'));
		}

		// Filter by haushalt type
		if (filterType !== 'all') {
			items = items.filter((i) => i.haushalt_type === filterType);
		}

		// Filter by amount type
		if (filterAmountType !== 'all') {
			items = items.filter((i) => i.amount_type === filterAmountType);
		}

		// Filter by year
		if (filterYear !== 'all') {
			items = items.filter((i) => i.year === Number.parseInt(filterYear));
		}

		// Search
		if (search.trim()) {
			const q = search.toLowerCase().trim();
			items = items.filter(
				(i) =>
					i.bezeichnung.toLowerCase().includes(q) ||
					i.nr.toLowerCase().includes(q) ||
					(i.konto && i.konto.toLowerCase().includes(q))
			);
		}

		// Sort
		items = [...items].sort((a, b) => {
			let cmp = 0;
			switch (sortCol) {
				case 'nr':
					cmp = Number.parseFloat(a.nr) - Number.parseFloat(b.nr);
					break;
				case 'bezeichnung':
					cmp = a.bezeichnung.localeCompare(b.bezeichnung, 'de');
					break;
				case 'year':
					cmp = a.year - b.year;
					break;
				case 'amount':
					cmp = a.amount - b.amount;
					break;
				default:
					cmp = 0;
			}
			return sortDir === 'asc' ? cmp : -cmp;
		});

		return items;
	});

	// Pagination
	let page = $state(0);
	const pageSize = 50;

	let totalPages = $derived(Math.ceil(filtered.length / pageSize));
	let paged = $derived(filtered.slice(page * pageSize, (page + 1) * pageSize));

	function toggleSort(col: string) {
		if (sortCol === col) {
			sortDir = sortDir === 'asc' ? 'desc' : 'asc';
		} else {
			sortCol = col;
			sortDir = 'asc';
		}
		page = 0;
	}

	// Reset page on filter change
	$effect(() => {
		// Access all filter dependencies to track them
		void search;
		void filterType;
		void filterAmountType;
		void filterYear;
		void showDetail;
		page = 0;
	});
</script>

<h2 class="page-title"><Search class="page-icon" /> Daten-Explorer</h2>
<p class="page-intro">
	Durchsuche und filtere alle {data.items.length.toLocaleString('de-DE')} Haushaltspositionen.
</p>

<!-- Filters -->
<div class="card filter-bar cols-5 section">
	<div>
		<label for="search" class="filter-label">Suche</label>
		<input
			id="search"
			type="search"
			placeholder="Bezeichnung, Nr., Konto…"
			bind:value={search}
			class="form-input"
		/>
	</div>
	<div>
		<label for="filter-type" class="filter-label">Haushalt</label>
		<select id="filter-type" bind:value={filterType} class="form-select">
			<option value="all">Alle</option>
			<option value="ergebnishaushalt">Ergebnishaushalt</option>
			<option value="finanzhaushalt">Finanzhaushalt</option>
			<option value="teilergebnishaushalt">Teilergebnishaushalt</option>
			<option value="teilfinanzhaushalt">Teilfinanzhaushalt</option>
			<option value="investitionen">Investitionen</option>
		</select>
	</div>
	<div>
		<label for="filter-amount" class="filter-label">Typ</label>
		<select id="filter-amount" bind:value={filterAmountType} class="form-select">
			<option value="all">Alle</option>
			<option value="ist">Ist (Ergebnis)</option>
			<option value="plan">Plan (Ansatz)</option>
		</select>
	</div>
	<div>
		<label for="filter-year" class="filter-label">Jahr</label>
		<select id="filter-year" bind:value={filterYear} class="form-select">
			<option value="all">Alle</option>
			{#each allYears as year}
				<option value={String(year)}>{year}{planOnlySet.has(year) ? ' (nur Plan)' : ''}</option>
			{/each}
		</select>
	</div>
	<div class="filter-checkbox-wrap">
		<label class="filter-checkbox">
			<input type="checkbox" bind:checked={showDetail} />
			Detail-Positionen
		</label>
	</div>
</div>

<!-- Results count -->
<div class="results-bar">
	<span>{filtered.length.toLocaleString('de-DE')} Ergebnisse</span>
	{#if totalPages > 1}
		<span>Seite {page + 1} von {totalPages}</span>
	{/if}
</div>

<!-- Table -->
<div class="table-wrap">
	<table class="data-table">
		<thead>
			<tr>
				<th class="sortable" onclick={() => toggleSort('nr')}>
					Nr. {sortCol === 'nr' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
				</th>
				{#if showDetail}
					<th>Konto</th>
				{/if}
				<th class="sortable" onclick={() => toggleSort('bezeichnung')}>
					Bezeichnung {sortCol === 'bezeichnung' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
				</th>
				<th class="sortable col-number" onclick={() => toggleSort('year')}>
					Jahr {sortCol === 'year' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
				</th>
				<th style="text-align:center">Typ</th>
				<th class="sortable col-number" onclick={() => toggleSort('amount')}>
					Betrag {sortCol === 'amount' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
				</th>
				<th style="text-align:center">Haushalt</th>
				<th>Quelle</th>
			</tr>
		</thead>
		<tbody>
			{#each paged as item, idx}
				<tr class="{idx % 2 === 0 ? '' : 'row-alt'}">
					<td class="mono">{item.nr}</td>
					{#if showDetail}
						<td class="mono">{item.konto ?? ''}</td>
					{/if}
					<td class="truncate" title={item.bezeichnung}>{item.bezeichnung}</td>
					<td class="col-number tabular-nums">{item.year}</td>
					<td style="text-align:center">
						<span class="badge {item.amount_type === 'ist' ? 'badge-green' : 'badge-blue'}">
							{item.amount_type === 'ist' ? 'Ist' : 'Plan'}
						</span>
					</td>
					<td class="col-number tabular-nums"
						style="color: {item.amount < 0 ? 'var(--green-700)' : 'var(--red-700)'}">
						{formatAmount(item.amount)}
					</td>
					<td class="haushalt-cell">
						{haushaltTypeLabel(item.haushalt_type)}
					</td>
					<td class="source-cell">
						<SourceCitation
							description={item.bezeichnung}
							links={itemSourceLinks(item)}
							condensed
						/>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<!-- Pagination -->
{#if totalPages > 1}
	<div class="pagination">
		<button disabled={page === 0} onclick={() => { page = Math.max(0, page - 1); }}>← Zurück</button>
		<span class="page-info">{page + 1} / {totalPages}</span>
		<button disabled={page >= totalPages - 1} onclick={() => { page = Math.min(totalPages - 1, page + 1); }}>Weiter →</button>
	</div>
{/if}

<style>
	.page-title {
		display: flex; align-items: center; gap: 0.75rem;
		margin-bottom: 1.5rem; font-size: 1.5rem; font-weight: 700; color: var(--gray-900);
	}
	:global(.page-icon) { width: 1.75rem; height: 1.75rem; }
	.page-intro { margin-bottom: 1.5rem; color: var(--gray-600); }
	.section { margin-bottom: 1.5rem; }
	.filter-label { display: block; font-size: 0.75rem; font-weight: 500; color: var(--gray-500); }
	.filter-checkbox-wrap { display: flex; align-items: flex-end; }
	.filter-checkbox { display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem; color: var(--gray-600); }
	.results-bar {
		display: flex; align-items: center; justify-content: space-between;
		margin-bottom: 0.75rem; font-size: 0.875rem; color: var(--gray-500);
	}
	.table-wrap {
		overflow-x: auto;
		background: #fff; box-shadow: var(--shadow-sm); border: 1px solid var(--gray-100);
		margin-left: -1rem;
		margin-right: -1rem;
		border-radius: 0;
	}
	@media (min-width: 640px) {
		.table-wrap {
			margin-left: 0;
			margin-right: 0;
			border-radius: 0.75rem;
		}
	}
	.sortable { cursor: pointer; }
	.sortable:hover { color: var(--gray-900); }
	.mono { white-space: nowrap; font-family: monospace; font-size: 0.75rem; color: var(--gray-500); }
	.haushalt-cell { white-space: nowrap; text-align: center; font-size: 0.75rem; color: var(--gray-500); }
	.source-cell { white-space: nowrap; font-size: 0.75rem; color: var(--gray-400); }
	.truncate { max-width: 20rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.page-info { font-size: 0.875rem; color: var(--gray-500); }
</style>
