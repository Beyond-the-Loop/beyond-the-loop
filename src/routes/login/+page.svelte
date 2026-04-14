<script lang="ts">
	import { toast } from 'svelte-sonner';

	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { getBackendConfig } from '$lib/apis';
	import { completeInvite } from '$lib/apis/auths';

	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';

	import { WEBUI_NAME, config, user, socket, toastVisible, toastMessage, toastType, showToast, company, companyConfig } from '$lib/stores';
    import { getSessionUser, userSignIn, getCompanyDetails, getCompanyConfig } from '$lib/apis/auths';

	import Plus from '$lib/components/icons/Plus.svelte';
	import UserIcon from '$lib/components/icons/UserIcon.svelte';
	import ShowPassIcon from '$lib/components/icons/ShowPassIcon.svelte';
	import CustomToast from '$lib/components/common/CustomToast.svelte';
	import LoaderIcon from '$lib/components/icons/LoaderIcon.svelte';
	import HidePassIcon from '$lib/components/icons/HidePassIcon.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import SignupBanner from '$lib/components/signup/shared/SignupBanner.svelte';
	import { theme, systemTheme } from '$lib/stores';

	const i18n = getContext('i18n');

	let email = '';
	let password = '';
    let showPassword = false;
	let loginError = '';

	let loading = false;
	let oauthLoading = false;

	const oauthErrorCodes = {
		"invalid_credentials": "The email or password provided is incorrect. Please check for typos and try logging in again.",
		"email_taken": "Uh-oh! This email is already registered. Sign in with your existing account or choose another email to start anew.",
		"access_prohibited": "You do not have permission to access this resource. Please contact your administrator for assistance.",
		"not_found": "We could not find what you're looking for :/",
		"incomplete_invitation": "Your invitation is incomplete. Please complete the invitation process before signing in with OAuth.",
		"no_seats_available": "No seats available for your company. Please contact your administrator to resolve this issue.",
		"invalid_company_structure": "The company structure is invalid. Please contact support for assistance.",
		"personal_email_prohibited": "Please use your business email address to sign in."
	};
	const setSessionUser = async (sessionUser) => {
		if (sessionUser) {
			console.log(sessionUser);
			// showToast('success', `You're now logged in.`);
			if (sessionUser.token) {
				localStorage.token = sessionUser.token;
			}

			$socket.emit('user-join', { auth: { token: sessionUser.token } });
			await user.set(sessionUser);
			await config.set(await getBackendConfig());
		}
	};

	const signInHandler = async () => {
		loginError = '';
        loading = true;
		const sessionUser = await userSignIn(email, password).catch((error) => {
			loginError = $i18n.t(error);
			loading = false;
			return null;
		});

		await setSessionUser(sessionUser);

		const [companyInfo, companyConfigInfo] = await Promise.all([
			getCompanyDetails(sessionUser.token).catch((error) => {
				showToast('error', error);
				return null;
			}),
			getCompanyConfig(sessionUser.token).catch((error) => {
				showToast('error', error);
				return null;
			})
		]);

		if(!companyInfo) {
			goto('/create-company');
			return;
		}

		if (companyInfo) {
			company.set(companyInfo);
		}

		if (companyConfigInfo) {
			console.log(companyConfigInfo);
			companyConfig.set(companyConfigInfo);
		}
		showToast('success', $i18n.t(`You're now logged in.`));
		goto('/');
        loading = false;
	};

    const checkOauthCallback = async () => {
		if (!$page.url.hash) {
			return;
		}
		oauthLoading = true;
		const hash = $page.url.hash.substring(1);
		if (!hash) {
			return;
		}
		const params = new URLSearchParams(hash);
		const error = params.get('error');
		if(error) {
			const message = oauthErrorCodes[error] || "An unknown error occurred.";
			showToast('error', $i18n.t(message));
			oauthLoading = false;
			return;
		}
		const token = params.get('token');
		if (!token) {
			return;
		}
		const sessionUser = await getSessionUser(token).catch((error) => {
			showToast('error', error);
			return null;
		});
		if (!sessionUser) {
			oauthLoading = false;
			return;
		}
		localStorage.token = token;
		await setSessionUser(sessionUser);

		const [companyInfo, companyConfigInfo] = await Promise.all([
			getCompanyDetails(sessionUser.token).catch((error) => {
				// showToast('error', error);
				return null;
			}),
			getCompanyConfig(sessionUser.token).catch((error) => {
				// showToast('error', error);
				return null;
			})
		]);

		if(!companyInfo) {
			goto('/create-company');
			return;
		}

		if (companyInfo) {
			company.set(companyInfo);
		}

		if (companyConfigInfo) {
			console.log(companyConfigInfo);
			companyConfig.set(companyConfigInfo);
		}
		showToast('success', `You're now logged in.`);
		goto('/');
		oauthLoading = false;
	};

	onMount(async () => {
        if ($user !== undefined && $company) {
			await goto('/');
		}
		await checkOauthCallback();
    });
	let logoSrc = '/logo_dark_transparent.png';

	onMount(() => {
		const theme = $theme === "system" ? $systemTheme : $theme;
		const isDark = theme === 'dark';
		logoSrc = isDark ? '/logo_dark_transparent.png' : '/logo_light_transparent.png';
	});

</script>

<svelte:head>
	<title>
		{`${$WEBUI_NAME}`}
	</title>
</svelte:head>

<CustomToast message={$toastMessage} type={$toastType} visible={$toastVisible} />
{#if oauthLoading}
	<div class="fixed h-full w-full flex justify-center items-center z-20">
		<Spinner />
	</div>
{/if}
<div class="flex min-h-screen bg-white dark:bg-customGray-900">
	<div class="flex w-full flex-col items-center px-6 sm:px-8 lg:w-1/2 lg:px-12 xl:px-16">
		<div class="flex-[2]"></div>
		<div class="w-full max-w-[25rem] lg:max-w-[clamp(20rem,31.5vw,28rem)]">
			<form
				on:submit={(e) => {
					e.preventDefault();
					signInHandler();
				}}
			>
				<div class="mb-6">
					<h1 class="text-2xl font-semibold text-[#16181D] dark:text-customGray-100">
						{$i18n.t('Welcome to')} Beyond Chat
					</h1>
					<p class="mt-2 text-base text-[#6B7280] dark:text-customGray-300">
						{$i18n.t('Sign in to continue')}
					</p>
				</div>

				<div class="flex flex-col gap-3">
					{#if $config?.oauth?.providers?.google}
						<button
							type="button"
							class="flex h-12 w-full items-center justify-center gap-3 rounded-lg border border-gray-200 bg-[#F1F1F1] text-sm font-medium text-[#16181D] transition hover:bg-[#E8E8E8] dark:border-customGray-700 dark:bg-customGray-900 dark:text-customGray-200 dark:hover:bg-customGray-950"
							on:click={() => {
								window.location.href = `${WEBUI_BASE_URL}/oauth/google/login`;
							}}
						>
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" class="h-5 w-5">
								<path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
								<path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
								<path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
								<path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
							</svg>
							<span>{$i18n.t('Continue with {{provider}}', { provider: 'Google' })}</span>
						</button>
					{/if}
					{#if $config?.oauth?.providers?.microsoft}
						<button
							type="button"
							class="flex h-12 w-full items-center justify-center gap-3 rounded-lg border border-gray-200 bg-[#F1F1F1] text-sm font-medium text-[#16181D] transition hover:bg-[#E8E8E8] dark:border-customGray-700 dark:bg-customGray-900 dark:text-customGray-200 dark:hover:bg-customGray-950"
							on:click={() => {
								window.location.href = `${WEBUI_BASE_URL}/oauth/microsoft/login`;
							}}
						>
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21" class="h-5 w-5">
								<rect x="1" y="1" width="9" height="9" fill="#f25022" />
								<rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
								<rect x="11" y="1" width="9" height="9" fill="#7fba00" />
								<rect x="11" y="11" width="9" height="9" fill="#ffb900" />
							</svg>
							<span>{$i18n.t('Continue with {{provider}}', { provider: 'Microsoft' })}</span>
						</button>
					{/if}
				</div>

				<div class="relative my-6">
					<hr class="border-gray-200 dark:border-customGray-700" />
					<span class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-white px-3 text-sm text-[#6B7280] dark:bg-customGray-900 dark:text-customGray-300">{$i18n.t("or")}</span>
				</div>

				<div class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
					{$i18n.t('Email address')}
				</div>
				<div class="mb-3">
					<input
						class="h-12 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 text-sm text-[#16181D] outline-none transition focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-customGray-300"
						placeholder={$i18n.t('Email address')}
						bind:value={email}
						type="email"
						autocomplete="email"
						name="email"
						required
						on:input={() => (loginError = '')}
					/>
				</div>

				<label for="login-password" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
					{$i18n.t('Password')}
				</label>
				<div class="relative">
					{#if showPassword}
						<input
							id="login-password"
							class="h-12 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 text-sm text-[#16181D] outline-none transition focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-customGray-300 pr-12{loginError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
							type="text"
							bind:value={password}
							placeholder={$i18n.t('Password')}
							autocomplete="current-password"
							name="password"
							required
							on:input={() => (loginError = '')}
						/>
					{:else}
						<input
							id="login-password"
							class="h-12 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 text-sm text-[#16181D] outline-none transition focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-customGray-300 pr-12{loginError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
							type="password"
							bind:value={password}
							placeholder={$i18n.t('Password')}
							autocomplete="current-password"
							name="current-password"
							required
							on:input={() => (loginError = '')}
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
				{#if loginError}
					<p class="mt-1.5 text-xs text-red-500">{loginError}</p>
				{/if}

				<div class="flex justify-end mb-4 mt-1.5">
					<a href="/reset-password" class="text-sm font-medium text-customBlue-500 hover:underline">{$i18n.t('Forgot password?')}</a>
				</div>

				<button
					class="flex h-12 w-full items-center justify-center rounded-lg bg-[#F1F1F1] text-sm font-medium text-[#16181D] transition hover:bg-[#E8E8E8] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-customGray-900 dark:text-customGray-200 dark:hover:bg-customGray-950"
					type="submit"
					disabled={loading}
				>
					{$i18n.t('Login')}
					{#if loading}
						<div class="ml-1.5">
							<LoaderIcon />
						</div>
					{/if}
				</button>

				<p class="mt-6 text-center text-sm leading-relaxed text-[#6B7280] dark:text-customGray-300">
					{$i18n.t('By using this service, you agree to our')}
					<a href="https://beyondtheloop.ai/tscs" target="_blank" rel="noopener noreferrer" class="font-medium text-customBlue-500 hover:underline">{$i18n.t('Terms and Conditions')}</a>{#if $i18n.language?.startsWith('de')}{' '}zu.{:else}.{/if}
				</p>

				<p class="mt-4 text-center text-sm text-[#6B7280] dark:text-customGray-300">
					{$i18n.t(`Don't have an account?`)}
					<a href="/signup" class="font-medium text-customBlue-500 hover:underline">{$i18n.t('Register now')}</a>
				</p>
			</form>
		</div>
		<div class="flex-[3]"></div>
	</div>

	<div class="hidden lg:block lg:w-1/2">
		<SignupBanner />
	</div>
</div>