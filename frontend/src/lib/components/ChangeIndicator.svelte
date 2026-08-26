<script lang="ts">
	import { TrendingUp, TrendingDown, Minus } from '@lucide/svelte';
	import { formatAmount } from '$lib/format';

	interface Props {
		/** Absolute difference */
		diff: number;
		/** Ratio (e.g. 0.05 = +5%) */
		ratio: number | null;
		/**
		 * Auch den Betrag zeigen, nicht nur den Prozentwert. Die Legende neben dem
		 * Donut hat dafür keinen Platz, eine Tabellenspalte schon.
		 */
		showAmount?: boolean;
		/**
		 * Ob ein Anstieg gut ist.
		 *
		 * Voreingestellt ist "nein": die Komponente kam von der Ausgabenseite, wo mehr
		 * schlechter ist. Bei Erträgen ist es umgekehrt – ohne diesen Schalter stünde
		 * eine Steuererhöhung in Rot und eine gestrichene Einnahme in Grün.
		 */
		upIsGood?: boolean;
		/** Text statt Balken, wenn sich nichts bewegt hat. */
		unchangedLabel?: string;
	}

	let {
		diff,
		ratio,
		showAmount = false,
		upIsGood = false,
		unchangedLabel = ''
	}: Props = $props();

	let unveraendert = $derived(Math.abs(diff) < 0.005);
	let gut = $derived(upIsGood ? diff > 0 : diff < 0);
	let sign = $derived(diff > 0 ? '+' : '');
</script>

{#if unveraendert && unchangedLabel}
	<span class="change is-flat">{unchangedLabel}</span>
{:else}
	<span class="change" class:is-good={!unveraendert && gut} class:is-bad={!unveraendert && !gut}>
		{#if diff > 0}
			<TrendingUp class="change-icon" />
		{:else if diff < 0}
			<TrendingDown class="change-icon" />
		{:else}
			<Minus class="change-icon" />
		{/if}
		{#if showAmount}
			{sign}{formatAmount(diff)}
		{/if}
		{#if ratio !== null}
			<span class="change-pct">
				{showAmount ? '(' : ''}{sign}{(ratio * 100).toFixed(1)} %{showAmount ? ')' : ''}
			</span>
		{/if}
	</span>
{/if}

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
	.change.is-good {
		color: var(--green-600, #16a34a);
	}
	.change.is-bad {
		color: var(--red-600, #dc2626);
	}
	.change.is-flat {
		color: var(--gray-400);
	}
	.change-pct {
		font-weight: 400;
		opacity: 0.85;
	}
	:global(.change-icon) {
		width: 0.875rem;
		height: 0.875rem;
		flex-shrink: 0;
	}
</style>
