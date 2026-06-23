<script lang="ts">
	import { formatEur } from '$lib/format';
	import { ArrowRight, House, Building2, KeyRound } from '@lucide/svelte';
	import { page } from '$app/state';
	import {
		parseGermanNumber,
		berechneMessbetragSchaetzung,
		berechneGrundsteuer,
		type Modus
	} from '$lib/grundsteuer';

	interface Props {
		/** Aktueller Hebesatz Grundsteuer B in Prozent (z. B. 990). */
		aktuell: number;
		/** Neuer Hebesatz Grundsteuer B in Prozent ab 2026 (z. B. 1327). */
		neu: number;
		/** Bezugsjahr des aktuellen Hebesatzes (z. B. 2025). */
		aktuellJahr: number;
		/** Bezugsjahr des neuen Hebesatzes (z. B. 2026). */
		neuJahr: number;
	}

	let { aktuell, neu, aktuellJahr, neuJahr }: Props = $props();

	type Eigentumsform = 'eigentuemer' | 'mieter';
	type Gebaeudetyp = 'haus' | 'wohnung';

	let step = $state(1); // 1 Eigentumsform · 2 Gebäudetyp · 3 Angaben · 4 Ergebnis
	let eigentumsform = $state<Eigentumsform | null>(null);
	let gebaeudetyp = $state<Gebaeudetyp | null>(null);
	let modus = $state<Modus>('grundsteuer'); // Dokument zuerst, Schätzen ist Fallback

	let wohnflaeche = $state('');
	let grundflaeche = $state('');
	let grundsteuerRoh = $state('');
	let messbetragRoh = $state('');

	const wohnNum = $derived(parseGermanNumber(wohnflaeche));
	const grundNum = $derived(parseGermanNumber(grundflaeche));
	const istHaus = $derived(gebaeudetyp === 'haus');
	const istMieter = $derived(eigentumsform === 'mieter');
	const istWohnung = $derived(gebaeudetyp === 'wohnung');

	const messbetragSchaetzung = $derived(
		wohnNum !== null ? berechneMessbetragSchaetzung(wohnNum, grundNum, istHaus) : null
	);

	const ergebnis = $derived(
		berechneGrundsteuer({
			modus,
			hebesatzAktuell: aktuell,
			hebesatzNeu: neu,
			grundsteuerBetrag: parseGermanNumber(grundsteuerRoh),
			messbetrag: parseGermanNumber(messbetragRoh),
			messbetragSchaetzung
		})
	);

	function fmtPct(p: number): string {
		return p.toLocaleString('de-DE') + ' %';
	}

	const eingabeOk = $derived.by(() => {
		if (modus === 'grundsteuer') return parseGermanNumber(grundsteuerRoh) !== null;
		if (modus === 'messbetrag') return parseGermanNumber(messbetragRoh) !== null;
		return wohnNum !== null;
	});

	function waehleEigentumsform(ef: Eigentumsform) {
		eigentumsform = ef;
		step = 2;
	}

	function waehleGebaeudetyp(gt: Gebaeudetyp) {
		gebaeudetyp = gt;
		modus = 'grundsteuer'; // Dokument-Option als Standard, Schätzen ist Fallback
		step = 3;
	}

	const schritte = ['Eigentumsform', 'Gebäude', 'Angaben', 'Ergebnis'];

	function shareWhatsApp() {
		if (!ergebnis) return;
		const url = page.url.href;
		const monat = formatEur(ergebnis.mehrMonat);
		const text = `Die Grundsteuererhöhung in Rödermark kostet mich ${monat} mehr im Monat. Rechne deinen Anteil aus: ${url}`;
		window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank', 'noopener');
	}

	function shareFacebook() {
		const url = page.url.href;
		window.open(
			`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,
			'_blank',
			'noopener,width=600,height=400'
		);
	}
</script>

<div class="rechner">
	<!-- Schrittanzeige -->
	<ol class="steps">
		{#each schritte as label, i (label)}
			{@const nr = i + 1}
			<li class:active={step === nr} class:done={step > nr}>
				<span class="step-nr">{step > nr ? '✓' : nr}</span>
				<span class="step-label">{label}</span>
			</li>
		{/each}
	</ol>

	<!-- Schritt 1: Eigentumsform -->
	{#if step === 1}
		<fieldset class="block">
			<legend>Sind Sie Eigentümer oder wohnen Sie zur Miete?</legend>
			<div class="wf-cards">
				<button type="button" class="wf-card" onclick={() => waehleEigentumsform('eigentuemer')}>
					<House size={26} />
					<span class="wf-label">Ich bin Eigentümer</span>
					<span class="wf-sub">Haus, ETW o. ä.</span>
				</button>
				<button type="button" class="wf-card" onclick={() => waehleEigentumsform('mieter')}>
					<KeyRound size={26} />
					<span class="wf-label">Ich wohne zur Miete</span>
					<span class="wf-sub">Haus oder Wohnung</span>
				</button>
			</div>
		</fieldset>

	<!-- Schritt 2: Gebäudetyp -->
	{:else if step === 2}
		<fieldset class="block">
			<legend>Wohnen Sie in einem Haus oder in einer Wohnung?</legend>
			<div class="wf-cards">
				<button type="button" class="wf-card" onclick={() => waehleGebaeudetyp('haus')}>
					<House size={26} />
					<span class="wf-label">Haus / ganzes Grundstück</span>
					<span class="wf-sub">Einfamilienhaus, Reihenhaus o. ä.</span>
				</button>
				<button type="button" class="wf-card" onclick={() => waehleGebaeudetyp('wohnung')}>
					<Building2 size={26} />
					<span class="wf-label">Wohnung</span>
					<span class="wf-sub">Eigentumswohnung oder Mietwohnung</span>
				</button>
			</div>
			<div class="nav-btns">
				<button type="button" class="btn btn-zurueck" onclick={() => (step = 1)}>Zurück</button>
			</div>
		</fieldset>

	<!-- Schritt 3: Angaben -->
	{:else if step === 3}
		<fieldset class="block">
			<legend>Ihre Angaben</legend>

			<!-- Modus-Wahl oben als Segmented Control -->
			<div class="modus-wahl">
				<button
					type="button"
					class="modus-btn"
					class:active={modus === 'grundsteuer'}
					onclick={() => (modus = 'grundsteuer')}
				>
					{istMieter ? 'Nebenkostenabrechnung' : 'Grundsteuerbescheid'}
				</button>
				{#if !istMieter}
					<button
						type="button"
						class="modus-btn"
						class:active={modus === 'messbetrag'}
						onclick={() => (modus = 'messbetrag')}
					>
						Messbetrag
					</button>
				{/if}
				<button
					type="button"
					class="modus-btn"
					class:active={modus === 'schaetzen'}
					onclick={() => (modus = 'schaetzen')}
				>
					Schätzen
				</button>
			</div>

			<!-- Eingabe je Modus -->
			{#if modus === 'grundsteuer'}
				<div class="feld">
					<label for="gst">{istMieter ? 'Grundsteuer-Anteil' : 'Jahres-Grundsteuer'} {aktuellJahr}</label>
					<div class="feld-input">
						<input id="gst" type="text" inputmode="decimal" placeholder="z. B. 750" bind:value={grundsteuerRoh} autocomplete="off" />
						<span class="einheit">€ / Jahr</span>
					</div>
				</div>
				<p class="hinweis">
					{#if istMieter}
						Steht in Ihrer Nebenkostenabrechnung in der Zeile „Grundsteuer" – das ist bereits Ihr
						Anteil. Bitte die Abrechnung für {aktuellJahr} verwenden.
					{:else}
						Steht auf Ihrem Grundsteuerbescheid der Stadt Rödermark – der Jahresbetrag.
					{/if}
				</p>

			{:else if modus === 'messbetrag'}
				<div class="feld">
					<label for="mb">Grundsteuermessbetrag</label>
					<div class="feld-input">
						<input id="mb" type="text" inputmode="decimal" placeholder="z. B. 75,76" bind:value={messbetragRoh} autocomplete="off" />
						<span class="einheit">€</span>
					</div>
				</div>
				<p class="hinweis">
					Steht auf dem Grundsteuermessbescheid des Finanzamts – nicht zu verwechseln mit dem
					Bescheid der Stadt.
				</p>

			{:else}
				<!-- Schätzen -->
				<div class="felder">
					<div class="feld">
						<label for="wohn">Ihre Wohnfläche</label>
						<div class="feld-input">
							<input id="wohn" type="text" inputmode="decimal" placeholder="z. B. 120" bind:value={wohnflaeche} autocomplete="off" />
							<span class="einheit">m²</span>
						</div>
					</div>
					{#if istHaus}
						<div class="feld">
							<label for="grund">Grundstücksfläche <span class="optional">(optional)</span></label>
							<div class="feld-input">
								<input id="grund" type="text" inputmode="decimal" placeholder="z. B. 500" bind:value={grundflaeche} autocomplete="off" />
								<span class="einheit">m²</span>
							</div>
						</div>
					{/if}
				</div>
				<p class="hinweis">
					{#if istHaus && !istMieter}
						Wohnfläche und Grundstücksgröße stehen im Kaufvertrag oder Grundbuchauszug.
					{:else if istHaus && istMieter}
						Wohnfläche steht im Mietvertrag. Die Grundstücksgröße ist optional – ohne sie fällt die Schätzung etwas zu niedrig aus.
					{:else if !istMieter}
						Geben Sie nur <strong>Ihre eigene</strong> Wohnfläche an – berechnet wird Ihr Anteil, nicht die Grundsteuer des ganzen Gebäudes. Der Grundstücksanteil bleibt außen vor.
					{:else}
						Ihre Wohnfläche steht im Mietvertrag. <strong>Achtung: grobe Schätzung</strong> – Grundstücksgröße und Gesamtfläche des Gebäudes sind unbekannt, der echte Wert liegt etwas höher. Am genauesten ist der Grundsteuer-Anteil aus Ihrer Nebenkostenabrechnung.
					{/if}
				</p>
			{/if}

			<div class="nav-btns">
				<button type="button" class="btn btn-zurueck" onclick={() => (step = 2)}>Zurück</button>
				<button type="button" class="btn btn-weiter" disabled={!eingabeOk} onclick={() => (step = 4)}>
					Ergebnis anzeigen →
				</button>
			</div>
		</fieldset>

	<!-- Schritt 4: Ergebnis -->
	{:else if ergebnis}
		<div class="ergebnis">
			{#if ergebnis.geschaetzt}
				<span class="badge-schaetzung">Schätzung</span>
			{/if}
			<p class="ergebnis-titel">
				{eigentumsform === 'eigentuemer' && istHaus ? 'Ihre Grundsteuer' : 'Ihr Anteil an der Grundsteuer'}
			</p>
			<div class="flow">
				<div class="flow-box">
					<span class="flow-label">Bisher ({fmtPct(aktuell)})</span>
					<span class="flow-wert">{formatEur(ergebnis.alt)}</span>
					<span class="flow-sub">pro Jahr</span>
				</div>
				<ArrowRight class="flow-arrow" size={22} />
				<div class="flow-box flow-box-neu">
					<span class="flow-label">Ab {neuJahr} ({fmtPct(neu)})</span>
					<span class="flow-wert">{formatEur(ergebnis.neu)}</span>
					<span class="flow-sub">pro Jahr</span>
				</div>
			</div>
			<div class="mehr">
				<span class="mehr-monat">≈ +{formatEur(ergebnis.mehrMonat)} / Monat</span>
				<span class="mehr-jahr">+{formatEur(ergebnis.mehrJahr)} / Jahr</span>
			</div>
			<div class="teilen">
				<span class="teilen-label">Ergebnis teilen:</span>
				<button type="button" class="teilen-btn btn-whatsapp" onclick={shareWhatsApp}>
					<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
					WhatsApp
				</button>
				<button type="button" class="teilen-btn btn-facebook" onclick={shareFacebook}>
					<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
					Facebook
				</button>
			</div>
			<p class="fussnote">
				{#if istMieter}
					Sie tragen die Erhöhung anteilig über die Nebenkosten – spürbar erst mit der
					Betriebskostenabrechnung für {neuJahr}, die meist erst {neuJahr + 1} kommt.
				{:else}
					Wird mit dem Grundsteuerbescheid {neuJahr} fällig.
				{/if}
				{#if ergebnis.geschaetzt}
					<br />Grobe Schätzung nach dem hessischen Flächen-Faktor-Modell (Lagefaktor pauschal
					1,0; je nach Lage in Rödermark ±5 %).{#if istWohnung} Ohne Grundstücksanteil des Gebäudes – tatsächlicher Wert liegt etwas höher.{/if}
					Den genauen Wert nennt {istMieter ? 'Ihre Nebenkostenabrechnung' : 'nur Ihr Steuerbescheid'}.
				{/if}
			</p>
			<div class="nav-btns">
				<button type="button" class="btn btn-zurueck" onclick={() => (step = 3)}>← Angaben ändern</button>
			</div>
		</div>
	{/if}
</div>

<style>
	.rechner {
		display: flex;
		flex-direction: column;
		gap: 1.75rem;
		max-width: 42rem;
		border: 1px solid var(--gray-200);
		border-radius: 0.85rem;
		background: #fff;
		padding: 1.75rem 1.85rem 2rem;
	}

	/* Schrittanzeige */
	.steps {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		list-style: none;
		margin: 0;
		padding: 0 0 1.5rem;
		border-bottom: 1px solid var(--gray-100);
		flex-wrap: wrap;
	}
	.steps li {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--gray-400);
		font-size: 0.9rem;
		font-weight: 600;
	}
	.steps li:not(:last-child)::after {
		content: '';
		width: 1.75rem;
		height: 1px;
		background: var(--gray-300);
		margin-left: 0.5rem;
	}
	.step-nr {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.7rem;
		height: 1.7rem;
		border-radius: 50%;
		border: 1px solid var(--gray-300);
		background: #fff;
		font-size: 0.85rem;
	}
	.steps li.active {
		color: var(--brand-700, #1d4ed8);
	}
	.steps li.active .step-nr {
		border-color: var(--brand-600, #2563eb);
		background: var(--brand-600, #2563eb);
		color: #fff;
	}
	.steps li.done {
		color: var(--gray-600);
	}
	.steps li.done .step-nr {
		border-color: var(--brand-600, #2563eb);
		color: var(--brand-700, #1d4ed8);
	}

	.block {
		border: none;
		margin: 0;
		padding: 0;
		min-width: 0;
	}
	.block legend {
		font-weight: 600;
		color: var(--gray-900);
		font-size: 1.1rem;
		margin-bottom: 1rem;
		padding: 0;
	}

	/* Auswahlkarten: 2 nebeneinander */
	.wf-cards {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 1rem;
	}
	.wf-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.4rem;
		padding: 1.5rem 0.75rem;
		border: 1px solid var(--gray-300);
		border-radius: 0.7rem;
		background: #fff;
		cursor: pointer;
		font: inherit;
		color: var(--gray-700);
		text-align: center;
		transition: border-color 0.12s, background 0.12s, box-shadow 0.12s;
	}
	.wf-card:hover {
		border-color: var(--brand-500, #3b82f6);
		background: var(--brand-50, #eff6ff);
		box-shadow: 0 1px 4px rgba(37, 99, 235, 0.1);
	}
	.wf-card :global(svg) {
		color: var(--brand-600, #2563eb);
	}
	.wf-label {
		font-size: 1rem;
		font-weight: 600;
		color: var(--gray-900);
		margin-top: 0.15rem;
	}
	.wf-sub {
		font-size: 0.8rem;
		color: var(--gray-500);
	}

	/* Modus-Auswahl (Pills) */
	.modus-wahl {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-bottom: 1.5rem;
	}
	.modus-btn {
		padding: 0.45rem 1rem;
		border-radius: 2rem;
		border: 1px solid var(--gray-300);
		background: #fff;
		font: inherit;
		font-size: 0.88rem;
		font-weight: 500;
		color: var(--gray-600);
		cursor: pointer;
		transition: border-color 0.1s, background 0.1s, color 0.1s;
	}
	.modus-btn.active {
		border-color: var(--brand-600, #2563eb);
		background: var(--brand-600, #2563eb);
		color: #fff;
	}
	.modus-btn:not(.active):hover {
		border-color: var(--brand-400, #60a5fa);
		background: var(--brand-50, #eff6ff);
		color: var(--brand-700, #1d4ed8);
	}

	/* Eingabefelder */
	.felder {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
		gap: 1.25rem;
	}
	.feld label {
		display: block;
		font-weight: 600;
		color: var(--gray-700);
		margin-bottom: 0.5rem;
		font-size: 0.95rem;
	}
	.optional {
		font-weight: 400;
		color: var(--gray-500);
		font-size: 0.85rem;
	}
	.feld-input {
		display: flex;
		align-items: stretch;
		border: 1px solid var(--gray-300);
		border-radius: 0.5rem;
		overflow: hidden;
	}
	.feld-input:focus-within {
		border-color: var(--brand-600, #2563eb);
		box-shadow: 0 0 0 2px var(--brand-100, #dbeafe);
	}
	.feld-input input {
		flex: 1;
		min-width: 0;
		border: none;
		outline: none;
		padding: 0.7rem 0.85rem;
		font: inherit;
		font-variant-numeric: tabular-nums;
	}
	.einheit {
		display: flex;
		align-items: center;
		padding: 0 0.95rem;
		background: var(--gray-50);
		border-left: 1px solid var(--gray-200);
		color: var(--gray-600);
		font-size: 0.9rem;
		white-space: nowrap;
	}
	.hinweis {
		margin: 1rem 0 0;
		font-size: 0.85rem;
		color: var(--gray-600);
		line-height: 1.55;
	}
	.hinweis strong {
		color: var(--gray-800);
	}

	.nav-btns {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		margin-top: 1.75rem;
		flex-wrap: wrap;
	}
	.btn {
		padding: 0.65rem 1.4rem;
		border-radius: 0.5rem;
		font: inherit;
		font-weight: 600;
		cursor: pointer;
		border: 1px solid transparent;
	}
	.btn-weiter {
		background: var(--brand-600, #2563eb);
		color: #fff;
		margin-left: auto;
	}
	.btn-weiter:hover:not(:disabled) {
		background: var(--brand-700, #1d4ed8);
	}
	.btn-weiter:disabled {
		background: var(--gray-300);
		cursor: not-allowed;
	}
	.btn-zurueck {
		background: #fff;
		border-color: var(--gray-300);
		color: var(--gray-700);
	}
	.btn-zurueck:hover {
		background: var(--gray-50);
	}

	/* Ergebnis */
	.ergebnis {
		position: relative;
		border: 1px solid var(--gray-200);
		border-radius: 0.75rem;
		background: var(--gray-50);
		padding: 1.75rem;
	}
	.ergebnis-titel {
		margin: 0 0 1rem;
		font-weight: 600;
		color: var(--gray-700);
	}
	.badge-schaetzung {
		position: absolute;
		top: 0.9rem;
		right: 0.9rem;
		font-size: 0.72rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--gray-500);
		background: #fff;
		border: 1px solid var(--gray-300);
		border-radius: 1rem;
		padding: 0.15rem 0.65rem;
	}
	.flow {
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
	}
	.flow-box {
		flex: 1;
		min-width: 9rem;
		display: flex;
		flex-direction: column;
		padding: 0.9rem 1.1rem;
		border-radius: 0.5rem;
		background: #fff;
		border: 1px solid var(--gray-200);
	}
	.flow-box-neu {
		border-color: var(--brand-200, #bfdbfe);
		background: var(--brand-50, #eff6ff);
	}
	.flow-label {
		font-size: 0.82rem;
		color: var(--gray-600);
	}
	.flow-wert {
		font-size: 1.6rem;
		font-weight: 700;
		color: var(--gray-900);
		font-variant-numeric: tabular-nums;
		margin: 0.2rem 0;
	}
	.flow-box-neu .flow-wert {
		color: var(--brand-700, #1d4ed8);
	}
	.flow-sub {
		font-size: 0.78rem;
		color: var(--gray-500);
	}
	.rechner :global(.flow-arrow) {
		color: var(--gray-400);
		flex-shrink: 0;
	}
	.mehr {
		display: flex;
		align-items: baseline;
		gap: 1rem;
		flex-wrap: wrap;
		margin-top: 1.4rem;
	}
	.mehr-monat {
		font-size: 1.55rem;
		font-weight: 800;
		color: var(--gray-900);
		font-variant-numeric: tabular-nums;
	}
	.mehr-jahr {
		font-size: 1.05rem;
		color: var(--gray-600);
		font-variant-numeric: tabular-nums;
	}
	.fussnote {
		margin: 1.25rem 0 0;
		font-size: 0.83rem;
		color: var(--gray-600);
		line-height: 1.55;
	}

	/* ── Mobile ─────────────────────────────────────────────── */
	@media (max-width: 520px) {
		/* Weniger Außenabstand – gibt dem Inhalt mehr Luft */
		.rechner {
			padding: 1.1rem 1rem 1.5rem;
			gap: 1.25rem;
		}

		/* Stepper: Labels ausblenden, nur Nummern zeigen */
		.steps {
			gap: 0.35rem;
			padding-bottom: 1rem;
		}
		.step-label {
			display: none;
		}
		.steps li:not(:last-child)::after {
			width: 0.6rem;
			margin-left: 0.15rem;
		}

		/* Auswahlkarten: weniger Innenabstand */
		.wf-card {
			padding: 1.1rem 0.5rem;
			gap: 0.3rem;
		}

		/* Ergebnis-Box: weniger Padding → Flow-Boxen passen nebeneinander */
		.ergebnis {
			padding: 1.1rem 1rem;
		}

		/* Mehrbelastung etwas kleiner */
		.mehr-monat {
			font-size: 1.3rem;
		}
	}

	/* Share-Buttons */
	.teilen {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		flex-wrap: wrap;
		margin-top: 1.4rem;
	}
	.teilen-label {
		font-size: 0.85rem;
		color: var(--gray-500);
		font-weight: 500;
	}
	.teilen-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.45rem 1rem;
		border-radius: 2rem;
		border: none;
		font: inherit;
		font-size: 0.875rem;
		font-weight: 600;
		color: #fff;
		cursor: pointer;
		transition: opacity 0.12s;
	}
	.teilen-btn:hover {
		opacity: 0.88;
	}
	.btn-whatsapp {
		background: #25d366;
	}
	.btn-facebook {
		background: #1877f2;
	}

	/* Sehr kleine Screens (≤ 380 px): Flow-Pfeil verbergen wenn Boxen stapeln */
	@media (max-width: 380px) {
		.rechner :global(.flow-arrow) {
			display: none;
		}
	}
</style>
