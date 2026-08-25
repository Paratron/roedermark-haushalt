<script lang="ts">
	import type { Snippet } from 'svelte';
	import Popover from './Popover.svelte';
	import { Info } from '@lucide/svelte';

	interface Props {
		/** The popover body content */
		children: Snippet;
		/** Opens upward or downward (default) */
		direction?: 'up' | 'down';
		/** Max width of the popover panel */
		maxWidth?: string;
		/** Icon size in px */
		size?: number;
		/** Accessible label / tooltip for the trigger */
		label?: string;
	}

	let {
		children,
		direction = 'down',
		maxWidth = '20rem',
		size = 14,
		label = 'Mehr Informationen'
	}: Props = $props();
</script>

<Popover {direction} {maxWidth}>
	{#snippet trigger()}
		<span class="info-trigger" title={label}>
			<Info {size} />
		</span>
	{/snippet}
	{@render children()}
</Popover>

<style>
	.info-trigger {
		display: inline-flex;
		align-items: center;
		vertical-align: middle;
		color: var(--brand-600);
	}
	.info-trigger:hover {
		color: var(--brand-700);
	}
</style>
