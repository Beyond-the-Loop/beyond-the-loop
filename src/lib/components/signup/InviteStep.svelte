<script lang="ts">
	import { createEventDispatcher, getContext, onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { WEBUI_NAME } from '$lib/stores';
	import LoaderIcon from '$lib/components/icons/LoaderIcon.svelte';
	import { inviteUsers } from '$lib/apis/auths';
	import StepHeader from './shared/StepHeader.svelte';
	import { translateInviteError } from '$lib/utils/invite-error';

	const i18n = getContext<import('svelte/store').Writable<import('i18next').i18n>>('i18n');

	const ROLES = ['User', 'Admin'] as const;
	const MAX_INVITES = 5;

	const INPUT_CLASSES =
		'h-11 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 text-sm text-[#16181D] outline-none transition focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-800 dark:text-white';

	const dispatch = createEventDispatcher();

	export let step = 5;
	export let totalSteps = 5;
	export let loading = false;

	type InviteRow = { email: string; role: (typeof ROLES)[number] };

	let rows: InviteRow[] = [{ email: '', role: 'User' }];
	let openDropdownIndex: number | null = null;
	let dropdownRefs: HTMLDivElement[] = [];

	const isValidEmail = (val: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim());

	function handleEmailInput(index: number) {
		if (!rows[index].email.trim()) {
			rows = rows.slice(0, index + 1);
			return;
		}
		if (index === rows.length - 1 && rows.length < MAX_INVITES) {
			rows = [...rows, { email: '', role: 'User' }];
		}
	}

	function handleEmailBlur(index: number) {
		if (index > 0 && !rows[index].email.trim()) {
			const hasContentAfter = rows.slice(index + 1).some((r) => r.email.trim());
			if (!hasContentAfter) {
				rows = rows.slice(0, index);
			}
		}
	}

	function removeRow(index: number) {
		rows = rows.filter((_, i) => i !== index);
	}

	function selectRole(index: number, r: (typeof ROLES)[number]) {
		rows[index].role = r;
		rows = rows;
		openDropdownIndex = null;
	}

	function toggleDropdown(index: number) {
		openDropdownIndex = openDropdownIndex === index ? null : index;
	}

	function handleClickOutside(e: MouseEvent) {
		if (openDropdownIndex !== null) {
			const ref = dropdownRefs[openDropdownIndex];
			if (ref && !ref.contains(e.target as Node)) {
				openDropdownIndex = null;
			}
		}
	}

	onMount(() => {
		document.addEventListener('click', handleClickOutside, true);
	});

	onDestroy(() => {
		document.removeEventListener('click', handleClickOutside, true);
	});

	let inviteError = '';

	async function handleInvite() {
		inviteError = '';
		const filledRows = rows.filter((r) => r.email.trim());

		if (filledRows.length === 0) {
			inviteError = $i18n.t('Please enter at least one email address.');
			return;
		}

		const invalidRow = filledRows.find((r) => !isValidEmail(r.email));
		if (invalidRow) {
			inviteError = $i18n.t('Please enter a valid email address.');
			return;
		}

		loading = true;
		const invitees = filledRows.map((r) => ({
			email: r.email.trim().toLowerCase(),
			role: r.role.toLowerCase() === 'admin' ? 'admin' : 'user'
		}));
		await inviteUsers(localStorage.token, invitees, null, null).catch((error) => {
			inviteError = translateInviteError(error, (key) => $i18n.t(key));
		});
		loading = false;
		if (!inviteError) goto('/');
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
		{$i18n.t('Invite up to 5 team members and collaborate more efficiently with Beyond Chat.')}
	</p>

	<div class="mt-6 flex flex-col gap-3">
		{#each rows as row, index}
			<div class="flex items-center gap-3">
				<input
					class={INPUT_CLASSES + ' min-w-0 flex-[3] placeholder:text-gray-400 dark:placeholder:text-customGray-300'}
					placeholder={index === 0 ? 'beispiel@email.com' : $i18n.t('Add more members')}
					bind:value={row.email}
					type="email"
					autocomplete="email"
					on:input={() => handleEmailInput(index)}
					on:blur={() => handleEmailBlur(index)}
				/>

				<div class="relative w-[7.5rem] shrink-0" bind:this={dropdownRefs[index]}>
					<button
						type="button"
						class="h-11 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 pr-9 text-left text-sm text-[#16181D] outline-none transition hover:border-gray-300 focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-800 dark:text-white dark:hover:border-customGray-600"
						on:click={() => toggleDropdown(index)}
					>
						{$i18n.t(row.role)}
						<svg
							class="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6B7280] transition-transform {openDropdownIndex === index ? 'rotate-180' : ''}"
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 20 20"
							fill="currentColor"
						>
							<path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
						</svg>
					</button>

					{#if openDropdownIndex === index}
						<div class="absolute left-0 right-0 top-[calc(100%+4px)] z-50 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg dark:border-customGray-700 dark:bg-customGray-800">
							{#each ROLES as r}
								<button
									type="button"
									class="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm transition
										{r === row.role
											? 'bg-gray-100 font-medium text-[#16181D] dark:bg-customGray-700 dark:text-white'
											: 'text-[#6B7280] hover:bg-gray-50 dark:text-customGray-300 dark:hover:bg-customGray-700'}"
									on:click={() => selectRole(index, r)}
								>
									{#if r === row.role}
										<svg class="h-4 w-4 shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
											<path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" />
										</svg>
									{:else}
										<span class="h-4 w-4 shrink-0"></span>
									{/if}
									{$i18n.t(r)}
								</button>
							{/each}
						</div>
					{/if}
				</div>

				{#if rows.length > 1}
					<button
						type="button"
						class="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-gray-400 transition hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-customGray-800 dark:hover:text-gray-200"
						on:click={() => removeRow(index)}
					>
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="h-5 w-5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
						</svg>
					</button>
				{/if}
			</div>
		{/each}

	</div>

	<button
		class="mt-6 flex h-12 w-full items-center justify-center rounded-lg bg-[#F1F1F1] text-sm font-medium text-[#16181D] transition hover:bg-[#E8E8E8] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-customGray-800 dark:text-customGray-200 dark:hover:bg-customGray-700"
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

	{#if inviteError}
		<p class="mt-2 text-xs text-red-500">{inviteError}</p>
	{/if}

	<p class="mt-4 text-center text-sm text-[#6B7280] dark:text-customGray-300">
		<button type="button" on:click={handleSkip} class="font-medium text-customBlue-500 hover:underline">
			{$i18n.t('Skip for now')}
		</button>
	</p>
</form>
