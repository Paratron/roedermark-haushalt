<script lang="ts">
	interface Props {
		title: string;
		description: string;
		path?: string;
		image?: string;
	}

	const SITE_URL = 'https://roedermark-haushalt.christian-engel.dev';

	let { title, description, path = '', image }: Props = $props();

	let ogImage = $derived(image ? `${SITE_URL}/${image}` : `${SITE_URL}/social-share.jpg`);
	let fullTitle = $derived(
		title === 'Haushalt Rödermark'
			? 'Haushalt Rödermark – Kommunale Finanzdaten'
			: `${title} – Haushalt Rödermark`
	);
	let canonicalUrl = $derived(`${SITE_URL}${path}`);
</script>

<svelte:head>
	<title>{fullTitle}</title>
	<meta name="description" content={description} />

	<!-- Open Graph -->
	<meta property="og:type" content="website" />
	<meta property="og:title" content={fullTitle} />
	<meta property="og:description" content={description} />
	<meta property="og:image" content={ogImage} />
	<meta property="og:url" content={canonicalUrl} />
	<meta property="og:site_name" content="Haushalt Rödermark" />
	<meta property="og:locale" content="de_DE" />

	<!-- Twitter Card -->
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content={fullTitle} />
	<meta name="twitter:description" content={description} />
	<meta name="twitter:image" content={ogImage} />

	<!-- Canonical -->
	<link rel="canonical" href={canonicalUrl} />
</svelte:head>
