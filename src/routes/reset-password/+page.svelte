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
	import { getSessionUser, userSignIn, requestPasswordReset } from '$lib/apis/auths';

	import Plus from '$lib/components/icons/Plus.svelte';
	import UserIcon from '$lib/components/icons/UserIcon.svelte';
	import ShowPassIcon from '$lib/components/icons/ShowPassIcon.svelte';
	import CustomToast from '$lib/components/common/CustomToast.svelte';
	import LoaderIcon from '$lib/components/icons/LoaderIcon.svelte';
	import ArrowLeft from '$lib/components/icons/ArrowLeft.svelte';
	import SignupBanner from '$lib/components/signup/shared/SignupBanner.svelte';
	import { theme, systemTheme } from '$lib/stores';

	const i18n = getContext('i18n');

	let email = '';
	let loading = false;

	const resetPassword = async () => {
		loading = true;
		try {
			await requestPasswordReset(email);
			showToast('success', 'If the email exists, a reset link has been sent.');
		} catch (error) {
			console.error('Error requesting password reset:', error);
			showToast('error', 'An error occurred. Please try again later.');
		} finally {
			loading = false;
		}
	};

	let logoSrc = '/logo_light.png';

	onMount(() => {
		const theme = $theme === "system" ? $systemTheme : $theme;
		const isDark = theme === 'dark';
		logoSrc = isDark ? '/logo_dark_transparent.png' : '/logo_light_transparent.png';
	});

	$: console.log($config?.oauth?.providers?.google);
</script>

<svelte:head>
	<title>
		{`${$WEBUI_NAME}`}
	</title>
</svelte:head>

<CustomToast message={$toastMessage} type={$toastType} visible={$toastVisible} />
<div class="flex min-h-screen bg-white dark:bg-customGray-900">
	<div class="flex w-full flex-col items-center px-6 sm:px-8 lg:w-1/2 lg:px-12 xl:px-16">
		<div class="flex-[2]"></div>
		<div class="w-full max-w-[25rem] lg:max-w-[clamp(20rem,31.5vw,28rem)]">
			<form
				on:submit={(e) => {
					e.preventDefault();
					resetPassword();
				}}
			>
				<div class="mb-6">
					<a
						href="/login"
						class="flex h-8 w-8 items-center justify-center rounded-lg text-[#16181D] transition hover:bg-gray-100 dark:text-customGray-100 dark:hover:bg-customGray-800"
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5">
							<path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd" />
						</svg>
					</a>
				</div>

				<h1 class="text-2xl font-semibold text-[#16181D] dark:text-customGray-100">
					{$i18n.t('Reset password')}
				</h1>
				<p class="mt-2 mb-6 text-base text-[#6B7280] dark:text-customGray-300">
					{$i18n.t('Enter your email to get a reset link')}
				</p>

				<div class="mb-4">
					<label for="reset-email" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
						{$i18n.t('Email address')}
					</label>
					<input
						id="reset-email"
						class="h-12 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 text-sm text-[#16181D] outline-none transition focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-800 dark:text-white placeholder:text-gray-400 dark:placeholder:text-customGray-300"
						placeholder={$i18n.t('Email address')}
						bind:value={email}
						type="email"
						autocomplete="email"
						name="email"
						required
					/>
				</div>

				<button
					class="flex h-12 w-full items-center justify-center rounded-lg bg-[#F1F1F1] text-sm font-medium text-[#16181D] transition hover:bg-[#E8E8E8] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-customGray-800 dark:text-customGray-200 dark:hover:bg-customGray-700"
					type="submit"
					disabled={loading}
				>
					{$i18n.t('Send')}
					{#if loading}
						<div class="ml-1.5">
							<LoaderIcon />
						</div>
					{/if}
				</button>

				<p class="mt-6 text-center text-xs text-[#6B7280] dark:text-customGray-300">
					{$i18n.t('By using this service, you agree to our')}
					<a href="https://beyondtheloop.ai/tscs" target="_blank" rel="noopener noreferrer" class="underline text-customBlue-500 font-medium">{$i18n.t('Terms and Conditions')}</a>{#if $i18n.language === "de-DE"}{" "}zu.{:else}.{/if}
				</p>
			</form>
		</div>
		<div class="flex-[3]"></div>
	</div>

	<div class="hidden lg:block lg:w-1/2">
		<SignupBanner />
	</div>
</div>
