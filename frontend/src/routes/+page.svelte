<script lang="ts">
	import type { PageData } from './$types';
	import { formatMio, formatNumber } from '$lib/format';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import StructuredData from '$lib/components/StructuredData.svelte';
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';
	import SocialMeta from '$lib/components/SocialMeta.svelte';
	import { Info, ClipboardList, Coins, Search, Building2, TrendingUp, Landmark, PieChart, Receipt, ShieldCheck, ArrowRight } from '@lucide/svelte';

	let { data }: { data: PageData } = $props();
	const { summary, documents } = data;
	const hsk = $derived(data.hsk);

	// Ist vs Plan year ranges
	const istYears = summary.ist_years;
	const planOnlyYears = summary.plan_only_years;
	const lastIstYear = summary.last_ist_year ?? (istYears.length > 0 ? istYears[istYears.length - 1] : null);

	// Build chart data from summary
	const ehJahresergebnis = summary.ergebnishaushalt.jahresergebnis;
	const ehErtraege = summary.ergebnishaushalt.ordentliche_ertraege;
	const ehAufwendungen = summary.ergebnishaushalt.ordentliche_aufwendungen;
</script>

<SocialMeta
	title="Haushalt Rödermark"
	description="Die Haushaltsdaten der Stadt Rödermark – extrahiert aus den offiziellen PDF-Haushaltsplänen, aufbereitet für Transparenz und Vergleichbarkeit."
	path="/"
/>

<!-- Hero Section -->
<section class="hero">
	<p>
		Die Haushaltsdaten der Stadt Rödermark – extrahiert aus den offiziellen PDF-Haushaltsplänen,
		aufbereitet für Transparenz und Vergleichbarkeit.
	</p>
</section>


	{#if hsk}
		<a href="/hsk2026" class="hsk-banner">
			<div class="hsk-banner-icon"><ShieldCheck /></div>
			<div class="hsk-banner-body">
				<div class="hsk-banner-kicker">Haushaltssicherungskonzept {hsk.laufzeit[0]}–{hsk.laufzeit[1]}</div>
				<h3 class="hsk-banner-title">Wie Rödermark seinen Haushalt sanieren will</h3>
				<p class="hsk-banner-text">
					{hsk.kennzahlen.anzahl_massnahmen} Maßnahmen mit einem Volumen von
					<strong>{formatMio(Math.abs(hsk.kennzahlen.konsolidierung_mit_grundsteuer_b ?? 0))}</strong>
					sollen den Haushalt bis 2029 ausgleichen. Wo die Stadt mehr einnimmt und wo sie spart –
					mit Quelle für jede Zahl.
				</p>
				<span class="hsk-banner-cta">Zum HSK 2026 <ArrowRight class="hsk-cta-icon" /></span>
			</div>
		</a>
	{/if}


<!-- Ergebnishaushalt Overview -->
<section class="section">
	<AnchorHeading level={3} id="jahresergebnis">Ergebnishaushalt – Jahresergebnis</AnchorHeading>
	<div class="card card-padded">
		<TimeSeriesChart
			title="Jahresergebnis (Erträge − Aufwendungen) · positiv = Überschuss, negativ = Defizit"
			series={ehJahresergebnis}
			yLabel="Mio. €"
			planOnlyYears={planOnlyYears}
			{lastIstYear}
			valueColoring={true}
		/>
		<StructuredData
			name="Jahresergebnis Stadt Rödermark"
			description="Jährliches Ergebnis (Erträge minus Aufwendungen) der Stadt Rödermark. Positiv = Überschuss, negativ = Defizit."
			series={ehJahresergebnis}
		/>
	</div>
    <br />
    <div class="info-box info-box-blue">
		<Info class="info-icon" />
		<div>
			<strong>Ist vs. Plan:</strong> Kräftige Balken zeigen tatsächliche Ergebnisse aus Jahresabschlüssen.
			<br />Blasse Balken sind <em>Planwerte</em> (Haushaltsansätze und Finanzplanung) –
			also Prognosen aus den jeweiligen Haushaltsplänen, keine realen Zahlen.
		</div>
	</div>
</section>

<!-- Erträge vs Aufwendungen -->
<section class="section">
	<AnchorHeading level={3} id="ertraege-aufwendungen">Ordentliche Erträge vs. Aufwendungen</AnchorHeading>
	<div class="card card-padded">
		<TimeSeriesChart
			title="Ordentliche Erträge und Aufwendungen im Vergleich"
			series={[...ehErtraege, ...ehAufwendungen]}
			yLabel="Mio. €"
			planOnlyYears={planOnlyYears}
			{lastIstYear}
			multiSeries={true}
		/>
		<StructuredData
			name="Ordentliche Erträge und Aufwendungen Stadt Rödermark"
			description="Vergleich der ordentlichen Erträge und Aufwendungen der Stadt Rödermark über die Jahre."
			series={[...ehErtraege, ...ehAufwendungen]}
			multiSeries={true}
		/>
	</div>
</section>

<!-- Quick Links -->
<section class="link-grid">
	<a href="/kategorien" class="card card-padded link-card">
		<h4 class="link-card-title"><PieChart class="link-card-icon" /> Einnahmen & Ausgaben</h4>
		<p class="link-card-desc">Wofür gibt die Stadt Geld aus und woher kommt es? Kategorien im Überblick</p>
	</a>
	<a href="/ergebnishaushalt" class="card card-padded link-card">
		<h4 class="link-card-title"><ClipboardList class="link-card-icon" /> Ergebnishaushalt</h4>
		<p class="link-card-desc">Erträge, Aufwendungen und Jahresergebnis im Detail</p>
	</a>
	<a href="/finanzhaushalt" class="card card-padded link-card">
		<h4 class="link-card-title"><Coins class="link-card-icon" /> Finanzhaushalt</h4>
		<p class="link-card-desc">Ein- und Auszahlungen, Investitionen, Saldo</p>
	</a>
	<a href="/teilhaushalte" class="card card-padded link-card">
		<h4 class="link-card-title"><Building2 class="link-card-icon" /> Teilhaushalte</h4>
		<p class="link-card-desc">Fachbereichs-Budgets: Erträge und Aufwendungen je Bereich</p>
	</a>
	<a href="/investitionen" class="card card-padded link-card">
		<h4 class="link-card-title"><TrendingUp class="link-card-icon" /> Investitionen</h4>
		<p class="link-card-desc">Einzelne Investitionsprojekte: geplant vs. tatsächlich umgesetzt</p>
	</a>
	<a href="/schulden" class="card card-padded link-card">
		<h4 class="link-card-title"><Landmark class="link-card-icon" /> Schulden &amp; Zinsen</h4>
		<p class="link-card-desc">Kreditaufnahme, Tilgung und Zinsbelastung der Stadt</p>
	</a>
	<a href="/steuern" class="card card-padded link-card">
		<h4 class="link-card-title"><Receipt class="link-card-icon" /> Steuern & Hebesätze</h4>
		<p class="link-card-desc">Grundsteuer, Gewerbesteuer und Hebesätze im Vergleich mit Nachbarkommunen</p>
	</a>
	<a href="/hsk2026" class="card card-padded link-card">
		<h4 class="link-card-title"><ShieldCheck class="link-card-icon" /> Haushaltssicherung (HSK 2026)</h4>
		<p class="link-card-desc">Wo die Stadt spart, was die Grundsteuer beiträgt und wann der Haushalt ausgeglichen ist</p>
	</a>
	<a href="/explorer" class="card card-padded link-card">
		<h4 class="link-card-title"><Search class="link-card-icon" /> Explorer</h4>
		<p class="link-card-desc">Alle {formatNumber(summary.total_line_items)} Positionen durchsuchen und filtern</p>
	</a>
</section>

<style>
	.hero {
		margin-bottom: 2.5rem;
	}
	.hero p {
		max-width: 42rem;
		font-size: 1.125rem;
		color: var(--gray-600);
	}

	/* ── HSK highlight banner ── */
	.hsk-banner {
		display: flex;
		gap: 1.25rem;
		align-items: flex-start;
		margin-bottom: 2.5rem;
		padding: 1.5rem 1.75rem;
		border-radius: 0.75rem;
		background: linear-gradient(135deg, var(--brand-700), var(--brand-800));
		color: #fff;
		text-decoration: none;
		box-shadow: var(--shadow-md);
		transition: box-shadow 0.15s, transform 0.15s;
	}
	.hsk-banner:hover {
		box-shadow: var(--shadow-lg);
		transform: translateY(-2px);
	}
	.hsk-banner-icon {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 3rem;
		height: 3rem;
		border-radius: 0.625rem;
		background: rgba(255, 255, 255, 0.15);
	}
	.hsk-banner-icon :global(svg) {
		width: 1.75rem;
		height: 1.75rem;
	}
	.hsk-banner-body {
		flex: 1;
	}
	.hsk-banner-kicker {
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		opacity: 0.85;
	}
	.hsk-banner-title {
		margin: 0.15rem 0 0.4rem;
		font-size: 1.35rem;
		font-weight: 700;
	}
	.hsk-banner-text {
		margin: 0;
		font-size: 0.95rem;
		line-height: 1.55;
		max-width: 46rem;
		color: rgba(255, 255, 255, 0.92);
	}
	.hsk-banner-cta {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		margin-top: 0.75rem;
		font-weight: 600;
		font-size: 0.9rem;
	}
	:global(.hsk-cta-icon) {
		width: 1rem;
		height: 1rem;
		transition: transform 0.15s;
	}
	.hsk-banner:hover :global(.hsk-cta-icon) {
		transform: translateX(3px);
	}

	.section {
		margin-bottom: 2.5rem;
	}
	:global(.info-icon) {
		margin-top: 0.125rem;
		width: 1.25rem;
		height: 1.25rem;
		flex-shrink: 0;
	}
	.link-card {
		transition: box-shadow 0.15s;
	}
	.link-card-title {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-weight: 600;
		color: var(--brand-700);
	}
	.link-card:hover .link-card-title {
		color: var(--brand-800);
	}
	:global(.link-card-icon) {
		width: 1.25rem;
		height: 1.25rem;
	}
	.link-card-desc {
		margin-top: 0.5rem;
		font-size: 0.875rem;
		color: var(--gray-500);
	}
</style>
