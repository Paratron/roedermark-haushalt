/** Formatting utilities for German locale display. */

const eurFormatter = new Intl.NumberFormat('de-DE', {
	style: 'currency',
	currency: 'EUR',
	maximumFractionDigits: 0
});

const eurDetailFormatter = new Intl.NumberFormat('de-DE', {
	style: 'currency',
	currency: 'EUR',
	maximumFractionDigits: 2
});

const numFormatter = new Intl.NumberFormat('de-DE', {
	maximumFractionDigits: 0
});

const pctFormatter = new Intl.NumberFormat('de-DE', {
	style: 'percent',
	minimumFractionDigits: 1,
	maximumFractionDigits: 1
});

/** Format as EUR (no decimals) */
export function formatEur(amount: number): string {
	return eurFormatter.format(amount);
}

/** Format as EUR with cents */
export function formatEurDetail(amount: number): string {
	return eurDetailFormatter.format(amount);
}

/** Format as Mio. € */
export function formatMio(amount: number): string {
	const mio = amount / 1_000_000;
	return `${mio.toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} Mio. €`;
}

/** Format as T€ */
export function formatTeur(amount: number): string {
	const teur = amount / 1_000;
	return `${teur.toLocaleString('de-DE', { maximumFractionDigits: 0 })} T€`;
}

/** Smart formatting: pick unit based on magnitude */
export function formatAmount(amount: number): string {
	const abs = Math.abs(amount);
	if (abs >= 1_000_000) return formatMio(amount);
	if (abs >= 10_000) return formatTeur(amount);
	return formatEur(amount);
}

/** Format a number without currency */
export function formatNumber(n: number): string {
	return numFormatter.format(n);
}

/** Format a percentage (input as ratio, e.g. 0.05 → 5,0 %) */
export function formatPercent(ratio: number): string {
	return pctFormatter.format(ratio);
}

/** Format year-over-year change */
export function formatChange(current: number, previous: number): string {
	if (previous === 0) return '–';
	const diff = current - previous;
	const ratio = diff / Math.abs(previous);
	const sign = diff > 0 ? '+' : '';
	return `${sign}${formatAmount(diff)} (${sign}${(ratio * 100).toFixed(1)} %)`;
}

/** Translate amount_type to German label */
export function amountTypeLabel(type: string): string {
	switch (type) {
		case 'ist':
			return 'Ist (Ergebnis)';
		case 'plan':
			return 'Plan (Ansatz)';
		default:
			return type;
	}
}

/** Format document_id into human-readable name */
export function formatDocumentName(docId: string): string {
	return docId
		.replace(/_/g, ' ')
		.replace(/\b\w/g, (l) => l.toUpperCase());
}
