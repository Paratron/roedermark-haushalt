<script lang="ts">
	import { formatAmount } from '$lib/format';

	export interface StackSegment {
		key: string;
		label: string;
		color: string;
		/** Wert der linken Säule */
		alt: number;
		/** Wert der rechten Säule */
		neu: number;
	}

	interface Props {
		segments: StackSegment[];
		altLabel: string;
		neuLabel: string;
		/** Hervorgehobenes Segment; alle anderen treten zurück. */
		selectedKey?: string | null;
		onSelect?: (key: string) => void;
	}

	let { segments, altLabel, neuLabel, selectedKey = null, onSelect }: Props = $props();

	let summeAlt = $derived(segments.reduce((s, x) => s + x.alt, 0));
	let summeNeu = $derived(segments.reduce((s, x) => s + x.neu, 0));

	/**
	 * Beide Säulen teilen sich einen Maßstab.
	 *
	 * Jede für sich auf volle Höhe zu strecken würde genau das verstecken, worum es
	 * hier geht: dass die eine Fassung insgesamt mehr vorsieht als die andere.
	 */
	let maximum = $derived(Math.max(summeAlt, summeNeu, 1));

	/**
	 * Ober- und Unterkante jedes Segments in beiden Säulen, in Prozent der Spurhöhe
	 * und von oben gemessen – so rechnet SVG.
	 *
	 * Daraus entsteht das Band dazwischen: es läuft von der Oberkante links zur
	 * Oberkante rechts und an der Unterkante zurück. Wo ein Posten gewachsen ist,
	 * wird das Band breiter.
	 */
	let baender = $derived.by(() => {
		let kumAlt = 0;
		let kumNeu = 0;
		return segments.map((seg) => {
			const altUnten = 100 - (kumAlt / maximum) * 100;
			const neuUnten = 100 - (kumNeu / maximum) * 100;
			kumAlt += seg.alt;
			kumNeu += seg.neu;
			const altOben = 100 - (kumAlt / maximum) * 100;
			const neuOben = 100 - (kumNeu / maximum) * 100;
			return {
				...seg,
				pfad:
					`M 0,${altOben} C 40,${altOben} 60,${neuOben} 100,${neuOben}` +
					` L 100,${neuUnten} C 60,${neuUnten} 40,${altUnten} 0,${altUnten} Z`
			};
		});
	});

	const hoehe = (wert: number) => (wert / maximum) * 100;

	const anteil = (wert: number, summe: number) =>
		summe > 0 ? `${((wert / summe) * 100).toFixed(1)} %` : '–';
</script>

<div class="vergleich">
	<div class="saeule-block">
		<div class="saeule-kopf">
			<span class="saeule-label">{altLabel}</span>
			<span class="saeule-summe">{formatAmount(summeAlt)}</span>
		</div>
		<div class="saeule-spur">
			<div class="saeule" style="height: {hoehe(summeAlt)}%">
				{#each segments as seg (seg.key)}
					{#if seg.alt > 0}
						<button
							class="segment"
							class:is-aktiv={selectedKey === seg.key}
							class:is-blass={selectedKey !== null && selectedKey !== seg.key}
							style="height: {(seg.alt / summeAlt) * 100}%; background: {seg.color}"
							title="{seg.label}: {formatAmount(seg.alt)} ({anteil(seg.alt, summeAlt)})"
							aria-label="{altLabel}, {seg.label}, {formatAmount(seg.alt)}"
							onclick={() => onSelect?.(seg.key)}
						></button>
					{/if}
				{/each}
			</div>
		</div>
	</div>

	<div class="baender-spur">
		<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
			{#each baender as b (b.key)}
				<path
					d={b.pfad}
					fill={b.color}
					class="band"
					class:is-aktiv={selectedKey === b.key}
					class:is-blass={selectedKey !== null && selectedKey !== b.key}
				/>
			{/each}
		</svg>
	</div>

	<div class="saeule-block">
		<div class="saeule-kopf">
			<span class="saeule-label">{neuLabel}</span>
			<span class="saeule-summe">{formatAmount(summeNeu)}</span>
		</div>
		<div class="saeule-spur">
			<div class="saeule" style="height: {hoehe(summeNeu)}%">
				{#each segments as seg (seg.key)}
					{#if seg.neu > 0}
						<button
							class="segment"
							class:is-aktiv={selectedKey === seg.key}
							class:is-blass={selectedKey !== null && selectedKey !== seg.key}
							style="height: {(seg.neu / summeNeu) * 100}%; background: {seg.color}"
							title="{seg.label}: {formatAmount(seg.neu)} ({anteil(seg.neu, summeNeu)})"
							aria-label="{neuLabel}, {seg.label}, {formatAmount(seg.neu)}"
							onclick={() => onSelect?.(seg.key)}
						></button>
					{/if}
				{/each}
			</div>
		</div>
	</div>
</div>

<style>
	.vergleich {
		display: flex;
		align-items: flex-end;
		gap: 0;
		padding: 0.5rem 0;
	}
	.saeule-block {
		display: flex;
		flex-direction: column;
		/* Die Saeulen tragen die Aussage, das Band verbindet sie nur - also bekommen
		   sie den Platz und der Zwischenraum den Rest, nicht umgekehrt. */
		flex: 1 1 0;
		min-width: 3rem;
	}
	.saeule-kopf {
		display: flex;
		flex-direction: column;
		gap: 0.0625rem;
		margin-bottom: 0.5rem;
		text-align: center;
	}
	.saeule-label {
		font-size: 0.75rem;
		color: var(--gray-500);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.saeule-summe {
		font-size: 0.8125rem;
		font-weight: 600;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	/* Die Spur gibt beiden Säulen und den Bändern dieselbe Bezugshöhe – nur so
	   liegen Segmentkanten und Bandkanten aufeinander. */
	.saeule-spur {
		height: 16rem;
		display: flex;
		align-items: flex-end;
	}
	.saeule {
		display: flex;
		flex-direction: column-reverse;
		width: 100%;
		overflow: hidden;
	}
	.segment {
		display: block;
		width: 100%;
		padding: 0;
		border: none;
		cursor: pointer;
		transition: opacity 0.15s ease, filter 0.15s ease;
	}
	.segment:hover {
		filter: brightness(1.12);
	}
	.segment.is-blass {
		opacity: 0.3;
	}
	.segment.is-aktiv {
		filter: brightness(1.15);
	}
	.segment:focus-visible {
		outline: 2px solid var(--brand-600);
		outline-offset: -2px;
	}

	.baender-spur {
		flex: 0 0 clamp(1.5rem, 18%, 3.5rem);
		/* Kopfzeile der Säulen ausgleichen, damit die Bänder auf Spurhöhe sitzen. */
		margin-top: calc(0.5rem + 2.1rem);
		height: 16rem;
	}
	.baender-spur svg {
		display: block;
		width: 100%;
		height: 100%;
	}
	.band {
		opacity: 0.35;
		transition: opacity 0.15s ease;
	}
	.band.is-blass {
		opacity: 0.08;
	}
	.band.is-aktiv {
		opacity: 0.6;
	}

	@media (max-width: 30rem) {
		.saeule-spur,
		.baender-spur {
			height: 12rem;
		}
		.saeule-block {
			min-width: 2.5rem;
		}
	}
</style>
