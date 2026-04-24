<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import { WEBUI_NAME, showToast } from '$lib/stores';
	import { BILLING_COUNTRY_OPTIONS } from '$lib/constants';
	import LoaderIcon from '$lib/components/icons/LoaderIcon.svelte';
	import StepHeader from './shared/StepHeader.svelte';
	import { validateWorkspaceStep } from '$lib/utils/input-validation';

	const i18n = getContext<import('svelte/store').Writable<import('i18next').i18n>>('i18n');

	const INPUT_CLASSES =
		'h-11 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 text-sm text-[#16181D] outline-none transition focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-800 dark:text-white';

	const dispatch = createEventDispatcher();

	export let workspace_name = '';
	export let workspace_logo = '';
	export let subdomain = '';
	export let billing_country = 'Deutschland';
	export let step = 4;
	export let totalSteps = 5;
	export let showBack = true;
	export let loading = false;

	let logoInputRef: HTMLInputElement;

	$: initial = workspace_name ? workspace_name.charAt(0).toUpperCase() : '';

	function handleLogoUpload() {
		const files = logoInputRef?.files ?? [];
		if (files.length === 0) return;

		const file = files[0];
		if (!['image/jpeg', 'image/png'].includes(file.type)) {
			showToast('error', $i18n.t('Only PNG and JPG files are supported.'));
			return;
		}
		if (file.size > 10 * 1024 * 1024) {
			showToast('error', $i18n.t('File must be under 10MB.'));
			return;
		}

		const reader = new FileReader();
		reader.onload = (event) => {
			const img = new Image();
			img.src = event.target?.result as string;
			img.onload = () => {
				const canvas = document.createElement('canvas');
				const ctx = canvas.getContext('2d');
				const size = 400;
				canvas.width = size;
				canvas.height = size;
				const scale = Math.max(size / img.width, size / img.height);
				const x = (size - img.width * scale) / 2;
				const y = (size - img.height * scale) / 2;
				ctx?.drawImage(img, x, y, img.width * scale, img.height * scale);
				workspace_logo = canvas.toDataURL('image/jpeg');
			};
		};
		reader.readAsDataURL(file);
	}

	let workspaceNameError = '';
	let subdomainError = '';

	function handleSubmit() {
		workspaceNameError = '';
		if (!workspace_name.trim()) {
			workspaceNameError = $i18n.t('Workspace name is required.');
			return;
		}
		dispatch('next');
	}
</script>

<svelte:head>
	<title>{$WEBUI_NAME}</title>
</svelte:head>

<input bind:this={logoInputRef} type="file" hidden accept="image/png,image/jpeg" on:change={handleLogoUpload} />

<form on:submit|preventDefault={handleSubmit}>
	<StepHeader {step} {totalSteps} {showBack} on:back />

	<h1 class="text-2xl font-semibold text-[#16181D] dark:text-customGray-100">{$i18n.t('Create workspace')}</h1>
	<p class="mt-2 text-base text-[#6B7280] dark:text-customGray-300">{$i18n.t('Set up your team workspace.')}</p>

	<div class="mt-6">
		<label class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
			{$i18n.t('Workspace logo')}
		</label>
		<div class="flex items-center gap-4">
			<button
				type="button"
				on:click={() => logoInputRef?.click()}
				class="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl"
			>
				{#if workspace_logo}
					<img src={workspace_logo} alt="logo" class="h-14 w-14 rounded-xl object-cover" />
				{:else}
					<div class="flex h-14 w-14 items-center justify-center rounded-xl bg-customBlue-500 text-xl font-bold text-white">
						{initial}
					</div>
				{/if}
			</button>
			<div>
				<button
					type="button"
					on:click={() => logoInputRef?.click()}
					class="flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-[#16181D] transition hover:bg-gray-50 dark:border-customGray-700 dark:text-customGray-200 dark:hover:bg-customGray-800"
				>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
						<path d="M9.25 13.25a.75.75 0 001.5 0V4.636l2.955 3.129a.75.75 0 001.09-1.03l-4.25-4.5a.75.75 0 00-1.09 0l-4.25 4.5a.75.75 0 101.09 1.03L9.25 4.636v8.614z" />
						<path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
					</svg>
					{$i18n.t('Upload image')}
				</button>
				<p class="mt-1 text-xs text-[#6B7280] dark:text-customGray-300">
					PNG, JPG {$i18n.t('up to')} 10MB, {$i18n.t('min.')} 400x400px
				</p>
			</div>
		</div>
	</div>

	<div class="mt-4">
		<label for="workspace-name" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
			{$i18n.t('Workspace name')}
		</label>
		<input
			id="workspace-name"
			class="{INPUT_CLASSES} placeholder:text-gray-400 dark:placeholder:text-customGray-300{workspaceNameError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
			bind:value={workspace_name}
			autocomplete="organization"
			on:input={() => (workspaceNameError = '')}
		/>
		{#if workspaceNameError}
			<p class="mt-1.5 text-xs text-red-500">{workspaceNameError}</p>
		{/if}
	</div>

	<!-- Subdomain (deaktiviert)
	<div class="mt-4">
		<label for="subdomain" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
			{$i18n.t('Subdomain')}
		</label>
		<div class="flex">
			<input
				id="subdomain"
				class="{INPUT_CLASSES} rounded-r-none placeholder:text-gray-400 dark:placeholder:text-customGray-300{subdomainError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
				bind:value={subdomain}
				on:input={() => (subdomainError = '')}
			/>
			<span class="flex shrink-0 items-center whitespace-nowrap rounded-r-lg border border-l-0 border-gray-200 bg-gray-50 px-3 text-sm text-[#6B7280] dark:border-customGray-700 dark:bg-customGray-800 dark:text-customGray-300">
				.chat.beyondtheloop.ai
			</span>
		</div>
		{#if subdomainError}
			<p class="mt-1.5 text-xs text-red-500">{subdomainError}</p>
		{/if}
	</div>
	-->

	<div class="mt-4">
		<label for="billing-country" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
			{$i18n.t('Billing country')}
		</label>
		<select
			id="billing-country"
			class={INPUT_CLASSES + ' appearance-none bg-no-repeat bg-[length:20px] bg-[right_12px_center] bg-[url("data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2020%2020%27%20fill%3D%27%236B7280%27%3E%3Cpath%20fill-rule%3D%27evenodd%27%20d%3D%27M5.23%207.21a.75.75%200%20011.06.02L10%2011.168l3.71-3.938a.75.75%200%20111.08%201.04l-4.25%204.5a.75.75%200%2001-1.08%200l-4.25-4.5a.75.75%200%2001.02-1.06z%27%20clip-rule%3D%27evenodd%27/%3E%3C/svg%3E")]'}
			bind:value={billing_country}
		>
			{#each BILLING_COUNTRY_OPTIONS as country}
				<option value={country}>{$i18n.t(country)}</option>
			{/each}
		</select>
	</div>

	<button
		class="mt-6 flex h-12 w-full items-center justify-center rounded-lg bg-[#F1F1F1] text-sm font-medium text-[#16181D] transition hover:bg-[#E8E8E8] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-customGray-800 dark:text-customGray-200 dark:hover:bg-customGray-700"
		type="submit"
		disabled={loading}
	>
		{$i18n.t('Continue')}
		{#if loading}
			<div class="ml-1.5">
				<LoaderIcon />
			</div>
		{/if}
	</button>
</form>
