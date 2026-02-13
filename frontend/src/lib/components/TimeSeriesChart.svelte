<script lang="ts">
	import { onMount } from 'svelte';
	import { untrack } from 'svelte';
	import {
		Chart,
		LineController,
		BarController,
		LineElement,
		BarElement,
		PointElement,
		LinearScale,
		CategoryScale,
		Tooltip,
		Legend,
		Filler
	} from 'chart.js';
	import type { TimeSeriesPoint } from '$lib/types';

	Chart.register(
		LineController,
		BarController,
		LineElement,
		BarElement,
		PointElement,
		LinearScale,
		CategoryScale,
		Tooltip,
		Legend,
		Filler
	);

	interface Props {
		title?: string;
		series: TimeSeriesPoint[];
		yLabel?: string;
		multiSeries?: boolean;
		chartType?: 'line' | 'bar';
		/** Years that only have plan data (no Ist). Used to visually distinguish forecast bars. */
		planOnlyYears?: number[];
		/** Last year with actual Ist data – determines divider position. */
		lastIstYear?: number | null;
		/** Color bars by value: green = positive, red = negative (for Ergebnis charts). */
		valueColoring?: boolean;
		/** Fixed color for all bars (overrides valueColoring). Use for uni-directional data like Schuldenstand. */
		fixedColor?: 'red' | 'amber' | 'blue' | 'green' | 'gray';
	}

	let {
		title = '',
		series,
		yLabel = 'EUR',
		multiSeries = false,
		chartType = 'bar',
		planOnlyYears = [],
		lastIstYear = null,
		valueColoring = false,
		fixedColor,
	}: Props = $props();

	let canvasEl: HTMLCanvasElement;
	let chart: Chart | undefined;

	// Compute minimum chart width so bars stay readable on mobile
	let minWidthPx = $derived.by(() => {
		const years = new Set(series.map(p => p.year));
		const n = years.size;
		const perLabel = multiSeries ? 55 : 40;
		return Math.max(n * perLabel, 280);
	});

	/** Pick the best unit (divisor + label) based on the max absolute value in the series */
	function pickUnit(series: TimeSeriesPoint[]): { divisor: number; label: string; suffix: string } {
		const maxAbs = Math.max(...series.map((p) => Math.abs(p.amount)), 0);
		if (maxAbs >= 1_000_000) return { divisor: 1_000_000, label: 'Mio. €', suffix: 'Mio. €' };
		if (maxAbs >= 10_000) return { divisor: 1_000, label: 'T€', suffix: 'T€' };
		return { divisor: 1, label: '€', suffix: '€' };
	}

	function buildChartData() {
		if (!series || series.length === 0) return null;

		const planOnlySet = new Set(planOnlyYears);

		// Smart unit: pick divisor based on max absolute value
		const unit = pickUnit(series);

		// Detect uni-directional data for abs() display in valueColoring mode
		const amounts = series.map((p) => p.amount).filter((a) => a !== 0);
		const allNonNeg = amounts.length > 0 && amounts.every((a) => a >= 0);
		const allNonPos = amounts.length > 0 && amounts.every((a) => a <= 0);
		const useAbs = valueColoring && (allNonNeg || allNonPos);

		// Group by label + amount_type for multi-series, or just amount_type for single
		const grouped = new Map<string, Map<number, number>>();

		for (const point of series) {
			const key = multiSeries
				? `${point.label} (${point.amount_type})`
				: point.amount_type === 'ist' ? 'Ist' : 'Plan';

			if (!grouped.has(key)) grouped.set(key, new Map());
			const yearMap = grouped.get(key)!;
			// Keep the latest value per year (dedup)
			yearMap.set(point.year, point.amount);
		}

		// Collect all years
		const allYears = [...new Set(series.map((p) => p.year))].sort((a, b) => a - b);

		// Determine divider position: after lastIstYear
		let dividerIdx = -1;
		if (lastIstYear !== null) {
			const istIdx = allYears.indexOf(lastIstYear);
			if (istIdx >= 0 && istIdx < allYears.length - 1) {
				dividerIdx = istIdx + 1; // divider is drawn BEFORE this index
			}
		}

		// Value-based coloring: green for positive, red for negative
		if (valueColoring && !multiSeries) {
			const datasets = [...grouped.entries()].map(([label, yearMap]) => {
				const isIst = label === 'Ist';

				const bgPerBar = allYears.map((y) => {
					const val = yearMap.get(y);
					if (val === undefined) return 'transparent';
					const isPlanOnly = planOnlySet.has(y);
					const alpha = isPlanOnly ? 0.25 : isIst ? 0.7 : 0.45;
					return val >= 0
						? `rgba(16, 185, 129, ${alpha})`   // green = surplus
						: `rgba(220, 38, 38, ${alpha})`;    // red = deficit
				});

				const borderPerBar = allYears.map((y) => {
					const val = yearMap.get(y);
					if (val === undefined) return 'transparent';
					const isPlanOnly = planOnlySet.has(y);
					const alphaHex = isPlanOnly ? '60' : isIst ? 'ff' : 'a0';
					return val >= 0
						? `#059669${alphaHex}`   // green border
						: `#dc2626${alphaHex}`;  // red border
				});

				return {
					label,
					data: allYears.map((y) => {
						const val = yearMap.get(y);
						if (val === undefined) return null;
						const scaled = val / unit.divisor;
						return useAbs ? Math.abs(scaled) : scaled;
					}),
					backgroundColor: bgPerBar,
					borderColor: borderPerBar,
					borderWidth: allYears.map((y) => planOnlySet.has(y) ? 1 : 2),
					borderDash: !isIst ? [4, 4] : [],
					pointRadius: 3,
					tension: 0.1,
					spanGaps: true,
				};
			});

			return { labels: allYears.map(String), datasets, _dividerIdx: dividerIdx, _unit: unit };
		}

		// Fixed color mode: one color for all bars (e.g. Schuldenstand always in red/amber)
		if (fixedColor && !multiSeries) {
			const colorMap: Record<string, { rgb: string; border: string }> = {
				red:   { rgb: '220, 38, 38',   border: '#dc2626' },
				amber: { rgb: '217, 119, 6',   border: '#d97706' },
				blue:  { rgb: '59, 130, 246',  border: '#2563eb' },
				green: { rgb: '16, 185, 129',  border: '#059669' },
				gray:  { rgb: '107, 114, 128', border: '#6b7280' },
			};
			const c = colorMap[fixedColor] ?? colorMap.gray;

			const datasets = [...grouped.entries()].map(([label, yearMap]) => {
				const isIst = label === 'Ist';

				const bgPerBar = allYears.map((y) => {
					const val = yearMap.get(y);
					if (val === undefined) return 'transparent';
					const isPlanOnly = planOnlySet.has(y);
					const alpha = isPlanOnly ? 0.25 : isIst ? 0.7 : 0.45;
					return `rgba(${c.rgb}, ${alpha})`;
				});

				const borderPerBar = allYears.map((y) => {
					if (yearMap.get(y) === undefined) return 'transparent';
					const isPlanOnly = planOnlySet.has(y);
					const alphaHex = isPlanOnly ? '60' : isIst ? 'ff' : 'a0';
					return `${c.border}${alphaHex}`;
				});

				return {
					label,
					data: allYears.map((y) => {
						const val = yearMap.get(y);
						return val !== undefined ? val / unit.divisor : null;
					}),
					backgroundColor: bgPerBar,
					borderColor: borderPerBar,
					borderWidth: allYears.map((y) => planOnlySet.has(y) ? 1 : 2),
					borderDash: !isIst ? [4, 4] : [],
					pointRadius: 3,
					tension: 0.1,
					spanGaps: true,
				};
			});

			return { labels: allYears.map(String), datasets, _dividerIdx: dividerIdx, _unit: unit };
		}

		// Standard coloring: by series name
		const colors: Record<string, { bg: string; border: string }> = {
			'Ist': { bg: 'rgba(16, 185, 129, 0.6)', border: '#059669' },
			'Plan': { bg: 'rgba(59, 130, 246, 0.6)', border: '#2563eb' },
		};

		// Semantic color mapping for multi-series: keywords → color
		function getSemanticColor(label: string): { bg: string; border: string } | null {
			const lower = label.toLowerCase();
			const isIst = lower.includes('(ist)');
			const isPlan = lower.includes('(plan)');

			// Debt page: Kreditaufnahme = red (new debt), Tilgung = green (paying off)
			if (lower.includes('kredit') || lower.includes('neuverschuldung')) {
				return isIst
					? { bg: 'rgba(220, 38, 38, 0.7)', border: '#dc2626' }
					: isPlan
						? { bg: 'rgba(220, 38, 38, 0.25)', border: '#dc262660' }
						: { bg: 'rgba(220, 38, 38, 0.5)', border: '#dc2626' };
			}
			if (lower.includes('tilg')) {
				return isIst
					? { bg: 'rgba(5, 150, 105, 0.7)', border: '#059669' }
					: isPlan
						? { bg: 'rgba(5, 150, 105, 0.25)', border: '#05966960' }
						: { bg: 'rgba(5, 150, 105, 0.5)', border: '#059669' };
			}

			if (lower.includes('ertr') || lower.includes('einnahm') || lower.includes('einzahl')) {
				return isIst
					? { bg: 'rgba(5, 150, 105, 0.7)', border: '#059669' }
					: isPlan
						? { bg: 'rgba(5, 150, 105, 0.25)', border: '#05966960' }
						: { bg: 'rgba(5, 150, 105, 0.5)', border: '#059669' };
			}
			if (lower.includes('aufwend') || lower.includes('ausgab') || lower.includes('auszahl')) {
				return isIst
					? { bg: 'rgba(220, 38, 38, 0.7)', border: '#dc2626' }
					: isPlan
						? { bg: 'rgba(220, 38, 38, 0.25)', border: '#dc262660' }
						: { bg: 'rgba(220, 38, 38, 0.5)', border: '#dc2626' };
			}
			return null;
		}

		// Color palette fallback for multi-series
		const palette = [
			{ bg: 'rgba(5, 150, 105, 0.5)', border: '#059669' },    // green
			{ bg: 'rgba(220, 38, 38, 0.5)', border: '#dc2626' },    // red
			{ bg: 'rgba(59, 130, 246, 0.5)', border: '#2563eb' },   // blue
			{ bg: 'rgba(245, 158, 11, 0.5)', border: '#d97706' },   // amber
			{ bg: 'rgba(139, 92, 246, 0.5)', border: '#7c3aed' },   // purple
			{ bg: 'rgba(236, 72, 153, 0.5)', border: '#db2777' },   // pink
		];

		// Sort entries: Ist datasets first, then Plan – so bars are grouped Ist|Ist, Plan|Plan
		const sortedEntries = [...grouped.entries()].sort(([a], [b]) => {
			const aIsIst = a.toLowerCase().includes('(ist)');
			const bIsIst = b.toLowerCase().includes('(ist)');
			if (aIsIst && !bIsIst) return -1;
			if (!aIsIst && bIsIst) return 1;
			return a.localeCompare(b);
		});

		let colorIdx = 0;
		const datasets = sortedEntries.map(([label, yearMap]) => {
			const semantic = multiSeries ? getSemanticColor(label) : null;
			const c = semantic || colors[label] || palette[colorIdx++ % palette.length];
			const isPlan = label.toLowerCase().includes('(plan)');

			// Per-bar colors: reduce opacity for plan-only years (non-semantic only)
			const bgPerBar = allYears.map((y) => {
				if (!semantic && planOnlySet.has(y)) {
					return c.bg.replace(/[\d.]+\)$/, '0.25)');
				}
				return c.bg;
			});
			const borderPerBar = allYears.map((y) => {
				if (!semantic && planOnlySet.has(y)) {
					return c.border + '80';
				}
				return c.border;
			});

			return {
				label,
				data: allYears.map((y) => {
					const val = yearMap.get(y);
					return val !== undefined ? val / unit.divisor : null;
				}),
				backgroundColor: bgPerBar,
				borderColor: borderPerBar,
				borderWidth: isPlan ? 1 : 2,
				borderDash: isPlan ? [4, 4] : [],
				pointRadius: 3,
				tension: 0.1,
				spanGaps: true,
			};
		});

		return {
			labels: allYears.map(String),
			datasets,
			_dividerIdx: dividerIdx,
			_unit: unit,
		};
	}

	function createChart() {
		if (chart) {
			chart.destroy();
			chart = undefined;
		}

		const data = buildChartData();
		if (!data || !canvasEl) return;

		const dividerIdx = data._dividerIdx as number;
		const chartUnit = (data as any)._unit as { divisor: number; label: string; suffix: string };

		// Custom plugin: draw a vertical dashed line separating Ist from Plan
		const dividerPlugin = {
			id: 'istPlanDivider',
			afterDraw(chart: any) {
				if (dividerIdx <= 0) return;
				const xScale = chart.scales.x;
				const yScale = chart.scales.y;
				// Draw between the year before and the year at dividerIdx
				const x = (xScale.getPixelForValue(dividerIdx - 1) + xScale.getPixelForValue(dividerIdx)) / 2;
				const ctx = chart.ctx;
				ctx.save();
				ctx.beginPath();
				ctx.setLineDash([6, 4]);
				ctx.strokeStyle = '#9ca3af';
				ctx.lineWidth = 1.5;
				ctx.moveTo(x, yScale.top);
				ctx.lineTo(x, yScale.bottom);
				ctx.stroke();
				// Label
				ctx.fillStyle = '#6b7280';
				ctx.font = '10px sans-serif';
				ctx.textAlign = 'center';
				ctx.fillText('← Ist | Plan →', x, yScale.top - 6);
				ctx.restore();
			}
		};

		chart = new Chart(canvasEl, {
			type: chartType,
			data: { labels: data.labels, datasets: data.datasets },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				layout: {
					padding: {
						top: dividerIdx > 0 ? 16 : 0,
					},
				},
				interaction: {
					mode: 'index',
					intersect: false,
				},
				plugins: {
					legend: {
						display: !valueColoring && !fixedColor,
						position: 'bottom',
					},
					tooltip: {
						callbacks: {
							label: (ctx) => {
								const val = ctx.parsed.y;
								if (val == null) return `${ctx.dataset.label}: Unbekannt`;
								const decimals = chartUnit.divisor >= 1_000_000 ? 1 : chartUnit.divisor >= 1_000 ? 0 : 0;
								return `${ctx.dataset.label}: ${val.toFixed(decimals)} ${chartUnit.suffix}`;
							},
						},
					},
				},
				scales: {
					y: {
						title: {
							display: true,
							text: chartUnit.label,
						},
						ticks: {
							callback: (value) => {
								const v = typeof value === 'number' ? value : parseFloat(value as string);
								const decimals = chartUnit.divisor >= 1_000_000 ? 1 : 0;
								return `${v.toFixed(decimals)} ${chartUnit.label}`;
							},
						},
					},
					x: {
						title: {
							display: true,
							text: 'Jahr',
						},
					},
				},
			},
			plugins: [dividerPlugin],
		});
	}

	onMount(() => {
		return () => {
			chart?.destroy();
		};
	});

	// React to prop changes: rebuild chart when series, planOnlyYears, etc. change
	$effect(() => {
		// Access reactive props to track them
		series;
		planOnlyYears;
		lastIstYear;
		valueColoring;
		fixedColor;
		multiSeries;
		chartType;

		// Run chart creation untracked to avoid circular deps
		untrack(() => {
			if (canvasEl) createChart();
		});
	});
</script>

{#if title}
	<h4 class="chart-title">{title}</h4>
{/if}
<div class="chart-scroll">
	<div class="chart-container" style="min-width: {minWidthPx}px;">
		<canvas bind:this={canvasEl}></canvas>
	</div>
</div>

<style>
	.chart-title {
		margin-bottom: 0.75rem;
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--gray-500);
	}
	.chart-scroll {
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
		margin-left: -1rem;
		margin-right: -1rem;
		padding-left: 1rem;
	}
	@media (min-width: 640px) {
		.chart-scroll {
			margin-left: -1.5rem;
			margin-right: -1.5rem;
			padding-left: 1.5rem;
		}
	}
	.chart-container {
		position: relative;
		width: 100%;
		height: 18rem;
	}
	@media (min-width: 640px) {
		.chart-container { height: 20rem; }
	}
</style>
