<script lang="ts">
	import { TrendingUp, TrendingDown, Minus } from '@lucide/svelte';

	interface Props {
		/** Absolute difference */
		diff: number;
		/** Ratio (e.g. 0.05 = +5%) */
		ratio: number;
	}

	let { diff, ratio }: Props = $props();

	let sign = $derived(diff > 0 ? '+' : '');
	let label = $derived(`${sign}${(ratio * 100).toFixed(1)} %`);
</script>

<span class="change" class:is-up={diff > 0} class:is-down={diff < 0}>
	{#if diff > 0}
		<TrendingUp class="change-icon" />
	{:else if diff < 0}
		<TrendingDown class="change-icon" />
	{:else}
		<Minus class="change-icon" />
	{/if}
	{label}
</span>

<style>
	.change {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--gray-400);
		white-space: nowrap;
	}
	.change.is-up {
		color: var(--red-600, #dc2626);
	}
	.change.is-down {
		color: var(--green-600, #16a34a);
	}
	:global(.change-icon) {
		width: 0.875rem;
		height: 0.875rem;
		flex-shrink: 0;
	}
</style>
