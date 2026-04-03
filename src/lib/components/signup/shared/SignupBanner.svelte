<script lang="ts">
	import { getContext } from 'svelte';

	const i18n = getContext<import('svelte/store').Writable<import('i18next').i18n>>('i18n');

	$: isGerman = $i18n.language?.startsWith('de');
	$: bannerSrc = isGerman ? '/signup-banner-de.png' : '/signup-banner-en.png';
	$: bannerAlt = isGerman
		? 'Beyond the Loop – Eine Plattform, alle KI-Modelle'
		: 'Beyond the Loop – One platform, all AI models';
</script>

<div class="flex h-full min-h-screen items-center justify-center bg-[#F7F7F8] p-8 dark:bg-customGray-900">
	<img
		src={bannerSrc}
		alt={bannerAlt}
		class="max-h-[calc(100vh-4rem)] w-auto object-contain"
	/>
</div>
