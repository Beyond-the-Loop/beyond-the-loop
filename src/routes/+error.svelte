<script lang="ts">
	import { page } from '$app/state';
	import { onMount, getContext } from 'svelte';
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { theme, systemTheme } from '$lib/stores';

	const i18n = getContext('i18n');

	let logoSrc: string = '/logo_light_transparent.png';

	function onContact() {
		window.open('https://thoreduecker.notion.site/208a1ab099c980c1905eeccd32ea53cd', '_blank');
	}

	const ERROR_MESSAGES: Record<number, string> = {
		'404': `This page doesn't exist. Please navigate <a href="/" class="underline text-gray-800">back to base</a>.`,
		'500': 'Beyond The Loop is temporarily unavailable. Please try refreshing.'
	};

	onMount(() => {
		const theme: string = $theme === 'system' ? $systemTheme : $theme;
		const isDark: boolean = theme === 'dark';
		logoSrc = isDark ? '/logo_dark_transparent.png' : '/logo_light_transparent.png';
		console.log(page.status);
	});
</script>

<div class="bg-lightGray-550 dark:bg-customGray-800 min-h-screen flex mb-16">
	<div class="flex-grow dark:text-gray-300 text-center flex justify-center mb-32">
		<div class="flex flex-col justify-center space-y-4">
			<img
				crossorigin="anonymous"
				src={logoSrc}
				class="rounded-full w-16 h-16 mx-auto"
				alt="Beyond The Loop Logo"
			/>
			<div>
				<div class="text-2xl font-normal mb-2">
					{@html $i18n.t(ERROR_MESSAGES[page.status])}
				</div>
				<div class="text-sm text-gray-500 dark:text-gray-500">
					{page.status}: {page.error.message}
				</div>
			</div>

			<div class="mx-auto flex flex-row">
				<button
					class="rounded-mdx bg-lightGray-300 dark:bg-customGray-900 border-lightGray-400 text-lightGray-100 font-medium hover:bg-lightGray-700 dark:hover:bg-customGray-950 border dark:border-customGray-700 px-4 py-3 text-xs dark:text-customGray-200"
					on:click={onContact}
				>
					{$i18n.t('Contact support')}
				</button>
			</div>
		</div>
	</div>
</div>
