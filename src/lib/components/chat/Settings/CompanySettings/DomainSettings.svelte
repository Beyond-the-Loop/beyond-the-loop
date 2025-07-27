<script lang="ts">
    import LoaderIcon from "$lib/components/icons/LoaderIcon.svelte";
    import { getContext, onMount, tick } from "svelte";
    import { addDomain, getDomains, switchOwnership, deleteDomain } from "$lib/apis/domain";
	import { toast } from "svelte-sonner";
	import Switch from "$lib/components/common/Switch.svelte";
    import DeleteIcon from "$lib/components/icons/DeleteIcon.svelte";
    import Spinner from '$lib/components/common/Spinner.svelte';
    import { copyToClipboard as _copyToClipboard } from "$lib/utils";
    import CopyMessageIcon from "$lib/components/icons/CopyMessageIcon.svelte";
    import InfoIcon from "$lib/components/icons/InfoIcon.svelte";
    import Tooltip from "$lib/components/common/Tooltip.svelte";
    
    
    const i18n = getContext('i18n');

    let domain = '';
    let loading = false;
    let loadingDomains = false;
    let domains = [];
    let registered_domain = '';
    let dns_approval_record = '';
    let approvindId = '';

    const copyToClipboard = async (text) => {
		const res = await _copyToClipboard(text);
		if (res) {
			toast.success($i18n.t('Copying to clipboard was successful!'));
		}
	};
    
    onMount(async() => {
        try {
            loadingDomains = true;
            domains = await getDomains(localStorage.token);
        } catch (error) {
            console.log(error)
        } finally {
            loadingDomains = false;
        }
    });
    const onSubmit = async () => {
        if(!domain) return;
        try {
            loading = true;
            const result = await addDomain(localStorage.token, domain);
            if(result.domain_fqdn) {
                 toast.success($i18n.t('Domain added successfuly'));
                 dns_approval_record = result.dns_approval_record;
                 registered_domain = result.domain_fqdn;
                 domain = '';
                 domains = await getDomains(localStorage.token);
            }
        } catch(error) {
            toast.error(`${error}`);
        } finally {
            loading = false;
        }
    }

    const toggleOwnership = async (id) => {
        try {
            approvindId = id;
            await switchOwnership(localStorage.token, id);
            domains = await getDomains(localStorage.token);
        } catch(error) {
            toast.error(`${error}`);
        } finally {
            approvindId = null;
        }
    }

    const removeDomain = async (id) => {
        try {
            const res = await deleteDomain(localStorage.token, id);
            if(res) {
                toast.success($i18n.t('Deleted successfuly'));
                domains = await getDomains(localStorage.token);
                registered_domain = "";
                dns_approval_record = "";
            }
        } catch(error) {
            toast.error(`${error}`);
        }
    }

    const showTxtRecord = (id) => {
        const clickedDomain = domains.find(domain => domain.id === id);
        if(clickedDomain) {
            registered_domain = clickedDomain.domain_fqdn;
            dns_approval_record = clickedDomain.dns_approval_record;
        }
    }
</script>

<div class="mt-2.5">
    <div
        class="flex w-full justify-between items-center py-2.5 border-b border-lightGray-400 dark:border-customGray-700 mb-2.5"
        >
        <div class="flex w-full justify-between items-center">
            <div class="text-xs text-lightGray-100 dark:text-customGray-300">{$i18n.t('All domains')}</div>
        </div>
    </div>
    
    {#if loadingDomains}
        <div class="flex flex-col justify-center min-h-[4rem]">
            <Spinner/>
        </div>
    {:else}
        {#if domains?.length > 0}
            <div class="grid grid-cols-[35%_25%_20%_10%] md:grid-cols-[40%_20%_20%_1fr] gap-2.5 text-2xs md:text-xs text-gray-600 dark:text-customGray-100/50 mb-3">
                <div>{$i18n.t('Name')}</div>
                <div>{$i18n.t('Ownership')}</div>
                <div class="flex justify-center">{$i18n.t('TXT record')}</div>
                <div class="flex justify-center">{$i18n.t('Delete')}</div>
            </div>
            <div class="grid grid-cols-[35%_25%_20%_10%] md:grid-cols-[40%_20%_20%_1fr] gap-2.5 text-lightGray-100 dark:text-customGray-100" >
                {#each domains as domain}
                    <div class="text-xs md:text-sm flex items-center">{domain?.domain_fqdn}</div>
                    <div>
                        {#if domain.ownership_approved}
                            <span
                                class="bg-[#DCFFCA] text-lightGray-100 font-medium dark:bg-[#12595A] rounded-[9px] text-xs dark:text-white px-2 py-1 w-fit"
                                >{$i18n.t('Approved')}</span
                            >
                        {:else}
                            <button
                                type="button"
                                on:click={() => toggleOwnership(domain.id)}
                                class="min-w-[4rem] md:min-w-[5rem] text-xs px-1 md:px-3 py-2 font-medium transition rounded-lg {approvindId === domain.id
                                    ? ' cursor-not-allowed bg-lightGray-300 hover:bg-lightGray-500 text-lightGray-100 dark:bg-customGray-950 dark:hover:bg-customGray-950 dark:text-white border dark:border-customGray-700'
                                    : 'bg-lightGray-300 hover:bg-lightGray-500 text-lightGray-100 dark:bg-customGray-900 dark:hover:bg-customGray-950 dark:text-customGray-200 border dark:border-customGray-700'} flex justify-center"
                                disabled={approvindId === domain.id}
                            >
                                {#if approvindId === domain.id}
                                    <div class="ml-1.5 self-center">
                                        <svg
                                            class=" w-4 h-4"
                                            viewBox="0 0 24 24"
                                            fill="currentColor"
                                            xmlns="http://www.w3.org/2000/svg"
                                            ><style>
                                                .spinner_ajPY {
                                                    transform-origin: center;
                                                    animation: spinner_AtaB 0.75s infinite linear;
                                                }
                                                @keyframes spinner_AtaB {
                                                    100% {
                                                        transform: rotate(360deg);
                                                    }
                                                }
                                            </style><path
                                                d="M12,1A11,11,0,1,0,23,12,11,11,0,0,0,12,1Zm0,19a8,8,0,1,1,8-8A8,8,0,0,1,12,20Z"
                                                opacity=".25"
                                            /><path
                                                d="M10.14,1.16a11,11,0,0,0-9,8.92A1.59,1.59,0,0,0,2.46,12,1.52,1.52,0,0,0,4.11,10.7a8,8,0,0,1,6.66-6.61A1.42,1.42,0,0,0,12,2.69h0A1.57,1.57,0,0,0,10.14,1.16Z"
                                                class="spinner_ajPY"
                                            /></svg
                                        >
                                    </div>
                                {:else}
                                    {$i18n.t("Approve")}
                                {/if}
                            </button>
                        {/if}
                    </div>
                    <div class="flex justify-center items-center">
                        <Tooltip content={$i18n.t('Click to see TXT record')}>
                            <button
                            type="button"
                            on:click={() => showTxtRecord(domain.id)}
                            class="ml-1 cursor-pointer group relative flex justify-center items-center w-[18px] h-[18px] rounded-full text-white dark:text-white bg-customBlue-600 dark:bg-customGray-700"
                        >
                            <InfoIcon className="size-6" />
                        </button>
                    </Tooltip>
                    </div>
                    <div class="flex justify-center">
                        <button on:click={() => removeDomain(domain.id)}><DeleteIcon/></button>
                    </div>
                {/each}
            </div>
        {:else}
            <div class="text-sm">{$i18n.t('No domains added yet')}</div>
        {/if}
    {/if}
    
</div>
<div class="mt-2.5 mb-2.5">
    <div
        class="flex w-full justify-between items-center py-2.5 border-b border-lightGray-400 dark:border-customGray-700 mb-2.5"
        >
        <div class="flex w-full justify-between items-center">
            <div class="text-xs text-lightGray-100 dark:text-customGray-300">{$i18n.t('Add new domain')}</div>
        </div>
    </div>
    <div class="flex justify-between">
        <div class="flex flex-col w-full mb-2.5">
            <div class="relative w-full bg-lightGray-300 dark:bg-customGray-900 rounded-md">
                {#if domain}
                    <div class="text-xs absolute left-2.5 top-1 text-lightGray-100/50 dark:text-customGray-100/50">
                        {$i18n.t('Domain')}
                    </div>
                {/if}
                <input
                    class={`px-2.5 text-sm ${domain ? 'pt-2' : 'pt-0'} text-lightGray-100 placeholder:text-lightGray-100 w-full h-12 bg-transparent dark:text-customGray-100 dark:placeholder:text-customGray-100 outline-none`}
                    placeholder={$i18n.t(' Domain')}
                    bind:value={domain}
                />
            </div>
        </div>
        <button
			class=" text-xs w-[168px] h-12 ml-2 px-3 py-2 transition rounded-lg {loading
				? ' cursor-not-allowed bg-lightGray-300 border-lightGray-400 text-lightGray-100 font-medium hover:bg-lightGray-700 dark:bg-customGray-950 dark:hover:bg-customGray-950 dark:text-white border dark:border-customGray-700'
				: 'bg-lightGray-300 border-lightGray-400 text-lightGray-100 font-medium hover:bg-lightGray-700 dark:bg-customGray-900 dark:hover:bg-customGray-950 dark:text-customGray-200 border dark:border-customGray-700'} flex justify-center items-center"
			type="button"
			disabled={loading}
			on:click={onSubmit}
		>
			{$i18n.t('Add')}
			{#if loading}
				<div class="ml-1.5 self-center">
					<LoaderIcon />
				</div>
			{/if}
		</button>
    </div>

     {#if dns_approval_record}
        <div>
            <div class="text-sm text-gray-600 dark:text-customGray-100/50 mb-3">{$i18n.t('Please add this dns approval record as a TXT record for the registered domain')} - {registered_domain}</div>
        </div>
        <div class="flex justify-between items-center mb-2 bg-lightGray-300 dark:bg-customGray-900 py-2 px-3 rounded-lg">
            <div class="text-xs">{dns_approval_record}</div>
            <button on:click={() => copyToClipboard(dns_approval_record)}><CopyMessageIcon/></button>
        </div>

    {/if}
</div>