<script lang="ts">
	import { onMount } from 'svelte';
	import { untrack } from 'svelte';
	import {
		Chart,
		DoughnutController,
		ArcElement,
		Tooltip,
		Legend
	} from 'chart.js';
	import type { CategorySlice } from '$lib/data';
	import { formatAmount } from '$lib/format';

	Chart.register(DoughnutController, ArcElement, Tooltip, Legend);

	interface Props {
		title: string;
		slices: CategorySlice[];
		/** Callback when a slice is clicked */
		onSliceClick?: (nr: string) => void;
		/** Hide the built-in legend (use your own alongside) */
		hideLegend?: boolean;
	}

	let { title, slices, onSliceClick, hideLegend = false }: Props = $props();

	let canvasEl: HTMLCanvasElement;
	let chart: Chart | undefined;

	function createChart() {
		if (chart) {
			chart.destroy();
			chart = undefined;
		}
		if (!canvasEl || slices.length === 0) return;

		const labels = slices.map((s) => s.category.shortLabel);
		const data = slices.map((s) => s.amount);
		const colors = slices.map((s) => s.category.color);

		chart = new Chart(canvasEl, {
			type: 'doughnut',
			data: {
				labels,
				datasets: [
					{
						data,
						backgroundColor: colors,
						borderColor: '#fff',
						borderWidth: 2,
						hoverBorderWidth: 3,
						hoverOffset: 6,
					},
				],
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				cutout: '55%',
				plugins: {
					legend: {
						display: false, // we render our own
					},
					tooltip: {
						callbacks: {
							label: (ctx) => {
								const slice = slices[ctx.dataIndex];
								if (!slice) return '';
								const pct = (slice.percent * 100).toFixed(1);
								return `${slice.category.label}: ${formatAmount(slice.amount)} (${pct} %)`;
							},
						},
					},
				},
				onClick: (_event, elements) => {
					if (elements.length > 0 && onSliceClick) {
						const idx = elements[0].index;
						onSliceClick(slices[idx].category.nr);
					}
				},
			},
		});
	}

	onMount(() => {
		return () => chart?.destroy();
	});

	$effect(() => {
		slices;
		untrack(() => {
			if (canvasEl) createChart();
		});
	});

	const total = $derived(slices.reduce((sum, s) => sum + s.amount, 0));
</script>

<div class="donut-wrapper" class:donut-compact={hideLegend}>
	<h4 class="donut-title">{title}</h4>
	<div class="donut-layout">
		<div class="donut-canvas-box">
			<canvas bind:this={canvasEl}></canvas>
			<div class="donut-center">
				<span class="donut-center-label">Gesamt</span>
				<span class="donut-center-amount">{formatAmount(total)}</span>
			</div>
		</div>
		{#if !hideLegend}
		<div class="donut-legend">
			{#each slices as slice, i}
				<button
					type="button"
					class="legend-item"
					onclick={() => onSliceClick?.(slice.category.nr)}
					title={slice.category.description}
				>
					<span class="legend-dot" style="background: {slice.category.color}"></span>
					<span class="legend-label">{slice.category.shortLabel}</span>
					<span class="legend-pct">{(slice.percent * 100).toFixed(1)} %</span>
					<span class="legend-amount">{formatAmount(slice.amount)}</span>
				</button>
			{/each}
		</div>
		{/if}
	</div>
</div>

<style>
	.donut-wrapper {
		width: 100%;
	}
	.donut-compact {
		width: auto;
		flex-shrink: 0;
	}
	.donut-compact .donut-layout {
		flex-direction: column;
		align-items: center;
	}
	.donut-title {
		margin-bottom: 1rem;
		font-size: 1rem;
		font-weight: 600;
		color: var(--gray-800);
	}
	.donut-layout {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		align-items: center;
	}
	@media (min-width: 640px) {
		.donut-layout {
			flex-direction: row;
			align-items: flex-start;
		}
	}
	.donut-canvas-box {
		position: relative;
		width: 14rem;
		height: 14rem;
		flex-shrink: 0;
	}
	.donut-center {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		pointer-events: none;
	}
	.donut-center-label {
		font-size: 0.75rem;
		color: var(--gray-400);
	}
	.donut-center-amount {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--gray-700);
	}
	.donut-legend {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		width: 100%;
		min-width: 0;
	}
	.legend-item {
		display: grid;
		grid-template-columns: 0.75rem 1fr auto auto;
		gap: 0.5rem;
		align-items: center;
		padding: 0.375rem 0.5rem;
		border: none;
		background: none;
		border-radius: 0.375rem;
		cursor: pointer;
		text-align: left;
		font-size: 0.8125rem;
		color: var(--gray-700);
		transition: background 0.1s;
	}
	.legend-item:hover {
		background: var(--gray-50);
	}
	.legend-dot {
		width: 0.75rem;
		height: 0.75rem;
		border-radius: 0.1875rem;
		flex-shrink: 0;
	}
	.legend-label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: 500;
	}
	.legend-pct {
		font-weight: 600;
		color: var(--gray-800);
		white-space: nowrap;
		min-width: 3rem;
		text-align: right;
	}
	.legend-amount {
		color: var(--gray-400);
		white-space: nowrap;
		min-width: 5rem;
		text-align: right;
		font-size: 0.75rem;
	}
</style>
