<script lang="ts">
	import { getContext } from 'svelte';
	import { systemTheme, theme } from '$lib/stores';

	const i18n = getContext<import('svelte/store').Writable<import('i18next').i18n>>('i18n');

	$: isGerman = $i18n.language?.startsWith('de');
	$: isDarkMode =
		$theme.includes('dark') || ($theme === 'system' && $systemTheme === 'dark');
	$: bannerSrc = isGerman
		? isDarkMode
			? '/signup-banner-de-dark.png'
			: '/signup-banner-de.png'
		: isDarkMode
			? '/signup-banner-en-dark.png'
			: '/signup-banner-en.png';
	$: bannerAlt = isGerman
		? 'Beyond the Loop – Eine Plattform, alle KI-Modelle'
		: 'Beyond the Loop – One platform, all AI models';
</script>

<div class="flex h-full min-h-screen items-center justify-center bg-[#F7F7F8] p-8 dark:bg-customGray-950">
	<img
		src={bannerSrc}
		alt={bannerAlt}
		class="max-h-[calc(100vh-4rem)] w-auto object-contain"
	/>
</div>
