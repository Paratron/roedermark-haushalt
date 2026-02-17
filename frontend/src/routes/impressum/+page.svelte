<script lang="ts">
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';
	import SocialMeta from '$lib/components/SocialMeta.svelte';
</script>

<SocialMeta
	title="Impressum"
	description="Impressum und Kontaktdaten für haushalt.roedermark.info – ein privates Transparenzprojekt von Christian Engel."
	path="/impressum"
/>

<AnchorHeading level={2} id="impressum">Impressum</AnchorHeading>

<section class="card card-padded section">
	<h3>Angaben gemäß § 5 TMG</h3>
	<p>
		Christian Engel<br />
		Konzeption, architekturelle Modellierung &amp; Realisierung<br />
		von Websystemen und Systemsoftware
	</p>
	<p>
		Traminer Straße 38<br />
		63322 Rödermark
	</p>
</section>

<section class="card card-padded section">
	<h3>Kontakt</h3>
	<p>
		E-Mail: <a href="mailto:hallo@christian-engel.dev">hallo@christian-engel.dev</a>
	</p>
</section>

<section class="card card-padded section">
	<h3>Haftungshinweis</h3>
	<p>
		Dies ist ein privates, nicht-kommerzielles Transparenzprojekt. Alle dargestellten Daten
		wurden automatisiert und teilweise KI-gestützt aus offiziellen PDF-Dokumenten der Stadt
		Rödermark extrahiert. Trotz sorgfältiger Prüfung kann keine Gewähr für die Richtigkeit,
		Vollständigkeit und Aktualität der Daten übernommen werden.
	</p>
	<p>
		Im Zweifelsfall gilt immer das jeweilige Originaldokument.
		Diese Website steht in keiner Verbindung zur Stadtverwaltung Rödermark.
	</p>
</section>

<style>
	.section {
		margin-bottom: 1.5rem;
	}
	.section h3 {
		margin-bottom: 0.75rem;
		font-size: 1.125rem;
		font-weight: 600;
		color: var(--gray-800);
	}
	.section p {
		font-size: 0.9375rem;
		color: var(--gray-600);
		line-height: 1.6;
	}
	.section p + p {
		margin-top: 0.75rem;
	}
	.section a {
		color: var(--brand-700);
		text-decoration: underline;
	}
	.section a:hover {
		color: var(--brand-800);
	}
</style>
