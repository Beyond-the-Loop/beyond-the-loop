<script lang="ts">
	import { toast } from 'svelte-sonner';

	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { getBackendConfig } from '$lib/apis';
	import { completeInvite } from '$lib/apis/auths';

	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';

	import {
		WEBUI_NAME,
		config,
		user,
		socket,
		toastVisible,
		toastMessage,
		toastType,
		showToast
	} from '$lib/stores';
	import { getSessionUser, userSignIn } from '$lib/apis/auths';

	import Plus from '$lib/components/icons/Plus.svelte';
	import UserIcon from '$lib/components/icons/UserIcon.svelte';
	import ShowPassIcon from '$lib/components/icons/ShowPassIcon.svelte';
	import CustomToast from '$lib/components/common/CustomToast.svelte';
	import LoaderIcon from '$lib/components/icons/LoaderIcon.svelte';
	import { createEventDispatcher } from 'svelte';
	import { createUser } from '$lib/apis/users';
	import { theme, systemTheme } from '$lib/stores';
	import { validateEmail, getEmailErrorMessage } from '$lib/utils/email-validation';

	const dispatch = createEventDispatcher();

	const i18n = getContext('i18n');

	export let email = '';
	let loading = false;
	let emailError = '';

	async function registerEmail() {
		const error = validateEmail(email);
		if (error) {
			emailError = $i18n.t(getEmailErrorMessage(error));
			return;
		}
		loading = true;
		const user = await createUser(email)
			.catch((error) => {
				showToast('error', error);
			})
			.finally(() => (loading = false));
		dispatch('next', { email: user.email });
	}

	let logoSrc = '/logo_light.png';

	onMount(() => {
		const currentTheme = $theme === 'system' ? $systemTheme : $theme;
		const isDark = currentTheme === 'dark';
		logoSrc = isDark ? '/logo_dark_transparent.png' : '/logo_light_transparent.png';
	});
</script>

<CustomToast message={$toastMessage} type={$toastType} visible={$toastVisible} />
<form
	class="flex flex-col self-center bg-lightGray-800 dark:bg-customGray-800 rounded-2xl w-full md:w-[34rem] px-6 py-8 md:py-10 md:px-16"
	on:submit={(e) => {
		e.preventDefault();
		registerEmail();
	}}
>
	<!-- Header -->
	<div class="self-center flex flex-col items-center mb-8">
		<div>
			<img
				width="48"
				height="48"
				crossorigin="anonymous"
				src={logoSrc}
				class="w-12 mb-6"
				alt="logo"
			/>
		</div>
		<div class="text-2xl font-semibold text-lightGray-100 dark:text-customGray-100 mb-2">
			{$i18n.t('Create your account')}
		</div>
		<div class="text-center text-sm text-[#8A8B8D] dark:text-customGray-300">
			{$i18n.t('Enter your work email to get started.')}
		</div>
	</div>

	<!-- OAuth Buttons -->
	<div class="flex flex-col space-y-3 mb-6">
		{#if $config?.oauth?.providers?.google}
			<button
				type="button"
				class="h-12 flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-customGray-900 dark:hover:bg-customGray-950 dark:text-customGray-200 transition w-full rounded-lg font-medium text-sm py-3 border border-lightGray-400 bg-lightGray-300 hover:bg-lightGray-700 text-lightGray-100 dark:border-customGray-700"
				on:click={() => {
					window.location.href = `${WEBUI_BASE_URL}/oauth/google/login`;
				}}
			>
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" class="size-5 mr-3">
					<path
						fill="#EA4335"
						d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
					/><path
						fill="#4285F4"
						d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
					/><path
						fill="#FBBC05"
						d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
					/><path
						fill="#34A853"
						d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
					/><path fill="none" d="M0 0h48v48H0z" />
				</svg>
				<span>{$i18n.t('Continue with {{provider}}', { provider: 'Google' })}</span>
			</button>
		{/if}
		{#if $config?.oauth?.providers?.microsoft}
			<button
				type="button"
				class="h-12 flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-customGray-900 dark:hover:bg-customGray-950 dark:text-customGray-200 transition w-full rounded-lg font-medium text-sm py-3 border border-lightGray-400 bg-lightGray-300 hover:bg-lightGray-700 text-lightGray-100 dark:border-customGray-700"
				on:click={() => {
					window.location.href = `${WEBUI_BASE_URL}/oauth/microsoft/login`;
				}}
			>
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21" class="size-5 mr-3">
					<rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect
						x="1"
						y="11"
						width="9"
						height="9"
						fill="#00a4ef"
					/><rect x="11" y="1" width="9" height="9" fill="#7fba00" /><rect
						x="11"
						y="11"
						width="9"
						height="9"
						fill="#ffb900"
					/>
				</svg>
				<span>{$i18n.t('Continue with {{provider}}', { provider: 'Microsoft' })}</span>
			</button>
		{/if}
	</div>

	<!-- Divider -->
	<div class="flex items-center my-6">
		<div class="flex-1 border-t border-lightGray-300 dark:border-customGray-700"></div>
		<span class="px-4 text-sm text-[#8A8B8D] dark:text-customGray-400">{$i18n.t('or')}</span>
		<div class="flex-1 border-t border-lightGray-300 dark:border-customGray-700"></div>
	</div>

	<!-- Email Input -->
	<div class="mb-4">
		<label
			for="email"
			class="block text-sm font-medium text-lightGray-100 dark:text-customGray-200 mb-2"
		>
			{$i18n.t('Work Email')}
		</label>
		<div class="relative w-full bg-lightGray-300 dark:bg-customGray-900 rounded-lg">
			<input
				id="email"
				class="px-4 text-base w-full h-14 bg-transparent text-lightGray-100 dark:text-white placeholder:text-lightGray-100/60 dark:placeholder:text-customGray-100/60 outline-none rounded-lg border border-transparent focus:border-customBlue-500 transition-colors"
				placeholder="name@company.com"
				bind:value={email}
				type="email"
				autocomplete="email"
				name="email"
				required
				on:input={() => (emailError = '')}
			/>
		</div>
		{#if emailError}
			<p class="text-red-500 text-sm mt-2">{emailError}</p>
		{/if}
	</div>

	<!-- Submit Button -->
	<button
		class="text-sm w-full font-semibold h-14 px-4 py-3 transition rounded-lg {loading
			? 'cursor-not-allowed bg-customBlue-500/70 text-white'
			: 'bg-customBlue-500 hover:bg-customBlue-600 text-white'} flex justify-center items-center"
		type="submit"
		disabled={loading}
	>
		{$i18n.t('Continue')}
		{#if loading}
			<div class="ml-2 self-center">
				<LoaderIcon />
			</div>
		{/if}
	</button>

	<!-- Legal Text -->
	<div class="mt-6 text-sm text-[#8A8B8D] dark:text-customGray-400 text-center leading-relaxed">
		{$i18n.t('By signing up, I confirm the')}
		<a
			href="https://beyondtheloop.ai/tscs"
			target="_blank"
			rel="noopener noreferrer"
			class="text-customBlue-500 hover:underline">{$i18n.t('Terms and Conditions')}</a
		>
		{$i18n.t('and that I am acting as an entrepreneur, not a consumer within the meaning of § 13 BGB.')}
	</div>

	<!-- Login Link -->
	<div class="mt-6 text-center">
		<span class="text-sm text-[#8A8B8D] dark:text-customGray-400">
			{$i18n.t('Already have an account?')}
		</span>
		<a href="/login" class="text-sm text-customBlue-500 font-medium hover:underline ml-1"
			>{$i18n.t('Log in')}</a
		>
	</div>
</form>
