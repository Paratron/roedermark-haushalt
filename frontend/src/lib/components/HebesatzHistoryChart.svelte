<script lang="ts">
	interface HistoryPoint {
		year: number;
		hebesatz: number;
	}
	/** Optional split of a single year into a neutral (blue) and an actual (red) bar. */
	interface SplitConfig {
		year: number;
		/** aufkommensneutraler Hebesatz (blauer Balken). */
		neutral: number;
	}

	let {
		history,
		split = null,
		newSystemFrom = null,
	}: {
		history: HistoryPoint[];
		split?: SplitConfig | null;
		/** Ab diesem Jahr gilt das neue Grundsteuersystem (Balken blau statt grau). */
		newSystemFrom?: number | null;
	} = $props();

	function fmtHS(v: number): string {
		if (!Number.isInteger(v)) {
			return v.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
		}
		return v.toLocaleString('de-DE');
	}

	let maxHist = $derived(
		Math.max(1, ...history.map((d) => d.hebesatz), split ? split.neutral : 0)
	);
</script>

<div class="vbar-chart">
	{#each history as entry, i (entry.year)}
		{@const prev = i > 0 ? history[i - 1] : null}
		{#if split && entry.year === split.year}
			{@const actual = entry.hebesatz}
			{@const realDelta = Math.round((actual - split.neutral) * 100) / 100}
			<div class="vbar-col vbar-col-split">
				<div class="vbar-split-pair">
					<!-- aufkommensneutral (blau): Reform-Umstellung, gleiche Einnahmen -->
					<div class="vbar-sub">
						<span class="vbar-delta vbar-delta-spacer">&nbsp;</span>
						<span class="vbar-label vbar-label-neutral">{fmtHS(split.neutral)}</span>
						<div class="vbar-track">
							<div
								class="vbar-fill vbar-fill-neutral"
								style="height: {(split.neutral / maxHist) * 100}%"
							></div>
						</div>
					</div>
					<!-- tatsächlich (rot): echte Erhöhung obendrauf -->
					<div class="vbar-sub">
						<span class="vbar-delta vbar-delta-up">▲{fmtHS(realDelta)}</span>
						<span class="vbar-label vbar-label-up">{fmtHS(actual)}</span>
						<div class="vbar-track">
							<div
								class="vbar-fill vbar-fill-up"
								style="height: {(actual / maxHist) * 100}%"
							></div>
						</div>
					</div>
				</div>
				<span class="vbar-year">{entry.year}</span>
			</div>
		{:else}
			{@const changed = prev && prev.hebesatz !== entry.hebesatz}
			{@const went_up = changed && entry.hebesatz > (prev?.hebesatz ?? 0)}
			{@const went_down = changed && entry.hebesatz < (prev?.hebesatz ?? 0)}
			{@const isOld = !changed && newSystemFrom != null && entry.year < newSystemFrom}
			<div class="vbar-col">
				{#if changed}
					<span class="vbar-delta" class:vbar-delta-up={went_up} class:vbar-delta-down={went_down}>
						{went_up ? '▲' : '▼'}{fmtHS(Math.abs(entry.hebesatz - (prev?.hebesatz ?? 0)))}
					</span>
				{/if}
				<span class="vbar-label" class:vbar-label-up={went_up} class:vbar-label-down={went_down}>
					{fmtHS(entry.hebesatz)}
				</span>
				<div class="vbar-track">
					<div
						class="vbar-fill"
						class:vbar-fill-up={went_up}
						class:vbar-fill-down={went_down}
						class:vbar-fill-old={isOld}
						style="height: {(entry.hebesatz / maxHist) * 100}%"
					></div>
				</div>
				<span class="vbar-year">{entry.year}</span>
			</div>
		{/if}
	{/each}
</div>

{#if newSystemFrom != null}
	<div class="vbar-legend">
		<span class="vbar-legend-item"><span class="vbar-sw vbar-sw-old"></span> altes Grundsteuersystem</span>
		<span class="vbar-legend-item"><span class="vbar-sw vbar-sw-new"></span> neues Grundsteuersystem</span>
		<span class="vbar-legend-item"><span class="vbar-sw vbar-sw-up"></span> Erhöhung</span>
	</div>
{/if}

<style>
	.vbar-chart { display: flex; align-items: flex-end; gap: 0.125rem; overflow-x: auto; padding-bottom: 0.25rem; }
	.vbar-col { display: flex; flex-direction: column; align-items: center; flex: 1 1 0; min-width: 2rem; }
	.vbar-col-split { flex: 1.4 1 0; min-width: 2.8rem; }
	.vbar-split-pair { display: flex; width: 100%; gap: 0; align-items: flex-end; }
	.vbar-sub { display: flex; flex-direction: column; align-items: center; flex: 1 1 0; min-width: 0; }
	.vbar-label { font-size: 0.625rem; font-weight: 600; color: var(--gray-500); margin-bottom: 0.125rem; white-space: nowrap; }
	.vbar-label-up { color: var(--red-600, #dc2626); }
	.vbar-label-down { color: var(--green-600, #16a34a); }
	.vbar-label-neutral { color: var(--brand-500, #3b82f6); }
	.vbar-delta { font-size: 0.5625rem; font-weight: 600; margin-bottom: 0.125rem; white-space: nowrap; }
	.vbar-delta-up { color: var(--red-500, #ef4444); }
	.vbar-delta-down { color: var(--green-500, #22c55e); }
	.vbar-delta-spacer { visibility: hidden; }
	.vbar-track { width: 100%; height: 8rem; background: var(--gray-50); border-radius: 0.25rem 0.25rem 0 0; display: flex; align-items: flex-end; }
	.vbar-fill { width: 100%; background: var(--brand-400, #60a5fa); border-radius: 0.25rem 0.25rem 0 0; transition: height 0.3s ease; min-height: 2px; }
	.vbar-fill-up { background: var(--red-400, #f87171); }
	.vbar-fill-down { background: var(--green-400, #4ade80); }
	.vbar-fill-old { background: var(--gray-300, #d1d5db); }
	.vbar-fill-neutral { background: var(--brand-400, #60a5fa); border-radius: 0.25rem 0 0 0; }
	.vbar-year { font-size: 0.625rem; color: var(--gray-400); margin-top: 0.25rem; white-space: nowrap; }

	.vbar-legend { display: flex; flex-wrap: wrap; align-items: center; gap: 0.25rem 0.75rem; margin-top: 0.5rem; font-size: 0.6875rem; color: var(--gray-500); }
	.vbar-legend-item { display: inline-flex; align-items: center; gap: 0.3rem; }
	.vbar-sw { display: inline-block; width: 0.7rem; height: 0.7rem; border-radius: 0.15rem; }
	.vbar-sw-old { background: var(--gray-300, #d1d5db); }
	.vbar-sw-new { background: var(--brand-400, #60a5fa); }
	.vbar-sw-up { background: var(--red-400, #f87171); }
</style>
