<script lang="ts">
	import type { PageData } from './$types';
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';
	import SocialMeta from '$lib/components/SocialMeta.svelte';
	import { Landmark, Calculator, ArrowRight, ShieldCheck, ChevronDown } from '@lucide/svelte';
	import { browser } from '$app/environment';

	let { data }: { data: PageData } = $props();

	const fmtHS = data.fmtHS;

	function fmtEur(v: number): string {
		return Math.round(v).toLocaleString('de-DE') + ' €';
	}
	function fmtEurMio(v: number): string {
		return (v / 1_000_000).toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' Mio. €';
	}

	let roedermarkHistory = $derived(data.roedermarkHistory);
	let maxHist = $derived(
		roedermarkHistory.length > 0 ? Math.max(...roedermarkHistory.map((d) => d.hebesatz)) : 1
	);

	let musterhausRoedermark = $derived(data.musterhaus.find((m) => m.kommune === 'Rödermark'));
	let musterhausGuenstigste = $derived(data.musterhaus[data.musterhaus.length - 1]);
	let musterhausTeuerste = $derived(data.musterhaus[0]);

	// Grundsteuer-Basis (Messbetragssumme je Einwohner, Näherung aus Ist 2024)
	let basisRows = $derived(
		data.kommunen
			.filter((k) => k.ist_2024)
			.map((k) => ({ kommune: k.kommune, basis: k.ist_2024!.bemessungsgrundlage_pro_kopf_eur }))
			.sort((a, b) => b.basis - a.basis)
	);
	let basisRoedermark = $derived(basisRows.find((r) => r.kommune === 'Rödermark'));
	let basisSpitze = $derived(basisRows[0]);

	// Steuermix: Segmente in fester Reihenfolge und mit festen Farben
	// (identisch zur Steuern-Seite: EkSt grün, GewSt amber, GrSt blau).
	const MIX_SEGMENTE = [
		{ key: 'einkommensteuer', label: 'Einkommensteuer-Anteil', color: '#10b981' },
		{ key: 'gewerbesteuer', label: 'Gewerbesteuer', color: '#f59e0b' },
		{ key: 'grundsteuer', label: 'Grundsteuer A+B', color: '#3b82f6' },
		{ key: 'sonstige', label: 'Sonstige (u. a. Umsatzsteuer-Anteil)', color: '#d1d5db' }
	] as const;
	let mixRoedermark = $derived(data.steuermix.find((r) => r.kommune === 'Rödermark'));
	let mixSpitze = $derived(data.steuermix[0]);
	let gewFaktor = $derived(
		mixRoedermark && mixSpitze && mixRoedermark.gewerbesteuer_pro_kopf > 0
			? Math.round(mixSpitze.gewerbesteuer_pro_kopf / mixRoedermark.gewerbesteuer_pro_kopf)
			: 0
	);

	const toc = [
		{ id: 'bundesvergleich', label: '2,5-mal so viel wie ganz Deutschland?' },
		{ id: 'musterhaus', label: 'Was zahle ich im Vergleich zu den Nachbarn?' },
		{ id: 'umlagen', label: 'Wohin fließt mein Geld?' },
		{ id: 'stadtkasse', label: 'Warum so ein hoher Hebesatz?' },
		{ id: 'gewerbe-ansiedeln', label: 'Warum nicht einfach Gewerbe ansiedeln?' },
		{ id: 'gewerbesteuer-erhoehen', label: 'Warum nicht die Gewerbesteuer erhöhen?' },
		{ id: 'verschwendung', label: 'Wird im Rathaus Geld verschwendet?' },
		{ id: 'eppertshausen', label: 'Warum zahlt Eppertshausen nur 480 %?' },
		{ id: 'hessen-schnitt', label: 'Der Hessen-Schnitt ist doch 400 %?' },
		{ id: 'vergleichbarkeit', label: 'Kann man Hebesätze überhaupt vergleichen?' },
		{ id: 'entwicklung', label: 'Wie kam es zur Erhöhung?' },
		{ id: 'erhoehung-2025', label: 'Gab es 2025 nicht schon eine Erhöhung?' },
		{ id: 'zu-einfach', label: 'Macht es sich die Stadt zu einfach?' },
		{ id: 'was-tun', label: 'Was kann man überhaupt tun?' },
		{ id: 'rechner', label: 'Was heißt das für mich konkret?' },
		{ id: 'tabelle', label: 'Alle Zahlen im Überblick' },
		{ id: 'quellen-grundsteuer', label: 'Quellen' }
	];

	// Scrollspy: aktiven Abschnitt in der Navigation markieren.
	let activeId = $state('');
	let mobileTocOpen = $state(false);
	$effect(() => {
		if (!browser) return;
		const observer = new IntersectionObserver(
			(entries) => {
				for (const e of entries) {
					if (e.isIntersecting) activeId = e.target.id;
				}
			},
			{ rootMargin: '-15% 0px -75% 0px' }
		);
		for (const t of toc) {
			const el = document.getElementById(t.id);
			if (el) observer.observe(el);
		}
		return () => observer.disconnect();
	});
</script>

<SocialMeta
	title="Grundsteuer: Fragen und Antworten"
	description="Zahlt Rödermark wirklich 2,5-mal so viel Grundsteuer wie der Rest von Deutschland? Die häufigsten Fragen zur Grundsteuer B, beantwortet mit belegten Zahlen."
	path="/grundsteuer"
/>

<AnchorHeading level={2} id="grundsteuer"><Landmark /> Grundsteuer: Fragen und Antworten</AnchorHeading>

<div class="article-layout">
<div class="article-body">

<details class="toc-mobile" bind:open={mobileTocOpen}>
	<summary>
		<span>Fragen{#if activeId}: {toc.find((t) => t.id === activeId)?.label ?? ''}{/if}</span>
		<ChevronDown size={16} class="toc-mobile-chevron" />
	</summary>
	<ol>
		{#each toc as t (t.id)}
			<li><a href="#{t.id}" class:active={t.id === activeId} onclick={() => (mobileTocOpen = false)}>{t.label}</a></li>
		{/each}
	</ol>
</details>

<p class="page-intro">
	Sie haben den neuen Grundsteuerbescheid geöffnet und sind sauer? Verständlich. Es geht um
	echtes Geld, jedes Jahr. Diese Seite beantwortet die Fragen, die dazu gerade überall in
	Rödermark diskutiert werden. Jede Antwort beginnt mit dem Ergebnis. Belege und Details folgen.
	Und jede Frage lässt sich einzeln verlinken.
</p>

<!-- F1: Bundesvergleich -->
<section class="section">
	<AnchorHeading level={3} id="bundesvergleich">Zahlen wir wirklich 2,5-mal so viel wie der Rest von Deutschland?</AnchorHeading>
	<p class="answer-lead">
		Nein. Die Rechnung klingt logisch, ist aber falsch. Und trotzdem steckt ein wahrer Kern
		drin.
	</p>
	<blockquote class="claim">
		Der Durchschnittshebesatz in Deutschland liegt bei rund 500&nbsp;%. Rödermark verlangt
		1.327&nbsp;%. Also zahlen wir mehr als das Zweieinhalbfache&nbsp;… oder?
	</blockquote>
	<p class="explainer-prose">
		Beide Zahlen stimmen sogar. Trotzdem geht die Rechnung nicht auf. Denn Grundsteuer heißt:
		<strong>Messbetrag mal Hebesatz</strong>. Und den Messbetrag berechnet
		<strong>jedes Bundesland anders</strong>. Hessen misst die Fläche. Andere Länder den
		Grundstückswert. Bayern macht wieder sein eigenes Ding.
	</p>
	<p class="explainer-prose">
		Heißt: Dasselbe Haus bekommt in Hessen einen ganz anderen Messbetrag als in Bayern oder NRW.
		500&nbsp;% dort und 500&nbsp;% hier: Das sind völlig verschiedene Beträge auf dem Bescheid.
		Ein „Bundesdurchschnitt der Hebesätze" vergleicht Äpfel mit Birnen. <strong>Nur innerhalb
		Hessens gilt überall dieselbe Formel.</strong> Da ist der Vergleich fair. Und den rechnen
		wir jetzt durch.
	</p>
</section>

<!-- F2: Musterhaus -->
<section class="section">
	<AnchorHeading level={3} id="musterhaus">Was zahle ich im Vergleich zu den Nachbarkommunen?</AnchorHeading>
	<p class="answer-lead">
		Für ein durchschnittliches Einfamilienhaus rund {fmtEur(musterhausRoedermark?.grundsteuer_eur ?? 0)}
		im Jahr. Fast dreimal so viel wie in {musterhausGuenstigste?.kommune}
		({fmtEur(musterhausGuenstigste?.grundsteuer_eur ?? 0)}).
	</p>
	<p class="section-desc">
		Gerechnet für ein Musterhaus ({data.musterhausSpec.grundflaeche}&nbsp;m² Grundstück,
		{data.musterhausSpec.wohnflaeche}&nbsp;m² Wohnfläche, mittlere Lage, Messbetrag nach
		hessischer Formel rund {fmtEur(data.musterhausMessbetrag)}) mit den Hebesätzen 2026:
	</p>
	<div class="card card-padded">
		<div class="emph-chart">
			{#each data.musterhaus as m (m.kommune)}
				{@const isRoedermark = m.kommune === 'Rödermark'}
				{@const isGuenstigste = m.kommune === musterhausGuenstigste?.kommune}
				{@const isTeuerste = m.kommune === musterhausTeuerste?.kommune}
				{@const immerSichtbar = isRoedermark || isGuenstigste || isTeuerste}
				{@const pct = (m.grundsteuer_eur / data.maxMusterhaus) * 100}
				<div class="emph-row">
					<span class="emph-label" class:emph-label-highlight={isRoedermark}>
						<span class="emph-label-name">{m.kommune.replace(' am Main', '')}{#if m.status === 'geplant'}<span class="status-geplant">*</span>{/if}</span>
						<span class="emph-label-hs">{fmtHS(m.hebesatz, true)}&thinsp;%</span>
					</span>
					<div class="emph-track" title="{m.kommune}: {fmtEur(m.grundsteuer_eur)} pro Jahr (Hebesatz {fmtHS(m.hebesatz, true)} %)">
						<div class="emph-fill" class:emph-fill-highlight={isRoedermark} style="width: {pct}%"></div>
						<span
							class="emph-value"
							class:emph-value-inside={pct > 30}
							class:emph-value-highlight={isRoedermark}
							class:emph-value-hover={!immerSichtbar}
							style={pct > 30 ? `left: calc(${pct}% - 6px)` : `left: calc(${pct}% + 6px)`}
						>{fmtEur(m.grundsteuer_eur)}</span>
					</div>
				</div>
			{/each}
		</div>
	</div>
	<p class="chart-note">
		* = geplanter, noch nicht beschlossener Hebesatz. Lagefaktor pauschal 1,0, denn er bewertet ein
		Grundstück relativ zum Durchschnitt seiner <em>eigenen</em> Kommune, für ein durchschnittlich
		gelegenes Haus ist er daher überall ≈&thinsp;1. Alle Werte in der <a href="#tabelle">Tabelle unten</a>;
		Ihre persönliche Rechnung macht der <a href="/grundsteuer-rechner">Grundsteuer-Rechner</a>.
	</p>
</section>

<!-- F3: Umlagen -->
<section class="section">
	<AnchorHeading level={3} id="umlagen">Wohin fließt mein Geld überhaupt?</AnchorHeading>
	<p class="answer-lead">
		Erst mal: weg. Der Kreis Offenbach schickt Rödermark {data.umlagen.jahr} eine Rechnung über
		{fmtEurMio(data.umlagen.summe)}. Die komplette Grundsteuer&nbsp;B deckt davon nicht mal ein
		Drittel.
	</p>
	<p class="explainer-prose">
		Der Hintergrund: Jede Stadt muss an ihren Landkreis zahlen. <strong>Kreisumlage</strong>
		(für Jugendamt und Soziales) und <strong>Schulumlage</strong> (für die Schulgebäude). Keine
		Verhandlung, keine Wahl: Der Kreis setzt fest, die Stadt überweist. Und der Kreis Offenbach
		gehört zu den höchstverschuldeten Landkreisen Deutschlands. Entsprechend fett ist die
		Rechnung:
	</p>
	<div class="umlagen-grid section-sm">
		<div class="kpi-card">
			<p class="kpi-label">Kreisumlage {data.umlagen.jahr}</p>
			<p class="kpi-value text-red-600">−{fmtEurMio(data.umlagen.kreisumlage)}</p>
			<p class="kpi-sub">Pflichtabgabe an den Kreis Offenbach</p>
		</div>
		<div class="kpi-card">
			<p class="kpi-label">Schulumlage {data.umlagen.jahr}</p>
			<p class="kpi-value text-red-600">−{fmtEurMio(data.umlagen.schulumlage)}</p>
			<p class="kpi-sub">Pflichtabgabe für die Schulträgerschaft</p>
		</div>
		<div class="kpi-card">
			<p class="kpi-label">Grundsteuer B {data.umlagen.jahr} (Plan)</p>
			<p class="kpi-value text-green-700">+{fmtEurMio(data.umlagen.grundsteuerBPlan)}</p>
			<p class="kpi-sub">gesamte geplante Einnahme</p>
		</div>
	</div>
	<p class="explainer-prose">
		Im Klartext: Rödermark plant {data.umlagen.jahr} mit rund
		{fmtEurMio(data.steuerquellen.gesamt)} Steuereinnahmen. Davon gehen
		{fmtEurMio(data.umlagen.summe)} direkt an den Kreis weiter:
		<strong>{Math.round((data.umlagen.summe / data.steuerquellen.gesamt) * 100)} Prozent</strong>.
		Für Kitas, Feuerwehr und Straßen bleibt nur der Rest. Und die Kreis-Rechnung wächst: von
		{fmtEurMio(data.umlagen.erstesJahrSumme)} ({data.umlagen.erstesJahr}) auf
		{fmtEurMio(data.umlagen.summe)} heute. <strong>Die Stadtverordneten können dagegen genau
		nichts tun.</strong> Sie dürfen nur bezahlen.
	</p>
	<p class="explainer-prose">
		Und der Rest? Ist größtenteils verplant, bevor irgendwer Wünsche äußern darf. Denn als
		Nächstes kommen die <strong>Pflichtaufgaben</strong>: Kita-Plätze (Rechtsanspruch!),
		Feuerwehr, Straßen, Verwaltung. Alles gesetzlich vorgeschrieben. Was die Stadt sich
		freiwillig leistet, etwa Vereinsförderung, Kulturbüro oder Badehaus, ist dagegen nur ein
		kleiner Posten. Wo die Grundsteuer im Gesamtbild steht, zeigt die
		<a href="/kategorien/ertrag?year=2026">Einnahmen-Übersicht 2026</a>. Was mit dem Geld
		passiert, zeigen die <a href="/kategorien?year=2026">Ausgaben nach Lebensbereichen</a>.
	</p>
</section>

<!-- F4: Stadtkasse -->
<section class="section">
	<AnchorHeading level={3} id="stadtkasse">Warum braucht Rödermark einen so hohen Hebesatz?</AnchorHeading>
	<p class="answer-lead">
		Zwei Gründe: Außer den Einwohnern zahlt hier kaum jemand ein. Und Rödermarks
		Grundsteuer-Basis ist die kleinste im ganzen Kreis.
	</p>
	<p class="explainer-prose">
		Woher kommt das Geld einer Stadt? In Rödermark vor allem vom
		<strong>Einkommensteuer-Anteil</strong>: rund
		{fmtEurMio(data.steuerquellen.einkommensteuer)} ({data.steuerquellen.jahr}). Das ist ein
		fester Anteil an der Einkommensteuer der Einwohner. Jede Wohnstadt bekommt ihn, keine kann
		ihn beeinflussen. Dahinter: Gewerbesteuer ({fmtEurMio(data.steuerquellen.gewerbesteuer)})
		und Grundsteuer&nbsp;B ({fmtEurMio(data.umlagen.grundsteuerBPlan)}).
	</p>
	<p class="explainer-prose">
		Moment, alle reden doch über die Grundsteuer! Was hat die Gewerbesteuer damit zu tun? Alles.
		Denn sie entscheidet, wie tief eine Stadt ihren Bürgern in die Tasche greifen muss. Der
		Steuer-Mix der Kommunen zeigt es: Die grünen Segmente (Einkommensteuer) sind überall ähnlich
		lang. <strong>Der Unterschied zwischen arm und reich ist fast nur das gelbe
		Gewerbesteuer-Segment:</strong>
	</p>
	<div class="card card-padded">
		<div class="mix-legend">
			{#each MIX_SEGMENTE as s (s.key)}
				<span class="mix-legend-item"><span class="mix-swatch" style="background: {s.color}"></span>{s.label}</span>
			{/each}
		</div>
		<div class="mix-chart">
			{#each data.steuermix as r (r.kommune)}
				{@const isRoedermark = r.kommune === 'Rödermark'}
				<div class="mix-row">
					<span class="mix-label" class:mix-label-highlight={isRoedermark}>{r.kommune.replace(' am Main', '')}</span>
					<div class="mix-track">
						{#each MIX_SEGMENTE as s (s.key)}
							{@const wert = r[`${s.key}_pro_kopf`]}
							<div
								class="mix-seg"
								style="width: {(wert / data.maxSteuermixProKopf) * 100}%; background: {s.color}"
								title="{r.kommune} – {s.label}: {fmtEur(wert)} je Einwohner ({fmtEurMio(r[s.key])} gesamt, Plan {r.jahr})"
							></div>
						{/each}
					</div>
					<span class="mix-total" class:mix-total-highlight={isRoedermark}>{fmtEur(r.summe_pro_kopf)}</span>
				</div>
			{/each}
			{#each data.steuermixFehlend as f (f.kommune)}
				<div class="mix-row">
					<span class="mix-label">{f.kommune.replace(' am Main', '')}</span>
					<div class="mix-track mix-track-leer" title={f.grund}>Haushaltsplan 2026 noch nicht veröffentlicht</div>
					<span class="mix-total mix-total-leer">–</span>
				</div>
			{/each}
		</div>
	</div>
	<p class="chart-note">
		Steuererträge je Einwohner, Planwerte 2026 aus den jeweiligen Haushaltsplänen (Konten
		5500–5559). Details je Segment per Maus.
	</p>
	<p class="explainer-prose">
		In {mixSpitze?.kommune} zahlen die Firmen {fmtEur(mixSpitze?.gewerbesteuer_pro_kopf ?? 0)}
		Gewerbesteuer <em>pro Einwohner</em>. Das ist rund das {gewFaktor}-Fache von Rödermark
		({fmtEur(mixRoedermark?.gewerbesteuer_pro_kopf ?? 0)}). Zahlen die Bürger dort weniger, weil
		ihre Stadt besser wirtschaftet? Nein. <strong>Es zahlt einfach jemand anderes für sie
		mit</strong>: die Firmen rund um Flughafen und Autobahnkreuz. Rödermark hat die nicht.
		Und das Muster gilt im ganzen Kreis: Die höchsten Grundsteuer-Hebesätze (Mühlheim,
		Heusenstamm, Rödermark, Egelsbach) haben genau die Kommunen mit dem wenigsten Gewerbe.
	</p>
	<p class="explainer-prose">
		Heißt das, Rödermark hat bei der Gewerbeansiedlung versagt? So einfach ist es nicht
		(<a href="#gewerbe-ansiedeln">nächste Frage</a>). Die Wohnstadt ist kein Unfall.
		Jahrzehntelang wollten die meisten hier genau das: Wohnen statt Gewerbegebiete. Die Kehrseite
		steht heute auf dem Grundsteuerbescheid. Und Gewerbesteuer ist auch kein sicheres Geld:
		Egelsbach plant für 2026 ein Drittel weniger als im Vorjahr (8,5 statt
		12,5&nbsp;Mio.&nbsp;€). Der Einkommensteuer-Anteil einer Wohnstadt fließt dagegen
		verlässlich. <strong>Stabil, aber knapp. Das ist Rödermarks Deal.</strong>
	</p>
	<p class="explainer-prose">
		<strong>Grund zwei: die Grundsteuer-Basis selbst.</strong> Der Hebesatz ist nur ein Bruch:
		benötigtes Geld geteilt durch die Steuersubstanz aller Grundstücke der Stadt. Viel Substanz,
		niedriger Satz. Wenig Substanz, hoher Satz. Und Rödermark hat die
		<strong>kleinste Grundsteuer-Basis im ganzen Kreis</strong>: rund
		{Math.round(basisRoedermark?.basis ?? 0)}&nbsp;€ Messbetrag je Einwohner.
		{basisSpitze?.kommune} hat gut 40&nbsp;% mehr ({Math.round(basisSpitze?.basis ?? 0)}&nbsp;€)
		und braucht für dasselbe Geld eben einen gut 40&nbsp;% niedrigeren Hebesatz. Wenig Gewerbe,
		wenig Substanz: Deshalb hat ausgerechnet die ruhige Wohnstadt die höchsten Sätze (mehr dazu:
		<a href="#vergleichbarkeit">Kann man Hebesätze überhaupt vergleichen?</a>).
	</p>
	<p class="chart-note">
		Grundsteuer-Basis als Näherung rückgerechnet: Ist-Einnahmen 2024 ÷ (Hebesatz&nbsp;÷&nbsp;100),
		je Einwohner (IHK-Gemeindesteckbriefe). Kein amtlicher Messbetrag, aber für den Vergleich der
		Größenordnungen belastbar.
	</p>
</section>

<!-- F5: Gewerbe ansiedeln -->
<section class="section">
	<AnchorHeading level={3} id="gewerbe-ansiedeln">Warum siedelt Rödermark nicht einfach Gewerbe an?</AnchorHeading>
	<p class="answer-lead">
		Weil Gewerbegebiete ausweisen nicht heißt, dass Firmen kommen.
	</p>
	<p class="explainer-prose">
		Firmen suchen sich ihren Standort aus, nicht umgekehrt. Autobahn, Flächen, Fachkräfte, die
		Konkurrenz der Nachbarn: alles entscheidet mit. Der Beweis steht im eigenen Kreis:
		<strong>Egelsbach</strong> liegt im begehrten Westkorridor, direkt neben Langen und Dreieich.
		Gewerbesteuer pro Kopf? Kaum mehr als Rödermark. Das kleine Mainhausen am östlichen Kreisrand
		holt dagegen überdurchschnittlich viel, weil dort ein paar größere Betriebe sitzen. Ein
		Bürgermeister kann Firmen nicht herbeibeschließen. Ob Rödermark vor Jahrzehnten mehr hätte
		tun sollen? Legitime Debatte. Aber der heutige Hebesatz ist die Folge gewachsener Struktur.
		Nicht von Verschwendung im Rathaus.
	</p>
	<p class="explainer-prose">
		Und selbst wenn Firmen kommen: Es zählt, <strong>was</strong> kommt. Beispiel Rechenzentren,
		auch für Rödermark im Gespräch. Riesige Hallen, viel Fläche, aber oft nur ein paar Dutzend
		Jobs. Genau da liegt der Haken: Die Gewerbesteuer großer Unternehmen wird nach
		<strong>Lohnsummen</strong> auf ihre Standorte verteilt (§&nbsp;29 GewStG). Wo die Server
		stehen, zählt nicht. Wo die Gehälter gezahlt werden, zählt. Ein Rechenzentrum mit 20
		Beschäftigten bringt seiner Kommune deshalb oft nur einen Bruchteil dessen, was das
		Riesengebäude vermuten lässt. Die Fläche ist trotzdem für immer belegt. Frankfurt, Europas
		größter Rechenzentrums-Standort, streitet über genau das seit Jahren. Für die Stadtkasse
		zählt nicht die Größe der Halle. Sondern Jobs und Gewinne vor Ort.
	</p>
</section>

<!-- F6: Gewerbesteuer erhöhen -->
<section class="section">
	<AnchorHeading level={3} id="gewerbesteuer-erhoehen">Warum erhöht die Stadt nicht einfach die Gewerbesteuer?</AnchorHeading>
	<p class="answer-lead">
		Hat sie: 2025 ging der Satz von 380 auf 400&nbsp;%. Das ist Kreisspitze, gleichauf mit Heusenstamm
		und Rodgau. Viel mehr geht kaum. Und es würde auch kaum etwas bringen.
	</p>
	<p class="explainer-prose">
		Das Problem ist die Mathematik: Rödermarks Gewerbesteuer-Basis ist klein. Zehn Punkte mehr
		(400 → 410&nbsp;%) brächten nur rund 450.000&nbsp;€ im Jahr. Die Grundsteuer-Erhöhung bringt
		rund 3&nbsp;Millionen. <strong>Pro Jahr.</strong> Um das über die Gewerbesteuer zu holen,
		müsste der Satz auf etwa 470&nbsp;% steigen. Zum Vergleich: Der höchste Satz im ganzen Kreis
		liegt bei 405&nbsp;% (Dietzenbach). Rödermark wäre mit Abstand der teuerste Gewerbestandort
		weit und breit.
	</p>
	<p class="explainer-prose">
		Dazu kommen zwei Risiken. <strong>Firmen sind mobil, Häuser nicht:</strong> Wer den Satz auf
		einer kleinen, beweglichen Basis überreizt, riskiert genau die Betriebe, die man halten
		will. Und <strong>Gewerbesteuer ist unzuverlässig</strong>, das zeigt Rödermark gerade
		selbst: 2023 kamen noch 18,9&nbsp;Mio.&nbsp;€ herein, 2024 nur noch 16,8. Für 2026 plant
		die Stadt mit 17,8&nbsp;Mio.&nbsp;€, zwei Millionen <em>weniger</em> als der Ansatz fürs
		Vorjahr, <em>trotz</em> des höheren Hebesatzes. Die Kommunalaufsicht verlangt für das
		Sparprogramm aber planbare Einnahmen. Und die stabilste Steuer, die eine Stadt hat, ist
		nun mal die Grundsteuer. Genau deshalb trifft es am Ende die Grundbesitzer:
		<strong>nicht, weil es fair ist, sondern weil sie nicht weglaufen können.</strong>
	</p>
</section>

<!-- F7: Verschwendung -->
<section class="section">
	<AnchorHeading level={3} id="verschwendung">Wird im Rathaus Geld verschwendet?</AnchorHeading>
	<p class="answer-lead">
		Die Zahlen liefern dafür keinen Beleg. Die großen Kostentreiber liegen außerhalb des
		Rathauses. Ein Freifahrtschein ist das trotzdem nicht.
	</p>
	<p class="explainer-prose">
		Die Belege stehen oben: Die <a href="#umlagen">Rechnung vom Kreis</a> frisst mehr, als die
		ganze Grundsteuer einbringt. Die <a href="#stadtkasse">Gewerbesteuer-Basis</a> ist dünn. Und
		<a href="#hessen-schnitt">der ganze Kreis</a> hat dieselben hohen Sätze. Ein
		Rödermark-Verschwendungsproblem sähe anders aus. Dazu kommt: Der Großteil der Ausgaben ist
		Pflicht. Freiwillig leistet sich die Stadt nur wenig: Vereinsförderung, Kulturbüro,
		Bücherei, Badehaus.
	</p>
	<p class="explainer-prose">
		Aber Achtung, kein Freifahrtschein: <strong>Für Ausgabendisziplin, für die Abfederung der
		Erhöhung und für ehrliche Kommunikation bleibt die Lokalpolitik voll
		verantwortlich.</strong> Das darf und soll man kritisch begleiten. Prüfen Sie selbst nach:
		Auf dieser Website steht jede Position des Haushalts: nach
		<a href="/kategorien">Lebensbereichen</a>, nach <a href="/teilhaushalte">Teilhaushalten</a>,
		im <a href="/explorer">Daten-Explorer</a>. Jede Zahl mit Quelle, bis auf die PDF-Seite genau.
	</p>
</section>

<!-- F7: Eppertshausen -->
<section class="section">
	<AnchorHeading level={3} id="eppertshausen">Warum zahlt Eppertshausen nur 480 %?</AnchorHeading>
	<p class="answer-lead">
		Weil Eppertshausen in fast allem anders ist: anderer Landkreis, ein Viertel der Einwohner,
		andere Struktur. Und auch dort steigen die Sätze, bei tiefroten Zahlen.
	</p>
	<p class="explainer-prose">
		Keine fünf Kilometer von Ober-Roden, aber haushaltstechnisch eine andere Welt. Eppertshausen
		liegt im <strong>Landkreis Darmstadt-Dieburg</strong>: anderes Umlagesystem, kein
		Kreis-Offenbach-Schuldenberg. Rund 6.500 Einwohner statt 28.700. Andere Grundstücke, anderes
		Gewerbe. Und selbst dort: Der Hebesatz stieg 2026 von 400 auf 480&nbsp;%, einstimmig
		beschlossen. Trotzdem meldet die Lokalpresse einen „tiefroten Etat". Der Bund der
		Steuerzahler zählt im ganzen Kreis Darmstadt-Dieburg eine Erhöhungswelle. <strong>Der
		günstige Nachbar ist kein Gegenbeweis. Er ist dieselbe Entwicklung, nur mit besserem
		Startpunkt.</strong>
	</p>
</section>

<!-- F8: Hessen-Schnitt -->
<section class="section">
	<AnchorHeading level={3} id="hessen-schnitt">Aber der Hessen-Durchschnitt liegt doch bei 400 %?</AnchorHeading>
	<p class="answer-lead">
		Ja. Aber dieser Schnitt wird von hunderten kleinen Landgemeinden dominiert und taugt nicht
		als Maßstab für eine Rhein-Main-Wohnstadt.
	</p>
	<p class="explainer-prose">
		Die Zahl stimmt: Hessen-Schnitt 2025 rund 400&nbsp;% (Bund der Steuerzahler). Der Kreis
		Offenbach liegt bei rund {Math.round(data.avgHebesatz2026).toLocaleString('de-DE')}&nbsp;%.
		Und das war schon vor der Reform so (2024: rund
		{Math.round(data.avgHebesatzVorReform).toLocaleString('de-DE')}&nbsp;% gegen 396&nbsp;%
		hessenweit). Aber der Hessen-Schnitt hat einen Haken: Er ist <strong>ungewichtet</strong>.
		Das 900-Einwohner-Dorf zählt darin genauso viel wie Frankfurt. Und die meisten der gut 420
		hessischen Kommunen sind genau solche Dörfer: große Grundstücke, niedrige Kosten, gesunder
		Landkreis. Da reicht ein niedriger Satz. Wer Rödermark am Hessen-Schnitt misst, vergleicht
		eine Rhein-Main-Wohnstadt mit einem Dorf im Vogelsberg. <strong>Den Dorf-Hebesatz gibt es
		nur zusammen mit dem Dorf.</strong>
	</p>
</section>

<!-- F9: Vergleichbarkeit -->
<section class="section">
	<AnchorHeading level={3} id="vergleichbarkeit">Kann man Hebesätze von Kommunen überhaupt vergleichen?</AnchorHeading>
	<p class="answer-lead">
		Nur für eine Frage: „Was kostet dasselbe Haus wo?" Und auch das nur innerhalb Hessens. Als
		Zeugnis dafür, wer besser wirtschaftet, taugt der Hebesatz nicht.
	</p>
	<p class="explainer-prose">
		Über Bundesländer hinweg: nein (<a href="#bundesvergleich">erste Frage</a>). Innerhalb
		Hessens: ja, aber nur für die Frage „Was kostet dasselbe Haus wo?"
		(<a href="#musterhaus">Musterhaus-Vergleich</a>). Als Zeugnis fürs Rathaus taugt der Hebesatz
		dagegen nicht. Denn jede Kommune ist ein Unikat: <strong>Fläche, Grundstücke, Einwohner,
		Gewerbe, Kreisumlage, Altschulden, Rücklagen</strong>. All das bestimmt mit, welcher Satz
		nötig ist. Zwei nackte Hebesätze vergleichen? Das ist wie zwei Mieten vergleichen, ohne
		Wohnungsgröße, ohne Lage. <strong>Der Hebesatz verrät, was Sie zahlen. Nicht, wie gut Ihre
		Stadt wirtschaftet.</strong>
	</p>
</section>

<!-- F10: Wie kam es zur Erhöhung -->
<section class="section">
	<AnchorHeading level={3} id="entwicklung">Wie kam es zur Erhöhung?</AnchorHeading>
	<p class="answer-lead">
		In drei Schritten. Und anders, als die Kurve vermuten lässt: Ein Teil des Sprungs 2025 war
		nur die Umstellung auf die Grundsteuerreform, ein Teil bereits eine echte Erhöhung. Der große
		Schritt auf 1.327&nbsp;% kommt aus dem Haushaltssicherungskonzept, gegen ein Defizit von
		13,8&nbsp;Mio.&nbsp;€.
	</p>
	<div class="card card-padded">
		<div class="vbar-chart">
			{#each roedermarkHistory as entry, i (entry.year)}
				{@const prev = i > 0 ? roedermarkHistory[i - 1] : null}
				{@const changed = prev && prev.hebesatz !== entry.hebesatz}
				{@const went_up = changed && entry.hebesatz > (prev?.hebesatz ?? 0)}
				{@const went_down = changed && entry.hebesatz < (prev?.hebesatz ?? 0)}
				<div class="vbar-col">
					{#if changed}
						<span class="vbar-delta" class:vbar-delta-up={went_up} class:vbar-delta-down={went_down}>
							{went_up ? '▲' : '▼'}{Math.abs(entry.hebesatz - (prev?.hebesatz ?? 0))}
						</span>
					{/if}
					<span class="vbar-label" class:vbar-label-up={went_up} class:vbar-label-down={went_down}>
						{fmtHS(entry.hebesatz, data.hasDecimals)}
					</span>
					<div class="vbar-track">
						<div
							class="vbar-fill"
							class:vbar-fill-up={went_up}
							class:vbar-fill-down={went_down}
							style="height: {(entry.hebesatz / maxHist) * 100}%"
						></div>
					</div>
					<span class="vbar-year">{entry.year}</span>
				</div>
			{/each}
		</div>
	</div>
	<p class="chart-note">
		Rödermarks Grundsteuer-B-Hebesatz über die Jahre, in Prozent (v. H.).
	</p>
	<p class="explainer-prose">
		<strong>Schritt 1, die Reform-Umstellung (1. Januar 2025):</strong> Die Grundsteuerreform
		hat alle Messbeträge neu festgesetzt. Damit dieselbe Summe reinkommt wie vorher, hätte der
		neue Satz laut Land Hessen bei <strong>803,51&nbsp;%</strong> liegen müssen (vorher:
		715&nbsp;%). Die Stadtverordneten beschlossen 800&nbsp;%, praktisch neutral. Bis hierhin:
		nur eine neue Zahl für dieselbe Steuer.
	</p>
	<p class="explainer-prose">
		<strong>Schritt 2, die erste echte Erhöhung (2025):</strong> Noch im selben Jahr ging der
		Satz auf <strong>990&nbsp;%</strong>, rund 23&nbsp;% über dem neutralen Niveau. Das war
		keine Reform-Mechanik mehr. Das war eine Erhöhung gegen das wachsende Defizit
		(<a href="#erhoehung-2025">eigene Frage unten</a>).
	</p>
	<p class="explainer-prose">
		<strong>Schritt 3, der große Schritt (2026):</strong> Der Haushaltsentwurf wies
		13,8&nbsp;Mio.&nbsp;€ Defizit aus. Ohne Gegenmaßnahmen: rund 69&nbsp;Millionen bis 2030.
		So einen Haushalt darf die Stadt gar nicht beschließen. Die Kommunalaufsicht verlangt ein
		Sparprogramm mit klarem Abbaupfad, das <strong>Haushaltssicherungskonzept</strong>.
		97 Maßnahmen, die größte: Grundsteuer&nbsp;B auf 1.327&nbsp;% (44&nbsp;% des Volumens;
		56&nbsp;% sind Sparen und andere Einnahmen). Ziel: schwarze Null ab 2029. Beschlossen im
		Juni 2026, namentliche Abstimmung, 20 zu 16, rückwirkend zum 1.&nbsp;Januar. Die
		Grundsteuer&nbsp;A (Land- und Forstwirtschaft) stieg gleich mit: von 175 auf 900&nbsp;%.
	</p>
	<a href="/hsk2026" class="link-box">
		<ShieldCheck class="link-box-icon" />
		<div class="link-box-body">
			<strong>Alle 97 Maßnahmen im Detail</strong>
			Wo die Stadt sparen und wo sie mehr einnehmen will: Die HSK-Seite schlüsselt das
			komplette Konzept auf.
		</div>
		<ArrowRight class="link-box-arrow" />
	</a>
</section>

<!-- F11: Erhöhung 2025 -->
<section class="section">
	<AnchorHeading level={3} id="erhoehung-2025">Gab es 2025 nicht schon eine kräftige Erhöhung?</AnchorHeading>
	<p class="answer-lead">
		Ja, rund 23&nbsp;% über dem aufkommensneutralen Niveau. Und wer die Gesamtbelastung seit der
		Reform betrachten will: Gegenüber einer neutralen Umsetzung wären 1.327&nbsp;% ein Plus von
		rund 65&nbsp;%.
	</p>
	<p class="explainer-prose">
		Der Einwand ist berechtigt. Hier die Zahlen: Neutral wären <strong>803,51&nbsp;%</strong>
		gewesen (Landes-Empfehlung). Beschlossen wurden erst 800, dann <strong>990&nbsp;%</strong>.
		Die Mehreinnahme steht schwarz auf weiß im Haushalt: Für 2026 sind mit dem 990er-Satz
		{fmtEurMio(data.umlagen.grundsteuerBPlan)} angesetzt. 2024, mit dem alten Satz, waren es
		{fmtEurMio(data.roedermarkIst2024GrundsteuerB)}. Macht rund
		{Math.round((data.umlagen.grundsteuerBPlan / data.roedermarkIst2024GrundsteuerB - 1) * 100)}&nbsp;%
		mehr. <strong>Wer sagt „2025 wurde schon erhöht", hat recht.</strong>
	</p>
	<p class="explainer-prose">
		<strong>Und der Rechner?</strong> Der <a href="/grundsteuer-rechner">Grundsteuer-Rechner</a>
		rechnet bewusst nur den jüngsten Schritt (990 → 1.327&nbsp;%, also +34&nbsp;%). Denn er
		startet bei Ihrer heutigen Grundsteuer, und da steckt die 2025er-Erhöhung schon drin.
		Einfach addieren hieße doppelt zählen. Die ehrliche Gesamtrechnung: Gegenüber einer
		neutralen Reform-Umsetzung (803,51&nbsp;%) sind 1.327&nbsp;% ein Plus von rund
		<strong>65&nbsp;%</strong>. Aber Achtung: Ihr <em>persönlicher</em> Sprung von 2024 auf 2025
		kann ganz anders aussehen. Die Reform hat die Last neu verteilt: Manche zahlen seither
		deutlich mehr, andere weniger. Das kommt vom Bewertungsmodell von Bund und Land. Nicht vom
		Hebesatz.
	</p>
</section>

<!-- F12: Macht es sich die Stadt zu einfach? -->
<section class="section">
	<AnchorHeading level={3} id="zu-einfach">„Aus dem Nichts so eine Erhöhung! Macht es sich die Stadt nicht zu einfach?"</AnchorHeading>
	<p class="answer-lead">
		Plötzlich ist nur der sichtbare Schritt, nicht die Ursache: Das Loch wuchs über Jahre, jetzt
		ist der Puffer aufgebraucht. Und neben der Erhöhung kürzt die Stadt gleichzeitig ihre
		Investitionen um mehr als die Hälfte. Bequem sieht anders aus.
	</p>
	<p class="explainer-prose">
		<strong>Warum es „plötzlich" wirkt:</strong> Die Kosten sind nicht explodiert, sie sind
		geschlichen. Allein die <a href="#umlagen">Rechnung vom Kreis</a>: plus 14&nbsp;Millionen
		seit {data.umlagen.erstesJahr}. So etwas deckt man eine Weile aus der Rücklage. Genau das
		ist passiert, bis sie leer war. Ende 2025 sind noch 11,1&nbsp;Mio.&nbsp;€ in der Kasse.
		Weniger als <em>ein einziges</em> Jahresdefizit (13,8&nbsp;Mio.). Eine Erhöhung, die
		jahrelang von Reserven abgefedert wurde, kommt dann eben geballt. Man kann kritisieren, dass
		frühere, kleinere Schritte ehrlicher gewesen wären. Aber „aus dem Nichts" kam hier nichts.
	</p>
	<p class="explainer-prose">
		<strong>Und „zu einfach"?</strong> Ein Körnchen Wahrheit steckt drin: Die Grundsteuer ist
		der einzige große Hebel, den eine Stadt selbst sicher steuern kann. Deshalb greift jede
		Haushaltssanierung in Deutschland zu ihr. Aber bequem ist das Paket nicht. Parallel kürzt
		die Stadt ihre <strong>Investitionen von 22,6 auf 10,6&nbsp;Mio.&nbsp;€</strong>, mehr als
		halbiert. Die <strong>Kreditaufnahme: von 16,3 auf 4,3&nbsp;Mio.</strong> Und 56&nbsp;% der
		Sanierung kommen aus Sparen und anderen Einnahmen, die Grundsteuer trägt 44&nbsp;%. Ob die
		Mischung richtig ist? Legitime politische Frage. Dass sich jemand vorm Sparen drückt?
		<strong>Geben die Zahlen nicht her.</strong>
	</p>
</section>

<!-- F13: Was tun -->
<section class="section">
	<AnchorHeading level={3} id="was-tun">Was kann man überhaupt tun?</AnchorHeading>
	<div class="info-box info-box-blue">
		<div>
			<strong>Einordnung:</strong> Alles bis hierhin waren belegbare Zahlen und Fakten. Was jetzt
			folgt, ist meine <strong>persönliche Einschätzung</strong> (Christian Engel; dieses Portal
			ist ein privates Projekt und keine Seite der Stadt, siehe
			<a href="/impressum">Impressum</a>). Man kann das politisch durchaus anders bewerten.
		</div>
	</div>
	<p class="explainer-prose">
		Nüchtern betrachtet hat eine Stadt genau drei Stellschrauben: <strong>mehr Einnahmen,
		weniger Leistungen, mehr Schulden.</strong> Schulden verschieben das Problem nur, und die
		Aufsicht deckelt sie ohnehin. Wer niedrigere Steuern fordert, sagt damit automatisch: dann
		eben eine der anderen beiden Schrauben. Das ist keine Polemik, das ist Mathematik. Innerhalb
		dieses engen Rahmens sehe ich folgende Möglichkeiten:
	</p>
	<p class="explainer-prose">
		<strong>Kurzfristig, die Stadt selbst:</strong> Das
		<a href="/hsk2026">Haushaltssicherungskonzept</a> ist genau dieser Versuch. 97 Maßnahmen,
		die Grundsteuer nur 44&nbsp;% davon. Viel mehr Spielraum gibt es ehrlicherweise nicht: Der
		Großteil der Ausgaben ist Pflicht, dazu die Rechnung vom Kreis. Die freiwilligen Leistungen
		(Vereinsförderung, Kulturbüro, Bücherei, Badehaus) sind ein kleiner Posten. Wer sie
		streicht, spart wenig. Und verliert viel von dem, was Rödermark lebenswert macht.
	</p>
	<p class="explainer-prose">
		<strong>Langfristig, Strukturen verschieben:</strong> Gewerbeentwicklung bleibt der einzige
		echte Ausweg aus dem Grundproblem, mit allen
		<a href="#gewerbe-ansiedeln">Grenzen von oben</a>. Realistisch heißt das: Bestandspflege
		statt Ansiedlungs-Träume, vielleicht interkommunale Gewerbegebiete mit den Nachbarn. Aber
		das wirkt in Jahrzehnten. Nicht in Haushaltsjahren.
	</p>
	<p class="explainer-prose">
		<strong>Der größte Hebel liegt nicht im Rathaus:</strong> Die Kreisumlage hängt am
		Schuldenberg des Kreises Offenbach. Die Kostenlast hängt an Gesetzen, die Bund und Land
		beschließen, ohne sie voll zu bezahlen, Stichwort Kita-Rechtsanspruch. Wer das ändern will,
		muss den Druck nach Wiesbaden und Berlin richten. Nicht auf die Stadtverordneten, die neben
		einem an der Supermarktkasse stehen.
	</p>
	<p class="explainer-prose">
		<strong>Und die Bürger?</strong> Können mehr tun, als Hebesätze zu googeln: zur
		Haushaltsdebatte gehen, bei den Prioritäten mitreden (welche freiwilligen Leistungen sind
		sie uns wert?) und kontrollieren, was mit dem Geld passiert. Die Missmanagement-These hält
		den Daten nicht stand. Die Kontrolle bleibt trotzdem Bürgeraufgabe. <strong>Genau dafür gibt
		es dieses Portal.</strong>
	</p>
</section>

<!-- F12: Rechner -->
<section class="section">
	<AnchorHeading level={3} id="rechner">Was heißt das für mich konkret?</AnchorHeading>
	<p class="answer-lead">
		Das hängt von Wohnfläche und Grundstück ab. Der Rechner schätzt Ihre persönliche
		Mehrbelastung in einer Minute, auch ohne Bescheid zur Hand.
	</p>
	<a href="/grundsteuer-rechner" class="link-box">
		<Calculator class="link-box-icon" />
		<div class="link-box-body">
			<strong>Zum Grundsteuer-Rechner</strong>
			Für Eigenheim, Eigentumswohnung oder Miete, mit Schätzung nach dem hessischen
			Flächen-Faktor-Modell.
		</div>
		<ArrowRight class="link-box-arrow" />
	</a>
</section>

<!-- Anhang: Detailtabelle -->
<section class="section">
	<AnchorHeading level={3} id="tabelle">Alle Zahlen im Überblick</AnchorHeading>
	<div class="scroll-x card">
		<table class="data-table">
			<thead>
				<tr>
					<th>Kommune</th>
					<th class="col-number">Hebesatz 2026</th>
					<th class="col-number">Musterhaus&thinsp;/&thinsp;Jahr</th>
					<th class="col-number">Gewerbesteuer&thinsp;/&thinsp;Kopf (2024)</th>
					<th class="col-number">Grundsteuer B (Plan 2026)</th>
				</tr>
			</thead>
			<tbody>
				{#each data.kommunen as k (k.kommune)}
					{@const mh = data.musterhaus.find((m) => m.kommune === k.kommune)}
					<tr class:row-sum={k.kommune === 'Rödermark'}>
						<td>{k.kommune}</td>
						<td class="col-number tabular-nums">
							{#if k.hebesatz_2026}
								{fmtHS(k.hebesatz_2026.hebesatz, true)}&nbsp;%
								{#if k.hebesatz_2026.status === 'geplant'}<span class="status-geplant"> (geplant)</span>{/if}
							{:else}
								<span class="text-gray-400">–</span>
							{/if}
						</td>
						<td class="col-number tabular-nums">
							{#if mh}
								{fmtEur(mh.grundsteuer_eur)}
							{:else}
								<span class="text-gray-400">–</span>
							{/if}
						</td>
						<td class="col-number tabular-nums">
							{#if k.ist_2024?.gewerbesteuer}
								{fmtEur(k.ist_2024.gewerbesteuer.pro_kopf_eur)}
							{:else}
								<span class="text-gray-400">–</span>
							{/if}
						</td>
						<td class="col-number tabular-nums">
							{#if k.plan_2026_grundsteuer_b}
								{fmtEurMio(k.plan_2026_grundsteuer_b.betrag_eur)}
								{#if k.plan_2026_grundsteuer_b.betrag_eur_angepasst}
									<span class="badge badge-amber" style="font-size:0.65rem;margin-left:0.3rem" title={k.plan_2026_grundsteuer_b.anmerkung}>
										angepasst: {fmtEurMio(k.plan_2026_grundsteuer_b.betrag_eur_angepasst)}
									</span>
								{/if}
							{:else}
								<span class="text-gray-400">noch nicht verfügbar</span>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="chart-note">
		Musterhaus: {data.musterhausSpec.grundflaeche}&thinsp;m² Grundstück, {data.musterhausSpec.wohnflaeche}&thinsp;m²
		Wohnfläche, Lagefaktor 1,0. Planzahlen 2026 aus dem „Finanzstatusbericht" (Konto 5552) der
		jeweiligen Haushaltspläne; wo dieser Anhang im vorliegenden Dokument nicht auffindbar oder
		nicht lesbar war, steht „noch nicht verfügbar". Geschätzt wird nicht.
	</p>
</section>

<!-- Quellen -->
<section class="section">
	<AnchorHeading level={3} id="quellen-grundsteuer">Quellen</AnchorHeading>
	<ul class="src-list">
		<li>Hebesätze 2026: IHK Gießen-Friedberg, Hebesatzumfrage 2026 (Stand 29.05.2026); IHK Offenbach Gemeindesteckbriefe 2025 (Vorjahre); Haushaltssatzungen der Stadt Rödermark; einzeln belegte Beschlussvorlagen für geplante Erhöhungen.</li>
		<li>Hessen-Durchschnitt (~400&nbsp;% 2025, ~396&nbsp;% 2024): Bund der Steuerzahler Hessen, Hebesatzumfragen.</li>
		<li>Gewerbesteuereinnahmen und Einwohnerzahlen: IHK Offenbach Gemeindesteckbriefe 2025 (Ist 2024).</li>
		<li>Steuerquellen-Mix 2026 (Einkommensteuer-/Umsatzsteuer-Anteil, Gewerbe- und Grundsteuer, Konten 5500–5559): jeweilige Haushaltspläne 2026 (Finanzstatusbericht-Anlagen bzw. Teilergebnishaushalte), mit Seitenangabe je Kommune in der <a href="/data/steuermix_2026.json" target="_blank" rel="noopener noreferrer">Datendatei</a>; gegen die ausgewiesenen Summenzeilen validiert. Dietzenbach weist die Gewerbesteuer in der Sammelzeile „Sonst. Kommunalsteuern" aus (Ist 2024 deckungsgleich mit dem IHK-Gewerbesteuerwert).</li>
		<li>Kreis- und Schulumlage, Steuer-Planzahlen Rödermark (Grundsteuer B, Gewerbesteuer, Einkommensteuer-Anteil, Ansätze 2025/2026) und Defizit: Haushaltsplan Rödermark 2026 (Entwurf) und Haushaltssicherungskonzept 2026; Gewerbesteuer-Ist 2023/2024: IHK Offenbach Gemeindesteckbrief 2025.</li>
		<li>Aufkommensneutraler Hebesatz Rödermark (803,51&nbsp;%): <a href="https://finanzamt.hessen.de/grundsteuerreform/hebesatzempfehlungen" target="_blank" rel="noopener noreferrer">Hebesatzempfehlungen der Hessischen Steuerverwaltung</a>; Einordnung und Beschluss-Chronik 2024/25: <a href="https://www.rm-news.de/?p=272680" target="_blank" rel="noopener noreferrer">rm-news.de</a>.</li>
		<li>Beschluss der Hebesatz-Anhebung 2026 (Grundsteuer B 990 → 1.327&nbsp;%, Grundsteuer A 175 → 900&nbsp;%, rückwirkend zum 01.01.2026, namentliche Abstimmung 20:16): <a href="https://www.rheinmainverlag.de/2026/06/25/die-grundsteuer-in-roedermark-geht-weiter-rauf/" target="_blank" rel="noopener noreferrer">Rhein-Main-Verlag, 25.06.2026</a>.</li>
		<li>Eppertshausen (Hebesatz 480&nbsp;%, Erhöhung von 400&nbsp;%, Defizit trotz Steuererhöhung): <a href="https://www.rheinmainverlag.de/2026/02/06/eppertshausen-tiefroter-etat-trotz-hoeherer-steuern/" target="_blank" rel="noopener noreferrer">Rhein-Main-Verlag, 06.02.2026</a>; Erhöhungswelle im Kreis Darmstadt-Dieburg: <a href="https://www.steuerzahler-hessen.de/neuigkeiten/artikel/massive-steuererhoehungswelle-im-kreis-darmstadt-dieburg/" target="_blank" rel="noopener noreferrer">Bund der Steuerzahler Hessen</a>.</li>
		<li>Berechnungsmodell Musterhaus: Hessisches Grundsteuergesetz (Flächen-Faktor-Verfahren).</li>
		{#each data.kommunen.filter((k) => k.plan_2026_grundsteuer_b) as k (k.kommune)}
			<li><strong>{k.kommune}</strong> (Planzahl 2026): {k.plan_2026_grundsteuer_b!.quelle}</li>
		{/each}
	</ul>
</section>

</div><!-- /article-body -->

<aside class="article-aside">
	<nav class="toc" aria-label="Fragenübersicht">
		<p class="toc-title">Fragen</p>
		<ol>
			{#each toc as t (t.id)}
				<li><a href="#{t.id}" class:active={t.id === activeId}>{t.label}</a></li>
			{/each}
		</ol>
	</nav>
</aside>

</div><!-- /article-layout -->

<style>
	/* Artikel-Layout: Textspalte fest auf Lesebreite, alle Inhalts-Elemente
	   (Karten, Charts, Tabellen) laufen in derselben Spalte mit.
	   Ab 1100px: sticky Fragenübersicht rechts daneben. */
	.article-layout { display: grid; grid-template-columns: minmax(0, 48rem); }
	@media (min-width: 1100px) {
		.article-layout { grid-template-columns: minmax(0, 48rem) 16rem; gap: 3rem; }
	}
	.article-body { min-width: 0; }
	.article-aside { display: none; }
	@media (min-width: 1100px) {
		.article-aside { display: block; }
		.article-aside .toc { position: sticky; top: 1.5rem; }
	}

	/* Mobile: aufklappbare, oben klebende Fragenübersicht */
	.toc-mobile {
		position: sticky; top: 0.5rem; z-index: 20;
		margin-bottom: 1.5rem;
		background: white; border-radius: 0.625rem;
		box-shadow: var(--shadow-md, 0 4px 6px -1px rgb(0 0 0 / 0.1));
		outline: 1px solid var(--gray-100); outline-offset: -1px;
	}
	@media (min-width: 1100px) { .toc-mobile { display: none; } }
	.toc-mobile summary {
		display: flex; align-items: center; justify-content: space-between; gap: 0.5rem;
		padding: 0.625rem 1rem; cursor: pointer;
		font-size: 0.875rem; font-weight: 600; color: var(--gray-700);
		list-style: none; -webkit-tap-highlight-color: transparent;
	}
	.toc-mobile summary::-webkit-details-marker { display: none; }
	.toc-mobile summary span {
		overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0;
	}
	:global(.toc-mobile-chevron) { flex-shrink: 0; transition: transform 0.15s; }
	.toc-mobile[open] :global(.toc-mobile-chevron) { transform: rotate(180deg); }
	.toc-mobile ol {
		margin: 0; padding: 0.25rem 1rem 0.75rem 2.25rem;
		display: flex; flex-direction: column; gap: 0.375rem;
		max-height: 60vh; overflow-y: auto;
	}
	.toc-mobile li { font-size: 0.8125rem; color: var(--gray-500); }
	.toc-mobile a { color: var(--gray-600); text-decoration: none; }
	.toc-mobile a.active { color: var(--brand-700, #1d4ed8); font-weight: 600; }

	.page-intro { margin-bottom: 2rem; max-width: 48rem; color: var(--gray-600); line-height: 1.65; }
	.section { margin-bottom: 3.5rem; }
	.section-sm { margin-top: 1rem; margin-bottom: 1rem; }

	/* Umlagen-KPIs: drei gleich breite Karten über die volle Contentbreite
	   (das globale .kpi-grid ist auf 4 Spalten ausgelegt und staucht 3 Karten) */
	.umlagen-grid { display: grid; gap: 1rem; grid-template-columns: 1fr; width: 100%; }
	@media (min-width: 640px) { .umlagen-grid { grid-template-columns: repeat(3, 1fr); } }
	.section-desc { font-size: 0.875rem; color: var(--gray-500); margin-bottom: 1rem; max-width: 48rem; }

	/* Antwort-Lead: der eine Satz, der die Frage beantwortet */
	.answer-lead {
		font-weight: 400; line-height: 1.55; color: var(--gray-900);
		max-width: 48rem; margin: 0 0 1rem;
	}
	.answer-lead a { color: var(--brand-600, #2563eb); text-decoration: underline; text-underline-offset: 2px; }

	.explainer-prose {
		font-size: 0.9375rem; line-height: 1.7; color: var(--gray-700);
		max-width: 48rem; margin: 1rem 0 0;
	}
	.explainer-prose a { color: var(--brand-600, #2563eb); text-decoration: underline; text-underline-offset: 2px; }

	/* Inhaltsverzeichnis (Desktop-Sidebar) */
	.toc {
		padding: 1rem 1.25rem;
		background: white; border-radius: 0.75rem;
		box-shadow: var(--shadow-sm);
		outline: 1px solid var(--gray-100); outline-offset: -1px;
		max-height: calc(100vh - 3rem); overflow-y: auto;
	}
	.toc-title {
		font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
		letter-spacing: 0.05em; color: var(--gray-400); margin: 0 0 0.5rem;
	}
	.toc ol { margin: 0; padding-left: 1.25rem; display: flex; flex-direction: column; gap: 0.375rem; }
	.toc li { font-size: 0.8125rem; color: var(--gray-500); }
	.toc a { color: var(--gray-600); text-decoration: none; }
	.toc a:hover { text-decoration: underline; text-underline-offset: 2px; }
	.toc a.active { color: var(--brand-700, #1d4ed8); font-weight: 600; }

	/* Zitat der kursierenden Rechnung */
	.claim {
		margin: 0 0 1rem; padding: 1rem 1.25rem; max-width: 48rem;
		border-left: 3px solid var(--amber-400, #fbbf24);
		background: var(--amber-50, #fffbeb); border-radius: 0 0.5rem 0.5rem 0;
		font-size: 1rem; font-style: italic; color: var(--gray-700); line-height: 1.6;
	}

	.chart-note { margin-top: 0.5rem; font-size: 0.75rem; color: var(--gray-400); max-width: 48rem; }
	.chart-note a { color: var(--brand-500); text-decoration: underline; text-underline-offset: 2px; }

	/* Emphasis chart: alle Kommunen grau, Rödermark in Akzentfarbe, Werte nur an
	   den Story-Polen (Rödermark + Extremwert) – Details trägt die Tabelle.
	   Alle Tracks sind exakt gleich breit (Label fix, Track füllt den Rest);
	   die Wertlabels liegen absolut IM Track und beeinflussen das Layout nicht:
	   bei langen Balken (>30 %) rechtsbündig im Balken, bei kurzen dahinter. */
	.emph-chart { display: flex; flex-direction: column; gap: 2px; }
	.emph-row { display: flex; align-items: center; gap: 0.5rem; }
	.emph-label {
		flex: 0 0 9.5rem; min-width: 0;
		display: flex; align-items: baseline; justify-content: space-between; gap: 0.375rem;
		font-size: 0.75rem; color: var(--gray-500);
	}
	@media (min-width: 640px) { .emph-label { flex-basis: 12rem; } }
	.emph-label-name {
		min-width: 0;
		overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
	}
	.emph-label-hs {
		font-size: 0.6875rem; color: var(--gray-400);
		white-space: nowrap; font-variant-numeric: tabular-nums;
	}
	.emph-label-highlight { color: var(--brand-700, #1d4ed8); font-weight: 600; }
	.emph-label-highlight .emph-label-hs { color: var(--brand-600, #2563eb); }
	.emph-track {
		position: relative; flex: 1; height: 24px;
		background: var(--gray-50); border-radius: 4px; overflow: hidden;
	}
	.emph-fill {
		height: 100%; background: var(--gray-300);
		border-radius: 0 4px 4px 0; transition: width 0.3s ease;
	}
	.emph-fill-highlight { background: var(--brand-500, #3b82f6); }
	.emph-value {
		position: absolute; top: 50%; transform: translateY(-50%);
		font-size: 0.8125rem; font-weight: 500; color: var(--gray-500);
		white-space: nowrap; font-variant-numeric: tabular-nums;
		pointer-events: none;
	}
	.emph-value-highlight { font-weight: 700; color: var(--brand-700, #1d4ed8); }
	.emph-value-inside { transform: translate(-100%, -50%); color: var(--gray-600); font-weight: 600; }
	.emph-value-inside.emph-value-highlight { color: white; }
	/* Werte ohne Dauer-Label erscheinen erst beim Hover über den Balken */
	.emph-value-hover { opacity: 0; transition: opacity 0.12s ease; }
	.emph-track:hover .emph-value-hover { opacity: 1; }
	.status-geplant { font-weight: 600; color: var(--amber-600, #d97706); }

	/* Steuermix: gestapelte Balken (Segmente mit 2px Weißraum getrennt),
	   Gesamtwert absolut positioniert wie beim Emphasis-Chart. */
	.mix-legend {
		display: flex; flex-wrap: wrap; gap: 0.375rem 1.25rem;
		margin-bottom: 0.875rem; font-size: 0.75rem; color: var(--gray-600);
	}
	.mix-legend-item { display: inline-flex; align-items: center; gap: 0.375rem; }
	.mix-swatch { width: 0.75rem; height: 0.75rem; border-radius: 0.1875rem; flex-shrink: 0; }
	.mix-chart { display: flex; flex-direction: column; gap: 2px; }
	.mix-row { display: flex; align-items: center; gap: 0.5rem; }
	.mix-label {
		flex: 0 0 6.5rem; min-width: 0;
		font-size: 0.75rem; color: var(--gray-500);
		overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
	}
	@media (min-width: 640px) { .mix-label { flex-basis: 8rem; font-size: 0.8125rem; } }
	.mix-label-highlight { color: var(--brand-700, #1d4ed8); font-weight: 600; }
	.mix-track {
		position: relative; flex: 1; height: 24px; min-width: 0;
		display: flex; gap: 2px;
		border-radius: 4px; overflow: hidden;
	}
	.mix-seg { height: 100%; flex-shrink: 0; }
	.mix-track-leer {
		border: 1px dashed var(--gray-200); overflow: hidden;
		align-items: center; padding: 0 0.5rem;
		font-size: 0.6875rem; font-style: italic; color: var(--gray-400);
		white-space: nowrap; text-overflow: ellipsis; display: block; line-height: 22px;
	}
	.mix-total {
		flex: 0 0 4.5rem; text-align: right;
		font-size: 0.8125rem; color: var(--gray-600);
		white-space: nowrap; font-variant-numeric: tabular-nums;
	}
	.mix-total-highlight { color: var(--brand-700, #1d4ed8); font-weight: 700; }
	.mix-total-leer { color: var(--gray-300); }

	/* Vertical bar chart (Hebesatz-Historie) */
	.vbar-chart { display: flex; align-items: flex-end; gap: 0.125rem; overflow-x: auto; padding-bottom: 0.25rem; }
	.vbar-col { display: flex; flex-direction: column; align-items: center; flex: 1 1 0; min-width: 2rem; }
	.vbar-label { font-size: 0.625rem; font-weight: 600; color: var(--gray-500); margin-bottom: 0.125rem; white-space: nowrap; }
	.vbar-label-up { color: var(--red-600, #dc2626); }
	.vbar-label-down { color: var(--green-600, #16a34a); }
	.vbar-delta { font-size: 0.5625rem; font-weight: 600; margin-bottom: 0.125rem; white-space: nowrap; }
	.vbar-delta-up { color: var(--red-500, #ef4444); }
	.vbar-delta-down { color: var(--green-500, #22c55e); }
	.vbar-track { width: 100%; height: 8rem; background: var(--gray-50); border-radius: 0.25rem 0.25rem 0 0; display: flex; align-items: flex-end; }
	.vbar-fill { width: 100%; background: var(--brand-400, #60a5fa); border-radius: 0.25rem 0.25rem 0 0; transition: height 0.3s ease; min-height: 2px; }
	.vbar-fill-up { background: var(--red-400, #f87171); }
	.vbar-fill-down { background: var(--green-400, #4ade80); }
	.vbar-year { font-size: 0.625rem; color: var(--gray-400); margin-top: 0.25rem; white-space: nowrap; }

	/* Link boxes (HSK, Rechner) */
	.link-box {
		display: flex; align-items: center; gap: 1rem; margin-top: 1.25rem; margin-bottom: 0.5rem;
		padding: 1rem 1.25rem; border-radius: 0.625rem;
		background: var(--brand-50, #eff6ff); border: 1px solid var(--brand-200, #bfdbfe);
		color: var(--gray-700); text-decoration: none; font-size: 0.9rem; line-height: 1.5;
		transition: background 0.15s, border-color 0.15s;
	}
	.link-box:hover { background: var(--brand-100, #dbeafe); border-color: var(--brand-300, #93c5fd); }
	:global(.link-box-icon) { flex-shrink: 0; width: 1.75rem; height: 1.75rem; color: var(--brand-700); }
	.link-box-body strong { color: var(--gray-900); display: block; }
	:global(.link-box-arrow) { flex-shrink: 0; width: 1.25rem; height: 1.25rem; color: var(--brand-700); transition: transform 0.15s; }
	.link-box:hover :global(.link-box-arrow) { transform: translateX(3px); }

	/* Quellenliste */
	.src-list { display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.8125rem; color: var(--gray-600); line-height: 1.5; padding: 0; }
	.src-list a { color: var(--brand-600, #2563eb); text-decoration: underline; text-underline-offset: 2px; }
</style>
