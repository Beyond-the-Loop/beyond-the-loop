<script lang="ts">
	import { page } from '$app/state';
	import { onMount, getContext } from 'svelte';
	import { theme, systemTheme } from '$lib/stores';

	const i18n = getContext('i18n');

	let logoSrc: string = '/logo_light_transparent.png';

	let errorId = page.status;
	let errorMessage = page.error.message;
	// Deactivate Comments for Test
	// errorId = 500;
	// errorMessage = 'Internal Server Error';

	const ERROR_MESSAGES: Record<number, string> = {
		'404': `This page doesn't exist. Please navigate {{link}}back to Beyond Chat{{_link}}.`,
		'500': 'Beyond Chat is temporarily unavailable. Please try refreshing.'
	};

	onMount(() => {
		const theme: string = $theme === 'system' ? $systemTheme : $theme;
		const isDark: boolean = theme === 'dark';
		logoSrc = isDark ? '/logo_dark_transparent.png' : '/logo_light_transparent.png';
	});
</script>

<div class="dark:bg-customGray-800 min-h-screen flex mb-16">
	<div
		class="flex-grow dark:text-gray-200 text-center flex justify-center flex-col space-y-4 mx-4 mb-32"
	>
		<a href="/">
			<img
				crossorigin="anonymous"
				src={logoSrc}
				class="rounded-full size-16 mx-auto"
				alt="Beyond The Loop Logo"
			/>
		</a>
		<div>
			<div class="text-xl md:text-2xl font-normal mb-2">
				{#if errorId in ERROR_MESSAGES}
					{@html $i18n.t(ERROR_MESSAGES[errorId], {
						link: '<a href=\"/\" class=\"underline text-gray-800 dark:text-gray-100\">',
						_link: '</a>'
					})}
				{:else}
					{$i18n.t('Unexpected system error. Please contact your administrator.')}
				{/if}
			</div>

			<div class="text-medium text-gray-500 dark:text-gray-500 flex flex-col">
				{#if errorId != 500}
					{errorId}: {errorMessage}
				{:else}
					<div
						class="relative md:w-[300px] h-[6px] bg-gray-200 dark:bg-gray-700 mx-auto rounded-full mt-3"
					>
						<div
							class="absolute h-full bg-gray-800 dark:bg-gray-200 rounded-full
									animate-[bounceWidth_5s_cubic-bezier(0.4,0,0.2,1)_infinite]"
						></div>
					</div>
					<style>
						@keyframes bounceWidth {
							0%,
							100% {
								width: 30%;
								left: 0;
							}

							25% {
								width: 70%;
								left: 15%;
							}

							50% {
								width: 30%;
								left: 70%;
							}

							75% {
								width: 60%;
								left: 15%;
							}
						}
					</style>
				{/if}
			</div>
		</div>
	</div>
</div>
