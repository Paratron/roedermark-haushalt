<script lang="ts">
	import type { SourceLink } from '$lib/types';
	import { FileText } from '@lucide/svelte';

	interface Props {
		/** Description of the data source, e.g. "Finanzhaushalt, Nr. 310 (Kreditaufnahme)" */
		description: string;
		/** Resolved source links with PDF deep links */
		links: SourceLink[];
		/** Condensed mode: only show icon, no text label. Popover opens downward. */
		condensed?: boolean;
	}

	let { description, links, condensed = false }: Props = $props();
	let open = $state(false);
	let wrapperEl: HTMLDivElement | undefined = $state();

	function toggle(e: MouseEvent) {
		e.stopPropagation();
		open = !open;
	}

	function handleClickOutside(e: MouseEvent) {
		if (wrapperEl && !wrapperEl.contains(e.target as Node)) {
			open = false;
		}
	}
</script>

<svelte:document onclick={handleClickOutside} />

{#if links.length > 0}
	<div class="source-wrapper" class:condensed bind:this={wrapperEl}>
		<button
			type="button"
			class="source-btn"
			class:source-btn-condensed={condensed}
			onclick={toggle}
			title="{links.length} {links.length === 1 ? 'Quelle' : 'Quellen'}"
		>
			<FileText class="source-icon" />
			{#if !condensed}
				<span>
					{links.length === 1 ? '1 Quelle' : `${links.length} Quellen`}
				</span>
			{/if}
		</button>

		{#if open}
			<div class="popover" class:popover-down={condensed} class:popover-up={!condensed}>
				{#if !condensed}
					<div class="popover-arrow popover-arrow-up"></div>
				{:else}
					<div class="popover-arrow popover-arrow-down"></div>
				{/if}
				<p class="popover-desc">{description}</p>
				<ul class="popover-list">
					{#each links as link (link.href)}
						<li>
							<a href={link.href} target="_blank" class="popover-link">
								<FileText class="source-icon-sm" />
								{link.label}
							</a>
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	</div>
{/if}

<style>
	.source-wrapper {
		position: relative;
		margin-top: 0.25rem;
		display: inline-block;
	}
	.source-wrapper.condensed {
		margin-top: 0;
		display: inline-flex;
		vertical-align: middle;
	}
	.source-btn {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		font-size: 0.75rem;
		color: var(--gray-400);
		background: none;
		border: none;
		cursor: pointer;
		transition: color 0.15s;
	}
	.source-btn:hover {
		color: var(--gray-600);
	}
	.source-btn-condensed {
		padding: 0.125rem;
		border-radius: 0.25rem;
	}
	.source-btn-condensed:hover {
		color: var(--brand-600);
		background: var(--brand-50);
	}
	.source-btn :global(.source-icon) {
		width: 0.875rem;
		height: 0.875rem;
		flex-shrink: 0;
	}
	.source-btn-condensed :global(.source-icon) {
		width: 0.75rem;
		height: 0.75rem;
	}
	.popover-link :global(.source-icon-sm) {
		width: 0.75rem;
		height: 0.75rem;
		flex-shrink: 0;
		color: var(--gray-400);
	}
	.popover {
		position: absolute;
		z-index: 50;
		width: 18rem;
		padding: 0.75rem;
		background: #fff;
		border-radius: 0.5rem;
		box-shadow: var(--shadow-lg);
		outline: 1px solid var(--gray-200);
		outline-offset: -1px;
	}
	.popover-up {
		bottom: 100%;
		left: 0;
		margin-bottom: 0.5rem;
	}
	.popover-down {
		top: 100%;
		right: 0;
		margin-top: 0.5rem;
	}
	.popover-arrow {
		position: absolute;
		width: 0.75rem;
		height: 0.75rem;
		background: #fff;
		transform: rotate(45deg);
		outline: 1px solid var(--gray-200);
	}
	.popover-arrow-up {
		bottom: -0.375rem;
		left: 1rem;
		clip-path: polygon(100% 0, 100% 100%, 0 100%);
	}
	.popover-arrow-down {
		top: -0.375rem;
		right: 1rem;
		clip-path: polygon(0 0, 100% 0, 0 100%);
	}
	.popover-desc {
		margin-bottom: 0.5rem;
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--gray-500);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.popover-list {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.popover-link {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.25rem 0.5rem;
		border-radius: 0.25rem;
		font-size: 0.75rem;
		color: var(--brand-700);
		transition: background-color 0.15s, color 0.15s;
	}
	.popover-link:hover {
		background: var(--brand-50);
		color: var(--brand-800);
	}
</style>
