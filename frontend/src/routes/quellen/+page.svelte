<script lang="ts">
	import type { PageData } from './$types';
	import { formatDocumentName, formatNumber } from '$lib/format';
	import { FileText, Download, ExternalLink, CircleAlert } from '@lucide/svelte';
	import AnchorHeading from '$lib/components/AnchorHeading.svelte';

	let { data }: { data: PageData } = $props();
	const { summary } = data;

	const istYears = summary.ist_years;
	const lastIstYear = summary.last_ist_year ?? (istYears.length > 0 ? istYears[istYears.length - 1] : null);
	const planOnlyYears = summary.plan_only_years;

	// All documents sorted by year (descending), available and missing mixed
	const documents = [...data.documents]
		.filter((d) => d.years && d.years.length > 0)
		.sort((a, b) => {
			const aMax = Math.max(...(a.years || [0]));
			const bMax = Math.max(...(b.years || [0]));
			return bMax - aMax;
		});

	function formatSize(bytes: number): string {
		if (bytes > 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
		if (bytes > 1_000) return `${(bytes / 1_000).toFixed(0)} KB`;
		return `${bytes} B`;
	}

	function formatDate(iso: string): string {
		return new Date(iso).toLocaleDateString('de-DE', {
			day: '2-digit',
			month: '2-digit',
			year: 'numeric'
		});
	}

	function docTypeLabel(type: string): string {
		const labels: Record<string, string> = {
			'haushaltsplan_beschluss': 'Haushaltsplan (Beschluss)',
			'haushaltsplan_entwurf': 'Haushaltsplan (Entwurf)',
			'anpassungsbeschluss': 'Anpassungsbeschluss',
			'jahresabschluss': 'Jahresabschluss',
			'gesamtabschluss': 'Gesamtabschluss',
			'nachtrag': 'Nachtragshaushalt',
			'haushaltssatzung': 'Haushaltssatzung',
			'haushaltsrede': 'Haushaltsrede',
			'beteiligungsbericht': 'Beteiligungsbericht',
			'konsolidierung': 'Konsolidierungsbericht',
			'praesentation': 'Präsentation',
		};
		return labels[type] ?? type;
	}
</script>

<AnchorHeading level={2} id="datenquellen"><FileText /> Datenquellen</AnchorHeading>
<p class="page-intro">
	Alle Daten stammen aus offiziellen PDF-Dokumenten der Stadt Rödermark. Jede extrahierte Zahl
	ist auf das Quelldokument und die Seitenzahl rückverfolgbar.
</p>

<!-- Key Figures -->
<section class="kpi-grid section">
	<div class="kpi-card">
		<p class="kpi-label">Datenpunkte</p>
		<p class="kpi-value text-brand-700">{formatNumber(summary.total_line_items)}</p>
		<p class="kpi-sub">{summary.overview_line_items} Übersicht · {summary.detail_line_items} Detail</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Ist-Daten (Ergebnisse)</p>
		<p class="kpi-value text-brand-700">{istYears[0] ?? '?'}–{lastIstYear ?? '?'}</p>
		<p class="kpi-sub">{istYears.length} Jahre mit Ist-Werten</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Planung (Ansatz/Finanzplan)</p>
		<p class="kpi-value text-blue-600">bis {planOnlyYears[planOnlyYears.length - 1] ?? '?'}</p>
		<p class="kpi-sub">{planOnlyYears.length} weitere Jahre · nur Planwerte</p>
	</div>
	<div class="kpi-card">
		<p class="kpi-label">Dokumente</p>
		<p class="kpi-value text-brand-700">{documents.length} ({documents.filter((d) => d.missing).length} fehlend)</p>
		<p class="kpi-sub">PDFs (Haushaltspläne, Abschlüsse, Reden u. a.)</p>
	</div>
</section>

<!-- Methodology -->
<section class="card card-padded section">
	<AnchorHeading level={3} id="methodik">Methodik</AnchorHeading>
	<div class="method-steps">
		<p>
			<strong>1. Fetch:</strong> PDFs werden von der Website der Stadt Rödermark heruntergeladen
			und mit SHA-256 Prüfsummen versioniert.
		</p>
		<p>
			<strong>2. Parse:</strong> Tabellen werden mit pdfplumber extrahiert. Die Seitenbereiche
			sind in <code>tables.yaml</code> definiert.
		</p>
		<p>
			<strong>3. Normalize:</strong> Jahresdaten werden aus den Spaltenüberschriften erkannt,
			Beträge von deutschem Zahlenformat in EUR konvertiert, und überlappende Daten dedupliziert.
		</p>
		<p>
			<strong>4. Publish:</strong> Export als CSV, Parquet und DuckDB für verschiedene Analysetools.
		</p>
	</div>
</section>

<!-- Documents Table -->
<section>
	<AnchorHeading level={3} id="quelldokumente">Quelldokumente ({documents.length})</AnchorHeading>
	<div class="doc-list">
		{#each documents as doc}
			{#if doc.missing}
				<div class="doc-card doc-missing">
					<div class="doc-row">
						<div>
							<h4 class="doc-name-missing">{formatDocumentName(doc.document_id)}</h4>
							<p class="doc-type-missing">{docTypeLabel(doc.doc_type)}</p>
							<div class="year-badges">
								{#each doc.years || [] as year}
									<span class="badge badge-gray">{year}</span>
								{/each}
							</div>
						</div>
						<span class="missing-badge">
							<CircleAlert class="missing-icon" /> PDF nicht verfügbar
						</span>
					</div>
					{#if doc.source_url}
						<a
							href="https://roedermark.de/rathaus-politik/haushalt-und-berichte.html"
							target="_blank"
							rel="noopener"
							class="search-link"
						>
							<ExternalLink class="link-icon" /> Auf roedermark.de suchen
						</a>
					{/if}
				</div>
			{:else}
				<div class="doc-card doc-available">
					<div class="doc-row">
						<div>
							<h4 class="doc-name">{formatDocumentName(doc.document_id)}</h4>
							<p class="doc-type">{docTypeLabel(doc.doc_type)}</p>
							<div class="year-badges">
								{#each doc.years || [] as year}
									<span class="badge badge-brand">{year}</span>
								{/each}
							</div>
						</div>
						<div class="doc-meta">
							{#if doc.size_bytes}<p>{formatSize(doc.size_bytes)}</p>{/if}
							{#if doc.fetched_at}<p>Abgerufen: {formatDate(doc.fetched_at)}</p>{/if}
						</div>
					</div>
					{#if doc.filename || doc.source_url}
						<div class="doc-links">
							<span class="doc-links-label">PDF öffnen:</span>
							{#if doc.source_url}
								<a href={doc.source_url} target="_blank" rel="noopener" class="doc-link">
									<ExternalLink class="link-icon" /> Offizieller Downloadlink
								</a>
							{/if}
							{#if doc.filename}
								<a href="/pdfs/{doc.filename}" target="_blank" rel="noopener" class="doc-link">
									<Download class="link-icon" /> Lokale Kopie
								</a>
							{/if}
						</div>
					{/if}
				</div>
			{/if}
		{/each}
	</div>
</section>

<!-- Disclaimer -->
<section class="info-box info-box-amber disclaimer">
	<AnchorHeading level={4} id="hinweise">⚠️ Hinweise</AnchorHeading>
	<ul class="disclaimer-list">
		<li>Dies ist <strong>keine offizielle Seite</strong> der Stadt Rödermark.</li>
		<li>Alle Daten wurden automatisch aus PDFs extrahiert – Fehler sind möglich.</li>
		<li>Im Zweifelsfall gilt immer das Originaldokument (PDF).</li>
		<li>Stand der Pipeline: {new Date(data.summary.generated_at).toLocaleDateString('de-DE')}</li>
	</ul>
</section>

<style>
	.page-intro { margin-bottom: 2rem; max-width: 48rem; color: var(--gray-600); }
	.section { margin-bottom: 2.5rem; }
	.method-steps { display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.875rem; color: var(--gray-600); }
	.method-steps code {
		background: var(--gray-100); padding: 0 0.25rem; border-radius: 0.25rem;
	}
	.doc-list { display: flex; flex-direction: column; gap: 0.75rem; }
	.doc-card { border-radius: 0.75rem; padding: 1rem; }
	.doc-available {
		background: #fff; box-shadow: var(--shadow-sm); border: 1px solid var(--gray-100);
	}
	.doc-missing {
		background: var(--gray-50); border: 1px dashed var(--gray-300);
	}
	.doc-row {
		display: flex; flex-direction: column; gap: 0.5rem;
	}
	@media (min-width: 640px) {
		.doc-row { flex-direction: row; align-items: flex-start; justify-content: space-between; }
	}
	.doc-name { font-weight: 500; color: var(--gray-900); }
	.doc-name-missing { font-weight: 500; color: var(--gray-500); }
	.doc-type { font-size: 0.875rem; color: var(--gray-500); }
	.doc-type-missing { font-size: 0.875rem; color: var(--gray-400); }
	.year-badges { margin-top: 0.25rem; display: flex; flex-wrap: wrap; gap: 0.25rem; }
	.badge-brand {
		display: inline-block; border-radius: 9999px;
		padding: 0.125rem 0.5rem; font-size: 0.75rem; font-weight: 500;
		background: var(--brand-100); color: var(--brand-700);
	}
	.missing-badge {
		display: inline-flex; align-items: center; gap: 0.25rem; align-self: flex-start;
		border-radius: 9999px; padding: 0.125rem 0.5rem;
		font-size: 0.75rem; font-weight: 500; background: var(--amber-100); color: var(--amber-700);
	}
	:global(.missing-icon) { width: 0.75rem; height: 0.75rem; }
	:global(.link-icon) { width: 0.875rem; height: 0.875rem; }
	.search-link {
		margin-top: 0.5rem; display: inline-flex; align-items: center; gap: 0.25rem;
		font-size: 0.875rem; color: var(--gray-400);
	}
	.search-link:hover { color: var(--gray-600); }
	.doc-meta { text-align: right; font-size: 0.875rem; color: var(--gray-400); }
	.doc-links {
		margin-top: 0.5rem; display: flex; flex-wrap: wrap;
		align-items: center; column-gap: 0.75rem; row-gap: 0.25rem; font-size: 0.875rem;
	}
	.doc-links-label { color: var(--gray-400); }
	.doc-link {
		display: inline-flex; align-items: center; gap: 0.25rem;
		color: var(--brand-600);
	}
	.doc-link:hover { color: var(--brand-800); }
	.disclaimer { margin-top: 2.5rem; }
	.disclaimer-list {
		margin-top: 0.5rem; padding-left: 1.25rem;
		list-style: disc inside; display: flex; flex-direction: column; gap: 0.25rem;
		font-size: 0.875rem; color: var(--amber-700);
	}
</style>
