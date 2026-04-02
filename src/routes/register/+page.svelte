<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { getBackendConfig } from '$lib/apis';
	import { completeInvite, getCompanyDetails, getCompanyConfig } from '$lib/apis/auths';

	import { WEBUI_NAME, config, user, socket, toastVisible, toastMessage, toastType, showToast, company, companyConfig } from '$lib/stores';

	import CustomToast from '$lib/components/common/CustomToast.svelte';
	import LoaderIcon from '$lib/components/icons/LoaderIcon.svelte';
	import SignupTestimonials from '$lib/components/signup/shared/SignupTestimonials.svelte';
	import { generateInitialsImage } from '$lib/utils';

	const i18n = getContext('i18n');

	const INPUT_CLASSES =
		'h-12 w-full rounded-lg border border-gray-200 bg-[#F1F1F1] px-4 text-sm text-[#16181D] outline-none transition focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 dark:border-customGray-700 dark:bg-customGray-900 dark:text-white';

	let firstName = '';
	let lastName = '';
	let password = '';
	let confirmPassword = '';
	let showPassword = false;
	let showConfirmPassword = false;
	let profileImageUrl = '';
	let profileImageInputRef: HTMLInputElement;

	let firstNameError = '';
	let lastNameError = '';
	let passwordError = '';
	let confirmPasswordError = '';

	let inviteToken = '';
	let loading = false;

	function handleProfileImageUpload(e: Event) {
		const file = (e.target as HTMLInputElement).files?.[0];
		if (!file) return;
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
				const size = 250;
				canvas.width = size;
				canvas.height = size;
				const scale = Math.max(size / img.width, size / img.height);
				const x = (size - img.width * scale) / 2;
				const y = (size - img.height * scale) / 2;
				ctx?.drawImage(img, x, y, img.width * scale, img.height * scale);
				profileImageUrl = canvas.toDataURL('image/jpeg');
			};
		};
		reader.readAsDataURL(file);
	}

	onMount(() => {
		if ($page.url.searchParams.get('inviteToken')) {
			inviteToken = $page.url.searchParams.get('inviteToken');
		} else {
			goto('/signup');
		}
	});

	const setSessionUser = async (sessionUser) => {
		if (sessionUser) {
			if (sessionUser.token) {
				localStorage.token = sessionUser.token;
			}

			$socket.emit('user-join', { auth: { token: sessionUser.token } });
			await user.set(sessionUser);
			await config.set(await getBackendConfig());
		}
	};

	const completeInviteHandler = async () => {
		firstNameError = lastNameError = passwordError = confirmPasswordError = '';

		if (!firstName.trim()) {
			firstNameError = $i18n.t('First name is required.');
			return;
		}
		if (!lastName.trim()) {
			lastNameError = $i18n.t('Last name is required.');
			return;
		}

		const strongPasswordRegex = /^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{8,}$/;
		if (!strongPasswordRegex.test(password)) {
			passwordError = $i18n.t('Password must be 8+ characters, with a number, capital letter, and symbol.');
			return;
		}

		if (password !== confirmPassword) {
			confirmPasswordError = $i18n.t('Passwords do not match.');
			return;
		}

		loading = true;
		const sessionUser = await completeInvite(
			firstName,
			lastName,
			password,
			inviteToken,
			profileImageUrl || generateInitialsImage(`${firstName} ${lastName}`)
		).catch((error) => {
			showToast('error', `${error}`);
			loading = false;
			return null;
		});

		if (!sessionUser) return;

		await setSessionUser(sessionUser);

		const [companyInfo, companyConfigInfo] = await Promise.all([
			getCompanyDetails(sessionUser.token).catch((error) => {
				showToast('error', `${error}`);
				return null;
			}),
			getCompanyConfig(sessionUser.token).catch((error) => {
				showToast('error', `${error}`);
				return null;
			})
		]);

		if (companyInfo && companyConfigInfo) {
			showToast('success', $i18n.t(`You're now logged in.`));
			company.set(companyInfo);
			companyConfig.set(companyConfigInfo);
			goto('/');
		}
		loading = false;
	};
</script>

<svelte:head>
	<title>{$WEBUI_NAME}</title>
</svelte:head>

<CustomToast message={$toastMessage} type={$toastType} visible={$toastVisible} />

<div class="flex min-h-screen bg-white dark:bg-customGray-900">
	<div class="flex w-full flex-col items-center px-6 sm:px-8 lg:w-1/2 lg:px-12 xl:px-16">
		<div class="flex-[2]"></div>
		<div class="w-full max-w-[25rem] lg:max-w-[clamp(20rem,31.5vw,28rem)]">
			<input bind:this={profileImageInputRef} type="file" hidden accept="image/png,image/jpeg" on:change={handleProfileImageUpload} />

			<form on:submit|preventDefault={completeInviteHandler}>
				<div class="mb-6">
					<h1 class="text-2xl font-semibold text-[#16181D] dark:text-customGray-100">
						{$i18n.t('Complete your registration')}
					</h1>
					<p class="mt-2 text-base text-[#6B7280] dark:text-customGray-300">
						{$i18n.t('Set up your account to get started.')}
					</p>
				</div>

				<div class="mb-6">
					<span class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
						{$i18n.t('Profile photo')}
					</span>
					<div class="flex items-center gap-4">
						<button
							type="button"
							on:click={() => profileImageInputRef?.click()}
							class="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-customBlue-500 text-xl font-bold text-white"
						>
							{#if profileImageUrl}
								<img src={profileImageUrl} alt="profile" class="h-14 w-14 rounded-xl object-cover" />
							{:else}
								{firstName ? firstName.charAt(0).toUpperCase() : ''}
							{/if}
						</button>
						<div>
							<button
								type="button"
								on:click={() => profileImageInputRef?.click()}
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

				<div class="grid grid-cols-2 gap-3">
					<div>
						<label for="first-name" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
							{$i18n.t('First name')}
						</label>
						<input
							id="first-name"
							class="{INPUT_CLASSES} placeholder:text-gray-400 dark:placeholder:text-customGray-300{firstNameError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
							placeholder="Max"
							bind:value={firstName}
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
							bind:value={lastName}
							autocomplete="family-name"
							on:input={() => (lastNameError = '')}
						/>
						{#if lastNameError}
							<p class="mt-1.5 text-xs text-red-500">{lastNameError}</p>
						{/if}
					</div>
				</div>

				<div class="mt-4">
					<label for="register-password" class="mb-1.5 block text-sm font-normal text-[#16181D] dark:text-customGray-200">
						{$i18n.t('Password')}
					</label>
					<div class="relative">
						{#if showPassword}
							<input
								id="register-password"
								class="{INPUT_CLASSES} placeholder:text-gray-400 dark:placeholder:text-customGray-300 pr-12{passwordError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
								type="text"
								placeholder={$i18n.t('Create password')}
								bind:value={password}
								autocomplete="new-password"
								on:input={() => (passwordError = '')}
							/>
						{:else}
							<input
								id="register-password"
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
								on:input={() => (confirmPasswordError = '')}
							/>
						{:else}
							<input
								id="confirm-password"
								class="{INPUT_CLASSES} placeholder:text-gray-400 dark:placeholder:text-customGray-300 pr-12{confirmPasswordError ? ' border-red-500 focus:border-red-500 focus:ring-red-500' : ''}"
								type="password"
								placeholder={$i18n.t('Confirm password')}
								bind:value={confirmPassword}
								autocomplete="new-password"
								on:input={() => (confirmPasswordError = '')}
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

				<button
					class="mt-6 flex h-12 w-full items-center justify-center rounded-lg bg-[#F1F1F1] text-sm font-medium text-[#16181D] transition hover:bg-[#E8E8E8] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-customGray-900 dark:text-customGray-200 dark:hover:bg-customGray-950"
					type="submit"
					disabled={loading}
				>
					{$i18n.t('Register')}
					{#if loading}
						<div class="ml-1.5">
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
			</form>
		</div>
		<div class="flex-[3]"></div>
	</div>

	<div class="hidden lg:block lg:w-1/2">
		<SignupTestimonials />
	</div>
</div>
