<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import ProgressIndicator from '$lib/components/company-register/ProgressIndicator.svelte';
	import Step1Email from '$lib/components/company-register/Step1Email.svelte';
	import Step2Verify from '$lib/components/company-register/Step2Verify.svelte';
	import Step3Personal from '$lib/components/company-register/Step3Personal.svelte';
	import Step4Company from '$lib/components/company-register/Step4Company.svelte';
	import Step5Invite from '$lib/components/company-register/Step5Invite.svelte';
	import { completeRegistration } from '$lib/apis/auths';
	import { COMPANY_SIZE_OPTIONS, INDUSTRY_OPTIONS, TEAM_FUNCTION_OPTIONS } from '$lib/constants';
	import {
		WEBUI_NAME,
		config,
		user,
		socket,
		toastVisible,
		toastMessage,
		toastType,
		showToast,
		company,
		companyConfig
	} from '$lib/stores';
	import { getSessionUser, userSignIn } from '$lib/apis/auths';
	import { getBackendConfig } from '$lib/apis';
	import { generateInitialsImage } from '$lib/utils';
	import CustomToast from '$lib/components/common/CustomToast.svelte';
	import { toast } from 'svelte-sonner';
	import { getCompanyDetails, getCompanyConfig } from '$lib/apis/auths';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	let step = 1;

	const i18n = getContext('i18n');

	let email = '';
	let first_name = '';
	let last_name = '';
	let registration_code = '';
	let password = '';
	let profile_image_url = '';

	let loading = false;

	onMount(() => {
		const emailFromUrl = $page.url.searchParams.get('email');
		if (emailFromUrl) {
			email = emailFromUrl;
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

	async function goNext(event) {
		if (step === 1) {
			email = event.detail.email;
		}
		if(step === 3) {
			loading = true;
			const utm_source = (document.getElementById('utm_source') as HTMLInputElement)?.value ?? '';
			const utm_medium = (document.getElementById('utm_medium') as HTMLInputElement)?.value ?? '';
			const utm_campaign = (document.getElementById('utm_campaign') as HTMLInputElement)?.value ?? '';
			const utm_content = (document.getElementById('utm_content') as HTMLInputElement)?.value ?? '';
			const utm_term = (document.getElementById('utm_term') as HTMLInputElement)?.value ?? '';

			const user = await completeRegistration(
				first_name,
				last_name,
				registration_code?.trim(),
				password,
				profile_image_url ? profile_image_url : generateInitialsImage(`${first_name} ${last_name}`),
				{ utm_source, utm_medium, utm_campaign, utm_content, utm_term },
			).catch(error => showToast('error', error));
			console.log(user)
			if(user) {
				await setSessionUser(user);
				goto('/create-company');
			}
			loading = false;
		}
		if (step < 3) step += 1;
	}

	const goBack = () => {
		if (step > 1) step -= 1;
	};
</script>

<CustomToast message={$toastMessage} type={$toastType} visible={$toastVisible} />

<!-- Hidden UTM fields — populated by GTM from first-party cookies -->
<input type="hidden" id="utm_source" name="utm_source" />
<input type="hidden" id="utm_medium" name="utm_medium" />
<input type="hidden" id="utm_campaign" name="utm_campaign" />
<input type="hidden" id="utm_content" name="utm_content" />
<input type="hidden" id="utm_term" name="utm_term" />

<div
	class="flex flex-col justify-between w-full h-screen max-h-[100dvh]  px-4 text-white relative bg-lightGray-300 dark:bg-customGray-900"
>
	<div></div>
	{#if step === 1}
		<Step1Email on:next={goNext} bind:email />
	{:else if step === 2}
		<Step2Verify {email} on:next={goNext} on:back={goBack} bind:registration_code />
	{:else if step === 3}
		<Step3Personal
			on:next={goNext}
			on:back={goBack}
			bind:profile_image_url
			bind:first_name
			bind:last_name
			bind:password
			{loading}
		/>
	{/if}

	<div class="flex flex-col justify-center">
		<ProgressIndicator {step} />
	</div>
</div>
