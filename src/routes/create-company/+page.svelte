<script lang="ts">
	import { getContext } from 'svelte';
	import ProgressIndicator from '$lib/components/company-register/ProgressIndicator.svelte';
	import Step1Email from '$lib/components/company-register/Step1Email.svelte';
	import Step2Verify from '$lib/components/company-register/Step2Verify.svelte';
	import Step3Personal from '$lib/components/company-register/Step3Personal.svelte';
	import Step4Company from '$lib/components/company-register/Step4Company.svelte';
	import Step5Invite from '$lib/components/company-register/Step5Invite.svelte';
	import { createCompany } from '$lib/apis/auths';
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

	const i18n = getContext('i18n');

	let step = 4;

	let company_name = '';
	let company_size = '';
	let company_industry = '';
	let company_team_function = '';
	let company_profile_image_url = '';

	let loading = false;

	async function goNext(event) {
	
		if (step === 4) {
			if(!company_name || !company_size || !company_industry || !company_team_function) {
				showToast('error', "To continue, please provide full information about your company and team.")
				return;
			}
			loading = true;
			const companyInfo = await createCompany(
				localStorage.token,
				company_name,
				company_size,
				company_industry,
				company_team_function,
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
		<Step4Company
			on:next={goNext}
			on:back={goBack}
			bind:company_profile_image_url
			bind:company_name
			bind:company_size
			bind:company_industry
			bind:company_team_function
			{loading}
		/>
	{:else if step === 5}
		<Step5Invite on:back={goBack} />
	{/if}

	<div class="flex flex-col justify-center">
		<ProgressIndicator {step} />
		<div class="self-center text-xs text-customGray-300 dark:text-customGray-100 pb-5 text-center">
			{$i18n.t('By using this service, you agree to our')}
			<a
				href="https://drive.google.com/file/d/1--HSBhHR8JSkz6q-qDgjJZWXvHWa6sh-/view?usp=sharing"
				target="_blank"
				rel="noopener noreferrer"
				class="underline">{$i18n.t('Terms and Conditions')}</a
			>.
		</div>
	</div>
</div>
