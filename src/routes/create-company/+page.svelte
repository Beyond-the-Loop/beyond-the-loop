<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import WorkspaceStep from '$lib/components/signup/WorkspaceStep.svelte';
	import InviteStep from '$lib/components/signup/InviteStep.svelte';
	import SignupTestimonials from '$lib/components/signup/shared/SignupTestimonials.svelte';
	import { createCompany } from '$lib/apis/auths';
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
	import { fetchLogoByEmail } from '$lib/utils/logo';
	import CustomToast from '$lib/components/common/CustomToast.svelte';
	import { toast } from 'svelte-sonner';
	import { getCompanyDetails, getCompanyConfig } from '$lib/apis/auths';

	const i18n = getContext('i18n');

	let step = 1;

	let company_name = '';
	let subdomain = '';
	let billing_country = 'Deutschland';
	let company_profile_image_url = '';

	onMount(() => {
		if ($user?.email) {
			fetchLogoByEmail($user.email).then((logo) => { if (logo) company_profile_image_url = logo; });
		}
	});

	let loading = false;

	async function goNext() {
	
		if (step === 1) {
			if(!company_name) {
				showToast('error', "To continue, please provide a workspace name.")
				return;
			}
			loading = true;
			const companyInfo = await createCompany(
				localStorage.token,
				company_name,
				subdomain,
				billing_country,
				company_profile_image_url ? company_profile_image_url : ''
			).catch(error => {
				showToast('error', error);
				loading = false;
		});
			company.set(companyInfo)
			if(companyInfo) {
				step = step + 1;
				const companyConfigInfo = await getCompanyConfig(localStorage.token).catch((error) => {
						toast.error(`${error}`);
						loading = false;
						return null;
					});
				if (companyConfigInfo) {
					companyConfig.set(companyConfigInfo);
				}
			}
			loading = false;
		}	
	}

	const goBack = () => {
		if (step > 1) step -= 1;
	};
</script>

<CustomToast message={$toastMessage} type={$toastType} visible={$toastVisible} />
<div class="flex min-h-screen bg-white dark:bg-customGray-900">
	<div class="flex w-full flex-col items-center px-6 sm:px-8 lg:w-1/2 lg:px-12 xl:px-16">
		<div class="flex-[2]"></div>
		<div class="w-full max-w-[25rem] lg:max-w-[clamp(20rem,31.5vw,28rem)]">
			{#if step === 1}
				<WorkspaceStep
					on:next={goNext}
					bind:workspace_name={company_name}
					bind:workspace_logo={company_profile_image_url}
					bind:subdomain
					bind:billing_country
					step={1}
					totalSteps={2}
					showBack={false}
					{loading}
				/>
			{:else if step === 2}
				<InviteStep on:back={goBack} step={2} totalSteps={2} />
			{/if}
		</div>
		<div class="flex-[3]"></div>
	</div>

	<div class="hidden lg:block lg:w-1/2">
		<SignupTestimonials />
	</div>
</div>
