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
	import { theme, systemTheme } from '$lib/stores';
	import { validateEmail, getEmailErrorMessage } from '$lib/utils/email-validation';

	const i18n = getContext('i18n');

	let email = '';
	let password = '';
	let showPassword = false;

	let loading = false;
	let oauthLoading = false;
	let emailError = '';

	const oauthErrorCodes = {
		"invalid_credentials": "The email or password provided is incorrect. Please check for typos and try logging in again.",
		"email_taken": "Uh-oh! This email is already registered. Sign in with your existing account or choose another email to start anew.",
		"access_prohibited": "You do not have permission to access this resource. Please contact your administrator for assistance.",
		"not_found": "We could not find what you're looking for :/",
		"incomplete_invitation": "Your invitation is incomplete. Please complete the invitation process before signing in with OAuth.",
		"no_seats_available": "No seats available for your company. Please contact your administrator to resolve this issue.",
		"invalid_company_structure": "The company structure is invalid. Please contact support for assistance."
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
		const error = validateEmail(email);
		if (error) {
			emailError = $i18n.t(getEmailErrorMessage(error));
			return;
		}

		loading = true;
		const sessionUser = await userSignIn(email, password).catch((error) => {
			// toast.error(`${error}`);
            showToast('error',error)
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
<div
	class="flex flex-col justify-center w-full h-screen max-h-[100dvh] px-4 text-white relative bg-lightGray-300 dark:bg-customGray-900"
>
	<form
		class="flex flex-col self-center bg-lightGray-800 dark:bg-customGray-800 rounded-2xl w-full md:w-[34rem] px-6 py-8 md:py-10 md:px-16"
		on:submit={(e) => {
			e.preventDefault();
			signInHandler();
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
				{$i18n.t('Welcome to Beyond Chat')}
			</div>
			<div class="text-center text-sm text-[#8A8B8D] dark:text-customGray-300">
				{$i18n.t('Sign in to continue')}
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
				for="login-email"
				class="block text-sm font-medium text-lightGray-100 dark:text-customGray-200 mb-2"
			>
				{$i18n.t('Work Email')}
			</label>
			<div class="relative w-full bg-lightGray-300 dark:bg-customGray-900 rounded-lg">
				<input
					id="login-email"
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

		<!-- Password Input -->
		<div class="mb-2">
			<label
				for="login-password"
				class="block text-sm font-medium text-lightGray-100 dark:text-customGray-200 mb-2"
			>
				{$i18n.t('Password')}
			</label>
			<div class="relative w-full bg-lightGray-300 dark:bg-customGray-900 rounded-lg">
				{#if showPassword}
					<input
						id="login-password"
						class="px-4 text-base w-full h-14 bg-transparent text-lightGray-100 dark:text-white placeholder:text-lightGray-100/60 dark:placeholder:text-customGray-100/60 outline-none rounded-lg border border-transparent focus:border-customBlue-500 transition-colors pr-12"
						type="text"
						bind:value={password}
						placeholder={$i18n.t('Enter your password')}
						autocomplete="current-password"
						name="password"
						required
					/>
				{:else}
					<input
						id="login-password"
						class="px-4 text-base w-full h-14 bg-transparent text-lightGray-100 dark:text-white placeholder:text-lightGray-100/60 dark:placeholder:text-customGray-100/60 outline-none rounded-lg border border-transparent focus:border-customBlue-500 transition-colors pr-12"
						type="password"
						bind:value={password}
						placeholder={$i18n.t('Enter your password')}
						autocomplete="current-password"
						name="current-password"
						required
					/>
				{/if}
				<button
					type="button"
					class="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 dark:text-customGray-400 hover:text-gray-700 dark:hover:text-white transition-colors"
					on:click={() => (showPassword = !showPassword)}
					tabindex="-1"
				>
					{#if showPassword}
						<HidePassIcon />
					{:else}
						<ShowPassIcon />
					{/if}
				</button>
			</div>
		</div>

		<!-- Forgot Password -->
		<div class="flex justify-end mb-4">
			<a href="/reset-password" class="text-sm font-medium text-customBlue-500 hover:underline">
				{$i18n.t('Forgot password?')}
			</a>
		</div>

		<!-- Submit Button -->
		<button
			class="text-sm w-full font-semibold h-14 px-4 py-3 transition rounded-lg {loading
				? 'cursor-not-allowed bg-customBlue-500/70 text-white'
				: 'bg-customBlue-500 hover:bg-customBlue-600 text-white'} flex justify-center items-center"
			type="submit"
			disabled={loading}
		>
			{$i18n.t('Login')}
			{#if loading}
				<div class="ml-2 self-center">
					<LoaderIcon />
				</div>
			{/if}
		</button>

		<!-- Register Link -->
		<div class="mt-6 text-center">
			<span class="text-sm text-[#8A8B8D] dark:text-customGray-400">
				{$i18n.t(`Don't have an account?`)}
			</span>
			<a href="/signup" class="text-sm text-customBlue-500 font-medium hover:underline ml-1">
				{$i18n.t('Register now')}
			</a>
		</div>

		<!-- Terms -->
		<div class="mt-6 text-sm text-[#8A8B8D] dark:text-customGray-400 text-center leading-relaxed">
			{$i18n.t('By using this service, you agree to our')}
			<a
				href="https://beyondtheloop.ai/tscs"
				target="_blank"
				rel="noopener noreferrer"
				class="text-customBlue-500 hover:underline">{$i18n.t('Terms and Conditions')}</a
			>.
		</div>
	</form>
</div>