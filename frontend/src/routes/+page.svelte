<script lang="ts">
	import type { PageData } from './$types';
	import { formatMio, formatNumber } from '$lib/format';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';
	import { Info, ClipboardList, Coins, Search, Building2, TrendingUp, Landmark, PieChart } from '@lucide/svelte';

	let { data }: { data: PageData } = $props();
	const { summary, documents } = data;

	// Ist vs Plan year ranges
	const istYears = summary.ist_years;
	const planOnlyYears = summary.plan_only_years;
	const lastIstYear = summary.last_ist_year ?? (istYears.length > 0 ? istYears[istYears.length - 1] : null);

	// Build chart data from summary
	const ehJahresergebnis = summary.ergebnishaushalt.jahresergebnis;
	const ehErtraege = summary.ergebnishaushalt.ordentliche_ertraege;
	const ehAufwendungen = summary.ergebnishaushalt.ordentliche_aufwendungen;
</script>

<!-- Hero Section -->
<section class="hero">
	<p>
		Die Haushaltsdaten der Stadt Rödermark – extrahiert aus den offiziellen PDF-Haushaltsplänen,
		aufbereitet für Transparenz und Vergleichbarkeit.
	</p>
</section>

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
