<script lang="ts">
    import LoaderIcon from "$lib/components/icons/LoaderIcon.svelte";
    import { getContext, onMount, tick } from "svelte";
    import { addDomain, getDomains, switchOwnership, deleteDomain } from "$lib/apis/domain";
	import { toast } from "svelte-sonner";
	import Switch from "$lib/components/common/Switch.svelte";
    import DeleteIcon from "$lib/components/icons/DeleteIcon.svelte";
    
    const i18n = getContext('i18n');
    
    let domain = '';
    let loading = false;
    let domains = [];
    let dns_approval_record = '';
    
    onMount(async() => {
        try {
            domains = await getDomains(localStorage.token);
        } catch (error) {
            console.log(error)
        }
    });
    const onSubmit = async () => {
        if(!domain) return;
        try {
            const result = await addDomain(localStorage.token, domain);
            if(result.domain_fqdn) {
                 toast.success($i18n.t('Domain added successfuly'));
                 domain = '';
                 domains = await getDomains(localStorage.token);
            }
        } catch(error) {
            toast.error(`${error}`);
        }
    }

    const toggleOwnership = async (id) => {
        try {
            await switchOwnership(localStorage.token, id);
        } catch(error) {
            toast.error(`${error}`);
        }
    }

    const removeDomain = async (id) => {
        try {
            const res = await deleteDomain(localStorage.token, id);
            if(res) {
                toast.success($i18n.t('Deleted successfuly'));
                 domains = await getDomains(localStorage.token);
            }
        } catch(error) {
            toast.error(`${error}`);
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
    
    {#if domains?.length > 0}
        <div class="grid grid-cols-[50%_30%_1fr] gap-2.5 text-xs mb-3">
            <div>{$i18n.t('Name')}</div>
            <div>{$i18n.t('Approve ownership')}</div>
            <div>{$i18n.t('Delete')}</div>
        </div>
        <div class="grid grid-cols-[50%_30%_1fr] gap-2.5" >
            {#each domains as domain}
                <div class="text-sm">{domain?.domain_fqdn}</div>
                <div>
                    <Switch
                        bind:state={domain.ownership_approved}
                    
                            on:change={async () => {
                           
                                await toggleOwnership(domain.id);
                            } }
                    /></div>
                <div><button on:click={() => removeDomain(domain.id)}><DeleteIcon/></button></div>
            {/each}
        </div>
    {:else}
        <div class="text-sm">{$i18n.t('No domains added yet')}</div>
    {/if}
</div>
<div class="mt-2.5">
    <div
        class="flex w-full justify-between items-center py-2.5 border-b border-lightGray-400 dark:border-customGray-700 mb-2.5"
        >
        <div class="flex w-full justify-between items-center">
            <div class="text-xs text-lightGray-100 dark:text-customGray-300">{$i18n.t('Add new domain')}</div>
        </div>
    </div>
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
    <div class="flex flex-col w-full mb-2.5">
        <div class="relative w-full bg-lightGray-300 dark:bg-customGray-900 rounded-md">
            {#if dns_approval_record}
                <div class="text-xs absolute left-2.5 top-1 text-lightGray-100/50 dark:text-customGray-100/50">
                    {$i18n.t('Dns approval record')}
                </div>
            {/if}
            <input
                class={`px-2.5 text-sm ${dns_approval_record ? 'pt-2' : 'pt-0'} text-lightGray-100 placeholder:text-lightGray-100 w-full h-12 bg-transparent dark:text-customGray-100 dark:placeholder:text-customGray-100 outline-none`}
                placeholder={$i18n.t('Dns approval record')}
                bind:value={dns_approval_record}
            />
        </div>
    </div>
    <div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class=" text-xs w-[168px] h-10 px-3 py-2 transition rounded-lg {loading
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
</div>