<script lang="ts">
	import { createEventDispatcher, getContext, onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { WEBUI_NAME, showToast } from '$lib/stores';
	import LoaderIcon from '$lib/components/icons/LoaderIcon.svelte';
	import { inviteUsers } from '$lib/apis/auths';
	import StepHeader from './shared/StepHeader.svelte';

	const i18n = getContext<import('svelte/store').Writable<import('i18next').i18n>>('i18n');

	const ROLES = ['Member', 'Admin'] as const;

	const INPUT_CLASSES =
		'h-11 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 text-sm text-[#16181D] outline-none transition focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-900 dark:text-white';

	const dispatch = createEventDispatcher();

	export let step = 5;
	export let totalSteps = 5;
	export let loading = false;

	let email = '';
	let role: (typeof ROLES)[number] = 'Member';
	let dropdownOpen = false;
	let dropdownRef: HTMLDivElement;

	const isValidEmail = (val: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim());

	function selectRole(r: (typeof ROLES)[number]) {
		role = r;
		dropdownOpen = false;
	}

	function handleClickOutside(e: MouseEvent) {
		if (dropdownRef && !dropdownRef.contains(e.target as Node)) {
			dropdownOpen = false;
		}
	}

	onMount(() => {
		document.addEventListener('click', handleClickOutside, true);
	});

	onDestroy(() => {
		document.removeEventListener('click', handleClickOutside, true);
	});

	async function handleInvite() {
		if (!email.trim() || !isValidEmail(email)) {
			showToast('error', $i18n.t('Please enter a valid email address.'));
			return;
		}

		loading = true;
		const invitees = [{ email: email.trim().toLowerCase(), role: role.toLowerCase() === 'admin' ? 'admin' : 'user' }];
		await inviteUsers(localStorage.token, invitees, null, null).catch((error) => {
			showToast('error', typeof error === 'string' ? error : $i18n.t('An error occurred.'));
		});
		loading = false;
		goto('/');
	}

	function handleSkip() {
		goto('/');
	}
</script>

<svelte:head>
	<title>{$WEBUI_NAME}</title>
</svelte:head>

<form on:submit|preventDefault={handleInvite}>
	<StepHeader {step} {totalSteps} on:back />

	<h1 class="text-2xl font-semibold text-[#16181D] dark:text-customGray-100">{$i18n.t('Collaborate with your team')}</h1>
	<p class="mt-2 text-base text-[#6B7280] dark:text-customGray-300">
		{$i18n.t('The more team members use Beyond the Loop, the more powerful it becomes.')}
	</p>

	<div class="mt-6 flex items-center gap-3">
		<input
			class={INPUT_CLASSES + ' min-w-0 flex-[3] placeholder:text-gray-400 dark:placeholder:text-customGray-300'}
			placeholder="beispiel@email.com"
			bind:value={email}
			type="email"
			autocomplete="email"
		/>

		<!-- Custom role dropdown -->
		<div class="relative w-[7.5rem] shrink-0" bind:this={dropdownRef}>
			<button
				type="button"
				class="h-11 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 pr-9 text-left text-sm text-[#16181D] outline-none transition hover:border-gray-300 focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-900 dark:text-white dark:hover:border-customGray-600"
				on:click={() => (dropdownOpen = !dropdownOpen)}
			>
				{role}
				<svg
					class="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6B7280] transition-transform {dropdownOpen ? 'rotate-180' : ''}"
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
				>
					<path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
				</svg>
			</button>

			{#if dropdownOpen}
				<div class="absolute left-0 right-0 top-[calc(100%+4px)] z-50 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg dark:border-customGray-700 dark:bg-customGray-800">
					{#each ROLES as r}
						<button
							type="button"
							class="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm transition
								{r === role
									? 'bg-gray-100 font-medium text-[#16181D] dark:bg-customGray-700 dark:text-white'
									: 'text-[#6B7280] hover:bg-gray-50 dark:text-customGray-300 dark:hover:bg-customGray-700'}"
							on:click={() => selectRole(r)}
						>
							{#if r === role}
								<svg class="h-4 w-4 shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
									<path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" />
								</svg>
							{:else}
								<span class="h-4 w-4 shrink-0"></span>
							{/if}
							{r}
						</button>
					{/each}
				</div>
			{/if}
		</div>
	</div>

	<button
		class="mt-6 flex h-12 w-full items-center justify-center rounded-lg bg-[#F1F1F1] text-sm font-medium text-[#16181D] transition hover:bg-[#E8E8E8] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-customGray-900 dark:text-customGray-200 dark:hover:bg-customGray-950"
		type="submit"
		disabled={loading}
	>
		{$i18n.t('Send invitations')}
		{#if loading}
			<div class="ml-1.5">
				<LoaderIcon />
			</div>
		{/if}
	</button>

	<p class="mt-4 text-center text-sm text-[#6B7280] dark:text-customGray-300">
		<button type="button" on:click={handleSkip} class="font-medium text-customBlue-500 hover:underline">
			{$i18n.t('Skip for now')}
		</button>
	</p>
</form>
