<script lang="ts">
	import type { PageData } from './$types';
	import type { SourceLink, HskMassnahme, HskSaeule, TimeSeriesPoint } from '$lib/types';
	import type { CategorySlice } from '$lib/data';
	import { formatAmount, formatMio } from '$lib/format';
	import SourceCitation from '$lib/components/SourceCitation.svelte';
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';
	import SocialMeta from '$lib/components/SocialMeta.svelte';
	import InfoPopover from '$lib/components/InfoPopover.svelte';
	import DonutChart from '$lib/components/DonutChart.svelte';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import { ShieldCheck, TrendingUp, TrendingDown, Scissors, Landmark, ChevronDown } from '@lucide/svelte';
	import { SvelteSet } from 'svelte/reactivity';

	let { data }: { data: PageData } = $props();

	const hsk = $derived(data.hsk);
	const docMap = $derived(new Map(data.documents.map((d) => [d.document_id, d])));

	const HSK_LABEL = 'HSK 2026';

	function measureLinks(page: number | null): SourceLink[] {
		if (!hsk) return [];
		const doc = docMap.get(hsk.source_document);
		if (!doc?.filename) return [];
		const base = `/pdfs/${doc.filename}`;
		const href = page ? `${base}#page=${page}` : base;
		const label = page ? `${HSK_LABEL}, S.\u00a0${page}` : HSK_LABEL;
		return [{ label, href, document_id: hsk.source_document, page }];
	}

	/** Effect on the budget: negative summe = relief → show as positive. */
	function wirkung(summe: number | null): number {
		return -(summe ?? 0);
	}
	function fmtSigned(v: number): string {
		return (v > 0 ? '+' : '') + formatAmount(v);
	}
	/** A single year cell: empty/zero years show a muted dash. */
	function fmtCell(raw: number | null | undefined): string {
		if (!raw) return '–';
		return fmtSigned(wirkung(raw));
	}

	const years = $derived.by(() => {
		const [start, end] = hsk?.laufzeit ?? [2026, 2030];
		return Array.from({ length: end - start + 1 }, (_, i) => start + i);
	});

	/** Investment line: show the raw value (negative = cut/shift), no sign flip. */
	function fmtInvest(raw: number | null | undefined): string {
		if (!raw) return '–';
		return (raw > 0 ? '+' : '') + formatAmount(raw);
	}
	let investOpen = $state(false);
	const investYears = $derived.by(() => {
		const keys = new Set<number>();
		for (const inv of hsk?.investitionen ?? []) {
			for (const y of Object.keys(inv.werte)) keys.add(Number(y));
		}
		return [...keys].sort((a, b) => a - b);
	});
	const investitionenSorted = $derived(
		[...(hsk?.investitionen ?? [])].sort((a, b) => (a.summe ?? 0) - (b.summe ?? 0))
	);

	// Abbaupfad als Jahresergebnis-Serie für TimeSeriesChart (Balken). ergebnis_nach_hsk
	// ist positiv = Fehlbetrag; wir drehen das Vorzeichen auf die Jahresergebnis-
	// Konvention (Überschuss = positiv/grün, Defizit = negativ/rot) wie auf der Startseite.
	const abbaupfadSeries: TimeSeriesPoint[] = $derived(
		(hsk?.abbaupfad ?? []).map((r) => ({
			year: r.year,
			amount_type: 'plan',
			amount: -(r.ergebnis_nach_hsk ?? 0),
			label: 'Ergebnis nach HSK',
			document_id: hsk?.source_document ?? '',
			page: r.page
		}))
	);

	// Wegfallende Investitionen thematisch nach Fachbereich gruppieren (Donut).
	const FB_DONUT: Record<string, { short: string; color: string }> = {
		'Kinder, Jugend, Schule & Soziales': { short: 'Kinder & Jugend', color: '#dc2626' },
		'Öffentliche Ordnung & Sicherheit': { short: 'Ordnung & Sicherheit', color: '#ea580c' },
		'Stadtentwicklung, Umwelt & Klima': { short: 'Umwelt & Klima', color: '#059669' },
		'Kultur, Sport & Bäder': { short: 'Kultur & Bäder', color: '#7c3aed' },
		'Zentrale Steuerung & Verwaltung': { short: 'Verwaltung', color: '#6b7280' }
	};
	const investSlices = $derived.by<CategorySlice[]>(() => {
		const sums = new Map<string, number>();
		for (const inv of hsk?.investitionen ?? []) {
			sums.set(inv.fb_label, (sums.get(inv.fb_label) ?? 0) + (inv.summe ?? 0));
		}
		const entries = [...sums.entries()]
			.map(([fb, net]) => ({ fb, amount: Math.abs(net) }))
			.filter((e) => e.amount > 0)
			.sort((a, b) => b.amount - a.amount);
		const total = entries.reduce((s, e) => s + e.amount, 0) || 1;
		return entries.map(({ fb, amount }) => {
			const meta = FB_DONUT[fb] ?? { short: fb, color: '#9ca3af' };
			return {
				category: {
					nr: fb,
					label: fb,
					shortLabel: meta.short,
					side: 'ausgaben' as const,
					color: meta.color,
					description: fb
				},
				amount,
				percent: amount / total
			};
		});
	});

	function fmtPct(p: number): string {
		return p.toLocaleString('de-DE') + ' %';
	}

	// Grundsteuer-B-Hebesatz. 990 % (aktuell) und 1.327 % (Schritt 1) sind
	// externe Vorgaben (nicht im HSK-PDF). Den Hebesatz der zweiten Stufe ab
	// 2028 leiten wir aus den Jahres-Mehreinnahmen ab: die Grundsteuer ist
	// linear im Hebesatz (Steuer = Messbetrag × Hebesatz), also gilt bei
	// gleichbleibendem Messbetrag €/Punkt(Schritt 1) = €/Punkt(Schritt 2).
	const GRST_B_AKTUELL = 990;
	const GRST_B_SCHRITT_1 = 1327;
	/**
	 * Hebesatz je Jahr für die Grundsteuer-B-Zeile, aber nur in den Jahren
	 * eingetragen, in denen er sich ändert. Schritt 1 (1.327 %) ist gegeben;
	 * spätere Stufen werden aus der jährlichen Mehreinnahme abgeleitet
	 * (Steuer linear im Hebesatz, gleichbleibender Messbetrag) und als
	 * Näherung markiert.
	 */
	const grstBSteps = $derived.by(() => {
		const map = new Map<number, { hs: number; derived: boolean }>();
		const m = hsk?.massnahmen.find((x) => x.is_grundsteuer_b);
		if (!m) return map;
		const e1 = years.map((y) => Math.abs(m.werte[String(y)] ?? 0)).find((v) => v > 0) ?? 0;
		if (!e1) return map;
		const proPunkt = e1 / (GRST_B_SCHRITT_1 - GRST_B_AKTUELL);
		let prev = GRST_B_AKTUELL;
		for (const y of years) {
			const v = Math.abs(m.werte[String(y)] ?? 0);
			if (!v) continue;
			const hs = Math.round(GRST_B_AKTUELL + v / proPunkt);
			if (hs !== prev) {
				map.set(y, { hs, derived: hs !== GRST_B_SCHRITT_1 });
				prev = hs;
			}
		}
		return map;
	});
	const grstBDerived = $derived([...grstBSteps.values()].some((s) => s.derived));

	// Gewerbesteuer und die beiden von ihr abhängigen Umlagen. Höhere
	// Gewerbesteuer-Einnahmen erhöhen die Bemessungsgrundlage der Umlagen,
	// daher zahlt die Stadt im selben Jahr mehr Gewerbesteuer- und
	// Heimatumlage. Wir halten die drei Zeilen zusammen und erklären sie.
	const GEWERBE_LEAD = 'Gewerbesteuer';
	const GEWERBE_UMLAGEN = ['Gewerbesteuerumlage', 'Heimatumlage'];

	// Kurzerklärungen für erklärungsbedürftige Maßnahmen-Begriffe. Schlüssel =
	// exakter Maßnahmen-Name; erscheint als Info-Popover neben dem Namen.
	const GLOSSAR: Record<string, string> = {
		Spielapparatesteuer:
			'Kommunale Steuer auf Geld- und Unterhaltungsspielgeräte – etwa Automaten in ' +
			'Spielhallen und Gaststätten. Sie gehört zu den örtlichen Aufwand- bzw. ' +
			'Vergnügungssteuern, deren Höhe die Stadt selbst festlegt.',
		'Grundsteuer A von 175% auf 900%':
			'Die Grundsteuer A betrifft nur land- und forstwirtschaftliche Grundstücke – nicht ' +
			'Wohn- oder Geschäftsgrundstücke (das ist die Grundsteuer B). Sie wird auf den ' +
			'vergleichsweise niedrigen Ertragswert der Flächen berechnet, nicht auf den Marktwert. ' +
			'Deshalb bringt die Anhebung trotz der prozentual großen Zahl insgesamt nur rund ' +
			'27.000 € mehr pro Jahr – für die gesamte Stadt, nicht je Betrieb.',
		'Verwaltungsgebühren Verkehr':
			'Gebühren, die die Stadt für Amtshandlungen rund um die Verkehrsüberwachung erhebt – ' +
			'etwa die Bearbeitungsgebühr, die bei einem Verwarnungs- oder Bußgeldbescheid ' +
			'zusätzlich zum Bußgeld anfällt. Das Geld fließt an die Stadt; höhere Gebühren ' +
			'bedeuten daher Mehreinnahmen.',
		'Benutzungsgebühren um 20 % erhöhen':
			'Benutzungsgebühren sind Entgelte für die Nutzung städtischer Einrichtungen im ' +
			'Bereich Kultur, Sport & Bäder (z. B. Eintritte oder Nutzungsentgelte). Das HSK sieht ' +
			'hier pauschal eine Erhöhung um 20 % ab 2027 vor, schlüsselt aber nicht auf, welche ' +
			'Einrichtungen konkret betroffen sind.',
		'Mühlengrund 17 Reduzierung Erträge':
			'Mühlengrund 17 (Stadtteil Urberach) ist ein städtisches Objekt; an der Adresse ist die ' +
			'Seniorenhilfe Rödermark e.V. ansässig. Die Stadt verkauft das Objekt: Der laufende ' +
			'Betrieb entfällt (sie spart den Sachaufwand, eigene Zeile) und es fließt ein einmaliger ' +
			'Verkaufserlös (im HSK gesondert aufgeführt). Zugleich fallen die bisherigen laufenden ' +
			'Erträge weg – diese Zeile zeigt genau diesen Ertrags-Wegfall und steht deshalb mit ' +
			'Minus, obwohl sie unter „Erträge" läuft.',
		'Schulkindbetreuung Erträge':
			'„GIP" ist die Ganztagsbetreuung im Pakt gGmbH, eine Gesellschaft des Kreises Offenbach, ' +
			'die die Schulkindbetreuung kreisweit übernimmt („Pakt für den Nachmittag"). Rödermark ' +
			'gibt seine Schulkindbetreuung (bislang in eigener Hand, u. a. an der Trinkbornschule) ab ' +
			'2030 an den Kreis ab: Die Stadt spart die Betreuungskosten, zahlt aber an den Kreis – und ' +
			'die bisherigen Elternbeiträge fallen bei der Stadt weg. Diese Zeile zeigt genau diesen ' +
			'Ertrags-Wegfall, deshalb steht sie mit Minus.',
		'Schulkindbetreuung Aufwand':
			'Teil der Übergabe der Schulkindbetreuung an den Kreis Offenbach (GIP = Ganztagsbetreuung ' +
			'im Pakt gGmbH, eine Gesellschaft des Kreises). Weil Rödermark die Nachmittagsbetreuung ab ' +
			'2030 nicht mehr selbst betreibt, entfallen die laufenden Betreuungskosten – das ist die ' +
			'größte Entlastung des Blocks. Im Gegenzug zahlt die Stadt an den Kreis (Zeile ' +
			'„Schulkindbetreuung – Zahlung an den Kreis") und verliert die Elternbeiträge (Zeile ' +
			'„Schulkindbetreuung Erträge").',
		'Schulkindbetreuung an Kreis (GIP)':
			'Teil der Übergabe der Schulkindbetreuung an den Kreis Offenbach. „GIP" ist die ' +
			'Ganztagsbetreuung im Pakt gGmbH, eine Gesellschaft des Kreises, die die Betreuung ' +
			'übernimmt. Diese Zeile ist die Zahlung, die Rödermark ab 2030 dafür an den Kreis leistet ' +
			'– also eine Belastung. Im Gegenzug spart die Stadt die Betreuungskosten (Zeile ' +
			'„Schulkindbetreuung Aufwand"); die Elternbeiträge fallen bei der Stadt weg (Zeile ' +
			'„Schulkindbetreuung Erträge").',
		'Mühlengrund 17 Reduzierung Sachaufwand':
			'Gehört zum Verkauf des städtischen Objekts Mühlengrund 17 (Urberach). Mit der Aufgabe ' +
			'des Objekts entfallen die laufenden Betriebskosten – das ist diese Einsparung. Im ' +
			'Gegenzug fallen die laufenden Erträge weg (Zeile „Mühlengrund 17 Reduzierung Erträge") ' +
			'und es fließt ein einmaliger Verkaufserlös.',
		'Kita Erträge (weniger Kinder)':
			'Teil des „weniger Kinder"-Blocks: Das HSK rechnet ab 2029 mit deutlich weniger Kindern ' +
			'in der Betreuung. Dadurch sinken die Einnahmen aus der Kinderbetreuung (z. B. ' +
			'Elternbeiträge und kindbezogene Zuweisungen) – das ist diese Zeile, deshalb mit Minus. ' +
			'Zugehörig: weniger Kita-Personal (Zeile „Weniger Kita-Personalkosten (weniger Kinder)") und ' +
			'weniger Zuschüsse an freie Träger (Zeile „Zuschüsse freie Träger (weniger Kinder)"), ' +
			'beides Einsparungen. Wie viele Kinder weniger angenommen werden, weist das HSK nicht aus.',
		'Reduzierung PK Kitas (weniger Kinder)':
			'Teil des „weniger Kinder"-Blocks: Bei ab 2029 angenommenen sinkenden Kinderzahlen ist ' +
			'weniger Kita-Personal nötig, dadurch sinken die Personalkosten (PK) – das ist diese ' +
			'Einsparung. Zugehörig: wegfallende Einnahmen (Zeile „Kita Erträge (weniger Kinder)") und ' +
			'weniger Zuschüsse an freie Träger (Zeile „Zuschüsse freie Träger (weniger Kinder)"). ' +
			'Wie viele Kinder weniger angenommen werden, weist das HSK nicht aus.',
		'Zuschüsse freie Träger (weniger Kinder)':
			'Teil des „weniger Kinder"-Blocks: Bei ab 2030 angenommenen sinkenden Kinderzahlen zahlt ' +
			'die Stadt weniger Zuschüsse an freie Kita-Träger – das ist diese Einsparung. Zugehörig: ' +
			'weniger eigenes Kita-Personal (Zeile „Weniger Kita-Personalkosten (weniger Kinder)") und ' +
			'wegfallende Einnahmen (Zeile „Kita Erträge (weniger Kinder)"). Wie viele Kinder weniger ' +
			'angenommen werden, weist das HSK nicht aus.',
		'Pauschale Reduzierung/PK Kitas wg. Fachkräftemangel':
			'Die Stadt geht davon aus, dass sie wegen des ' +
			'Fachkräftemangels nicht alle Kita-Stellen besetzen kann, und veranschlagt das dadurch ' +
			'nicht ausgegebene Personalgeld als Einsparung – pauschal rund 1 Mio. € pro Jahr (in ' +
			'Summe −5,3 Mio.). Das HSK nennt diesen Ansatz auf Seite 8 ausdrücklich. „Pauschal" ' +
			'heißt: ein Sammelansatz ohne benannte Stellen; wie der Betrag hergeleitet wird, zeigt ' +
			'das HSK nicht. Anders als andere Personalmaßnahmen ist es eine Einsparung durch eine ' +
			'Personallücke – die Kehrseite ist eine geringere Kita-Besetzung.',
		'2 Stellen Steuerverwaltung (Sozialstaffel Gebühren Kitas)':
			'Eine Personalmaßnahme im Fachbereich Finanzen & Steuerverwaltung: Eingespart werden die ' +
			'Kosten von zwei Stellen (rund 134.000 € pro Jahr, jährlich ~3 % steigend). Die Klammer ' +
			'nennt die Aufgabe dieser Stellen – die „Sozialstaffel" der Kita-Gebühren, also die ' +
			'einkommensabhängige Staffelung, bei der Familien mit geringerem Einkommen weniger zahlen; ' +
			'deren Bearbeitung erfordert Personal. Das HSK nennt nur die Einsparung, nicht ' +
			'ausdrücklich, ob die Stellen gestrichen, nicht besetzt oder gar nicht erst geschaffen ' +
			'werden.',
		'1 Stelle FD 1.2':
			'Wegfall einer Stelle im Fachdienst 1.2 (Zentrale Steuerung & Verwaltung). 2026 wirkt nur ' +
			'ein Teiljahr (rund 50.000 € ≈ halbe Jahreskosten), ab 2027 die volle Jahreseinsparung ' +
			'(~103.000 €, danach ~3 % Tarifsteigerung pro Jahr). Das Muster passt zu einer Stelle, die ' +
			'etwa zur Jahresmitte 2026 wegfällt; den genauen Grund und Zeitpunkt (z. B. Austritt) ' +
			'nennt das HSK nicht.',
		'Erstmals angemeldete IT-Schulungen':
			'Das ist eine Einsparung, keine Einnahme. „Erstmals angemeldet" heißt: Die Fachbereiche ' +
			'hatten für IT-Schulungen erstmals Geld im Haushaltsentwurf angemeldet (~98.500 € pro ' +
			'Jahr, quer über alle Bereiche). Das Haushaltssicherungskonzept streicht diese neu ' +
			'angemeldeten Schulungen wieder – die Stadt gibt das Geld also nicht aus, das entlastet ' +
			'den Haushalt.',
		'Kommunale Wärmeplanung':
			'Eine Einsparung – obwohl eine Wärmeplanung Geld kostet. Die Stadt reduziert das Budget, ' +
			'das sie für die kommunale Wärmeplanung vorgesehen hatte (rund 20.000 € pro Jahr ab 2026). ' +
			'Diese Zeile streicht also einen Teil dieser eingeplanten Kosten wieder. Ob die Planung ' +
			'dadurch kleiner ausfällt oder die Kosten anderweitig (z. B. über Förderung) gedeckt ' +
			'werden, sagt das HSK nicht.',
		'Kosten Präsenz im Internet':
			'Kosten für den Internetauftritt der Stadt (Website, Online-Präsenz), pauschal um rund ' +
			'25.000 € pro Jahr ab 2027 gekürzt. Auffällig: Genau derselbe Betrag steht auch bei ' +
			'„Verbrauchsmaterial" und „Büromaterial/Drucksachen" – es ist also eine einheitliche, ' +
			'pauschale Kürzung quer über alle Fachbereiche, nicht im Detail aufgeschlüsselt.',
		'Aufwand für den Betrieb':
			'Eine pauschale Querschnitts-Kürzung über alle Fachbereiche (~15.150 € pro Jahr ab 2027). ' +
			'„Aufwand für den Betrieb" ist eine allgemeine Sachkosten-Position (laufende betriebliche ' +
			'Aufwendungen); das HSK schlüsselt nicht auf, was konkret darunterfällt. Sie gehört zum ' +
			'selben Block pauschaler Sachkosten-Kürzungen wie Honorare, Büromaterial oder ' +
			'Fachliteratur.',
		'Jägerhaus (Sachaufwand)':
			'Das Jägerhaus ist ein markantes historisches Gebäude am Rathausplatz in Ober-Roden. Die ' +
			'Stadt will es abgeben (Konzept „Jägerhaus 2.0", Gastronomie im Erdgeschoss bleibt ' +
			'Auflage). Diese Zeile ist die Einsparung beim laufenden Sachaufwand des Objekts; ein ' +
			'Verkaufserlös ist im HSK separat aufgeführt.',
		'Schasser (Sachaufwand)':
			'Der „Schasser" ist ein historisches städtisches Gebäude in Urberach (ortsüblicher Name, ' +
			'früherer Schützenhof). Die Stadt gibt das Objekt ab (Verkauf im HSK separat aufgeführt). ' +
			'Diese Zeile ist die Einsparung beim laufenden Sachaufwand.',
		'Bachgasse (Sachaufwand)':
			'Eine städtische Liegenschaft in der Bachgasse (gleiches Produkt wie Mühlengrund 17 und ' +
			'Schasser). Diese Zeile senkt den laufenden Sachaufwand des Objekts. Um welches Gebäude ' +
			'genau es geht, ist im HSK nicht näher bezeichnet.',
		'Kiga Taubhaus':
			'Die städtische Kindertagesstätte „Im Taubhaus" in Urberach (rund 100 Kinder, vier ' +
			'Gruppen). Diese Zeile senkt den laufenden Sachaufwand der Einrichtung. Zusätzlich wird ' +
			'die geplante Sanierung/der Neubau der Kita im HSK zurückgestellt (−5 Mio. €, siehe ' +
			'Investitionsliste).'
	};

	// Lesbare Anzeige-Namen für Maßnahmen mit kryptischen Kürzeln. Schlüssel =
	// HSK-Originalname (so wie er in der Quelle steht), Wert = ausgeschriebene
	// Fassung für die Liste. Der Originalname bleibt als Hover-Titel erhalten.
	// NN = unbesetzte Stelle, PK = Personalkosten, OPo = Ordnungspolizei,
	// FBL = Fachbereichsleitung, EG = Entgeltgruppe, AfA = Abschreibung.
	const LABELS: Record<string, string> = {
		'DV-Benutzerentgelte': 'Weniger IT-Nutzungsentgelte (Datenverarbeitung)',
		'Wartung EDV-Anlage': 'Weniger Wartung der IT-Anlage',
		'Rechts-u. Beratungskosten (DMS)':
			'Weniger Rechts- und Beratungskosten (Dokumentenmanagementsystem)',
		'1 Stelle FD 1.2': '1 Stelle (Fachdienst 1.2)',
		'Opo 1': 'Ordnungspolizei (1)',
		'OPo 4': 'Ordnungspolizei (4)',
		'NN OPo 2': 'Unbesetzte Stelle Ordnungspolizei (2)',
		'NN OPo 3': 'Unbesetzte Stelle Ordnungspolizei (3)',
		'NN Illegale Ablagerungen': 'Unbesetzte Stelle (illegale Müllablagerungen)',
		'NN Bürgerbüro': 'Unbesetzte Stelle Bürgerbüro',
		'2 NN Friedhofsgärtner': '2 unbesetzte Stellen Friedhofsgärtner',
		'NN Bäderbetrieb (EG5)': 'Unbesetzte Stelle Bäderbetrieb (Entgeltgruppe 5)',
		'1 NN Azubi Badehaus': 'Unbesetzte Ausbildungsstelle Badehaus',
		'1 NN Stelle für technischer Badehausleiter entfällt':
			'Unbesetzte Stelle technische Badehausleitung entfällt',
		'1 NN Stelle für technischer Badehausleiter (von EG 8 auf EG9a, NN Bade':
			'Unbesetzte Stelle technische Badehausleitung (von Entgeltgruppe 8 auf 9a)',
		'NN FBl 3 (bis 30.4.26)': 'Unbesetzte Fachbereichsleitung FB3 (bis 30.4.2026)',
		'FBl 5 1/2 Finanzierung (2026)': 'Fachbereichsleitung FB5 – halbe Finanzierung (2026)',
		'FBL 1/2 Jahr': 'Fachbereichsleitung – halbes Jahr',
		'FBL Differenz zur Planung': 'Fachbereichsleitung – Differenz zur Planung',
		'1 Stelle von EG8 nach EG7': '1 Stelle – Herabstufung von Entgeltgruppe 8 auf 7',
		'Pauschale Reduzierung/PK Kitas wg. Fachkräftemangel':
			'Pauschale Senkung der Kita-Personalkosten (Fachkräftemangel)',
		'PK durch Austritte': 'Personalkosten-Einsparung durch Austritte',
		'Reduzierung PK Kitas (weniger Kinder)': 'Weniger Kita-Personalkosten (weniger Kinder)',
		'Reduzierung AfA': 'Reduzierung der Abschreibungen',
		'Erstmals angemeldete IT-Schulungen': 'Verzicht auf neu angemeldete IT-Schulungen',
		'Aufwand für Fortbildung': 'Weniger Fortbildung',
		'Kommunale Wärmeplanung': 'Weniger Budget für Kommunale Wärmeplanung',
		'Kosten Präsenz im Internet': 'Weniger Kosten für den Internetauftritt',
		'Aufwand für Aus- und Weiterbildung': 'Weniger Aus- und Weiterbildung',
		'Aufw. Betriebswirtschaftliche Beratungen': 'Weniger betriebswirtschaftliche Beratungen',
		'Honoraraufwand': 'Weniger Honorare',
		'Aufwand für den Betrieb': 'Weniger laufender Betriebsaufwand',
		'sonstiger Materialaufwand': 'Weniger sonstiger Materialaufwand',
		'Verbrauchsmaterial': 'Weniger Verbrauchsmaterial',
		'Aufwend. für Büromaterial und Drucksachen reduzieren': 'Weniger Büromaterial und Drucksachen',
		'Planungen u. Gutachten': 'Weniger Planungen und Gutachten',
		'Zeitungen und Fachliteratur': 'Weniger Zeitungen und Fachliteratur',
		'Porto und Versand': 'Weniger Porto und Versand',
		'Printmedien': 'Weniger Printmedien',
		'Fortbildung Digitalisierung': 'Weniger Fortbildung (Digitalisierung)',
		'Wartung Verkehrsüberwachungsanlage': 'Weniger Wartung der Verkehrsüberwachungsanlage',
		'Bauliche Unterhaltung allgemein': 'Weniger bauliche Unterhaltung',
		'Schließdienst Halle Urb/Rathäuser/Tiefgarage/Kulturhalle/Kelter':
			'Weniger Schließdienst (Halle Urberach, Rathäuser, Tiefgarage, Kulturhalle, Kelter)',
		'Grabenpflege Gewässer': 'Weniger Grabenpflege an Gewässern',
		'Ordnungsamt (Gebäudekosten)': 'Weniger Gebäudekosten Ordnungsamt',
		'Brückensanierung': 'Weniger Brückensanierung',
		'Kiga Taubhaus': 'Kita Im Taubhaus (Sachaufwand)',
		'Schulkindbetreuung an Kreis (GIP)': 'Schulkindbetreuung – Zahlung an den Kreis',
		'Eine Stelle FB Finanzen wird nicht neu besetzt; Ende 09/2028':
			'Eine Stelle Fachbereich Finanzen wird nicht neu besetzt (Ende 09/2028)',
		// Investitionsnamen
		'Erweiterung, Um- u. Ausbau Friedhof Ober-Roden':
			'Erweiterung, Um- und Ausbau Friedhof Ober-Roden',
		'Bewegl. Anlagevermögen Feuerwehr Ober-Roden':
			'Bewegliches Anlagevermögen Feuerwehr Ober-Roden',
		'Anschaffung v. Fahrzeugen Feuerwehr Ober-Roden':
			'Anschaffung von Fahrzeugen Feuerwehr Ober-Roden',
		'Bewegl. Anlagevermögen Feuerwehr Urberach': 'Bewegliches Anlagevermögen Feuerwehr Urberach',
		'Anschaffung v. Fahrzeugen Feuerwehr Urberach':
			'Anschaffung von Fahrzeugen Feuerwehr Urberach',
		'Bewegl. Anlagevermögen Kita V Im Taubhaus': 'Bewegliches Anlagevermögen Kita V Im Taubhaus',
		'Außengelände JUZ Ober-Roden': 'Außengelände Jugendzentrum Ober-Roden',
		'Bewegl. Anlagevermögen JUZ ORo': 'Bewegliches Anlagevermögen Jugendzentrum Ober-Roden',
		'ISEK - Alte Wache': 'Alte Wache (Integriertes Städtebauliches Entwicklungskonzept)',
		'Maßnahmen z. Erhaltung der Funktionalität Badehaus':
			'Maßnahmen zur Erhaltung der Funktionalität Badehaus',
		'Büroausstattung FB': 'Büroausstattung Fachbereiche',
		'Parkplatz Dieburger Str 29/31': 'Parkplatz Dieburger Straße 29/31',
		'Erricht., Um- u. Ausbau Jugendpl./Freizeitanlagen':
			'Errichtung, Um- und Ausbau Jugendplätze/Freizeitanlagen',
		'Förderung umweltfr. Maßnahmen an Gebäuden/Grundst.':
			'Förderung umweltfreundlicher Maßnahmen an Gebäuden/Grundstücken',
		'Naturschutzrechtliche Auslgeichsmaßnahmen': 'Naturschutzrechtliche Ausgleichsmaßnahmen'
	};
	function displayName(massnahme: string): string {
		return LABELS[massnahme] ?? massnahme;
	}

	/** Measures belonging to a pillar group, biggest contribution first. */
	function measuresOf(label: string): HskMassnahme[] {
		if (!hsk) return [];
		const list = hsk.massnahmen
			.filter((m) => m.gruppe_label === label)
			.sort((a, b) => (a.summe ?? 0) - (b.summe ?? 0));
		// Gewerbesteuer-Umlagen direkt hinter die Gewerbesteuer ziehen.
		if (!list.some((m) => m.massnahme === GEWERBE_LEAD)) return list;
		const linked = list.filter((m) => GEWERBE_UMLAGEN.includes(m.massnahme));
		if (!linked.length) return list;
		const rest = list.filter((m) => !GEWERBE_UMLAGEN.includes(m.massnahme));
		const at = rest.findIndex((m) => m.massnahme === GEWERBE_LEAD);
		rest.splice(at + 1, 0, ...linked);
		return rest;
	}

	/** The Gewerbesteuer block: gross gain, levy clawback, net effect. */
	const gewerbe = $derived.by(() => {
		if (!hsk) return null;
		const get = (name: string) => hsk.massnahmen.find((m) => m.massnahme === name) ?? null;
		const haupt = get(GEWERBE_LEAD);
		if (!haupt) return null;
		const umlagen = GEWERBE_UMLAGEN.map(get).filter((m): m is HskMassnahme => m !== null);
		if (!umlagen.length) return null;
		const brutto = haupt.summe ?? 0; // negativ = Mehreinnahme
		const rueck = umlagen.reduce((s, m) => s + (m.summe ?? 0), 0); // positiv = Belastung
		return { brutto, rueck, netto: brutto + rueck, anchor: umlagen[umlagen.length - 1].massnahme };
	});

	const expanded = new SvelteSet<string>();
	function toggle(label: string) {
		if (expanded.has(label)) expanded.delete(label);
		else expanded.add(label);
	}

	const n = $derived(hsk?.narrative ?? {});
	const k = $derived(hsk?.kennzahlen);
	const einnahmen: HskSaeule | undefined = $derived(hsk?.saeulen.einnahmen);
	const ausgaben: HskSaeule | undefined = $derived(hsk?.saeulen.ausgaben);

	const fullPdf = $derived.by(() => {
		if (!hsk) return null;
		const doc = docMap.get(hsk.source_document);
		return doc?.filename ? `/pdfs/${doc.filename}` : null;
	});
</script>

<SocialMeta
	title="Haushaltssicherungskonzept 2026"
	description="Wie Rödermark seinen Haushalt sanieren will: 97 Maßnahmen über 2026–2030 – wo die Stadt mehr einnimmt und wo sie spart, mit Quelle für jede Zahl."
	path="/hsk2026"
	image="share-default.jpg"
/>

<AnchorHeading level={2} id="haushaltssicherungskonzept-2026">
	<ShieldCheck /> Haushaltssicherungskonzept 2026
</AnchorHeading>

{#if !hsk || !einnahmen || !ausgaben}
	<p class="page-intro">Die Daten zum Haushaltssicherungskonzept konnten nicht geladen werden.</p>
{:else}
	<p class="page-intro">
		Rödermark plant 2026 mit einem Defizit von rund
		{formatMio(Number(n.defizit_entwurf_2026?.value ?? 0))} (Entwurf). Das
		Haushaltssicherungskonzept (HSK) bündelt {k?.anzahl_massnahmen} Maßnahmen, mit denen der
		Haushalt bis 2029 ausgeglichen und der aufgelaufene Fehlbetrag bis 2030 getilgt werden
		soll. Diese Seite zeigt, wo die Stadt dafür mehr einnimmt und wo sie spart – mit Quelle
		für jede Zahl.
	</p>

	<!-- ── Header summary ── -->
	<section class="kpi-grid section">
		<div class="kpi-card">
			<p class="kpi-label">Defizit 2026</p>
			<p class="kpi-value kpi-flow">
				{formatMio(Number(n.defizit_entwurf_2026?.value ?? 0))}
				<span class="kpi-arrow">→</span>
				<strong>{formatMio(Number(n.ordentliches_ergebnis_2026_nach_hsk?.value ?? 0))}</strong>
			</p>
			<p class="kpi-sub">ordentliches Ergebnis vor → nach HSK</p>
		</div>
		<div class="kpi-card">
			<p class="kpi-label">Volumen 2026–2030</p>
			<p class="kpi-value">{formatMio(Math.abs(k?.konsolidierung_mit_grundsteuer_b ?? 0))}</p>
			<p class="kpi-sub">{k?.anzahl_massnahmen} Maßnahmen zusammen</p>
		</div>
		<div class="kpi-card">
			<p class="kpi-label">Mehr Einnahmen</p>
			<p class="kpi-value" style="color: var(--color-income)">
				{formatMio(Math.abs(einnahmen.summe))}
			</p>
			<p class="kpi-sub">{einnahmen.anzahl} Maßnahmen</p>
		</div>
		<div class="kpi-card">
			<p class="kpi-label">Weniger Ausgaben</p>
			<p class="kpi-value" style="color: var(--color-income)">
				{formatMio(Math.abs(ausgaben.summe))}
			</p>
			<p class="kpi-sub">{ausgaben.anzahl} Maßnahmen</p>
		</div>
	</section>

	<p class="legend">
		Werte sind der Beitrag zum Haushalt über 2026–2030.
		<span class="num-pos">Positive Werte</span> entlasten den Haushalt,
		<span class="num-neg">negative</span> belasten ihn (z. B. wegbrechende Erträge).
	</p>

	{#snippet pillar(saeule: HskSaeule)}
		<div class="groups">
			{#each saeule.gruppen as g (g.label)}
				<div class="group">
					<button
						class="group-btn"
						aria-expanded={expanded.has(g.label)}
						onclick={() => toggle(g.label)}
					>
						<span class="group-label">{g.label}</span>
						<span class="group-meta">
							<span class="badge badge-gray">{g.anzahl}</span>
							<span class="group-sum" class:num-pos={g.summe < 0} class:num-neg={g.summe > 0}>
								{fmtSigned(wirkung(g.summe))}
							</span>
							<ChevronDown class="chevron" style={expanded.has(g.label) ? 'transform: rotate(180deg)' : ''} />
						</span>
					</button>
					{#if expanded.has(g.label)}
						<div class="measure-scroll">
							<table class="data-table measure-table">
								<thead>
									<tr>
										<th class="col-sticky col-sticky-last" style="left:0">Maßnahme</th>
										{#each years as y (y)}
											<th class="col-number">{y}</th>
										{/each}
										<th class="col-number col-total">Gesamt</th>
										<th class="col-source">Quelle</th>
									</tr>
								</thead>
								<tbody>
									{#each measuresOf(g.label) as m, i (`${m.fb}-${m.produkt ?? ''}-${m.massnahme}-${i}`)}
										<tr
											class:linked-row={gewerbe &&
												(m.massnahme === GEWERBE_LEAD || GEWERBE_UMLAGEN.includes(m.massnahme))}
											class:linked-sub={gewerbe && GEWERBE_UMLAGEN.includes(m.massnahme)}
										>
											<td class="col-sticky col-sticky-last m-cell" style="left:0">
												<span
													class="m-name"
													title={LABELS[m.massnahme]
														? `HSK-Originalbezeichnung: ${m.massnahme}`
														: null}
												>
													{displayName(m.massnahme)}
													{#if m.massnahme === GEWERBE_LEAD && gewerbe}
														<InfoPopover
															direction="down"
															maxWidth="22rem"
															label="Zusammenhang mit den Umlagen"
														>
															<p class="popover-text">
																<strong>Diese drei Zeilen hängen zusammen.</strong> Der höhere
																Gewerbesteuer-Hebesatz bringt ab 2030 rund {formatMio(
																	Math.abs(gewerbe.brutto)
																)} mehr Einnahmen.
															</p>
															<p class="popover-text">
																Höhere Gewerbesteuer erhöht zugleich die <strong
																	>Gewerbesteuerumlage</strong
																> (Abgabe an Bund und Land) und die <strong>Heimatumlage</strong>
																(hessische Umlage nach Steuerkraft), die die Stadt zahlt – zusammen
																{formatAmount(gewerbe.rueck)} mehr.
															</p>
															<p class="popover-text">
																Netto verbleiben rund <strong>{formatMio(Math.abs(gewerbe.netto))}</strong>.
															</p>
														</InfoPopover>
													{/if}
													{#if GLOSSAR[m.massnahme]}
														<InfoPopover direction="down" label="Was ist das?">
															<p class="popover-text">{GLOSSAR[m.massnahme]}</p>
														</InfoPopover>
													{/if}
												</span>
												<span class="m-fb">{m.fb_label}</span>
											</td>
											{#each years as y (y)}
												{@const raw = m.werte[String(y)]}
												{@const step = m.is_grundsteuer_b ? grstBSteps.get(y) : undefined}
												<td
													class="col-number"
													class:num-pos={(raw ?? 0) < 0}
													class:num-neg={(raw ?? 0) > 0}
												>
													{fmtCell(raw)}
													{#if step}
														<span class="cell-hebesatz" title="Grundsteuer-B-Hebesatz ab {y}">
															{step.derived ? '≈ ' : ''}{fmtPct(step.hs)}{#if step.derived}<sup>*</sup>{/if}
														</span>
													{/if}
												</td>
											{/each}
											<td
												class="col-number col-total"
												class:num-pos={(m.summe ?? 0) < 0}
												class:num-neg={(m.summe ?? 0) > 0}
											>
												{fmtSigned(wirkung(m.summe))}
											</td>
											<td class="col-source">
												<SourceCitation
													description="Haushaltssicherungskonzept 2026, Anlage 1"
													links={measureLinks(m.page)}
													condensed
												/>
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/snippet}

	<!-- ── Abbaupfad ── -->
	<section class="section">
		<AnchorHeading level={3} id="abbaupfad">
			<TrendingDown /> Abbaupfad: Ergebnis nach HSK
		</AnchorHeading>
		<p class="pillar-total">
			Auch nach allen {k?.anzahl_massnahmen} Maßnahmen bleibt 2026 ein Defizit von
			{formatMio(Number(n.ordentliches_ergebnis_2026_nach_hsk?.value ?? 0))}. Das ordentliche
			Ergebnis ist {n.ausgleich_ab_jahr?.text ?? 'ab 2029'} ausgeglichen, der aufgelaufene
			Fehlbetrag wird {n.altfehlbetrag_getilgt?.text ?? 'bis 2030'} getilgt.
		</p>
		<div class="card card-padded">
			<TimeSeriesChart
				title="Ordentliches Ergebnis nach HSK · positiv = Überschuss, negativ = Defizit"
				series={abbaupfadSeries}
				yLabel="Mio. €"
				chartType="bar"
				valueColoring
				planOnlyYears={years}
			/>
		</div>
		{#if fullPdf}
			<p class="invest-note">
				<SourceCitation
					description="Haushaltssicherungskonzept 2026, S. 11"
					links={measureLinks(11)}
					condensed
				/>
			</p>
		{/if}
	</section>

	<!-- ── Pillar A: more income ── -->
	<section class="section">
		<AnchorHeading level={3} id="mehr-einnehmen">
			<TrendingUp /> Wo die Stadt mehr einnimmt
		</AnchorHeading>
		<p class="pillar-total">
			Beitrag der Einnahmenseite:
			<strong class="num-pos">{fmtSigned(wirkung(einnahmen.summe))}</strong>
		</p>
		{@render pillar(einnahmen)}
	</section>

	<!-- ── Pillar B: savings ── -->
	<section class="section">
		<AnchorHeading level={3} id="wo-wir-sparen">
			<Scissors /> Wo die Stadt spart
		</AnchorHeading>
		<p class="pillar-total">
			Beitrag der Ausgabenseite:
			<strong class="num-pos">{fmtSigned(wirkung(ausgaben.summe))}</strong>
		</p>
		{@render pillar(ausgaben)}
	</section>

	<!-- ── Investitionen (separate dimension) ── -->
	<section class="section">
		<AnchorHeading level={3} id="investitionen">
			<Landmark /> Investitionen und neue Schulden
		</AnchorHeading>
		<div class="info-box info-box-blue">
			<p>
				Gekürzte Investitionen verbessern nicht direkt das laufende Ergebnis, sondern senken
				vor allem die neuen Schulden – die Investitionen wären über Kredite finanziert worden.
				Sie werden deshalb getrennt von den Einnahmen und Ausgaben oben ausgewiesen.
			</p>
			<p>
				Indirekt und zeitversetzt entlasten sie das laufende Ergebnis trotzdem: Weniger
				Investitionen bedeuten über die Folgejahre weniger Abschreibungen (AfA) und weniger
				Zinsen. Diesen AfA-Effekt führt das HSK separat als Einsparung „Reduzierung der
				Abschreibungen" auf.
			</p>
		</div>
		<div class="invest-grid">
			<div class="card card-padded">
				<p class="kpi-label">Investitionsvolumen 2026</p>
				<p class="invest-flow">
					{formatMio(Number(n.investitionen_2026_vorher?.value ?? 0))}
					<span class="invest-arrow">→</span>
					<strong>{formatMio(Number(n.investitionen_2026_nachher?.value ?? 0))}</strong>
				</p>
				<p class="kpi-sub">
					gekürzt um {formatMio(Number(n.investitionen_2026_kuerzung?.value ?? 0))}
				</p>
			</div>
			<div class="card card-padded">
				<p class="kpi-label">Kreditaufnahme 2026</p>
				<p class="invest-flow">
					{formatMio(Number(n.kreditaufnahme_2026_vorher?.value ?? 0))}
					<span class="invest-arrow">→</span>
					<strong>{formatMio(Number(n.kreditaufnahme_2026_nachher?.value ?? 0))}</strong>
				</p>
				<p class="kpi-sub">
					{formatMio(Number(n.kreditaufnahme_2026_kuerzung?.value ?? 0))} weniger neue Schulden
				</p>
			</div>
		</div>
		<p class="invest-note">
			Insgesamt {hsk.investitionen.length} Investitionen wurden verschoben oder gestrichen.
			{#if fullPdf}
				<SourceCitation
					description="Haushaltssicherungskonzept 2026, S. 9"
					links={measureLinks(9)}
					condensed
				/>
			{/if}
		</p>

		<div class="invest-chart">
			<DonutChart title="Wo am meisten Investitionen wegfallen (nach Bereich)" slices={investSlices} />
		</div>

		<button class="group-btn invest-toggle" aria-expanded={investOpen} onclick={() => (investOpen = !investOpen)}>
			<span class="group-label">Alle {hsk.investitionen.length} Investitionen anzeigen</span>
			<ChevronDown class="chevron" style={investOpen ? 'transform: rotate(180deg)' : ''} />
		</button>
		{#if investOpen}
			<p class="legend">
				Negative Werte = gekürzte oder in spätere Jahre verschobene Beträge. Eine reine
				Verschiebung erscheint als Minus im einen und Plus im anderen Jahr (Summe 0).
			</p>
			<div class="measure-scroll">
				<table class="data-table measure-table">
					<thead>
						<tr>
							<th class="col-sticky col-sticky-last" style="left:0">Investition</th>
							{#each investYears as y (y)}
								<th class="col-number">{y}</th>
							{/each}
							<th class="col-number col-total">Gesamt</th>
							<th class="col-source">Quelle</th>
						</tr>
					</thead>
					<tbody>
						{#each investitionenSorted as inv, i (`${inv.code}-${i}`)}
							<tr>
								<td class="col-sticky col-sticky-last m-cell" style="left:0">
									<span
										class="m-name"
										title={LABELS[inv.name] ? `HSK-Originalbezeichnung: ${inv.name}` : null}
									>
										{displayName(inv.name)}
									</span>
									<span class="m-fb">{inv.fb_label}</span>
								</td>
								{#each investYears as y (y)}
									<td class="col-number">{fmtInvest(inv.werte[String(y)])}</td>
								{/each}
								<td class="col-number col-total">{fmtInvest(inv.summe)}</td>
								<td class="col-source">
									<SourceCitation
										description="Haushaltssicherungskonzept 2026, Änderungsliste"
										links={measureLinks(inv.page)}
										condensed
									/>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>

	<!-- ── Stand des Verfahrens ── -->
	<section class="section">
		<div class="info-box info-box-amber">
			<p>
				<strong>Stand des Verfahrens.</strong>
				Das Haushaltssicherungskonzept ist nach aktuellem Stand noch nicht genehmigt. Eine
				Beratung mit der Kommunalaufsicht ist für den 25.06.2026 vorgesehen.
			</p>
		</div>
	</section>

	{#if grstBDerived}
		<p class="source-footer">
			<sup>*</sup> Mit <sup>*</sup> markierte Grundsteuer-B-Hebesätze sind im HSK nicht genannt,
			sondern aus der jährlichen Mehreinnahme abgeleitet: Die Grundsteuer steigt linear mit dem
			Hebesatz, daher ergibt sich aus dem ersten Schritt ({fmtPct(GRST_B_AKTUELL)} → {fmtPct(
				GRST_B_SCHRITT_1
			)}) der Wert je Hebesatzpunkt und daraus die spätere Stufe. Annahme: gleichbleibender
			Steuermessbetrag. Die Ausgangswerte {fmtPct(GRST_B_AKTUELL)} und {fmtPct(GRST_B_SCHRITT_1)} stammen
			nicht aus dem HSK.
		</p>
	{/if}

	{#if fullPdf}
		<p class="source-footer">
			Quelle: <a href={fullPdf} target="_blank" rel="noopener">Haushaltssicherungskonzept 2026 (PDF)</a>.
			Die Zuordnung der Maßnahmen zu Kategorien erfolgt regelbasiert nach Stichworten. Einzelne
			Bezeichnungen wurden für die Lesbarkeit ausgeschrieben; die Originalbezeichnung des HSK
			erscheint beim Überfahren mit der Maus.
		</p>
	{/if}
{/if}

<style>
	.section {
		padding-top: 40px;
	}

	.page-intro {
		color: var(--gray-700);
		max-width: 60ch;
		margin-bottom: 1.5rem;
	}

	.legend {
		font-size: 0.85rem;
		color: var(--gray-700);
		margin: 0.5rem 0 0;
	}

	.pillar-total {
		margin: 0 0 1rem;
		color: var(--gray-700);
	}
	.pillar-total strong {
		font-size: 1.15rem;
	}

	.num-pos {
		color: var(--color-income);
		font-variant-numeric: tabular-nums;
	}
	.num-neg {
		color: var(--color-expense);
		font-variant-numeric: tabular-nums;
	}

	.groups {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.group {
		border: 1px solid var(--gray-200);
		border-radius: 0.5rem;
		overflow: hidden;
		background: #fff;
	}
	.group-btn {
		width: 100%;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.85rem 1rem;
		background: none;
		border: none;
		cursor: pointer;
		text-align: left;
		font: inherit;
	}
	.group-btn:hover {
		background: var(--gray-50);
	}
	.group-label {
		font-weight: 600;
		color: var(--gray-800);
	}
	.group-meta {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		white-space: nowrap;
	}
	.group-sum {
		font-weight: 700;
	}
	.group-btn :global(.chevron) {
		width: 18px;
		height: 18px;
		color: var(--gray-500);
		transition: transform 0.15s ease;
	}

	.measure-scroll {
		overflow-x: auto;
		border-top: 1px solid var(--gray-200);
	}
	.measure-table {
		min-width: 100%;
	}
	.measure-table .col-sticky {
		left: 0;
	}
	.m-cell {
		white-space: normal;
		min-width: 13rem;
		max-width: 18rem;
	}
	.m-name {
		display: block;
	}
	.m-fb {
		display: block;
		font-size: 0.8rem;
		color: var(--gray-500);
	}
	.cell-hebesatz {
		display: block;
		margin-top: 0.15rem;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--brand-700);
	}
	.popover-text {
		margin: 0 0 0.5rem;
		font-size: 0.85rem;
		line-height: 1.45;
		color: var(--gray-700);
	}
	.popover-text:last-child {
		margin-bottom: 0;
	}
	/* Gewerbesteuer cluster: keep the linked rows visually together */
	.measure-table .linked-row td {
		background: var(--brand-50);
	}
	.measure-table .linked-sub .m-name {
		padding-left: 0.85rem;
		position: relative;
		color: var(--gray-600);
	}
	.measure-table .linked-sub .m-name::before {
		content: '↳';
		position: absolute;
		left: 0;
		color: var(--gray-400);
	}
	.col-total {
		border-left: 1px solid var(--gray-200);
		font-weight: 600;
	}
	.col-source {
		width: 1%;
		white-space: nowrap;
		text-align: right;
	}

	.invest-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 1rem;
		margin-top: 1rem;
	}
	.kpi-flow {
		display: flex;
		align-items: baseline;
		gap: 0.1rem;
		flex-wrap: wrap;
		font-size: 1.15rem;
	}
	.kpi-arrow {
		margin: 0 0.3rem;
		color: var(--gray-400);
		font-weight: 400;
	}
	.invest-flow {
		font-size: 1.35rem;
		margin: 0.25rem 0;
		color: var(--gray-700);
	}
	.invest-flow strong {
		color: var(--gray-900);
	}
	.invest-arrow {
		margin: 0 0.4rem;
		color: var(--gray-400);
	}
	.invest-note {
		margin-top: 1rem;
		color: var(--gray-700);
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.invest-chart {
		margin-top: 1.5rem;
	}
	.invest-toggle {
		margin-top: 1rem;
		border: 1px solid var(--gray-200);
		border-radius: 0.5rem;
		background: #fff;
	}
	.invest-toggle:hover {
		background: var(--gray-50);
	}

	.source-footer {
		margin-top: 2rem;
		font-size: 0.85rem;
		color: var(--gray-500);
	}
</style>
