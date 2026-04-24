<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import { Separator } from 'bits-ui';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { config } from '$lib/stores';
	import LoaderIcon from '$lib/components/icons/LoaderIcon.svelte';
	import AuthSocialButton from './shared/AuthSocialButton.svelte';
	import { createUser } from '$lib/apis/users';
	import { normalizeEmailValidationError, validateEmailStep } from '$lib/utils/input-validation';

	const i18n = getContext<import('svelte/store').Writable<import('i18next').i18n>>('i18n');
	const dispatch = createEventDispatcher();

	export let email = '';

	let loading = false;
	let emailError = '';

	async function registerEmail() {
		const errors = validateEmailStep({ email });
		if (errors) {
			emailError = $i18n.t(normalizeEmailValidationError(errors.email ?? ''));
			return;
		}
		emailError = '';

		loading = true;

		const user = await createUser(email)
			.catch((error) => {
				emailError = $i18n.t(normalizeEmailValidationError(error));
			})
			.finally(() => (loading = false));

		if (user) {
			dispatch('next', { email: user.email });
		}
	}
</script>

<form class="w-full" on:submit|preventDefault={registerEmail}>
	<h1 class="text-2xl font-semibold text-[#16181D] dark:text-customGray-100">
		{$i18n.t('Create account')}
	</h1>
	<p class="mt-2 text-base text-[#6B7280] dark:text-customGray-300">
		{$i18n.t('Enter your work email to get started.')}
	</p>

	<div class="mt-8 flex flex-col gap-3">
		{#if $config?.oauth?.providers?.google}
			<AuthSocialButton provider="google" href="{WEBUI_BASE_URL}/oauth/google/login" />
		{/if}
		{#if $config?.oauth?.providers?.microsoft}
			<AuthSocialButton provider="microsoft" href="{WEBUI_BASE_URL}/oauth/microsoft/login" />
		{/if}
	</div>

	<div class="relative my-6 flex items-center">
		<Separator.Root class="h-px flex-1 bg-gray-200 dark:bg-customGray-700" />
		<span class="px-4 text-sm text-[#6B7280] dark:text-customGray-300">{$i18n.t('or')}</span>
		<Separator.Root class="h-px flex-1 bg-gray-200 dark:bg-customGray-700" />
	</div>

	<div>
		<label for="signup-email" class="mb-1.5 block text-sm font-normal leading-none text-[#16181D] dark:text-customGray-200">
			{$i18n.t('Work email')}
		</label>
		<input
			id="signup-email"
			class="h-12 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 text-sm text-[#16181D] placeholder:text-gray-400 outline-none transition focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-800 dark:text-white dark:placeholder:text-customGray-300"
			placeholder={$i18n.t('name@company.com')}
			bind:value={email}
			type="email"
			autocomplete="email"
			name="email"
			on:input={() => (emailError = '')}
		/>
		{#if emailError}
			<p class="mt-1.5 text-xs text-red-500">{emailError}</p>
		{/if}
	</div>

	<button
		class="mt-4 flex h-12 w-full items-center justify-center rounded-lg bg-[#F1F1F1] text-sm font-medium text-[#16181D] transition hover:bg-[#E8E8E8] focus:outline-none disabled:cursor-not-allowed disabled:opacity-60 dark:bg-customGray-800 dark:text-customGray-200 dark:hover:bg-customGray-700"
		type="submit"
		disabled={loading}
	>
		{$i18n.t('Continue')}
		{#if loading}
			<div class="ml-2">
				<LoaderIcon />
			</div>
		{/if}
	</button>

	<p class="mt-6 text-center text-sm leading-relaxed text-[#6B7280] dark:text-customGray-300">
		{$i18n.t('By signing up, I confirm the')}
		<a href="https://beyondtheloop.ai/tscs" target="_blank" rel="noopener noreferrer"
			class="font-medium text-customBlue-500 hover:underline">{$i18n.t('Terms of Use')}</a>
		{$i18n.t('and that I am ordering as a business and not as a consumer within the meaning of § 13 BGB.')}
	</p>

	<p class="mt-4 text-center text-sm text-[#6B7280] dark:text-customGray-300">
		{$i18n.t('Already have an account?')}
		<a href="/login" class="font-medium text-customBlue-500 hover:underline">{$i18n.t('Log in')}</a>
	</p>
</form>
