<script lang="ts">
	import type { PageData } from './$types';
	import type { KommuneData } from './+page.ts';
	import { MapPin, Info, ExternalLink, AlertTriangle } from '@lucide/svelte';
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';
	import SocialMeta from '$lib/components/SocialMeta.svelte';
	import Popover from '$lib/components/Popover.svelte';

	let { data }: { data: PageData } = $props();

	const kommunen: KommuneData[] = data.kommunen;
	const mapSvg: string = data.mapSvg;

	const mitDaten = $derived(kommunen.filter((k) => k.jahresergebnis_eur !== null));
	const defizitAnzahl = $derived(mitDaten.filter((k) => (k.jahresergebnis_eur ?? 0) < 0).length);
	const roedermark = $derived(kommunen.find((k) => k.kommune === 'Rödermark')!);

	const rankProKopf = $derived.by(() => {
		const sorted = [...mitDaten].sort(
			(a, b) => (a.jahresergebnis_pro_kopf_eur ?? 0) - (b.jahresergebnis_pro_kopf_eur ?? 0)
		);
		return sorted.findIndex((k) => k.kommune === 'Rödermark') + 1;
	});

	// Balkendiagramm: sortiert nach Ergebnis/Kopf absteigend (bester oben)
	const barchart = $derived(
		[...mitDaten].sort(
			(a, b) => (b.jahresergebnis_pro_kopf_eur ?? 0) - (a.jahresergebnis_pro_kopf_eur ?? 0)
		)
	);
	const maxAbsPK = $derived(
		Math.max(...mitDaten.map((k) => Math.abs(k.jahresergebnis_pro_kopf_eur ?? 0)))
	);

	// Tabelle: gleiche Sortierung wie Balkendiagramm (Ergebnis/Kopf absteigend)
	const tabelle = $derived(
		[...kommunen].sort(
			(a, b) => (b.jahresergebnis_pro_kopf_eur ?? 0) - (a.jahresergebnis_pro_kopf_eur ?? 0)
		)
	);

	function fmtMio(eur: number | null): string {
		if (eur === null) return '—';
		const m = eur / 1_000_000;
		const sign = m >= 0 ? '+' : '−';
		return `${sign}${Math.abs(m).toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} Mio. €`;
	}

	function fmtMioAbs(eur: number | null): string {
		if (eur === null) return '—';
		return (eur / 1_000_000).toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' Mio. €';
	}

	function fmtPK(pk: number | null): string {
		if (pk === null) return '—';
		const sign = pk >= 0 ? '+' : '−';
		return `${sign}${Math.abs(Math.round(pk)).toLocaleString('de-DE')} €`;
	}

	function barPct(pk: number | null): number {
		if (pk === null || maxAbsPK === 0) return 0;
		return (Math.abs(pk) / maxAbsPK) * 100;
	}

	// ─── Steuer-Mix (Plan 2026) ───
	const steuermix = data.steuermix;
	const maxSteuermixProKopf = data.maxSteuermixProKopf;
	const steuermixFehlend = data.steuermixFehlend;
	const grstHebesatz = data.grstHebesatz;

	const MIX_SEGMENTE = [
		{ key: 'einkommensteuer', label: 'Einkommensteuer-Anteil', color: '#10b981' },
		{ key: 'grundsteuer', label: 'Grundsteuer A+B', color: '#3b82f6' },
		{ key: 'gewerbesteuer', label: 'Gewerbesteuer', color: '#f59e0b' },
		{ key: 'sonstige', label: 'Sonstige (u. a. Umsatzsteuer-Anteil)', color: '#d1d5db' }
	] as const;
	type MixKey = (typeof MIX_SEGMENTE)[number]['key'];
	let mixSortKey = $state<MixKey | null>(null);
	let mixSegmente = $derived(
		mixSortKey
			? [...MIX_SEGMENTE.filter((s) => s.key === mixSortKey), ...MIX_SEGMENTE.filter((s) => s.key !== mixSortKey)]
			: [...MIX_SEGMENTE]
	);
	let steuermixSortiert = $derived.by(() => {
		const key = mixSortKey;
		if (!key) return steuermix;
		return [...steuermix].sort(
			(a, b) => (b[`${key}_pro_kopf`] ?? 0) - (a[`${key}_pro_kopf`] ?? 0)
		);
	});

	function fmtEur(v: number): string {
		return Math.round(v).toLocaleString('de-DE') + '\u00a0€';
	}
	function fmtEurMio(v: number): string {
		return (v / 1_000_000).toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + '\u00a0Mio.\u00a0€';
	}
	function fmtHS(v: number): string {
		return Number.isInteger(v)
			? v.toLocaleString('de-DE')
			: v.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
	}

</script>

<SocialMeta
	title="Kreisvergleich 2026"
	description="Haushaltsvergleich aller 13 Kommunen im Kreis Offenbach für 2026: Jahresergebnis, Ergebnis pro Kopf und Einordnung der Rödermarker Haushaltslage."
	path="/kreisvergleich"
/>

<AnchorHeading level={2} id="kreisvergleich"><MapPin /> Kreisvergleich 2026</AnchorHeading>
<p class="page-intro">
	Wie steht Rödermark im Vergleich zu den anderen 12 Kommunen des Kreises Offenbach?
	Karte und Tabelle zeigen geplante Jahresergebnisse aus den Haushaltsplänen 2025/2026.
</p>

<div class="info-box info-box-amber section-lg">
	<AlertTriangle class="icon-shrink" size={18} />
	<div>
		<strong>Planwerte – kein 1:1-Vergleich.</strong>
		Alle Zahlen sind Haushaltsplan-Ansätze (Soll), keine Ist-Ergebnisse.
		Unterschiedliche Buchungspraktiken (Abschreibungen, Rückstellungen, innere Verrechnungen) schränken die Vergleichbarkeit der absoluten Beträge ein.
		Die Frage „Defizit oder Überschuss" ist dagegen robust.{#if kommunen.some((k) => k.plan_jahr !== 2026)}
		{' '}Kommunen ohne 2026-Plan sind mit dem Planungsjahr gekennzeichnet.{/if}
	</div>
</div>

<!-- KPI-Karten -->
<section class="kpi-grid section">
	<div class="kpi-card">
		<p class="kpi-label">Kommunen im Defizit</p>
		<p class="kpi-value">{defizitAnzahl} <span style="font-size:1rem;font-weight:400;color:var(--gray-400)">von {mitDaten.length}</span></p>
		<p class="kpi-sub">auswertbare Planwerke 2025/2026</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Rödermark – Jahresergebnis</p>
		<p class="kpi-value text-red-600">{fmtMio(roedermark?.jahresergebnis_eur ?? null)}</p>
		<p class="kpi-sub">Haushaltsplan 2026</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Rödermark – pro Einwohner</p>
		<p class="kpi-value text-red-600">{fmtPK(roedermark?.jahresergebnis_pro_kopf_eur ?? null)}</p>
		<p class="kpi-sub">Jahresergebnis je Einwohner</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Rödermark – Rang</p>
		<p class="kpi-value">{rankProKopf} <span style="font-size:1rem;font-weight:400;color:var(--gray-400)">von {mitDaten.length}</span></p>
		<p class="kpi-sub">nach Ergebnis/Kopf (Rang&thinsp;1 = schlechtestes)</p>
	</div>
</section>

<!-- Karte + Balkendiagramm nebeneinander -->
<section class="chart-section">
	<AnchorHeading level={3} id="karte">Lage im Kreis &amp; Jahresergebnis pro Einwohner</AnchorHeading>
	<div class="map-bar-grid">
		<!-- Karte links -->
		<div class="chart-card map-card">
			<div class="map-svg-wrapper">
				{@html mapSvg}
			</div>
			<div class="map-legend">
				<span><span class="ldot lred"></span> Defizit</span>
				<span><span class="ldot lgreen"></span> Überschuss</span>
			</div>
		</div>
		<!-- Balkendiagramm rechts -->
		<div class="chart-card">
			<div class="bar-chart">
				{#each barchart as k}
					{@const neg = (k.jahresergebnis_pro_kopf_eur ?? 0) < 0}
					<div class="bar-row">
						<span class="bar-label">
							{k.kommune.replace(' am Main', '')}{#if k.plan_jahr !== 2026}<span class="badge badge-gray" style="font-size:0.6rem;margin-left:0.2rem">{k.plan_jahr}</span>{/if}
						</span>
						<div class="bar-track-h">
							<div class="bar-fill" class:bar-fill-neg={neg} class:bar-fill-pos={!neg} style="width:{barPct(k.jahresergebnis_pro_kopf_eur)}%"></div>
						</div>
						<span class="bar-value" class:bar-value-neg={neg} class:bar-value-pos={!neg}>{fmtPK(k.jahresergebnis_pro_kopf_eur)}</span>
					</div>
				{/each}
			</div>
		</div>
	</div>
	<p class="chart-note">
		Karte: <a href="https://commons.wikimedia.org/wiki/File:Municipalities_in_OF_(district).svg" target="_blank" rel="noopener noreferrer">Wikimedia Commons</a>, Public Domain (CC0).
		Graue Flächen: Offenbach am Main (kreisfreie Stadt) und angrenzende Kommunen anderer Landkreise.
	</p>
</section>

<!-- Steuer-Mix -->
<section class="chart-section">
	<AnchorHeading level={3} id="steuer-mix">Wer nimmt wie ein? Der Steuer-Mix je Einwohner</AnchorHeading>
	<p class="mix-desc">
		So unterschiedlich generieren die Kommunen ihr Geld: Einkommensteuer-Anteil, Gewerbesteuer,
		Grundsteuer und Sonstige – je Einwohner (Plan 2026). Klick auf einen Balken zeigt alle Werte,
		Klick auf die Legende sortiert eine Steuerart nach vorn.
	</p>
	<div class="mix-card">
		<div class="mix-legend">
			{#each MIX_SEGMENTE as s (s.key)}
				<button
					type="button"
					class="mix-legend-item"
					class:mix-legend-active={mixSortKey === s.key}
					onclick={() => (mixSortKey = mixSortKey === s.key ? null : s.key)}
					title="Diese Steuerart in den Balken nach vorne sortieren"
				>
					<span class="mix-swatch" style="background: {s.color}"></span>{s.label}
				</button>
			{/each}
		</div>
		<div class="mix-chart">
			{#each steuermixSortiert as r (r.kommune)}
				{@const isRoedermark = r.kommune === 'Rödermark'}
				<div class="mix-row">
					<span class="mix-label" class:mix-label-highlight={isRoedermark}>{r.kommune.replace(' am Main', '')}</span>
					<Popover direction="up" maxWidth="24rem" hover={true}>
						{#snippet trigger()}
							<span class="mix-track">
								{#each mixSegmente as s (s.key)}
									{@const wert = r[`${s.key}_pro_kopf`]}
									<span class="mix-seg" style="width: {(wert / maxSteuermixProKopf) * 100}%; background: {s.color}"></span>
								{/each}
							</span>
						{/snippet}
						<div class="mix-pop">
							<div class="mix-pop-head">
								<strong>{r.kommune}</strong>
								<span>{r.einwohner.toLocaleString('de-DE')} Einwohner · Plan {r.jahr}</span>
							</div>
							<table class="mix-pop-table">
								<thead>
									<tr><th></th><th>je Einw.</th><th>gesamt</th></tr>
								</thead>
								<tbody>
									{#each mixSegmente as s (s.key)}
										<tr>
											<td><span class="mix-swatch" style="background: {s.color}"></span><span class="mix-pop-name">{s.label}{#if s.key === 'grundsteuer' && grstHebesatz[r.kommune] != null} <span class="mix-pop-hs">{fmtHS(grstHebesatz[r.kommune])}&thinsp;%</span>{/if}</span></td>
											<td>{fmtEur(r[`${s.key}_pro_kopf`])}</td>
											<td>{fmtEurMio(r[s.key])}</td>
										</tr>
									{/each}
								</tbody>
								<tfoot>
									<tr><td>Gesamt</td><td>{fmtEur(r.summe_pro_kopf)}</td><td>{fmtEurMio(r.summe)}</td></tr>
								</tfoot>
							</table>
						</div>
					</Popover>
					<span class="mix-total" class:mix-total-highlight={isRoedermark}>{fmtEur(r.summe_pro_kopf)}</span>
				</div>
			{/each}
			{#each steuermixFehlend as f (f.kommune)}
				<div class="mix-row">
					<span class="mix-label">{f.kommune.replace(' am Main', '')}</span>
					<div class="mix-track mix-track-leer" title={f.grund}>Haushaltsplan 2026 noch nicht veröffentlicht</div>
					<span class="mix-total mix-total-leer">–</span>
				</div>
			{/each}
		</div>
	</div>
	<p class="chart-note">
		Steuerträge je Einwohner, Planwerte 2026 aus den jeweiligen Haushaltsplänen (Konten
		5500–5559).
	</p>
</section>

<!-- Detailtabelle -->
<section class="chart-section">
	<AnchorHeading level={3} id="tabelle">Alle Kommunen im Überblick</AnchorHeading>
	<div class="scroll-x card">
		<table class="data-table">
			<thead>
				<tr>
					<th>Kommune</th>
					<th class="col-number">Einwohner</th>
					<th class="col-number">Erträge</th>
					<th class="col-number">Aufwendungen</th>
					<th class="col-number">Jahresergebnis</th>
					<th class="col-number">€&thinsp;/&thinsp;Kopf</th>
					<th></th>
				</tr>
			</thead>
			<tbody>
				{#each tabelle as k}
					{@const neg = (k.jahresergebnis_eur ?? 0) < 0}
					{@const isRÖ = k.kommune === 'Rödermark'}
					<tr class:row-sum={isRÖ}>
						<td>
							<span class="kommune-cell">
								{k.kommune}
								{#if k.plan_jahr !== 2026}<span class="badge badge-gray" style="font-size:0.65rem;margin-left:0.3rem" title="Datenbasis: Haushaltsplan {k.plan_jahr}">{k.plan_jahr}</span>{/if}
								{#if k.anmerkung?.includes('HSK') || k.anmerkung?.includes('Sicherungskonzept')}<span class="badge badge-amber" style="font-size:0.65rem;margin-left:0.25rem">HSK</span>{/if}
								{#if k.anmerkung}
									<Popover direction="down" maxWidth="18rem">
										{#snippet trigger()}
											<span class="info-icon-btn"><Info size={13} /></span>
										{/snippet}
										<p class="anmerkung-text">{k.anmerkung}</p>
									</Popover>
								{/if}
							</span>
						</td>
						<td class="col-number">{k.einwohner.toLocaleString('de-DE')}</td>
						<td class="col-number tabular-nums">{fmtMioAbs(k.gesamteinnahmen_eur)}</td>
						<td class="col-number tabular-nums">{fmtMioAbs(k.gesamtausgaben_eur)}</td>
						<td class="col-number tabular-nums">
							{#if k.jahresergebnis_eur !== null}
								<span class:text-red-600={neg} class:text-green-700={!neg} style="font-weight:600">{fmtMio(k.jahresergebnis_eur)}</span>
							{:else}
								<span class="text-gray-400">—</span>
							{/if}
						</td>
						<td class="col-number tabular-nums">
							<span class:text-red-600={k.jahresergebnis_pro_kopf_eur !== null && neg} class:text-green-700={k.jahresergebnis_pro_kopf_eur !== null && !neg}>
								{fmtPK(k.jahresergebnis_pro_kopf_eur)}
							</span>
						</td>
						<td style="text-align:center">
							{#if k.url}
								<a href={k.url} target="_blank" rel="noopener noreferrer" class="src-btn" title={k.quelle ?? ''}><ExternalLink size={13} /></a>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="chart-note">
		HSK = Haushaltssicherungskonzept. Heusenstamm: Jahresergebnis nur durch Sondererlöse (Immobilienverkäufe) positiv; ordentliches Ergebnis −2,57 Mio. €.
	</p>
</section>

<!-- Quellen -->
<section class="chart-section">
	<AnchorHeading level={3} id="quellen-kreisvergleich">Quellen</AnchorHeading>
	<ul class="src-list">
		{#each kommunen as k}
			<li>
				<strong>{k.kommune}</strong>{k.plan_jahr !== 2026 ? ` (${k.plan_jahr})` : ''}:{' '}
				{#if k.url && k.quelle}
					<a href={k.url} target="_blank" rel="noopener noreferrer">{k.quelle}</a>
				{:else if k.quelle}
					{k.quelle}
				{:else}
					<span class="text-gray-400">{k.anmerkung ?? 'Keine Quelle verfügbar'}</span>
				{/if}
			</li>
		{/each}
	</ul>
</section>

<style>
	.page-intro { margin-bottom: 2rem; max-width: 48rem; color: var(--gray-600); }
	.section    { margin-bottom: 2rem; }
	.section-lg { margin-bottom: 2.5rem; }

	.chart-section { margin-bottom: 2.5rem; }
	.chart-card {
		background: white;
		border-radius: 0.75rem;
		box-shadow: var(--shadow-sm);
		outline: 1px solid var(--gray-100);
		outline-offset: -1px;
		overflow: hidden;
	}
	.chart-note { margin-top: 0.5rem; font-size: 0.75rem; color: var(--gray-400); }
	.chart-note a { color: var(--brand-500); text-decoration: underline; text-underline-offset: 2px; }

	/* Karte + Balken nebeneinander */
	.map-bar-grid {
		display: grid;
		grid-template-columns: 1fr 2fr;
		gap: 1rem;
		align-items: start;
	}
	@media (max-width: 700px) {
		.map-bar-grid { grid-template-columns: 1fr; }
	}

	/* Karte */
	.map-svg-wrapper { display: block; line-height: 0; }
	:global(.map-svg-wrapper svg) { width: 100%; height: auto; display: block; }
	.map-legend {
		display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; align-items: center;
		padding: 0.5rem 0.75rem; border-top: 1px solid var(--gray-100);
		font-size: 0.75rem; color: var(--gray-600);
	}
	.ldot {
		display: inline-block; width: 0.65rem; height: 0.65rem;
		border-radius: 50%; margin-right: 0.2rem; vertical-align: middle;
	}
	.lred   { background: #fca5a5; }
	.lgreen { background: #86efac; }
	.lgray  { background: #cccccc; }

	/* Balkendiagramm */
	.bar-chart {
		display: flex; flex-direction: column; gap: 0.375rem;
		padding: 0.75rem;
	}
	.bar-row {
		display: grid; grid-template-columns: 6rem 1fr 5.5rem; gap: 0.25rem; align-items: center;
	}
	@media (min-width: 640px) {
		.bar-row { grid-template-columns: 9rem 1fr 6rem; gap: 0.5rem; }
	}
	.bar-label {
		font-size: 0.6875rem; color: var(--gray-600);
		overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
		display: flex; align-items: center; gap: 0.2rem;
	}
	@media (min-width: 640px) {
		.bar-label { font-size: 0.8125rem; }
	}
	.bar-track-h {
		height: 1.25rem; background: var(--gray-100); border-radius: 0.25rem;
		overflow: hidden;
	}
	.bar-fill {
		height: 100%; border-radius: 0.25rem; transition: width 0.3s ease;
		background: var(--gray-300);
	}
	.bar-fill-neg { background: #fca5a5; }
	.bar-fill-pos { background: #86efac; }
	.bar-value {
		font-size: 0.6875rem; color: var(--gray-600);
		text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums;
	}
	@media (min-width: 640px) {
		.bar-value { font-size: 0.8125rem; }
	}
	.bar-value-neg { color: #dc2626; font-weight: 600; }
	.bar-value-pos { color: #16a34a; font-weight: 600; }

	/* Kommune-Zelle mit Inline-Elementen */
	.kommune-cell { display: inline-flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; }
	.info-icon-btn {
		display: inline-flex; align-items: center; justify-content: center;
		color: var(--gray-400); padding: 0.125rem; border-radius: 0.25rem;
		transition: color 0.15s, background 0.15s;
	}
	.info-icon-btn:hover { color: var(--gray-600); background: var(--gray-100); }
	.anmerkung-text {
		font-size: 0.75rem; line-height: 1.4; color: var(--gray-600); font-style: italic; margin: 0;
	}

	/* Tabelle-Extras */
	.src-btn { display: inline-flex; align-items: center; color: var(--brand-500); padding: 0.2rem; border-radius: 0.25rem; }
	.src-btn:hover { background: var(--brand-50); }

	/* Quellenlist */
	.src-list { display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.8125rem; color: var(--gray-600); line-height: 1.5; padding: 0; }
	.src-list a { color: var(--brand-600); text-decoration: underline; text-underline-offset: 2px; }

	/* Steuer-Mix */
	.mix-card { background: #fff; border-radius: 0.75rem; box-shadow: var(--shadow-sm); outline: 1px solid var(--gray-100); outline-offset: -1px; padding: 1rem 1.25rem; }
	.mix-desc { font-size: 0.9rem; color: var(--gray-600); line-height: 1.5; margin-bottom: 1rem; }
	.mix-legend { display: flex; flex-wrap: wrap; gap: 0.375rem 1.25rem; margin-bottom: 0.875rem; font-size: 0.75rem; color: var(--gray-600); }
	.mix-legend-item { display: inline-flex; align-items: center; gap: 0.375rem; background: none; border: none; margin: 0; padding: 0.1rem 0.3rem; font: inherit; color: inherit; cursor: pointer; border-radius: 0.25rem; line-height: 1.2; }
	.mix-legend-item:hover { background: var(--gray-100); }
	.mix-legend-active { background: var(--gray-100); font-weight: 700; color: var(--gray-800); }
	.mix-swatch { width: 0.75rem; height: 0.75rem; border-radius: 0.1875rem; flex-shrink: 0; }
	.mix-row :global(.popover-trigger) { flex: 1 1 auto; min-width: 0; display: flex; cursor: pointer; }
	.mix-pop { font-size: 0.75rem; color: var(--gray-700); }
	.mix-pop-head { display: flex; flex-direction: column; gap: 0.05rem; margin-bottom: 0.5rem; }
	.mix-pop-head strong { color: var(--gray-900); font-size: 0.85rem; }
	.mix-pop-head span { color: var(--gray-500); font-size: 0.7rem; }
	.mix-pop-table { width: 100%; border-collapse: collapse; }
	.mix-pop-table th { font-size: 0.65rem; font-weight: 600; color: var(--gray-400); text-align: right; padding: 0 0 0.15rem 0.5rem; }
	.mix-pop-table th:first-child { text-align: left; }
	.mix-pop-table td { padding: 0.12rem 0; }
	.mix-pop-table td:first-child { display: flex; align-items: center; gap: 0.35rem; padding-right: 0.75rem; }
	.mix-pop-table td:not(:first-child) { text-align: right; font-variant-numeric: tabular-nums; padding-left: 0.5rem; white-space: nowrap; }
	.mix-pop-name { min-width: 0; }
	.mix-pop-hs { color: var(--gray-400); font-weight: 400; white-space: nowrap; }
	.mix-chart { display: flex; flex-direction: column; gap: 2px; }
	.mix-row { display: flex; align-items: center; gap: 0.5rem; }
	.mix-label { flex: 0 0 6.5rem; min-width: 0; font-size: 0.75rem; color: var(--gray-500); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	@media (min-width: 640px) { .mix-label { flex-basis: 8rem; font-size: 0.8125rem; } }
	.mix-label-highlight { color: var(--brand-700, #1d4ed8); font-weight: 600; }
	.mix-track { position: relative; flex: 1; height: 24px; min-width: 0; display: flex; gap: 2px; border-radius: 4px; overflow: hidden; }
	.mix-seg { height: 100%; flex-shrink: 0; }
	.mix-track-leer { border: 1px dashed var(--gray-200); overflow: hidden; align-items: center; padding: 0 0.5rem; font-size: 0.6875rem; font-style: italic; color: var(--gray-400); white-space: nowrap; text-overflow: ellipsis; display: block; line-height: 22px; }
	.mix-total { flex: 0 0 4.5rem; text-align: right; font-size: 0.8125rem; color: var(--gray-600); white-space: nowrap; font-variant-numeric: tabular-nums; }
	.mix-total-highlight { color: var(--brand-700, #1d4ed8); font-weight: 700; }
	.mix-total-leer { color: var(--gray-300); }
</style>
