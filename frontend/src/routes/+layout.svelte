<script lang="ts">
	import '../app.css';
	import { Landmark, Menu, X } from '@lucide/svelte';
	import { page } from '$app/state';

	let { children } = $props();
	let mobileNavOpen = $state(false);

	const navItems = [
		{ href: '/', label: 'Übersicht' },
		{ href: '/kategorien', label: 'Einnahmen & Ausgaben' },
		{ href: '/ergebnishaushalt', label: 'Ergebnishaushalt' },
		{ href: '/finanzhaushalt', label: 'Finanzhaushalt' },
		{ href: '/teilhaushalte', label: 'Teilhaushalte' },
		{ href: '/investitionen', label: 'Investitionen' },
		{ href: '/steuern', label: 'Steuern' },
		{ href: '/schulden', label: 'Schulden & Zinsen' },
		{ href: '/explorer', label: 'Explorer' },
		{ href: '/quellen', label: 'Quellen' }
	];

	function isActive(href: string): boolean {
		const path = page.url.pathname;
		if (href === '/') return path === '/';
		return path.startsWith(href);
	}

	function handleNavClick() {
		mobileNavOpen = false;
	}
</script>

<div class="app-shell">
	<!-- Header -->
	<header class="app-header">
		<div class="container header-inner">
			<div class="header-top">
				<div class="header-brand">
					<h1>
						<a href="/" class="brand-link">
							<Landmark class="brand-icon" size={32} />
							<span>Haushalt Rödermark</span>
						</a>
					</h1>
					<p class="brand-sub">Interaktive Kommunale Finanzdaten</p>
				</div>
				<button
					class="burger-btn"
					onclick={() => mobileNavOpen = !mobileNavOpen}
					aria-label={mobileNavOpen ? 'Navigation schließen' : 'Navigation öffnen'}
					aria-expanded={mobileNavOpen}
				>
					{#if mobileNavOpen}
						<X size={24} />
					{:else}
						<Menu size={24} />
					{/if}
				</button>
			</div>
			<nav class="nav" class:nav-open={mobileNavOpen}>
				{#each navItems as item}
					<a
						href={item.href}
						class="nav-link"
						class:nav-active={isActive(item.href)}
						aria-current={isActive(item.href) ? 'page' : undefined}
						onclick={handleNavClick}
					>{item.label}</a>
				{/each}
			</nav>
		</div>
	</header>

	<!-- Main content -->
	<main class="container main-content">
		{@render children()}
	</main>

	<!-- Footer -->
	<footer class="app-footer">
		<div class="container footer-inner">
			<p>
				Datenquelle: <a href="https://www.roedermark.de" target="_blank" rel="noopener">Stadt Rödermark</a> – offizielle Haushaltspläne (PDF)
			</p>
			<p>
				Keine offizielle Seite der Stadt. Alle Angaben ohne Gewähr.
			</p>
		</div>
	</footer>
</div>

<style>
	.app-shell {
		min-height: 100vh;
		background: var(--gray-50);
	}
	.app-header {
		background: var(--brand-800);
		color: white;
		box-shadow: var(--shadow-lg);
	}
	.header-inner {
		padding-top: 0.75rem;
		padding-bottom: 0.75rem;
	}
	.header-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.brand-link {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 1.125rem;
		font-weight: 700;
		transition: color 0.15s;
	}
	.brand-link span {
		white-space: nowrap;
	}
	:global(.brand-icon) { min-width: 1.5rem; min-height: 1.5rem; }
	@media (min-width: 768px) {
		.brand-link { font-size: 1.5rem; }
	}
	.brand-link:hover {
		color: var(--brand-200);
	}
	.brand-sub {
		font-size: 0.75rem;
		color: var(--brand-200);
		display: none;
	}
	@media (min-width: 768px) {
		.brand-sub {
			display: block;
			font-size: 0.875rem;
		}
	}

	/* Hamburger button – visible on mobile only */
	.burger-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.75rem;
		height: 2.75rem;
		border: none;
		border-radius: 0.5rem;
		background: transparent;
		color: white;
		cursor: pointer;
		-webkit-tap-highlight-color: transparent;
	}
	.burger-btn:hover {
		background: var(--brand-700);
	}
	@media (min-width: 768px) {
		.burger-btn { display: none; }
	}

	/* Navigation */
	.nav {
		display: none;
		flex-direction: column;
		gap: 0.125rem;
		margin-top: 0.75rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--brand-700);
	}
	.nav-open {
		display: flex;
	}
	@media (min-width: 768px) {
		.nav {
			display: flex;
			flex-direction: row;
			flex-wrap: wrap;
			gap: 0.25rem;
			margin-top: 0.5rem;
			padding-top: 0;
			border-top: none;
		}
	}
	.nav-link {
		display: block;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		font-weight: 500;
		color: var(--brand-100);
		border-radius: 0.5rem;
		transition: background-color 0.15s, color 0.15s;
		-webkit-tap-highlight-color: transparent;
	}
	@media (min-width: 768px) {
		.nav-link {
			padding: 0.375rem 0.75rem;
			font-size: 0.875rem;
		}
	}
	.nav-link:hover {
		background: var(--brand-700);
		color: white;
	}
	.nav-active {
		background: var(--brand-700);
		color: white;
	}

	.main-content {
		padding-top: 1.5rem;
		padding-bottom: 2rem;
	}
	@media (min-width: 768px) {
		.main-content {
			padding-top: 2rem;
		}
	}
	.app-footer {
		margin-top: 4rem;
		border-top: 1px solid var(--gray-200);
		background: white;
	}
	.footer-inner {
		padding-top: 1.5rem;
		padding-bottom: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		font-size: 0.875rem;
		color: var(--gray-500);
	}
	@media (min-width: 640px) {
		.footer-inner {
			flex-direction: row;
			justify-content: space-between;
		}
	}
	.footer-inner a {
		text-decoration: underline;
	}
	.footer-inner a:hover {
		color: var(--gray-700);
	}
</style>
