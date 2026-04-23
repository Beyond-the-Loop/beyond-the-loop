<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import { WEBUI_NAME, showToast } from '$lib/stores';
	import LoaderIcon from '$lib/components/icons/LoaderIcon.svelte';
	import OtpInput from './shared/OtpInput.svelte';
	import StepHeader from './shared/StepHeader.svelte';
	import { createUser } from '$lib/apis/users';
	import { validateVerifyStep } from '$lib/utils/input-validation';

	const i18n = getContext<import('svelte/store').Writable<import('i18next').i18n>>('i18n');
	const CODE_LENGTH = 9;
	const dispatch = createEventDispatcher();

	export let email = '';
	export let registration_code = '';
	export let step = 2;
	export let totalSteps = 5;

	let loading = false;
	let codeError = '';

	async function handleSubmit() {
		const errors = validateVerifyStep({ code: registration_code, codeLength: CODE_LENGTH });
		if (errors) {
			codeError = $i18n.t(errors.code ?? '');
			return;
		}
		codeError = '';
		dispatch('next');
	}

	async function handleResend() {
		loading = true;
		await createUser(email)
			.then(() => showToast('success', $i18n.t('Code has been resent.')))
			.catch((error) => showToast('error', error))
			.finally(() => (loading = false));
	}
</script>

<svelte:head>
	<title>{$WEBUI_NAME}</title>
</svelte:head>

<form on:submit|preventDefault={handleSubmit}>
	<StepHeader {step} {totalSteps} on:back />

	<h1 class="text-2xl font-semibold text-[#16181D] dark:text-customGray-100">{$i18n.t('Verify email')}</h1>
	<p class="mt-2 text-sm text-[#6B7280] dark:text-customGray-300">
		{$i18n.t("We've sent a 9-digit code to")} <span class="font-semibold text-[#16181D] dark:text-customGray-100">{email}</span> {$i18n.t('sent')}.
	</p>

	<div class="mt-6">
		<OtpInput length={CODE_LENGTH} bind:value={registration_code} on:change={() => (codeError = '')} />
		{#if codeError}
			<p class="mt-1.5 text-xs text-red-500">{codeError}</p>
		{/if}
	</div>

	<button
		class="mt-6 flex h-12 w-full items-center justify-center rounded-lg bg-[#F1F1F1] text-sm font-medium text-[#16181D] transition hover:bg-[#E8E8E8] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-customGray-800 dark:text-customGray-200 dark:hover:bg-customGray-700"
		type="submit"
		disabled={loading}
	>
		{$i18n.t('Confirm')}
		{#if loading}
			<div class="ml-1.5">
				<LoaderIcon />
			</div>
		{/if}
	</button>

	<p class="mt-4 text-center text-sm text-[#6B7280] dark:text-customGray-300">
		{$i18n.t("Didn't receive a code?")}
		<button type="button" on:click={handleResend} disabled={loading} class="font-medium text-customBlue-600 hover:underline disabled:opacity-60">{$i18n.t('Resend')}</button>
	</p>
</form>
