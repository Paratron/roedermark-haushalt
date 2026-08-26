<script lang="ts">
	import type { PageData } from './$types';
	import { formatAmount, formatMio } from '$lib/format';
	import StackedCompareBars from '$lib/components/StackedCompareBars.svelte';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';
	import SocialMeta from '$lib/components/SocialMeta.svelte';
	import ChangeIndicator from '$lib/components/ChangeIndicator.svelte';
	import { GitCompareArrows, TriangleAlert, List } from '@lucide/svelte';

	let { data }: { data: PageData } = $props();

	const { jahr, altLabel, neuLabel, seiten, ergebnis, quellen } = data;

	let selectedNr = $state<string | null>(null);
	let selectedSide = $state<'einnahmen' | 'ausgaben'>('einnahmen');

	function klick(side: 'einnahmen' | 'ausgaben', nr: string) {
		if (selectedNr === nr && selectedSide === side) {
			selectedNr = null;
		} else {
			selectedNr = nr;
			selectedSide = side;
		}
	}

	let gewaehlt = $derived.by(() => {
		if (!selectedNr) return null;
		const seite = seiten.find((s) => s.side === selectedSide);
		return seite?.slices.find((s) => s.category.nr === selectedNr) ?? null;
	});

	const defizitAlt = ergebnis ? Math.abs(ergebnis.alt) : null;
	const defizitNeu = ergebnis ? Math.abs(ergebnis.neu) : null;
</script>

<SocialMeta
	title="Haushalt {jahr}: Entwurf und Neufassung im Vergleich"
	description="Das geplante Defizit der Stadt Rödermark für {jahr} halbiert sich. Welche Einnahmen und Ausgaben sich dafür bewegt haben – mit Quelle für jede Zahl."
	path="/vergleich-{jahr}"
/>

<AnchorHeading level={2} id="vergleich">
	<GitCompareArrows /> Haushalt {jahr}: was sich geändert hat
</AnchorHeading>
<p class="page-intro">
	Für {jahr} gibt es zwei Fassungen des Haushaltsplans: den ursprünglichen Entwurf und die
	Neufassung, die ihn ersetzt. Die beiden Säulen stellen sie im gleichen Maßstab gegenüber; die
	Bänder dazwischen verbinden, was zusammengehört – wo ein Band breiter wird, ist der Posten
	gewachsen. Ein Klick zeigt, was darin steckt.
</p>

<div class="info-box info-box-amber vorlage-hinweis">
	<TriangleAlert class="info-icon" />
	<div>
		<strong>Noch nicht beschlossen.</strong> Die Neufassung ist eine Beschlussvorlage. Die
		Stadtverordnetenversammlung entscheidet am <strong>08.09.2026</strong> darüber.
	</div>
</div>

{#if defizitAlt !== null && defizitNeu !== null && ergebnis}
	<section class="section">
		<div class="ergebnis-leiste">
			<div class="ergebnis-teil">
				<span class="ergebnis-label">{altLabel}</span>
				<span class="ergebnis-wert">&minus;{formatMio(defizitAlt)}</span>
			</div>
			<span class="ergebnis-pfeil" aria-hidden="true">&rarr;</span>
			<div class="ergebnis-teil">
				<span class="ergebnis-label">{neuLabel}</span>
				<span class="ergebnis-wert">&minus;{formatMio(defizitNeu)}</span>
			</div>
			<div class="ergebnis-teil ergebnis-delta">
				<span class="ergebnis-label">geplantes Jahresergebnis</span>
				<span class="ergebnis-wert ergebnis-besser">{formatMio(ergebnis.delta)} weniger Defizit</span>
			</div>
		</div>
		<SourceCitation description="Ordentliches Ergebnis {jahr}, beide Fassungen" links={quellen} />
	</section>
{/if}

{#each seiten as seite (seite.side)}
	<section class="section">
		<h4 class="detail-title {seite.side}-title">
			{seite.titel} {jahr}
			<span class="detail-title-sum">
				{formatAmount(seite.summe)}
				<span class="detail-title-diff">
					<ChangeIndicator
						diff={seite.summe - seite.summeAlt}
						ratio={seite.summeAlt > 0 ? (seite.summe - seite.summeAlt) / seite.summeAlt : null}
						showAmount
						upIsGood={seite.side === 'einnahmen'}
					/>
					gegenüber {altLabel}
				</span>
			</span>
		</h4>
		<div class="card card-padded donut-detail-row">
			<div class="donut-col">
				<StackedCompareBars
					segments={seite.slices.map((sl) => ({
						key: sl.category.nr,
						label: sl.category.label,
						color: sl.category.color,
						alt: sl.alt,
						neu: sl.amount
					}))}
					{altLabel}
					{neuLabel}
					selectedKey={selectedSide === seite.side ? selectedNr : null}
					onSelect={(nr) => klick(seite.side, nr)}
				/>
			</div>
			<div class="detail-col">
				<div class="detail-table-wrap">
					<table class="detail-table">
						<thead>
							<tr>
								<th>Kategorie</th>
								<th class="col-right">{neuLabel}</th>
								<th class="col-right hide-mobile">Anteil</th>
								<th class="col-right">gegenüber {altLabel}</th>
							</tr>
						</thead>
						<tbody>
							{#each seite.slices as slice (slice.category.nr)}
								{@const aktiv = selectedNr === slice.category.nr && selectedSide === seite.side}
								<tr
									class="detail-row {aktiv ? 'detail-row-active' : ''}"
									onclick={() => klick(seite.side, slice.category.nr)}
									onkeydown={(e) => {
										if (e.key === 'Enter' || e.key === ' ') {
											e.preventDefault();
											klick(seite.side, slice.category.nr);
										}
									}}
									tabindex="0"
									role="button"
									aria-expanded={aktiv}
								>
									<td>
										<span class="cat-dot" style="background: {slice.category.color}"></span>
										{slice.category.label}
										{#if slice.detail.length > 0}<span class="mehr-hinweis">Details</span>{/if}
									</td>
									<td class="col-right">{formatAmount(slice.amount)}</td>
									<td class="col-right hide-mobile">{(slice.percent * 100).toFixed(1)} %</td>
									<td class="col-right">
										<ChangeIndicator
											diff={slice.diff}
											ratio={slice.ratio}
											showAmount
											upIsGood={seite.side === 'einnahmen'}
											unchangedLabel="unverändert"
										/>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		</div>

		{#if gewaehlt && selectedSide === seite.side}
			{@const g = gewaehlt}
			<div class="card card-padded sub-items-card">
				<h4 class="sub-items-title">
					<List class="sub-items-icon" />
					<span class="cat-dot-lg" style="background: {g.category.color}"></span>
					{g.category.label} –
					{g.detailArt === 'konten' ? 'im Einzelnen' : 'nach Fachbereich'}
				</h4>
				<p class="sub-items-hint">{g.category.description}</p>
				{#if g.detail.length === 0}
					<p class="sub-items-hint">
						Für diese Kategorie geben die beiden Pläne keine vergleichbare Aufschlüsselung her.
					</p>
				{:else}
					<div class="sub-items-table-wrap">
						<table class="sub-items-table">
							<thead>
								<tr>
									<th>Position</th>
									<th class="col-right">{neuLabel}</th>
									<th class="col-right hide-mobile">Anteil</th>
									<th class="col-right">gegenüber {altLabel}</th>
								</tr>
							</thead>
							<tbody>
								{#each g.detail as z (z.konto ?? z.label)}
									<tr>
										<td class="sub-item-label">
											{#if z.konto}<span class="sub-item-konto">{z.konto}</span>{/if}
											{z.label}
										</td>
										<td class="col-right">{formatAmount(z.amount)}</td>
										<td class="col-right hide-mobile">{(z.percent * 100).toFixed(1)} %</td>
										<td class="col-right">
											<ChangeIndicator
												diff={z.diff}
												ratio={z.ratio}
												showAmount
												upIsGood={seite.side === 'einnahmen'}
												unchangedLabel="unverändert"
											/>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</div>
		{/if}
	</section>
{/each}

<section class="section">
	<AnchorHeading level={3} id="methodik">Woher die Zahlen kommen</AnchorHeading>
	<div class="card card-padded methodik">
		<p>
			Beide Fassungen stammen aus den offiziellen PDF-Haushaltsplänen der Stadt Rödermark. Die
			Kategorien sind dieselben wie auf der Seite
			<a href="/kategorien/ertrag">Einnahmen &amp; Ausgaben</a>.
		</p>
		<p>
			Alle Beträge stehen ohne Vorzeichen, auch die Ausgaben. Ein Minus heißt deshalb immer, dass
			der Posten kleiner geworden ist. <strong>Grün</strong> markiert, was den Haushalt entlastet –
			mehr Einnahmen oder weniger Ausgaben –, <strong>rot</strong> das Gegenteil.
		</p>
		<p>
			Die Aufschlüsselung zeigt einzelne Konten, wo beide Pläne sie vollständig ausweisen, sonst
			die Fachbereiche. Wo die Neufassung eine Kategorie nur teilweise nach Konten aufgliedert,
			bleibt die Aufschlüsselung leer: eine stadtweite Summe gegen den Anteil eines einzelnen
			Teilhaushalts zu stellen ergäbe Zahlen, die nach Einsparung aussehen, aber keine sind.
		</p>
		<SourceCitation description="Haushaltsplan {jahr}, beide Fassungen" links={quellen} />
	</div>
</section>

<style>
	/*
	 * .section definiert jede Seite fuer sich - global gibt es die Klasse nicht.
	 * Ohne diese Regeln stehen Ueberschriften, Karten und Hinweisbox ohne jeden
	 * Abstand aufeinander.
	 */
	.section {
		margin-bottom: 2.5rem;
	}
	.section + .section {
		margin-top: 2.5rem;
	}
	.vorlage-hinweis {
		margin-bottom: 2rem;
	}
	.page-intro {
		max-width: 46rem;
		color: var(--gray-600);
		margin-bottom: 1.25rem;
	}
	.ergebnis-leiste {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 1.5rem;
		padding: 1rem 1.25rem;
		border-radius: 0.75rem;
		background: var(--gray-50);
		border: 1px solid var(--gray-200, #e5e7eb);
		margin-bottom: 0.625rem;
	}
	.ergebnis-teil {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}
	.ergebnis-delta {
		margin-left: auto;
	}
	@media (max-width: 40rem) {
		.ergebnis-delta {
			margin-left: 0;
			flex-basis: 100%;
			padding-top: 0.5rem;
			border-top: 1px solid var(--gray-200, #e5e7eb);
		}
		.ergebnis-wert {
			font-size: 1.125rem;
		}
	}
	.ergebnis-label {
		font-size: 0.8125rem;
		color: var(--gray-500);
	}
	.ergebnis-wert {
		font-size: 1.375rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.ergebnis-besser {
		color: var(--green-600, #16a34a);
	}
	.ergebnis-pfeil {
		font-size: 1.25rem;
		color: var(--gray-400);
	}
	.detail-title-sum {
		display: block;
		margin-top: 0.25rem;
		font-size: 0.9375rem;
		font-weight: 500;
		color: var(--gray-600);
		font-variant-numeric: tabular-nums;
	}
	.detail-title-diff {
		font-size: 0.875rem;
	}
	.mehr-hinweis {
		margin-left: 0.375rem;
		padding: 0.0625rem 0.375rem;
		border-radius: 0.25rem;
		background: var(--gray-100, #f3f4f6);
		color: var(--gray-500);
		font-size: 0.6875rem;
		vertical-align: middle;
	}
	.methodik p {
		max-width: 46rem;
		color: var(--gray-600);
		font-size: 0.9375rem;
		margin-bottom: 0.75rem;
	}
</style>
