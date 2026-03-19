<script lang="ts">
	import { getContext } from 'svelte';
	import WorkspaceStep from '$lib/components/signup/WorkspaceStep.svelte';
	import InviteStep from '$lib/components/signup/InviteStep.svelte';
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
	import CustomToast from '$lib/components/common/CustomToast.svelte';
	import { toast } from 'svelte-sonner';
	import { getCompanyDetails, getCompanyConfig } from '$lib/apis/auths';

	const i18n = getContext('i18n');

	let step = 4;

	let company_name = '';
	let subdomain = '';
	let billing_country = 'Deutschland';
	let company_profile_image_url = '';

	let loading = false;

	async function goNext(event) {
	
		if (step === 4) {
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
<div
	class="flex flex-col justify-between w-full h-screen max-h-[100dvh]  px-4 text-white relative bg-lightGray-300 dark:bg-customGray-900"
>
	<div></div>
	{#if step === 4}
		<WorkspaceStep
			on:next={goNext}
			on:back={goBack}
			bind:workspace_name={company_name}
			bind:workspace_logo={company_profile_image_url}
			bind:subdomain
			bind:billing_country
			{loading}
		/>
	{:else if step === 5}
		<InviteStep on:back={goBack} />
	{/if}
</div>
