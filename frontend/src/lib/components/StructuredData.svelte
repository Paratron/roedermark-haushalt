<script lang="ts">
	import type { TimeSeriesPoint } from '$lib/types';

	interface Props {
		name: string;
		description?: string;
		series: TimeSeriesPoint[];
		multiSeries?: boolean;
	}

	let { name, description, series, multiSeries = false }: Props = $props();

	function buildJsonLd(name: string, description: string | undefined, series: TimeSeriesPoint[], multiSeries: boolean) {
		if (multiSeries) {
			// Group by label
			const groups: Record<string, { year: number; amount: number; amount_type: string }[]> = {};
			for (const p of series) {
				const key = p.label;
				if (!groups[key]) groups[key] = [];
				groups[key].push({ year: p.year, amount: p.amount, amount_type: p.amount_type });
			}

			return {
				'@context': 'https://schema.org',
				'@type': 'Dataset',
				name,
				description: description ?? name,
				publisher: {
					'@type': 'GovernmentOrganization',
					name: 'Stadt Rödermark'
				},
				variableMeasured: Object.entries(groups).map(([label, points]) => ({
					'@type': 'PropertyValue',
					name: label,
					unitText: 'EUR',
					value: points.map((p) => ({
						'@type': 'Observation',
						observationDate: String(p.year),
						measuredValue: p.amount,
						measurementMethod: p.amount_type === 'ist' ? 'Jahresabschluss (Ist)' : 'Haushaltsplan (Plan)'
					}))
				}))
			};
		}

		return {
			'@context': 'https://schema.org',
			'@type': 'Dataset',
			name,
			description: description ?? name,
			publisher: {
				'@type': 'GovernmentOrganization',
				name: 'Stadt Rödermark'
			},
			variableMeasured: [
				{
					'@type': 'PropertyValue',
					name,
					unitText: 'EUR',
					value: series.map((p) => ({
						'@type': 'Observation',
						observationDate: String(p.year),
						measuredValue: p.amount,
						measurementMethod: p.amount_type === 'ist' ? 'Jahresabschluss (Ist)' : 'Haushaltsplan (Plan)'
					}))
				}
			]
		};
	}

	const jsonLd = $derived(buildJsonLd(name, description, series, multiSeries));
</script>

{@html `<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>`}
