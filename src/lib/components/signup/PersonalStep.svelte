<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import { WEBUI_NAME } from '$lib/stores';
	import { POSITION_OPTIONS } from '$lib/constants';
	import StepHeader from './shared/StepHeader.svelte';
	import PhoneInput from './shared/PhoneInput.svelte';
	import { validatePersonalStep } from '$lib/utils/input-validation';

	const i18n = getContext<import('svelte/store').Writable<import('i18next').i18n>>('i18n');

	const INPUT_CLASSES =
		'h-12 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 text-sm text-[#16181D] outline-none transition focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-900 dark:text-white';

	const dispatch = createEventDispatcher();

	export let first_name = '';
	export let last_name = '';
	export let password = '';
	export let position = '';
	export let phone = '';
	export let step = 3;
	export let totalSteps = 5;

	let confirmPassword = '';
	let firstNameError = '';
	let lastNameError = '';
	let passwordError = '';
	let confirmPasswordError = '';
	let positionError = '';
	let phoneError = '';
	let showPassword = false;
	let showConfirmPassword = false;

	function handleSubmit() {
		confirmPasswordError = '';
		const errors = validatePersonalStep({ first_name, last_name, password, position, phone });
		if (errors) {
			firstNameError = $i18n.t(errors.firstName ?? '');
			lastNameError = $i18n.t(errors.lastName ?? '');
			passwordError = $i18n.t(errors.password ?? '');
			positionError = $i18n.t(errors.position ?? '');
			phoneError = $i18n.t(errors.phone ?? '');
			return;
		}
		if (password !== confirmPassword) {
			confirmPasswordError = $i18n.t('Passwords do not match.');
			return;
		}
		firstNameError = lastNameError = passwordError = confirmPasswordError = positionError = phoneError = '';
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
		<label for="password" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
			{$i18n.t('Password')}
		</label>
		<div class="relative">
			{#if showPassword}
				<input
					id="password"
					class="{INPUT_CLASSES} placeholder:text-gray-400 dark:placeholder:text-customGray-300 pr-12{passwordError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
					type="text"
					placeholder={$i18n.t('Create password')}
					bind:value={password}
					autocomplete="new-password"
					on:input={() => (passwordError = '')}
				/>
			{:else}
				<input
					id="password"
					class="{INPUT_CLASSES} placeholder:text-gray-400 dark:placeholder:text-customGray-300 pr-12{passwordError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
					type="password"
					placeholder={$i18n.t('Create password')}
					bind:value={password}
					autocomplete="new-password"
					on:input={() => (passwordError = '')}
				/>
			{/if}
			<button
				type="button"
				class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
				on:click={() => (showPassword = !showPassword)}
			>
				{#if showPassword}
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
						<path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12c1.292 4.338 5.31 7.5 10.066 7.5.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
					</svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
						<path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
						<path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
					</svg>
				{/if}
			</button>
		</div>
		{#if passwordError}
			<p class="mt-1.5 text-xs text-red-500">{passwordError}</p>
		{/if}
	</div>

	<div class="mt-4">
		<label for="confirm-password" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
			{$i18n.t('Confirm password')}
		</label>
		<div class="relative">
			{#if showConfirmPassword}
				<input
					id="confirm-password"
					class="{INPUT_CLASSES} placeholder:text-gray-400 dark:placeholder:text-customGray-300 pr-12{confirmPasswordError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
					type="text"
					placeholder={$i18n.t('Confirm password')}
					bind:value={confirmPassword}
					autocomplete="new-password"
					on:input={() => {
						if (confirmPassword && confirmPassword !== password) {
							confirmPasswordError = $i18n.t('Passwords do not match.');
						} else {
							confirmPasswordError = '';
						}
					}}
				/>
			{:else}
				<input
					id="confirm-password"
					class="{INPUT_CLASSES} placeholder:text-gray-400 dark:placeholder:text-customGray-300 pr-12{confirmPasswordError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
					type="password"
					placeholder={$i18n.t('Confirm password')}
					bind:value={confirmPassword}
					autocomplete="new-password"
					on:input={() => {
						if (confirmPassword && confirmPassword !== password) {
							confirmPasswordError = $i18n.t('Passwords do not match.');
						} else {
							confirmPasswordError = '';
						}
					}}
				/>
			{/if}
			<button
				type="button"
				class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
				on:click={() => (showConfirmPassword = !showConfirmPassword)}
			>
				{#if showConfirmPassword}
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
						<path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12c1.292 4.338 5.31 7.5 10.066 7.5.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
					</svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
						<path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
						<path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
					</svg>
				{/if}
			</button>
		</div>
		{#if confirmPasswordError}
			<p class="mt-1.5 text-xs text-red-500">{confirmPasswordError}</p>
		{/if}
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
		<PhoneInput
			bind:value={phone}
			hasError={!!phoneError}
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
