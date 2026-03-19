<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { getBackendConfig } from '$lib/apis';
	import { completeRegistration } from '$lib/apis/auths';
	import { generateInitialsImage } from '$lib/utils';

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
	import SignupTestimonials from '$lib/components/signup/shared/SignupTestimonials.svelte';

	let step = 1;

	let email = '';
	let first_name = '';
	let last_name = '';
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
		}
		if (step === 3) {
			loading = true;
			const registeredUser = await completeRegistration(
				first_name,
				last_name,
				registration_code?.trim(),
				null,
				generateInitialsImage(`${first_name} ${last_name}`),
				position,
				phone
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
					bind:position
					bind:phone
				/>
			{:else if step === 4}
				<WorkspaceStep
					on:next={goNext}
					on:back={goBack}
					bind:workspace_name
					bind:workspace_logo
					bind:subdomain
					bind:billing_country
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
		<SignupTestimonials />
	</div>
</div>
