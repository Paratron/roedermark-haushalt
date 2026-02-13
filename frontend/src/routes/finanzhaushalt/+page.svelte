<script lang="ts">
	import type { PageData } from './$types';
	import { formatAmount } from '$lib/format';
	import { sourceLinksFromItems, sourceLinksPerYear } from '$lib/data';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import HaushaltTable from '$lib/components/HaushaltTable.svelte';
	import { Coins, Info } from '@lucide/svelte';
	import { browser } from '$app/environment';

	let { data }: { data: PageData } = $props();

	// Read initial selection from URL, fallback to '300'
	function initNr(): string {
		if (!browser) return '300';
		const nr = new URLSearchParams(window.location.search).get('nr');
		return nr && data.positions.some((p) => p.nr === nr) ? nr : '300';
	}

	let selectedNr = $state(initNr());

	// Sync selection to URL
	$effect(() => {
		if (!browser) return;
		const url = new URL(window.location.href);
		if (selectedNr === '300') {
			url.searchParams.delete('nr');
		} else {
			url.searchParams.set('nr', selectedNr);
		}
		history.replaceState(history.state, '', url);
	});

	let selectedItems = $derived(
		data.items.filter((i) => i.nr === selectedNr).sort((a, b) => a.year - b.year)
	);

	let chartSeries = $derived(
		selectedItems.map((i) => ({
			year: i.year,
			amount_type: i.amount_type,
			amount: i.amount,
			label: i.bezeichnung,
			document_id: i.document_id
		}))
	);

	let selectedLabel = $derived(
		data.positions.find((p) => p.nr === selectedNr)?.bezeichnung ?? ''
	);

	let selectedSourceLinks = $derived(
		sourceLinksFromItems(
			data.items.filter((i) => i.nr === selectedNr),
			data.documents
		)
	);

	/** Human-readable explanations for Finanzhaushalt positions */
	const positionInfo: Record<string, string> = {
		'10': 'Hier fließt Geld aus privatrechtlichen Geschäften: Mieteinnahmen städtischer Gebäude, Pachterlöse für Grundstücke, Eintrittsgelder für Schwimmbad oder Bücherei. Im Gegensatz zum Ergebnishaushalt zählt nur, was tatsächlich auf dem Konto eingeht.',
		'20': 'Gebühren, die Bürger für kommunale Dienste zahlen – z.\u00a0B. Kindergartenbeiträge, Wasser-/Abwassergebühren, Friedhofsgebühren, Bußgelder. Meist zweckgebundene Einnahmen.',
		'30': 'Geld, das die Stadt von anderen Stellen zurückbekommt – z.\u00a0B. wenn der Kreis anteilige Kosten erstattet oder der Bund Unterkunftskosten für Geflüchtete zurückzahlt.',
		'40': 'Die wichtigste Einnahmequelle: Gewerbesteuer, Grundsteuer A (land- und forstwirtschaftlich) und B (Grundstücke), Vergnügungssteuer auf Spielautomaten, plus der kommunale Anteil an der Einkommensteuer.',
		'50': 'Geld vom Bund für gesetzlich vorgeschriebene Leistungen, v.\u00a0a. der Familienleistungsausgleich als Kompensation für kommunale Kindergeld-Bearbeitung.',
		'60': 'Zuweisungen vom Land Hessen, insbesondere Schlüsselzuweisungen aus dem Kommunalen Finanzausgleich (KFA). Dies ist neben den Steuern die zweitwichtigste Einnahmequelle und hängt von der Finanzkraft der Stadt ab.',
		'70': 'Zinserträge aus städtischen Geldanlagen und Ausleihungen sowie Gewinnausschüttungen von Beteiligungen (z.\u00a0B. Stadtwerke).',
		'80': 'Restposten: Einzahlungen, die nicht in die Kategorien 10–70 passen, z.\u00a0B. Spenden, Versicherungsentschädigungen oder Erlöse aus der Veräußerung von Vorräten.',
		'90': 'Gesamtsumme aller laufenden Einzahlungen (Nr.\u00a010–80). Zeigt, wie viel Geld im Tagesgeschäft tatsächlich eingeht – ohne Investitionen und Kredite.',
		'100': 'Was die Stadt tatsächlich an Gehältern, Löhnen und Sozialabgaben an ihre Mitarbeiter überweist. Größter Einzelposten bei den laufenden Auszahlungen.',
		'110': 'Pensionszahlungen und Beihilfen an ehemalige Beamte. Steigt tendenziell, da immer mehr Beamte in den Ruhestand gehen.',
		'120': 'Alle Rechnungen für den laufenden Betrieb: Strom, Heizung, Reinigung, IT-Wartung, Büromaterial, Reparaturen an Gebäuden und Straßen, Honorare für externe Dienstleister.',
		'140': 'Zahlungen an Dritte für laufende Aufgaben: Zuschüsse an freie Kita-Träger, Jugendhilfe-Umlagen, Sozialtransfers. Auch Zahlungen an Zweckverbände (z.\u00a0B. Abfallwirtschaft).',
		'150': 'Die großen Pflichtabgaben: Kreisumlage an den Kreis Offenbach, Schulumlage, Gewerbesteuerumlage an Bund/Land. Zusammen oft der größte Ausgabenblock nach Personal.',
		'160': 'Zinszahlungen für die aufgenommenen Kredite der Stadt. Sinkt bei niedrigem Zinsniveau, steigt bei Neuverschuldung zu höheren Zinsen.',
		'170': 'Sammelposten für sonstige Auszahlungen: Versicherungsprämien, Mitgliedsbeiträge, Schadenersatz, Prozesskosten.',
		'180': 'Gesamtsumme aller laufenden Auszahlungen (Nr.\u00a0100–170). Zeigt, wie viel Geld im Tagesgeschäft tatsächlich abfließt.',
		'190': 'Kernkennzahl: Reicht das laufende Geschäft, um sich selbst zu tragen? Positiv = die Stadt erwirtschaftet einen Überschuss, der für Investitionen oder Schuldentilgung zur Verfügung steht. Negativ = die Stadt muss für den Normalbetrieb bereits Kredite aufnehmen.',
		'200': 'Zuschüsse von Land oder Bund für konkrete Investitionsprojekte – z.\u00a0B. Fördermittel für den Neubau einer Kita oder die Sanierung einer Sporthalle. Reduzieren den Eigenanteil der Stadt.',
		'210': 'Erlöse aus dem Verkauf städtischen Eigentums: Grundstücke, Gebäude, Fahrzeuge, Ausstattung. Einmaleffekte, die den Haushalt kurzfristig entlasten, aber das Vermögen schmälern.',
		'221': 'Die Stadt hat in der Vergangenheit Darlehen an Dritte vergeben (z.\u00a0B. an städtische Gesellschaften). Hier fließen die Tilgungsraten zurück.',
		'230': 'Gesamtsumme der investiven Einzahlungen. Zeigt, wie viel Geld für Investitionen von außen hereinkommt (Zuschüsse + Verkäufe + Darlehensrückflüsse).',
		'240': 'Kaufpreise für Grundstücke und Gebäude – z.\u00a0B. Flächen für Neubaugebiete oder den Erwerb eines Gebäudes für eine Kita.',
		'250': 'Das Investitionsbudget für Bauprojekte: Schulneubauten, Straßensanierung, Kanalbau, Spielplätze, Feuerwehrhaus. Oft der größte Investitionsposten.',
		'260': 'Anschaffungen wie Feuerwehrfahrzeuge, Playground-Geräte, Server, Software-Lizenzen – alles, was nicht Bau oder Grundstück ist, aber langfristig genutzt wird.',
		'261': 'Investitionszuschüsse, die die Stadt an Dritte zahlt und die aktiviert werden – z.\u00a0B. Zuschuss für den Vereinssportplatz, der über Jahre abgeschrieben wird.',
		'270': 'Kauf von Unternehmensanteilen oder Kapitaleinlagen bei städtischen Gesellschaften und Beteiligungen.',
		'271': 'Darlehen, die die Stadt an Dritte vergibt – z.\u00a0B. an eine eigene Wohnungsbaugesellschaft für ein Bauprojekt.',
		'280': 'Gesamtsumme der investiven Auszahlungen. Zeigt den tatsächlichen Investitionsumfang der Stadt.',
		'290': 'Differenz aus investiven Ein- und Auszahlungen. Fast immer negativ, weil Investitionsausgaben die Zuschüsse übersteigen. Die Lücke muss aus dem laufenden Überschuss (Nr.\u00a0190) oder Krediten gedeckt werden.',
		'300': 'Neue Schulden für Investitionen: Wenn der laufende Überschuss und Zuschüsse nicht reichen, nimmt die Stadt langfristige Kredite auf. Steigende Werte deuten auf wachsende Verschuldung hin.',
		'301': 'Kurzfristige Überbrückungskredite für Liquiditätsengpässe – wie ein Dispo-Kredit. Sollte idealerweise null sein; hohe Werte zeigen angespannte Kassenlage.',
		'310': 'Rückzahlung bestehender Investitionskredite. Die Stadt muss jedes Jahr einen Teil ihrer Altschulden tilgen. Hohe Tilgung = solide Entschuldung, aber weniger Spielraum für Neues.',
		'320': 'Kreditaufnahmen minus Tilgung: Positiv = Netto-Neuverschuldung (Stadt nimmt mehr auf als sie tilgt). Negativ = Netto-Entschuldung. Eine der wichtigsten Kennzahlen für die finanzielle Nachhaltigkeit.',
		'360': 'Die Bilanz des gesamten Jahres über alle drei Bereiche (Verwaltung + Investition + Finanzierung): Wie viel Geld hat die Stadt am Ende des Jahres mehr oder weniger auf dem Konto als zu Beginn?',
		'370': 'Der Kontostand zum 1. Januar. Ausgangspunkt für die Liquiditätsplanung des Jahres.',
		'380': 'Der Kontostand zum 31. Dezember. Ergibt sich aus Anfangsbestand plus Zahlungsmittelüberschuss/-bedarf des Jahres.',
		'400': 'Geplanter Endbestand ohne kurzfristige Kassenkredite. Zeigt, wie viel „echte" Liquidität die Stadt am Jahresende haben will – ein Gradmesser für die finanzielle Handlungsfähigkeit.',
	};

	let selectedInfo = $derived(positionInfo[selectedNr] ?? '');

	const years = data.summary.years;
	const planOnlySet = new Set(data.summary.plan_only_years);

	interface PivotRow {
		nr: string;
		bezeichnung: string;
		values: Map<string, number | null>;
	}

	let pivotData = $derived.by(() => {
		const rows: PivotRow[] = [];
		for (const pos of data.positions) {
			const values = new Map<string, number | null>();
			for (const item of data.items) {
				if (item.nr === pos.nr) {
					values.set(`${item.year}_${item.amount_type}`, item.amount);
				}
			}
			rows.push({ nr: pos.nr, bezeichnung: pos.bezeichnung, values });
		}
		return rows;
	});

	let yearSourceLinks = $derived(sourceLinksPerYear(data.items, data.documents, 'finanzhaushalt'));
</script>

<h2 class="page-title"><Coins class="page-icon" /> Finanzhaushalt</h2>
<p class="page-intro">
	Der Finanzhaushalt zeigt die tatsächlichen Zahlungsströme: Einzahlungen und Auszahlungen
	aus laufender Verwaltung und Investitionstätigkeit. Negative Werte = Einzahlungen, positive = Auszahlungen.
</p>

<!-- Position Selector + Chart -->
<section class="section">
	<div class="selector-row">
		<label for="fh-position-select" class="field-label">Position auswählen</label>
		<select id="fh-position-select" bind:value={selectedNr} class="form-select">
			{#each data.positions as pos}
				<option value={pos.nr}>Nr. {pos.nr} – {pos.bezeichnung}</option>
			{/each}
		</select>
	</div>

	<div class="card card-padded">
		<TimeSeriesChart
			title="Nr. {selectedNr} – {selectedLabel}"
			series={chartSeries}
			yLabel="Mio. €"
			planOnlyYears={data.summary.plan_only_years}
			lastIstYear={data.summary.last_ist_year}
			valueColoring={true}
		/>
	</div>

	<SourceCitation
		description="Finanzhaushalt, Nr. {selectedNr}"
		links={selectedSourceLinks}
	/>

	{#if selectedInfo}
		<div class="info-box info-box-amber">
			<Info class="info-icon" />
			<div>
				<strong>{selectedLabel}</strong><br />
				{selectedInfo}
			</div>
		</div>
	{/if}
</section>

<!-- Data Table -->
<section>
	<h3 class="table-title">Alle Positionen im Überblick</h3>
	<HaushaltTable
		rows={pivotData}
		{years}
		planOnlyYears={data.summary.plan_only_years}
		sumNrs={['90', '180', '190', '230', '280', '290', '320', '360']}
		{yearSourceLinks}
		sourceLabel="Finanzhaushalt"
		onRowClick={(nr) => { selectedNr = nr; window.scrollTo({ top: 0, behavior: 'smooth' }); }}
	/>
</section>

<style>
	.page-title {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1.5rem;
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--gray-900);
	}
	:global(.page-icon) { width: 1.75rem; height: 1.75rem; }
	.page-intro { margin-bottom: 2rem; max-width: 48rem; color: var(--gray-600); }
	.section { margin-bottom: 2.5rem; }
	.selector-row { margin-bottom: 1rem; }
	.field-label { display: block; font-size: 0.875rem; font-weight: 500; color: var(--gray-700); }
	.info-box :global(.info-icon) {
		margin-top: 0.125rem;
		width: 1.25rem;
		height: 1.25rem;
		flex-shrink: 0;
	}
	.table-title { margin-bottom: 1rem; font-size: 1.125rem; font-weight: 600; color: var(--gray-800); }

</style>
