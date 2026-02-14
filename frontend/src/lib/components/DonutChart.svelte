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
		/** Per-segment colors for a thin outer ring. Length must match slices. */
		outerRingColors?: string[];
		/** Per-segment labels for the outer ring (shown in tooltip). Length must match slices. */
		outerRingLabels?: string[];
	}

	let { title, slices, onSliceClick, hideLegend = false, outerRingColors, outerRingLabels }: Props = $props();

	let canvasEl: HTMLCanvasElement;
	let chart: Chart | undefined;
	let tooltipEl!: HTMLDivElement;

	function externalTooltipHandler(context: any) {
		const { chart: c, tooltip } = context;
		if (!tooltipEl) return;

		if (tooltip.opacity === 0) {
			tooltipEl.style.opacity = '0';
			tooltipEl.style.pointerEvents = 'none';
			return;
		}

		// Build content
		const dataIndex = tooltip.dataPoints?.[0]?.dataIndex;
		if (dataIndex == null) return;
		const slice = slices[dataIndex];
		if (!slice) return;

		const pct = (slice.percent * 100).toFixed(1);
		let html = `<div class="tt-line"><strong>${slice.category.label}</strong></div>`;
		html += `<div class="tt-line">${formatAmount(slice.amount)} (${pct} %)</div>`;
		if (outerRingLabels?.[dataIndex]) {
			html += `<div class="tt-pflicht">${outerRingLabels[dataIndex]}</div>`;
		}
		tooltipEl.innerHTML = html;

		// Position relative to chart canvas
		const canvasRect = c.canvas.getBoundingClientRect();
		const wrapperRect = c.canvas.closest('.donut-canvas-box')?.getBoundingClientRect() ?? canvasRect;

		tooltipEl.style.opacity = '1';
		tooltipEl.style.left = `${tooltip.caretX + (canvasRect.left - wrapperRect.left)}px`;
		tooltipEl.style.top = `${tooltip.caretY + (canvasRect.top - wrapperRect.top)}px`;
	}

	function createChart() {
		if (chart) {
			chart.destroy();
			chart = undefined;
		}
		if (!canvasEl || slices.length === 0) return;

		const labels = slices.map((s) => s.category.shortLabel);
		const data = slices.map((s) => s.amount);
		const colors = slices.map((s) => s.category.color);

		const datasets: any[] = [];

		// Thin outer ring (pflicht indicator)
		if (outerRingColors) {
			datasets.push({
				data,
				backgroundColor: outerRingColors,
				borderColor: '#fff',
				borderWidth: 1,
				hoverOffset: 0,
				weight: 0.1,
			});
		}

		// Main donut
		datasets.push({
			data,
			backgroundColor: colors,
			borderColor: '#fff',
			borderWidth: 2,
			hoverBorderWidth: 3,
			hoverOffset: 6,
		});

		chart = new Chart(canvasEl, {
			type: 'doughnut',
			data: {
				labels,
				datasets,
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
						enabled: false,
						external: externalTooltipHandler,
						filter: (tooltipItem) => {
							return outerRingColors ? tooltipItem.datasetIndex === 1 : true;
						},
					},
				},
				onClick: (_event, elements) => {
					if (elements.length > 0 && onSliceClick) {
						// Only respond to clicks on the main dataset
						const main = outerRingColors
							? elements.find(e => e.datasetIndex === 1)
							: elements[0];
						if (main) onSliceClick(slices[main.index].category.nr);
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
			<div class="chart-tooltip" bind:this={tooltipEl}></div>
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
		width: 18rem;
		height: 18rem;
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

	/* External HTML tooltip */
	.chart-tooltip {
		position: absolute;
		opacity: 0;
		pointer-events: none;
		background: rgba(0, 0, 0, 0.8);
		color: #fff;
		border-radius: 0.375rem;
		padding: 0.5rem 0.75rem;
		font-size: 0.8125rem;
		line-height: 1.5;
		white-space: nowrap;
		z-index: 50;
		transform: translate(-50%, -110%);
		transition: opacity 0.15s ease;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
	}
	:global(.tt-line) {
		font-size: 0.8125rem;
	}
	:global(.tt-pflicht) {
		font-size: 0.6875rem;
		color: rgba(255, 255, 255, 0.7);
		margin-top: 0.125rem;
	}
</style>
