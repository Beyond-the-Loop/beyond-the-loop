<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { getBackendConfig } from '$lib/apis';
	import { completeRegistration } from '$lib/apis/auths';
	import { generateInitialsImage } from '$lib/utils';
	import { fetchLogoByEmail } from '$lib/utils/logo';

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

	import CustomToast from '$lib/components/common/CustomToast.svelte';
	import EmailStep from '$lib/components/signup/EmailStep.svelte';
	import VerifyStep from '$lib/components/signup/VerifyStep.svelte';
	import PersonalStep from '$lib/components/signup/PersonalStep.svelte';
	import WorkspaceStep from '$lib/components/signup/WorkspaceStep.svelte';
	import InviteStep from '$lib/components/signup/InviteStep.svelte';
	import SignupBanner from '$lib/components/signup/shared/SignupBanner.svelte';

	let step = 1;

	let email = '';
	let first_name = '';
	let last_name = '';
	let password = '';
	let registration_code = '';
	let position = '';
	let phone = '';
	let workspace_name = '';
	let workspace_logo = '';
	let subdomain = '';
	let billing_country = 'Deutschland';

	let loading = false;

	onMount(() => {
		document.documentElement.style.setProperty('overflow-y', 'auto', 'important');

		const emailFromUrl = $page.url.searchParams.get('email');
		if (emailFromUrl) {
			email = emailFromUrl;
		}

		return () => {
			document.documentElement.style.removeProperty('overflow-y');
		};
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

	async function goNext(event) {
		if (step === 1) {
			email = event.detail.email;
			fetchLogoByEmail(email).then((logo) => { if (logo) workspace_logo = logo; });
		}
		if (step === 3) {
			loading = true;
			const utm_source = (document.getElementById('utm_source') as HTMLInputElement)?.value ?? '';
			const utm_medium = (document.getElementById('utm_medium') as HTMLInputElement)?.value ?? '';
			const utm_campaign = (document.getElementById('utm_campaign') as HTMLInputElement)?.value ?? '';
			const utm_content = (document.getElementById('utm_content') as HTMLInputElement)?.value ?? '';
			const utm_term = (document.getElementById('utm_term') as HTMLInputElement)?.value ?? '';
			const utm_gclid = (document.getElementById('utm_gclid') as HTMLInputElement)?.value ?? '';

			const registeredUser = await completeRegistration(
				first_name,
				last_name,
				registration_code?.trim(),
				password || null,
				generateInitialsImage(`${first_name} ${last_name}`),
				position,
				phone,
				{ utm_source, utm_medium, utm_campaign, utm_content, utm_term, utm_gclid },
			).catch((error) => showToast('error', error));

			if (registeredUser) {
				await setSessionUser(registeredUser);
				goto('/create-company');
			}
			loading = false;
		}
		if (step < 5) step += 1;
	}

	const goBack = () => {
		if (step > 1) step -= 1;
	};
</script>

<svelte:head>
	<title>{$WEBUI_NAME}</title>
</svelte:head>

<!-- Hidden UTM fields — populated by GTM from first-party cookies -->
<input type="hidden" id="utm_source" name="utm_source" />
<input type="hidden" id="utm_medium" name="utm_medium" />
<input type="hidden" id="utm_campaign" name="utm_campaign" />
<input type="hidden" id="utm_content" name="utm_content" />
<input type="hidden" id="utm_term" name="utm_term" />
<input type="hidden" id="utm_gclid" name="utm_gclid" />

<CustomToast message={$toastMessage} type={$toastType} visible={$toastVisible} />

<div class="flex min-h-screen bg-white dark:bg-customGray-900">
	<!-- Left: Auth Form -->
	<div class="flex w-full flex-col items-center px-6 sm:px-8 lg:w-1/2 lg:px-12 xl:px-16">
		<div class="flex-[2]"></div>
		<div class="w-full max-w-[25rem] lg:max-w-[clamp(20rem,31.5vw,28rem)]">
			{#if step === 1}
				<EmailStep on:next={goNext} bind:email />
			{:else if step === 2}
				<VerifyStep {email} on:next={goNext} on:back={goBack} bind:registration_code />
			{:else if step === 3}
				<PersonalStep
					on:next={goNext}
					on:back={goBack}
					bind:first_name
					bind:last_name
					bind:password
					bind:position
					bind:phone
				/>
			{:else if step === 4}
				<WorkspaceStep
					on:next={goNext}
					bind:workspace_name
					bind:workspace_logo
					bind:subdomain
					bind:billing_country
					showBack={false}
				/>
			{:else if step === 5}
				<InviteStep
					on:next={goNext}
					on:back={goBack}
					{loading}
				/>
			{/if}
		</div>
		<div class="flex-[3]"></div>
	</div>

	<!-- Right: Testimonials (hidden on mobile) -->
	<div class="hidden lg:block lg:w-1/2">
		<SignupBanner />
	</div>
</div>
