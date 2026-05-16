<script lang="ts">
	import type { Snippet } from 'svelte';
	import { getOpenId, setOpenId } from './popover-state.svelte.js';
	import { tick } from 'svelte';

	interface Props {
		/** The trigger button content */
		trigger: Snippet;
		/** The popover body content */
		children: Snippet;
		/** Opens upward (default) or downward */
		direction?: 'up' | 'down';
		/** Max width of the popover panel */
		maxWidth?: string;
	}

	let {
		trigger,
		children,
		direction = 'down',
		maxWidth = '18rem',
	}: Props = $props();

	const instanceId = Symbol();
	let triggerEl: HTMLButtonElement | undefined = $state();
	let popoverEl: HTMLDivElement | undefined = $state();
	let popoverStyle = $state('');

	let open = $derived(getOpenId() === instanceId);

	function position() {
		if (!triggerEl || !popoverEl) return;
		const rect = triggerEl.getBoundingClientRect();
		const pw = popoverEl.offsetWidth;
		const ph = popoverEl.offsetHeight;

		// Vertical: prefer requested direction, flip if no room
		let goUp = direction === 'up';
		if (goUp && rect.top - ph - 8 < 0) goUp = false;
		if (!goUp && rect.bottom + ph + 8 > window.innerHeight) goUp = true;

		const top = goUp ? rect.top - ph - 8 : rect.bottom + 8;

		// Horizontal: center on trigger, clamp to viewport
		let left = rect.left + rect.width / 2 - pw / 2;
		left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));

		popoverStyle = `top:${top}px;left:${left}px;--popover-max-w:${maxWidth}`;
		popoverEl.dataset.dir = goUp ? 'up' : 'down';
	}

	async function toggle(e: MouseEvent) {
		e.stopPropagation();
		if (open) {
			setOpenId(null);
		} else {
			setOpenId(instanceId);
			await tick();
			position();
		}
	}

	function handleClickOutside(e: MouseEvent) {
		if (!open) return;
		const target = e.target as Node;
		if (triggerEl?.contains(target)) return;
		if (popoverEl?.contains(target)) return;
		setOpenId(null);
	}

	function handleScroll() {
		if (open) setOpenId(null);
	}
</script>

<svelte:document onclick={handleClickOutside} onscroll={handleScroll} />
<svelte:window onresize={handleScroll} />

<button type="button" class="popover-trigger" bind:this={triggerEl} onclick={toggle}>
	{@render trigger()}
</button>

{#if open}
	<div
		class="popover"
		bind:this={popoverEl}
		style={popoverStyle}
	>
		{@render children()}
	</div>
{/if}

<style>
	.popover-trigger {
		display: inline-flex;
		align-items: center;
		vertical-align: middle;
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		color: inherit;
		font: inherit;
	}
	.popover {
		position: fixed;
		z-index: 100;
		width: var(--popover-max-w, 18rem);
		max-width: calc(100vw - 1rem);
		padding: 0.75rem;
		background: #fff;
		border-radius: 0.5rem;
		box-shadow: var(--shadow-lg);
		outline: 1px solid var(--gray-200);
		outline-offset: -1px;
		word-wrap: break-word;
		overflow-wrap: break-word;
		white-space: normal;
	}
</style>
