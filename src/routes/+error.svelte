<script lang="ts">
	import { page } from '$app/state';
	import { onMount, getContext } from 'svelte';
	import { theme, systemTheme } from '$lib/stores';
	import { goto } from '$app/navigation';
	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext('i18n');

	let errorId = page.status;
	let errorMessage = page.error.message;
	// errorId = 500;
	// errorMessage = 'Internal Server Error';

	let logoSrc = '/logo_light_transparent.png';
	let buttonClicked = false;

	function navigateHome () {
		buttonClicked = true;
		goto('/');
	}

	onMount(() => {
		const theme: string = $theme === 'system' ? $systemTheme : $theme;
		const isDark: boolean = theme === 'dark';
		logoSrc = isDark ? '/logo_dark_transparent.png' : '/logo_light_transparent.png';
	});
</script>

<div class="flex h-screen w-full dark:bg-[#111111] bg-lightGray-200 items-center justify-center">
	<div class="flex flex-col items-center gap-6">
		<a href="/">
			<img
				crossorigin="anonymous"
				src={logoSrc}
				class="size-16 mx-auto -mb-2"
				alt="Beyond The Loop Logo"
			/>
		</a>
		<h1 class="text-2xl font-semibold text-black dark:text-white text-center -mb-2">
				<!-- Etwas ist schiefgelaufen -->
				{#if errorId == 404} 
					404: {$i18n.t('Page not found')}
				{:else}
					{$i18n.t('Something went wrong')}
				{/if} 
			</h1>
		<p class="text-sm text-[#666] text-center leading-[1.65] max-w-[380px] ">
				{#if errorId == 404} 
					{$i18n.t('Return to Beyond Chat or contact our support if this is an error.')}
				{:else}
					{$i18n.t('There is currently a temporary disruption. We are working on it — please try again in a moment.')}
				{/if} 	
		</p>
		<button class="relative px-5 py-2 rounded-md bg-customBlue-500 hover:bg-customBlue-600 text-sm font-medium text-white transition-colors duration-150" on:click={navigateHome}>
			{#if errorId == 404} 
				{$i18n.t('Return to Beyond Chat')}
			{:else}
				{$i18n.t('Try again')}
			{/if} 
			{#if buttonClicked}
				<div class="dark:text-white text-black absolute top-2 -right-8">
					<Spinner />
				</div>
			{/if}
			
		</button>
	</div>
</div>
