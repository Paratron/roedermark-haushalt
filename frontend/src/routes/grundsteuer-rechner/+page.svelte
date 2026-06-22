<script lang="ts">
	import type { PageData } from './$types';
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';
	import SocialMeta from '$lib/components/SocialMeta.svelte';
	import GrundsteuerRechner from '$lib/components/GrundsteuerRechner.svelte';
	import { Calculator } from '@lucide/svelte';

	let { data }: { data: PageData } = $props();

	function fmtPct(p: number): string {
		return p.toLocaleString('de-DE') + ' %';
	}
</script>

<SocialMeta
	title="Grundsteuer-Rechner Rödermark"
	description="Was die Anhebung der Grundsteuer B in Rödermark ({fmtPct(data.aktuell)} → {fmtPct(
		data.neu
	)}) konkret für Sie bedeutet – für Eigenheim, Eigentumswohnung und Miete, mit Schätzung ohne Steuerbescheid."
	path="/grundsteuer-rechner"
/>

<AnchorHeading level={2} id="grundsteuer-rechner">
	<Calculator /> Grundsteuer-Rechner
</AnchorHeading>

<p class="page-intro">
	Rödermark hebt den Hebesatz der Grundsteuer&nbsp;B zum {data.neuJahr} von
	<strong>{fmtPct(data.aktuell)}</strong> auf <strong>{fmtPct(data.neu)}</strong> an – die mit
	Abstand größte Einzelmaßnahme des <a href="/hsk2026">Haushaltssicherungskonzepts</a>. Weil die
	Grundsteuer direkt mit dem Hebesatz steigt, bedeutet das rund
	<strong>{Math.round((data.neu / data.aktuell - 1) * 100)} % mehr</strong> für jeden betroffenen
	Haushalt. Rechnen Sie hier aus, was das für Sie heißt – auch ohne Steuerbescheid zur Hand.
</p>

<section class="section">
	<GrundsteuerRechner
		aktuell={data.aktuell}
		neu={data.neu}
		aktuellJahr={data.aktuellJahr}
		neuJahr={data.neuJahr}
	/>
</section>

<div class="info-box info-box-blue section">
	<div class="info-content">
		<p>
			<strong>Wie der Rechner rechnet.</strong> Die Grundsteuer ist
			<em>Messbetrag × Hebesatz</em>. Der Messbetrag (vom Finanzamt) ändert sich {data.neuJahr}
			nicht – nur der Hebesatz. Die Mehrbelastung ist daher schlicht Ihre bisherige Grundsteuer
			mal {(data.neu / data.aktuell).toLocaleString('de-DE', { maximumFractionDigits: 2 })}.
		</p>
		<p>
			Kennen Sie weder Grundsteuer noch Messbetrag, schätzt der Rechner den Messbetrag nach dem
			hessischen <strong>Flächen-Faktor-Modell</strong>: Grundstücksfläche × 0,04&nbsp;€ +
			Wohnfläche × 0,35&nbsp;€ (0,50&nbsp;€/m² × 70&nbsp;% Steuermesszahl für Wohnen). Bei
			Eigentumswohnung und Miete zählt nur Ihre eigene Wohnfläche – das ergibt Ihren Anteil, nicht
			die Steuer des ganzen Gebäudes. Der Lagefaktor liegt in Rödermark durch die enge
			Bodenrichtwert-Spanne nahe 1,0 (±5&nbsp;%) und wird pauschal so angesetzt. Die Schätzung
			ersetzt keinen Steuerbescheid.
		</p>
	</div>
</div>

<p class="source-footer">
	Hebesätze: Grundsteuer-B-Datensatz der Stadt Rödermark
	{#if data.quelle}({data.quelle}){/if}. Berechnungsmodell: Hessisches Grundsteuergesetz
	(Flächen-Faktor-Verfahren), Hessisches Ministerium der Finanzen.
</p>

<style>
	.section {
		padding-top: 1.5rem;
	}
	.info-content > p {
		margin: 0 0 0.75rem;
	}
	.info-content > p:last-child {
		margin-bottom: 0;
	}
	.page-intro {
		color: var(--gray-700);
		max-width: 65ch;
		margin-bottom: 0.5rem;
		line-height: 1.6;
	}
	.source-footer {
		margin-top: 2rem;
		font-size: 0.85rem;
		color: var(--gray-500);
		max-width: 65ch;
	}
</style>
