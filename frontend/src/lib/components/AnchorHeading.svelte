<script lang="ts">
	import { Link } from '@lucide/svelte';
	import type { Snippet } from 'svelte';

	interface Props {
		/** Heading level: 2, 3, or 4 */
		level?: 2 | 3 | 4;
		/** Explicit anchor id – auto-generated from text content if omitted */
		id?: string;
		/** Extra CSS class on the heading element */
		class?: string;
		/** Heading content */
		children: Snippet;
	}

	let { level = 3, id, class: cls = '', children }: Props = $props();

	function slugify(text: string): string {
		return text
			.toLowerCase()
			.replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-+|-+$/g, '');
	}

	let headingEl = $state<HTMLElement | null>(null);
	let anchorId = $derived(id ?? (headingEl ? slugify(headingEl.textContent ?? '') : undefined));

	function copyLink() {
		if (!anchorId) return;
		const url = `${location.origin}${location.pathname}#${anchorId}`;
		navigator.clipboard.writeText(url);
	}
</script>

{#if level === 2}
<h2 bind:this={headingEl} id={anchorId} class={cls}>
	{@render children()}
	{#if anchorId}<a href="#{anchorId}" title="Link zu diesem Abschnitt" onclick={copyLink}><Link size={16} /></a>{/if}
</h2>
{:else if level === 3}
<h3 bind:this={headingEl} id={anchorId} class={cls}>
	{@render children()}
	{#if anchorId}<a href="#{anchorId}" title="Link zu diesem Abschnitt" onclick={copyLink}><Link size={16} /></a>{/if}
</h3>
{:else}
<h4 bind:this={headingEl} id={anchorId} class={cls}>
	{@render children()}
	{#if anchorId}<a href="#{anchorId}" title="Link zu diesem Abschnitt" onclick={copyLink}><Link size={14} /></a>{/if}
</h4>
{/if}

<style>
	h2, h3, h4 {
		position: relative;
		scroll-margin-top: 5rem;
		display: flex;
		align-items: center;
	}

	h2 {
		gap: 0.5rem;
		margin-bottom: 1.5rem;
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--gray-900);
	}

	h3 {
		gap: 0.25rem;
		margin-bottom: 1rem;
		font-size: 1.125rem;
		font-weight: 600;
		color: var(--gray-800);
	}

	h4 {
		gap: 0.1rem;
		margin-bottom: 0.5rem;
		font-size: 1rem;
		font-weight: 500;
		color: var(--gray-800);
	}

	a {
		color: var(--gray-300);
		opacity: 0;
		transition: opacity 0.15s ease, color 0.15s ease;
		text-decoration: none;
	}
	h2:hover a, h3:hover a, h4:hover a,
	a:focus-visible {
		opacity: 1;
	}
	a:hover {
		color: var(--brand-500);
	}
	@media (hover: none) {
		a { opacity: 0.5; }
	}
</style>
