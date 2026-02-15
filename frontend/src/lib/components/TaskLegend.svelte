<script lang="ts">
	import type { TaskSlice } from '$lib/data';
	import { formatAmount } from '$lib/format';
	import ChangeIndicator from './ChangeIndicator.svelte';
	import { Info } from '@lucide/svelte';

	interface Props {
		slices: TaskSlice[];
		selectedId?: string | null;
		onSelect?: (id: string) => void;
		/** Previous year amounts by task id – if provided, shows YoY delta columns */
		prevAmounts?: Map<string, number>;
		/** The previous year number, shown in the column header */
		prevYear?: number | null;
	}

	let { slices, selectedId = null, onSelect, prevAmounts, prevYear = null }: Props = $props();

	let hasPrev = $derived(prevAmounts && prevAmounts.size > 0);

	function delta(taskId: string, current: number): { diff: number; ratio: number } | null {
		if (!prevAmounts) return null;
		const prev = prevAmounts.get(taskId);
		if (prev == null || prev === 0) return null;
		const diff = current - prev;
		const ratio = diff / Math.abs(prev);
		return { diff, ratio };
	}
</script>

<div class="task-legend">
	{#if !selectedId}
		<div class="click-hint">
			<Info size={14} /> Aufgabenbereich anklicken für detaillierte Aufschlüsselung
		</div>
	{/if}
	<table class="legend-table">
		<thead>
			<tr>
				<th class="th-left">Aufgabe</th>
				<th class="th-left hide-mobile">Art</th>
				<th class="th-right">Anteil</th>
				<th class="th-right">Betrag</th>
				{#if hasPrev}
					<th class="th-right hide-mobile">ggü. {prevYear ?? 'Vorjahr'}</th>
					<th class="th-right hide-mobile"></th>
				{/if}
			</tr>
		</thead>
		<tbody>
			{#each slices as slice (slice.task.id)}
				{@const d = delta(slice.task.id, slice.amount)}
				<tr
					class="legend-row"
					class:active={selectedId === slice.task.id}
					onclick={() => onSelect?.(slice.task.id)}
					title={slice.task.description}
				>
					<td class="td-label"><span class="legend-dot" style="background: {slice.task.color}"></span> {slice.task.shortLabel}</td>
					<td class="hide-mobile"><span class="legend-badge pflicht-{slice.task.pflicht}">{slice.task.pflichtLabel}</span></td>
					<td class="td-right td-pct">{(slice.percent * 100).toFixed(1)} %</td>
					<td class="td-right td-amount">{formatAmount(slice.amount)}</td>
					{#if hasPrev}
						<td class="td-right td-delta-abs hide-mobile" class:is-up={d && d.diff > 0} class:is-down={d && d.diff < 0}>
							{#if d}
								{d.diff > 0 ? '+' : ''}{formatAmount(d.diff)}
							{:else}
								–
							{/if}
						</td>
						<td class="td-right hide-mobile">
							{#if d}
								<ChangeIndicator diff={d.diff} ratio={d.ratio} />
							{:else}
								<span class="na">–</span>
							{/if}
						</td>
					{/if}
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.task-legend {
		flex: 1;
		min-width: 0;
		overflow-x: auto;
	}
	.legend-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.8125rem;
	}

	/* Header */
	.legend-table thead th {
		font-size: 0.6875rem;
		font-weight: 500;
		color: var(--gray-400);
		text-transform: uppercase;
		letter-spacing: 0.025em;
		padding: 0.25rem 0.5rem;
		border-bottom: 1px solid var(--gray-100);
		white-space: nowrap;
		text-align: left;
	}
	.th-right { text-align: right !important; }

	/* Rows */
	.legend-row {
		cursor: pointer;
		transition: background 0.1s;
		color: var(--gray-700);
	}
	.legend-row:hover { background: var(--gray-50); }
	.legend-row:hover .td-label { color: var(--brand-600, #2563eb); }
	.legend-row.active { background: var(--brand-50, #f0f4ff); }
	.legend-row.active .td-label { color: var(--brand-700, #1d4ed8); }
	.legend-row td {
		padding: 0.625rem 0.5rem;
		white-space: nowrap;
	}
	@media (min-width: 768px) {
		.legend-row td {
			padding: 0.375rem 0.5rem;
		}
	}

	/* Hide columns on mobile to keep table readable */
	.hide-mobile { display: none; }
	@media (min-width: 768px) {
		.hide-mobile { display: table-cell; }
	}

	/* Cell types */
	.td-label { font-weight: 500; }
	.td-right { text-align: right; }
	.td-pct { font-weight: 600; color: var(--gray-800); }
	.td-amount { color: var(--gray-400); font-size: 0.75rem; }
	.td-delta-abs { font-size: 0.75rem; color: var(--gray-400); }
	.td-delta-abs.is-up { color: var(--red-600, #dc2626); }
	.td-delta-abs.is-down { color: var(--green-600, #16a34a); }
	.na { color: var(--gray-300); }

	/* Dot */
	.legend-dot {
		display: inline-block;
		width: 0.75rem;
		height: 0.75rem;
		border-radius: 0.1875rem;
		vertical-align: middle;
		margin-right: 0.375rem;
	}

	/* Badge */
	.legend-badge {
		display: inline-block;
		font-size: 0.625rem;
		font-weight: 600;
		padding: 0.0625rem 0.375rem;
		border-radius: 999px;
		white-space: nowrap;
		line-height: 1.4;
	}
	.pflicht-pflicht { background: var(--red-50, #fef2f2); color: var(--red-700, #b91c1c); }
	.pflicht-freiwillig { background: var(--green-50, #f0fdf4); color: var(--green-700, #15803d); }
	.pflicht-misch { background: var(--amber-50, #fffbeb); color: var(--amber-700, #b45309); }

	/* Click hint */
	.click-hint {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		font-size: 0.75rem;
		color: var(--brand-600, #2563eb);
		background: var(--brand-50, #eff6ff);
		padding: 0.375rem 0.625rem;
		border-radius: 0.375rem;
		margin-bottom: 0.5rem;
	}
</style>
