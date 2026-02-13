<script lang="ts">
	import { formatAmount } from '$lib/format';
	import SourceCitation from './SourceCitation.svelte';
	import type { SourceLink } from '$lib/types';

	interface PivotRow {
		nr: string;
		bezeichnung: string;
		values: Map<string, number | null>;
	}

	interface Props {
		rows: PivotRow[];
		years: number[];
		planOnlyYears: number[];
		/** Nr values that should be highlighted as sum rows */
		sumNrs?: string[];
		/** Source links per year for condensed citations in column headers */
		yearSourceLinks?: Map<number, SourceLink[]>;
		/** Label prefix for source citations, e.g. "Ergebnishaushalt" */
		sourceLabel?: string;
		/** Invert coloring: negative = green, positive = red (for Finanzhaushalt) */
		invertColors?: boolean;
		/** Callback when a row is clicked, receives the row's nr */
		onRowClick?: (nr: string) => void;
	}

	let {
		rows,
		years,
		planOnlyYears,
		sumNrs = [],
		yearSourceLinks = new Map(),
		sourceLabel = '',
		invertColors = false,
		onRowClick,
	}: Props = $props();

	let planOnlySet = $derived(new Set(planOnlyYears));
	let sumSet = $derived(new Set(sumNrs));

	function valueClass(val: number | null | undefined, isPlanOnly: boolean): string {
		if (val === null || val === undefined) return 'val-neutral';
		const isPositiveGood = !invertColors;
		const isGood = isPositiveGood ? val > 0 : val < 0;
		const isBad = isPositiveGood ? val < 0 : val > 0;
		let cls = isGood ? 'val-positive' : isBad ? 'val-negative' : 'val-neutral';
		if (isPlanOnly) cls += ' is-plan';
		return cls;
	}
</script>

<div class="scroll-x card">
	<table class="data-table">
		<thead>
			<tr>
				<th class="col-sticky" style="left:0">Nr.</th>
				<th class="col-sticky col-sticky-last" style="left:3rem">Bezeichnung</th>
				{#each years as year}
					<th class="col-number {planOnlySet.has(year) ? 'plan-only' : ''}">
						{year}{#if planOnlySet.has(year)}<span class="plan-marker">P</span>{/if}
						{#if yearSourceLinks.get(year)}
							<SourceCitation
								description="{sourceLabel} {year}"
								links={yearSourceLinks.get(year) ?? []}
								condensed
							/>
						{/if}
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each rows as row, idx}
				{@const isSum = sumSet.has(row.nr)}
				<tr
					class="{isSum ? 'row-sum' : idx % 2 === 0 ? '' : 'row-alt'}"
					class:clickable={!!onRowClick}
					onclick={() => onRowClick?.(row.nr)}
				>
					<td class="col-sticky nr-cell {isSum ? 'row-sum' : idx % 2 === 0 ? '' : 'row-alt'}" style="left:0">
						{row.nr}
					</td>
					<td class="col-sticky col-sticky-last {isSum ? 'row-sum' : idx % 2 === 0 ? '' : 'row-alt'}" style="left:3rem;max-width:15rem" class:truncate={true}>
						{row.bezeichnung}
					</td>
					{#each years as year}
						{@const planVal = row.values.get(`${year}_plan`)}
						{@const istVal = row.values.get(`${year}_ist`)}
						{@const val = istVal ?? planVal}
						{@const isPlanOnly = planOnlySet.has(year)}
						<td class="col-number {isPlanOnly ? 'plan-col-bg' : ''} {valueClass(val, isPlanOnly)}">
							{#if val != null}
								{formatAmount(val)}
							{:else}
								–
							{/if}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<p class="table-hint">
	Klicke auf eine Zeile, um den Zeitreihen-Chart zu aktualisieren. Ist-Werte bevorzugt, sonst Plan.
</p>
<p class="table-hint legend-row">
	<span class="legend-swatch"></span>
	<span class="legend-text">Kursive Spalten</span> = nur Planwerte (Ansatz/Finanzplanung), keine Ist-Ergebnisse vorhanden.
</p>

<style>
	/* Value coloring */
	.val-positive { color: var(--green-700); }
	.val-negative { color: var(--red-700); }
	.val-neutral  { color: var(--gray-400); }
	.val-positive.is-plan { color: var(--green-500); }
	.val-negative.is-plan { color: var(--red-400); }

	.clickable { cursor: pointer; }

	.nr-cell {
		font-family: monospace;
		font-size: 0.75rem;
		color: var(--gray-500);
	}

	.table-hint {
		font-size: 0.75rem;
		color: var(--gray-400);
		margin-top: 0.5rem;
	}
	.legend-row { margin-top: 0.25rem; }
	.legend-swatch {
		display: inline-block;
		width: 0.75rem;
		height: 0.75rem;
		background: var(--blue-50);
		border: 1px solid var(--blue-300);
		border-radius: 0.125rem;
		vertical-align: middle;
		margin-right: 0.25rem;
	}
	.legend-text {
		font-style: italic;
		color: var(--blue-400);
	}
</style>
