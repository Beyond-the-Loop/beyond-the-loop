<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { getBaseModels, updateModelById } from '$lib/apis/models';
	import { getModels } from '$lib/apis';
	import { filterCatalog, mapModelsToOrganizations, modelsInfo } from '../../../../../data/modelsInfo';
	import { getModelIcon, onClickOutside } from '$lib/utils';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { getModelsConfig, setModelsConfig } from '$lib/apis/configs';
	import { companyConfig, mobile, models as storeModels, subscription } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import GroupIcon from '$lib/components/icons/GroupIcon.svelte';
	import PublicIcon from '$lib/components/icons/PublicIcon.svelte';
	import PrivateIcon from '$lib/components/icons/PrivateIcon.svelte';
	import AccessModel from '$lib/components/common/AccessModel.svelte';
	import { getGroups } from '$lib/apis/groups';
	import InfoIcon from '$lib/components/icons/InfoIcon.svelte';
	import AdditionaModelInfo from '../../ModelSelector/AdditionaModelInfo.svelte';
	import { getCompanyConfig } from '$lib/apis/auths';

	const i18n = getContext('i18n');

	let models = null;

	let config = null;

	let modelIds = [];
	let defaultModelIds = [];

	let baseModelName = '';
	let showBaseDropdown = false;
	let dropdownBaseRef;

	let imageModelName = '';
	let showImageDropdown = false;
	let dropdownImageRef;

	let organizations = mapModelsToOrganizations(modelsInfo);

	let workspaceModels = null;
	let baseModels = null;
	let accessControl = null;

	const desiredOrder = Object.values(organizations).flat();
	const orderMap = new Map(desiredOrder.map((name, index) => [name, index]));

	const init = async () => {
		workspaceModels = await getBaseModels(localStorage.token);

		models = workspaceModels.sort(
			(a, b) => (orderMap.get(a?.name) ?? Infinity) - (orderMap.get(b?.name) ?? Infinity)
		);
		const availableModels = models.map((model) => model?.name);
		organizations = filterCatalog(organizations, availableModels);
	};

	const defaultInit = async () => {
		config = await getModelsConfig(localStorage.token);

		const modelOrderList = config.MODEL_ORDER_LIST || [];
		const allModelIds = $storeModels.map((model) => model.id);

		if (config?.default_models) {
			defaultModelIds = (config?.default_models ?? '')
				.split(',')
				.filter(Boolean)
				.map((id) => $storeModels.find((m) => m.id === id)?.name ?? '');
		} else {
			defaultModelIds = [];
		}

		// Create a Set for quick lookup of ordered IDs
		const orderedSet = new Set(modelOrderList);

		modelIds = [
			// Add all IDs from MODEL_ORDER_LIST that exist in allModelIds
			...modelOrderList.filter((id) => orderedSet.has(id) && allModelIds.includes(id)),
			// Add remaining IDs not in MODEL_ORDER_LIST, sorted alphabetically
			...allModelIds.filter((id) => !orderedSet.has(id)).sort((a, b) => a.localeCompare(b))
		];
	};

	const savebaseModel = async (defaultModelIds) => {
		const res = await setModelsConfig(localStorage.token, {
			DEFAULT_MODELS: defaultModelIds.join(','),
			MODEL_ORDER_LIST: modelIds
		});

		if (res) {
			toast.success($i18n.t('Models configuration saved successfully'));
			defaultInit();
			const companyConfigInfo = await getCompanyConfig(localStorage.token).catch((error) =>
				toast.error(error)
			);
			if (companyConfigInfo) {
				companyConfig.set(companyConfigInfo);
			}
		} else {
			toast.error($i18n.t('Failed to save models configuration'));
		}
	};
	onMount(async () => {
		init();
		defaultInit();
	});
	let groups = [];
	onMount(async () => {
		groups = await getGroups(localStorage.token);
	});

	let openAccessDropdownId = null;

	const updateModel = async (modelId, accessControl, isActive) => {
		const selectedModel = models.find((model) => model.id === modelId);
		let info = {};
		info.id = selectedModel.id;
		info.name = selectedModel.name;
		info.base_model_id = null;
		info.params = {};
		info.access_control = accessControl;
		info.is_active = isActive;
		info.created_at = selectedModel.created_at;
		info.updated_at = selectedModel.updated_at;
		info.user_id = selectedModel.user_id;
		info.company_id = selectedModel.company_id;
		info.meta = { ...selectedModel.meta, files: [] };

		const res = await updateModelById(localStorage.token, modelId, info).catch((error) => {
			return null;
		});

		if (res) {
			toast.success($i18n.t('Model updated successfully'));
		}
		init();
		if (selectedModel.is_active !== isActive) {
			storeModels.set(await getModels(localStorage.token));
		}
	};
	let showPricingTooltip = false;
	let showCategoryTooltip = false;
</script>

<div class="min-h-[40rem] pb-4">
	<div
		class="flex w-full justify-between items-center py-2.5 border-b border-lightGray-400 dark:border-customGray-700 mb-2.5"
	>
		<div class="flex w-full justify-between items-center">
			<div class="text-xs text-lightGray-100 dark:text-customGray-300">{$i18n.t('Model')}</div>
		</div>
	</div>
	<div class="mb-5" use:onClickOutside={() => (showBaseDropdown = false)}>
		<div class="relative" bind:this={dropdownBaseRef}>
			<button
				type="button"
				class={`flex items-center justify-between w-full text-sm h-10 px-3 py-2  ${showBaseDropdown ? 'border' : ''} border-lightGray-400 dark:border-customGray-700 rounded-md bg-lightGray-300 dark:bg-customGray-900 cursor-pointer`}
				on:click={() => (showBaseDropdown = !showBaseDropdown)}
			>
				<div class="text-lightGray-100 dark:text-customGray-100 flex items-center">
					<span>{$i18n.t('Default model')}</span>
				</div>
				<div class="flex items-center gap-2">
					{#if defaultModelIds?.length > 0}
						<div
							class="flex items-center gap-2 text-xs text-lightGray-100 dark:text-customGray-100/50"
						>
							<img src={getModelIcon(defaultModelIds?.[0])} alt="icon" class="w-4 h-4" />
							{defaultModelIds?.[0]}
						</div>
					{/if}
					<ChevronDown className="size-3" />
				</div>
			</button>

			{#if showBaseDropdown}
				<div
					class="max-h-60 overflow-y-auto custom-scrollbar absolute z-50 w-full -mt-1 bg-lightGray-300 dark:bg-customGray-900 border-l border-r border-b border-lightGray-400 dark:border-customGray-700 rounded-b-md"
				>
					<hr class="border-t border-lightGray-400 dark:border-customGray-700 mb-2 mt-1 mx-0.5" />
					<div class="px-1">
						{#each models?.filter((model) => model.is_active) as model (model.id)}
							<button
								class="px-3 py-2 flex items-center gap-2 w-full rounded-xl text-sm hover:bg-gray-100 dark:hover:bg-customGray-950 dark:text-customGray-100 cursor-pointer text-gray-900"
								on:click={() => {
									// baseModelName = model.name
									savebaseModel([model.id]);
									showBaseDropdown = false;
								}}
							>
								<img src={getModelIcon(model.name)} alt="icon" class="w-4 h-4" />
								{model.name}
							</button>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	</div>
	{#if models !== null}
		<div>
			{#each Object.keys(organizations) as organization, idx (organization)}
				<div class="mb-5">
					<div
						class="grid grid-cols-[32%_1.1fr_0.9fr_0.9fr_22%] md:grid-cols-[32%_1.1fr_0.9fr_0.9fr_22%] mb-2.5"
					>
						<div
							class="text-sm text-lightGray-100 dark:text-customGray-100 flex items-end justify-start"
						>
							{organization}
						</div>
						{#if idx === 0}
							<div
								class="text-2xs md:text-2xs text-[#8A8B8D] dark:text-customGray-300 flex items-end justify-center"
							>
								{$i18n.t('Speed')}
							</div>
							<div
								class="text-2xs md:text-2xs text-[#8A8B8D] dark:text-customGray-300 flex items-end justify-center"
							>
								{$i18n.t('Intelligence score')}
							</div>
							<div
								class="text-2xs md:text-2xs text-[#8A8B8D] dark:text-customGray-300 flex items-end justify-center"
							>
								{#if $subscription.plan === 'free' || $subscription.plan === 'premium'}
									{$i18n.t('Category')}
									{#if !$mobile}
										<div
											class="relative ml-1 cursor-pointer flex justify-center items-center w-[18px] h-[18px] rounded-full text-white dark:text-white bg-customBlue-600 dark:bg-customGray-700">
											<a
												href="https://beyond-the-loop.notion.site/fair-usage-policy"
												target="_blank"
												rel="noopener noreferrer"
											>
												<InfoIcon class="size-6 cursor-pointer" />
											</a>
										</div>
									{/if}
								{:else}
									<div>{$i18n.t('Pricing')}</div>
									{#if !$mobile}
										<div
											on:mouseenter={() => (showPricingTooltip = true)}
											on:mouseleave={() => (showPricingTooltip = false)}
											class="relative ml-1 cursor-pointer flex justify-center items-center w-[18px] h-[18px] rounded-full text-white dark:text-white bg-customBlue-600 dark:bg-customGray-700"
										>
											{#if showPricingTooltip}
												<div
													class="text-lightGray-100 dark:text-customGray-100 w-[12rem] text-xs absolute left-0 -top-12 bg-lightGray-300 border-lightGray-400 dark:bg-customGray-900 px-1 py-2 border-l border-b border-r dark:border-customGray-700 rounded-lg shadow z-10"
												>
													{$i18n.t('Please visit our')} <a
													class="underline"
													href="https://beyondtheloop.ai/pricing-breakdown"
													target="_blank"
													rel="noopener noreferrer">{$i18n.t('pricing page')}</a
												> {$i18n.t('for a detailed breakdown')}.
												</div>
											{/if}
											<InfoIcon className="size-6" />
										</div>
									{/if}
								{/if}
							</div>
							<div class="text-2xs text-[#8A8B8D] dark:text-customGray-300 flex justify-center items-end">
								{$i18n.t('Access rights')}
							</div>
						{/if}
					</div>
					{#each models?.filter((m) => organizations[organization]
						.map((item) => {
							return item.toLowerCase();
						})
						.includes(m.name.toLowerCase())) as model (model.name)}
						<div
							class="grid grid-cols-[32%_1.1fr_0.9fr_0.9fr_22%] md:grid-cols-[32%_1.1fr_0.9fr_0.9fr_22%] border-t last:border-b border-lightGray-400 dark:border-customGray-700"
						>
							<div
								class="border-l border-r border-lightGray-400 dark:border-customGray-700 py-3 px-2"
							>
								<div class="flex items-center">
									<img
										class="w-4 h-4 rounded-full"
										src={getModelIcon(model.name)}
										alt={model.name}
									/>
									<div class="text-xs dark:text-white ml-2">{model.name}</div>
									<AdditionaModelInfo hoveredItem={model} />
								</div>
							</div>
							<div
								class="border-r border-lightGray-400 dark:border-customGray-700 text-xs flex justify-center items-center dark:text-customGray-100"
							>
								{#if modelsInfo?.[model?.name]?.speed}
									{modelsInfo?.[model?.name]?.speed}
								{:else}
									N/A
								{/if}
							</div>
							<div
								class="border-r border-lightGray-400 dark:border-customGray-700 text-xs flex justify-center items-center dark:text-customGray-100"
							>
								{#if modelsInfo?.[model?.name]?.intelligence_score}
									{modelsInfo?.[model?.name]?.intelligence_score}/5
								{:else}
									N/A
								{/if}
							</div>
							<div
								class="border-r border-lightGray-400 dark:border-customGray-700 text-xs flex justify-center items-center dark:text-customGray-100"
							>
								{#if $subscription.plan === 'free' || $subscription.plan === 'premium'}
									{#if modelsInfo?.[model?.name]?.category}
										{modelsInfo?.[model?.name]?.category}
									{:else}
										N/A
									{/if}
								{:else}
									{#if modelsInfo?.[model?.name]?.category}
										{modelsInfo?.[model?.name]?.costFactor}/5
									{:else}
										N/A
									{/if}
								{/if}
							</div>
							<div
								class="border-r border-lightGray-400 dark:border-customGray-700 flex justify-center items-center"
							>
								<div class="flex items-center justify-center">
									<div
										class="bg-lightGray-700 dark:bg-customGray-900 px-2 py-1 rounded-lg"
										on:click={() =>
											(openAccessDropdownId = openAccessDropdownId === model.id ? null : model.id)}
									>
										{#if !model.is_active}
											<div
												class="cursor-pointer flex items-center gap-1 text-xs dark:text-customGray-100/50 leading-none whitespace-nowrap"
											>
												<PrivateIcon className="size-3" />{$i18n.t('Disabled')}
											</div>
										{:else if model.access_control === null}
											<div
												class="cursor-pointer flex items-center gap-1 text-xs dark:text-customGray-100/50 leading-none whitespace-nowrap"
											>
												<PublicIcon className="size-3" />{$i18n.t('Public')}
											</div>
										{:else if [...(model?.access_control?.read?.group_ids ?? []), ...(model?.access_control?.write?.group_ids ?? [])].length > 0}
											<div
												class="cursor-pointer flex items-center gap-1 text-xs dark:text-customGray-100/50 leading-none whitespace-nowrap"
											>
												<GroupIcon className="size-3" />{$i18n.t('Group')}
											</div>
										{:else}
											<div
												class="cursor-pointer flex items-center gap-1 text-xs dark:text-customGray-100/50 leading-none whitespace-nowrap"
											>
												<PrivateIcon className="size-3" />{$i18n.t('Admin only')}
											</div>
										{/if}
									</div>
									<ChevronDown className="size-2 ml-[3px]" />
								</div>
								{#if openAccessDropdownId === model.id}
									<AccessModel
										bind:openAccessDropdownId
										{groups}
										{updateModel}
										accessControl={model.access_control}
										is_active={model.is_active}
										{defaultModelIds}
									/>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{/each}
		</div>
	{:else}
		<div class="h-[20rem] w-full flex justify-center items-center">
			<Spinner />
		</div>
	{/if}
</div>
