<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import { WEBUI_NAME } from '$lib/stores';
	import { POSITION_OPTIONS } from '$lib/constants';
	import StepHeader from './shared/StepHeader.svelte';
	import { validatePersonalStep } from '$lib/utils/input-validation';

	const i18n = getContext<import('svelte/store').Writable<import('i18next').i18n>>('i18n');

	const INPUT_CLASSES =
		'h-12 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 text-sm text-[#16181D] outline-none transition focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-900 dark:text-white';

	const dispatch = createEventDispatcher();

	export let first_name = '';
	export let last_name = '';
	export let position = '';
	export let phone = '';
	export let step = 3;
	export let totalSteps = 5;

	let firstNameError = '';
	let lastNameError = '';
	let positionError = '';
	let phoneError = '';

	function handleSubmit() {
		const errors = validatePersonalStep({ first_name, last_name, position, phone });
		if (errors) {
			firstNameError = $i18n.t(errors.firstName ?? '');
			lastNameError = $i18n.t(errors.lastName ?? '');
			positionError = $i18n.t(errors.position ?? '');
			phoneError = $i18n.t(errors.phone ?? '');
			return;
		}
		firstNameError = lastNameError = positionError = phoneError = '';
		dispatch('next');
	}
</script>

<svelte:head>
	<title>{$WEBUI_NAME}</title>
</svelte:head>

<form on:submit|preventDefault={handleSubmit}>
	<StepHeader {step} {totalSteps} on:back />

	<h1 class="text-2xl font-semibold text-[#16181D] dark:text-customGray-100">{$i18n.t('About you')}</h1>
	<p class="mt-2 text-base text-[#6B7280] dark:text-customGray-300">{$i18n.t('Tell us a bit about yourself.')}</p>

	<div class="mt-6 grid grid-cols-2 gap-3">
		<div>
			<label for="first-name" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
				{$i18n.t('First name')}
			</label>
			<input
				id="first-name"
				class="{INPUT_CLASSES} placeholder:text-gray-400 dark:placeholder:text-customGray-300{firstNameError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
				placeholder="Max"
				bind:value={first_name}
				autocomplete="given-name"
				on:input={() => (firstNameError = '')}
			/>
			{#if firstNameError}
				<p class="mt-1.5 text-xs text-red-500">{firstNameError}</p>
			{/if}
		</div>
		<div>
			<label for="last-name" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
				{$i18n.t('Last name')}
			</label>
			<input
				id="last-name"
				class="{INPUT_CLASSES} placeholder:text-gray-400 dark:placeholder:text-customGray-300{lastNameError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
				placeholder="Mustermann"
				bind:value={last_name}
				autocomplete="family-name"
				on:input={() => (lastNameError = '')}
			/>
			{#if lastNameError}
				<p class="mt-1.5 text-xs text-red-500">{lastNameError}</p>
			{/if}
		</div>
	</div>

	<div class="mt-4">
		<label for="position" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
			{$i18n.t('Position')}
		</label>
		<select
			id="position"
			class="{INPUT_CLASSES} appearance-none bg-no-repeat bg-[length:20px] bg-[right_12px_center] bg-[url('data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2020%2020%27%20fill%3D%27%236B7280%27%3E%3Cpath%20fill-rule%3D%27evenodd%27%20d%3D%27M5.23%207.21a.75.75%200%20011.06.02L10%2011.168l3.71-3.938a.75.75%200%20111.08%201.04l-4.25%204.5a.75.75%200%2001-1.08%200l-4.25-4.5a.75.75%200%2001.02-1.06z%27%20clip-rule%3D%27evenodd%27/%3E%3C/svg%3E')]{positionError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
			bind:value={position}
			on:change={() => (positionError = '')}
		>
			<option value="" disabled selected>{$i18n.t('Select position')}</option>
			{#each POSITION_OPTIONS as pos}
				<option value={pos}>{$i18n.t(pos)}</option>
			{/each}
		</select>
		{#if positionError}
			<p class="mt-1.5 text-xs text-red-500">{positionError}</p>
		{/if}
	</div>

	<div class="mt-4">
		<label for="phone" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
			{$i18n.t('Phone number')}
		</label>
		<input
			id="phone"
			class="{INPUT_CLASSES} placeholder:text-gray-400 dark:placeholder:text-customGray-300{phoneError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
			placeholder="+49 123 456789"
			bind:value={phone}
			type="tel"
			autocomplete="tel"
			on:input={() => (phoneError = '')}
		/>
		{#if phoneError}
			<p class="mt-1.5 text-xs text-red-500">{phoneError}</p>
		{/if}
	</div>

	<button
		class="mt-6 flex h-12 w-full items-center justify-center rounded-lg bg-[#F1F1F1] text-sm font-medium text-[#16181D] transition hover:bg-[#E8E8E8] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-customGray-900 dark:text-customGray-200 dark:hover:bg-customGray-950"
		type="submit"
	>
		{$i18n.t('Continue')}
	</button>
</form>
