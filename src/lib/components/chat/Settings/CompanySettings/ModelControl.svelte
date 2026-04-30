<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { getContext, onMount } from 'svelte';
	import { getBaseModels, updateModelById } from '$lib/apis/models';
	import { getModels } from '$lib/apis';
	import {
		filterCatalog,
		mapModelsToOrganizations,
		regionLabel
	} from '../../../../../data/modelsInfo';
	import EuIcon from '$lib/components/icons/EuIcon.svelte';
	import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
	import { modelsInfo } from '$lib/stores';
	import { getModelIcon, onClickOutside } from '$lib/utils';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { getModelsConfig, setModelsConfig } from '$lib/apis/configs';
	import { companyConfig, mobile, models as storeModels, subscription } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import PrivateIcon from '$lib/components/icons/PrivateIcon.svelte';
	import { getGroups } from '$lib/apis/groups';
	import QuestionMarkCircle from '$lib/components/icons/QuestionMarkCircle.svelte';
	import Info from '$lib/components/icons/Info.svelte';
	import UsersIcon from '$lib/components/icons/UsersIcon.svelte';
	import AccessControlModal from './AccessControlModal.svelte';
	import ModelDetailsModal from './ModelDetailsModal.svelte';
	import { getCompanyConfig } from '$lib/apis/auths';

	const i18n: Writable<i18nType> = getContext('i18n');

	let config = null;
	let modelIds = [];
	let defaultModelIds = [];

	let searchQuery = '';
	let filterRegion: string | null = null;
	let filterProvider: string | null = null;
	let showRegionDropdown = false;
	let showProviderDropdown = false;

	let pageSize = 10;
	let currentPage = 1;
	let showPageSizeDropdown = false;

	let openKebabDropdownId = null;
	let showBaseDropdown = false;

	let showAccessModal = false;
	let showDetailsModal = false;
	let selectedModel: any = null;

	const openAccessFor = (model: any) => {
		selectedModel = model;
		showAccessModal = true;
		openKebabDropdownId = null;
	};
	const openDetailsFor = (model: any) => {
		selectedModel = model;
		showDetailsModal = true;
		openKebabDropdownId = null;
	};
	const handleAccessSave = (modelId: string, accessControl: any, isActive: boolean) => {
		updateModel(modelId, accessControl, isActive);
	};

	$: organizations = mapModelsToOrganizations($modelsInfo);
	$: desiredOrder = Object.values(organizations).flat();
	$: orderMap = new Map(desiredOrder.map((name, index) => [name, index]));

	let workspaceModels = null;

	const init = async () => {
		workspaceModels = await getBaseModels(localStorage.token);
		const availableModels = (workspaceModels ?? []).map((m) => m?.name);
		organizations = filterCatalog(organizations, availableModels);
	};

	$: models = workspaceModels && [...workspaceModels]
		.filter((m) => m?.name !== 'Smart Router')
		.sort((a, b) =>
			(orderMap.get(a?.name) ?? Infinity) - (orderMap.get(b?.name) ?? Infinity)
		);

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

		const orderedSet = new Set(modelOrderList);

		modelIds = [
			...modelOrderList.filter((id) => orderedSet.has(id) && allModelIds.includes(id)),
			...allModelIds.filter((id) => !orderedSet.has(id)).sort((a, b) => a.localeCompare(b))
		];
	};

	const savebaseModel = async (defaultModelIds) => {
		const res = await setModelsConfig(localStorage.token, {
			default_models: defaultModelIds.join(','),
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

	const updateModel = async (modelId, accessControl, isActive) => {
		const selectedModel = models.find((model) => model.id === modelId);
		let info: any = {};
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

		const res = await updateModelById(localStorage.token, modelId, info).catch(() => null);
		if (res) toast.success($i18n.t('Model updated successfully'));
		init();
		if (selectedModel.is_active !== isActive) {
			storeModels.set(await getModels(localStorage.token));
		}
	};

	// Reverse map: model name -> organization
	$: modelToOrg = (() => {
		const m: Record<string, string> = {};
		for (const [org, names] of Object.entries(organizations)) {
			for (const name of names as string[]) m[name] = org;
		}
		return m;
	})();

	$: availableRegions = Array.from(
		new Set<string>(
			(models ?? [])
				.map((m: any) => $modelsInfo?.[m?.name]?.hosted_in as string | undefined)
				.filter((r: string | undefined): r is string => !!r)
		)
	).sort();
	$: availableProviders = Object.keys(organizations);

	$: defaultModel = (models ?? []).find((m: any) => m?.name === defaultModelIds?.[0]) ?? null;
	$: activeModels = (models ?? []).filter((m: any) => m?.is_active);

	// Filtered + paginated
	$: filteredModels = (models ?? []).filter((m) => {
		const name = m?.name ?? '';
		const org = modelToOrg[name] ?? '';
		const region = $modelsInfo?.[name]?.hosted_in ?? '';
		if (searchQuery) {
			const q = searchQuery.toLowerCase();
			if (!name.toLowerCase().includes(q) && !org.toLowerCase().includes(q)) return false;
		}
		if (filterRegion && region !== filterRegion) return false;
		if (filterProvider && org !== filterProvider) return false;
		return true;
	});

	$: totalPages = Math.max(1, Math.ceil(filteredModels.length / pageSize));
	$: if (currentPage > totalPages) currentPage = totalPages;
	$: paginatedModels = filteredModels.slice((currentPage - 1) * pageSize, currentPage * pageSize);

	// Reset page when filters change
	$: {
		searchQuery;
		filterRegion;
		filterProvider;
		currentPage = 1;
	}

	$: totalCount = (models ?? []).length;
	$: activeCount = (models ?? []).filter((m) => m.is_active).length;
	$: euCount = (models ?? []).filter(
		(m) => ($modelsInfo?.[m?.name]?.hosted_in ?? '').toUpperCase() === 'EU'
	).length;

	const classValue = (modelName: string) => {
		const info = $modelsInfo?.[modelName];
		if (!info) return null;
		if ($subscription?.plan === 'free' || $subscription?.plan === 'premium') {
			return info.category ?? null;
		}
		return info.costFactor ?? null;
	};

	let showRegionTooltip = false;
	let showClassTooltip = false;
</script>

<div class="pb-4 text-lightGray-100 dark:text-customGray-100">
	<div class="flex w-full justify-between items-center py-2.5 border-b border-lightGray-400 dark:border-customGray-700 my-1.5">
		<div class="flex flex-col w-full">
			<div class="text-lg font-semibold">{$i18n.t('Models')}</div>
			<div class="text-xs text-lightGray-100 dark:text-customGray-100">
				{$i18n.t('Manage AI models, set access, and view model details.')}
			</div>
		</div>
	</div>

	<!-- Default model picker -->
	<div class="mb-5">
		<div class="text-xs text-[#8A8B8D] dark:text-customGray-300 mb-2">
			{$i18n.t('Default model for the workspace')}
		</div>
		<div class="relative" use:onClickOutside={() => (showBaseDropdown = false)}>
			<button
				type="button"
				class="flex items-center justify-between w-full h-12 px-3 rounded-md border border-lightGray-400 dark:border-customGray-700 bg-lightGray-300 dark:bg-customGray-900 text-xs text-lightGray-100 dark:text-customGray-100 hover:border-lightGray-100 dark:hover:border-customGray-500 transition-colors"
				on:click={() => (showBaseDropdown = !showBaseDropdown)}
			>
				{#if defaultModel}
					<div class="flex items-center gap-2.5 min-w-0">
						<img
							src={getModelIcon(defaultModel.name)}
							alt={defaultModel.name}
							class="shrink-0 w-7 h-7 object-contain"
						/>
						<span class="font-medium truncate">{defaultModel.name}</span>
						<span class="text-2xs text-[#8A8B8D] dark:text-customGray-300 truncate">
							{modelToOrg[defaultModel.name] ?? ''}
						</span>
					</div>
				{:else}
					<span class="text-[#8A8B8D] dark:text-customGray-300">
						{$i18n.t('Select a model')}
					</span>
				{/if}
				<ChevronDown className="size-3 {showBaseDropdown ? 'rotate-180' : ''} transition-transform" />
			</button>

			{#if showBaseDropdown}
				<div class="absolute z-50 w-full mt-1 max-h-80 overflow-y-auto custom-scrollbar bg-lightGray-300 dark:bg-customGray-900 border border-lightGray-400 dark:border-customGray-700 rounded-md py-1 shadow-md">
					{#each activeModels as m (m.id)}
						{@const isSelected = defaultModelIds?.[0] === m.name}
						<button
							class="w-full flex items-center justify-between gap-2 px-3 py-2 text-xs hover:bg-lightGray-700 dark:hover:bg-customGray-800 text-lightGray-100 dark:text-customGray-100"
							on:click={() => {
								savebaseModel([m.id]);
								showBaseDropdown = false;
							}}
						>
							<div class="flex items-center gap-2.5 min-w-0">
								<img
									src={getModelIcon(m.name)}
									alt={m.name}
									class="shrink-0 w-6 h-6 object-contain"
								/>
								<span class="truncate">{m.name}</span>
								<span class="text-2xs text-[#8A8B8D] dark:text-customGray-300 truncate">
									{modelToOrg[m.name] ?? ''}
								</span>
							</div>
							{#if isSelected}
								<svg
									xmlns="http://www.w3.org/2000/svg"
									width="14"
									height="14"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="2.5"
									stroke-linecap="round"
									stroke-linejoin="round"
									class="shrink-0 text-lightGray-100 dark:text-white"
								>
									<polyline points="20 6 9 17 4 12" />
								</svg>
							{/if}
						</button>
					{/each}
				</div>
			{/if}
		</div>
		<p class="mt-2 text-2xs text-[#8A8B8D] dark:text-customGray-300">
			{$i18n.t('Will be used automatically for new chats by all workspace members.')}
		</p>
	</div>

	<div class="border-t border-lightGray-400 dark:border-customGray-700 mb-4"></div>

	<!-- Toolbar -->
	<div class="flex flex-col md:flex-row gap-2 mb-4">
		<div class="relative flex-1">
			<div class="absolute left-3 top-1/2 -translate-y-1/2 text-[#8A8B8D] dark:text-customGray-300">
				<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<circle cx="11" cy="11" r="8" />
					<path d="m21 21-4.3-4.3" />
				</svg>
			</div>
			<input
				type="text"
				bind:value={searchQuery}
				placeholder={$i18n.t('Search models or providers...')}
				class="w-full h-9 pl-9 pr-3 text-xs rounded-md bg-lightGray-300 dark:bg-customGray-900 border border-lightGray-400 dark:border-customGray-700 text-lightGray-100 dark:text-customGray-100 placeholder:text-[#8A8B8D] dark:placeholder:text-customGray-300 focus:outline-none"
			/>
		</div>

		<!-- Region filter -->
		<div class="relative w-full md:w-44" use:onClickOutside={() => (showRegionDropdown = false)}>
			<button
				type="button"
				class="flex items-center justify-between w-full h-9 px-3 text-xs rounded-md bg-lightGray-300 dark:bg-customGray-900 border border-lightGray-400 dark:border-customGray-700 text-lightGray-100 dark:text-customGray-100"
				on:click={() => (showRegionDropdown = !showRegionDropdown)}
			>
				<span class="flex items-center gap-1.5 truncate">
					{#if filterRegion}
						{#if filterRegion?.toUpperCase() === 'EU'}
							<EuIcon className="w-7 h-5" />
						{:else}
							<GlobeAlt className="w-5 h-5" />
						{/if}
						<span class="truncate">{regionLabel(filterRegion)}</span>
					{:else}
						{$i18n.t('All regions')}
					{/if}
				</span>
				<ChevronDown className="size-3" />
			</button>
			{#if showRegionDropdown}
				<div class="absolute z-40 w-full mt-1 bg-lightGray-300 dark:bg-customGray-900 border border-lightGray-400 dark:border-customGray-700 rounded-md py-1 shadow-sm">
					<button
						class="w-full px-3 py-1.5 text-left text-xs hover:bg-lightGray-700 dark:hover:bg-customGray-800 text-lightGray-100 dark:text-customGray-100"
						on:click={() => { filterRegion = null; showRegionDropdown = false; }}
					>{$i18n.t('All regions')}</button>
					{#each availableRegions as r}
						<button
							class="w-full px-3 py-1.5 text-left text-xs hover:bg-lightGray-700 dark:hover:bg-customGray-800 text-lightGray-100 dark:text-customGray-100 flex items-center gap-2"
							on:click={() => { filterRegion = r; showRegionDropdown = false; }}
						>
							{#if r?.toUpperCase() === 'EU'}
								<EuIcon className="w-7 h-5" />
							{:else}
								<GlobeAlt className="w-5 h-5" />
							{/if}
							<span>{regionLabel(r)}</span>
						</button>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Provider filter -->
		<div class="relative w-full md:w-44" use:onClickOutside={() => (showProviderDropdown = false)}>
			<button
				type="button"
				class="flex items-center justify-between w-full h-9 px-3 text-xs rounded-md bg-lightGray-300 dark:bg-customGray-900 border border-lightGray-400 dark:border-customGray-700 text-lightGray-100 dark:text-customGray-100"
				on:click={() => (showProviderDropdown = !showProviderDropdown)}
			>
				<span class="truncate">{filterProvider ?? $i18n.t('All providers')}</span>
				<ChevronDown className="size-3" />
			</button>
			{#if showProviderDropdown}
				<div class="absolute z-40 w-full mt-1 bg-lightGray-300 dark:bg-customGray-900 border border-lightGray-400 dark:border-customGray-700 rounded-md py-1 shadow-sm max-h-60 overflow-y-auto custom-scrollbar">
					<button
						class="w-full px-3 py-1.5 text-left text-xs hover:bg-lightGray-700 dark:hover:bg-customGray-800 text-lightGray-100 dark:text-customGray-100"
						on:click={() => { filterProvider = null; showProviderDropdown = false; }}
					>{$i18n.t('All providers')}</button>
					{#each availableProviders as p}
						<button
							class="w-full px-3 py-1.5 text-left text-xs hover:bg-lightGray-700 dark:hover:bg-customGray-800 text-lightGray-100 dark:text-customGray-100"
							on:click={() => { filterProvider = p; showProviderDropdown = false; }}
						>{p}</button>
					{/each}
				</div>
			{/if}
		</div>
	</div>

	{#if models !== null}
		<!-- Table card -->
		<div class="rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-lightGray-550 dark:bg-customGray-900 overflow-visible">
			<div class="overflow-x-auto overflow-y-visible custom-scrollbar">
				<div class="min-w-[42rem]">
			<!-- Header row -->
			<div class="grid grid-cols-[minmax(0,2.4fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.7fr)_minmax(0,1.1fr)_44px] items-center px-3 sm:px-4 py-2.5 text-2xs text-[#8A8B8D] dark:text-customGray-300 border-b border-lightGray-400 dark:border-customGray-700">
				<div>{$i18n.t('Model')}</div>
				<div>{$i18n.t('Provider')}</div>
				<div class="flex items-center gap-1">
					<span>{$i18n.t('Region')}</span>
						<span
							role="tooltip"
							on:mouseenter={() => (showRegionTooltip = true)}
							on:mouseleave={() => (showRegionTooltip = false)}
							class="relative cursor-pointer text-[#D1D5DB] dark:text-customGray-300 hover:text-[#6B7280] dark:hover:text-white transition-colors flex items-center"
						>
							{#if showRegionTooltip}
								<div class="absolute left-1/2 -translate-x-1/2 top-full pt-1 z-40 font-normal text-left">
									<div class="w-[18rem] bg-white dark:bg-customGray-900 border border-lightGray-400 dark:border-customGray-700 rounded-lg px-3.5 py-3 shadow-xl">
										<div class="text-xs text-[#374151] dark:text-customGray-100 leading-relaxed mb-2.5">
											{$i18n.t('The region indicates which hosting locations are used for a model.')}
										</div>
										<div class="flex flex-col gap-1 text-[11px]">
											<div class="flex items-center justify-between gap-4">
												<span class="text-[#6B7280] dark:text-customGray-300">EU</span>
												<span class="text-[#9CA3AF] dark:text-customGray-400">{$i18n.t('Locations within the EU')}</span>
											</div>
											<div class="flex items-center justify-between gap-4">
												<span class="text-[#6B7280] dark:text-customGray-300">Global</span>
												<span class="text-[#9CA3AF] dark:text-customGray-400">{$i18n.t('Locations may be worldwide')}</span>
											</div>
										</div>
										<div class="mt-2.5 text-[11px] text-[#9CA3AF] dark:text-customGray-400 leading-relaxed">
											{$i18n.t('The actual region used depends on the respective model provider.')}
										</div>
									</div>
								</div>
							{/if}
							<QuestionMarkCircle className="size-3" strokeWidth="1.8" />
						</span>
				</div>
				<div class="flex items-center gap-1">
					<span>{$i18n.t('Class')}</span>
						<span
							role="tooltip"
							on:mouseenter={() => (showClassTooltip = true)}
							on:mouseleave={() => (showClassTooltip = false)}
							class="relative cursor-pointer text-[#D1D5DB] dark:text-customGray-300 hover:text-[#6B7280] dark:hover:text-white transition-colors flex items-center"
						>
							{#if showClassTooltip}
								<div class="absolute left-1/2 -translate-x-1/2 top-full pt-1 z-40 font-normal text-left">
									<div class="w-[17rem] bg-white dark:bg-customGray-900 border border-lightGray-400 dark:border-customGray-700 rounded-lg px-3.5 py-3 shadow-xl">
										<div class="text-xs text-[#374151] dark:text-customGray-100 leading-relaxed mb-2.5">
											{$i18n.t('Higher classes have stricter rate limits according to the Fair Usage Policy.')}
										</div>
										<a
											href="https://beyond-the-loop.notion.site/fair-usage-policy"
											target="_blank"
											rel="noopener noreferrer"
											class="flex items-center gap-1 text-[11px] text-customBlue-600 dark:text-blue-400 hover:text-customBlue-500 dark:hover:text-blue-300 transition-colors"
										>
											<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
												<path d="M15 3h6v6" />
												<path d="M10 14 21 3" />
												<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
											</svg>
											<span>{$i18n.t('Fair Usage Policy')}</span>
										</a>
									</div>
								</div>
							{/if}
							<QuestionMarkCircle className="size-3" strokeWidth="1.8" />
						</span>
				</div>
				<div>{$i18n.t('Access')}</div>
				<div></div>
			</div>

			<!-- Rows -->
			{#if paginatedModels.length === 0}
				<div class="px-4 py-10 text-center text-xs text-[#8A8B8D] dark:text-customGray-300">
					{$i18n.t('No models found')}
				</div>
				{:else}
				{#each paginatedModels as model (model.id)}
					{@const info = $modelsInfo?.[model?.name]}
					{@const org = modelToOrg[model?.name] ?? '—'}
					{@const region = info?.hosted_in}
					{@const modelClass = classValue(model?.name)}
					{@const inactive = !model.is_active}
					{@const groupIds = new Set([...(model?.access_control?.read?.group_ids ?? []), ...(model?.access_control?.write?.group_ids ?? [])])}
					{@const userIds = new Set([...(model?.access_control?.read?.user_ids ?? []), ...(model?.access_control?.write?.user_ids ?? [])])}
					{@const isPublic = model.access_control === null || (groupIds.size === 0 && userIds.size === 0)}
						<div
							class="grid grid-cols-[minmax(0,2.4fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.7fr)_minmax(0,1.1fr)_44px] items-center px-3 sm:px-4 py-2.5 border-b last:border-b-0 border-lightGray-400 dark:border-customGray-700 hover:bg-lightGray-700 dark:hover:bg-customGray-800 transition-colors"
						>
						<!-- Model -->
							<div class="flex items-center gap-2.5 min-w-0 {inactive ? 'opacity-50' : ''}">
							<img
								src={getModelIcon(model.name)}
								alt={model.name}
								class="shrink-0 w-7 h-7 object-contain"
							/>
							<span class="text-xs dark:text-white text-lightGray-100 truncate">{model.name}</span>
							</div>
							<!-- Provider -->
							<div class="text-xs text-lightGray-100 dark:text-customGray-100 truncate {inactive ? 'opacity-50' : ''}">{org}</div>
							<!-- Region -->
							<div class="flex items-center text-xs text-lightGray-100 dark:text-customGray-100 {inactive ? 'opacity-50' : ''}">
							{#if region}
								<span class="cursor-default inline-flex items-center justify-center w-7" title={regionLabel(region)}>
									{#if region?.toUpperCase() === 'EU'}
										<EuIcon className="w-[22px] h-[16px]" />
									{:else}
										<GlobeAlt className="w-[18px] h-[18px]" />
									{/if}
								</span>
							{:else}
								<span class="text-[#8A8B8D] dark:text-customGray-300 inline-flex justify-center w-7">—</span>
							{/if}
							</div>
							<!-- Class -->
							<div class="{inactive ? 'opacity-50' : ''}">
								{#if modelClass != null}
									<span class="inline-flex items-center justify-center min-w-7 h-6 px-2 text-xs rounded-full bg-lightGray-700 dark:bg-customGray-800 border border-lightGray-400 dark:border-customGray-700 text-lightGray-100 dark:text-white">
										{modelClass}
								</span>
							{:else}
								<span class="text-xs text-[#8A8B8D] dark:text-customGray-300">—</span>
							{/if}
						</div>
						<!-- Access -->
						<div class="flex items-center text-xs font-medium {inactive ? 'opacity-50' : ''}">
							{#if !model.is_active}
								<span class="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-lightGray-700 dark:bg-customGray-800 text-[#8A8B8D] dark:text-customGray-300">
									{$i18n.t('Disabled')}
								</span>
							{:else if isPublic}
								<span class="inline-flex items-center px-2 py-1 rounded-md bg-lightGray-700 dark:bg-customGray-800 text-emerald-600 dark:text-emerald-400">
									{$i18n.t('All')}
								</span>
							{:else if groupIds.size > 0}
								<span class="inline-flex items-center px-2 py-1 rounded-md bg-lightGray-700 dark:bg-customGray-800 text-lightGray-100 dark:text-customGray-100">
									{groupIds.size} {groupIds.size === 1 ? $i18n.t('Group') : $i18n.t('Groups')}
								</span>
							{:else}
								<span class="inline-flex items-center gap-1 text-lightGray-100 dark:text-customGray-100">
									<PrivateIcon className="size-3" />{$i18n.t('Admin only')}
								</span>
							{/if}
						</div>
						<!-- Kebab -->
						<div class="flex justify-end relative" use:onClickOutside={() => { if (openKebabDropdownId === model.id) openKebabDropdownId = null; }}>
							<button
								type="button"
								aria-label="more"
								class="w-7 h-7 flex items-center justify-center rounded-md text-[#8A8B8D] dark:text-customGray-300 hover:bg-lightGray-700 dark:hover:bg-customGray-800"
								on:click={() => (openKebabDropdownId = openKebabDropdownId === model.id ? null : model.id)}
							>
								<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
									<circle cx="12" cy="5" r="1.6" />
									<circle cx="12" cy="12" r="1.6" />
									<circle cx="12" cy="19" r="1.6" />
								</svg>
							</button>
							{#if openKebabDropdownId === model.id}
								<div class="absolute right-0 top-8 z-30 min-w-[12rem] bg-lightGray-300 dark:bg-customGray-900 border border-lightGray-400 dark:border-customGray-700 rounded-md py-1 shadow-md">
									<button
										class="w-full flex items-center gap-2 px-3 py-2 text-left text-xs hover:bg-lightGray-700 dark:hover:bg-customGray-800 text-lightGray-100 dark:text-customGray-100"
										on:click={() => openDetailsFor(model)}
									>
										<Info className="size-3.5" strokeWidth="1.8" />
										{$i18n.t('Model details')}
									</button>
									<button
										class="w-full flex items-center gap-2 px-3 py-2 text-left text-xs hover:bg-lightGray-700 dark:hover:bg-customGray-800 text-lightGray-100 dark:text-customGray-100"
										on:click={() => openAccessFor(model)}
									>
										<UsersIcon className="size-3.5" />
										{$i18n.t('Access')}
									</button>
								</div>
							{/if}
						</div>
					</div>
				{/each}
			{/if}
				</div>
			</div>
		</div>

		<!-- Footer -->
		<div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-2 mt-3 text-2xs text-[#8A8B8D] dark:text-customGray-300">
			<div>
				{totalCount} {$i18n.t('Models')} · {activeCount} {$i18n.t('active')} · {euCount} {$i18n.t('EU-hosted')}
			</div>
			<div class="flex items-center gap-3">
				<div class="flex items-center gap-1.5">
					<span>{$i18n.t('Rows per page')}</span>
					<div class="relative" use:onClickOutside={() => (showPageSizeDropdown = false)}>
						<button
							class="flex items-center gap-1 px-2 h-7 rounded-md border border-lightGray-400 dark:border-customGray-700 bg-lightGray-300 dark:bg-customGray-900 text-lightGray-100 dark:text-customGray-100"
							on:click={() => (showPageSizeDropdown = !showPageSizeDropdown)}
						>
							<span>{pageSize}</span>
							<ChevronDown className="size-2.5" />
						</button>
						{#if showPageSizeDropdown}
							<div class="absolute right-0 bottom-8 min-w-[5rem] bg-lightGray-300 dark:bg-customGray-900 border border-lightGray-400 dark:border-customGray-700 rounded-md py-1 shadow-sm z-20">
								{#each [5, 10, 20, 50, 100] as n}
									<button
										class="w-full px-3 py-1.5 text-left hover:bg-lightGray-700 dark:hover:bg-customGray-800 text-lightGray-100 dark:text-customGray-100"
										on:click={() => { pageSize = n; showPageSizeDropdown = false; currentPage = 1; }}
									>{n}</button>
								{/each}
							</div>
						{/if}
					</div>
				</div>
				<div class="flex items-center gap-1">
					<button
						class="w-6 h-6 flex items-center justify-center rounded hover:bg-lightGray-700 dark:hover:bg-customGray-800 disabled:opacity-30"
						disabled={currentPage <= 1}
						on:click={() => (currentPage = Math.max(1, currentPage - 1))}
						aria-label="prev"
					>
						<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
					</button>
					<span>{currentPage} {$i18n.t('of')} {totalPages}</span>
					<button
						class="w-6 h-6 flex items-center justify-center rounded hover:bg-lightGray-700 dark:hover:bg-customGray-800 disabled:opacity-30"
						disabled={currentPage >= totalPages}
						on:click={() => (currentPage = Math.min(totalPages, currentPage + 1))}
						aria-label="next"
					>
						<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>
					</button>
				</div>
			</div>
		</div>
	{:else}
		<div class="h-[20rem] w-full flex justify-center items-center">
			<Spinner />
		</div>
	{/if}
</div>

<AccessControlModal
	bind:show={showAccessModal}
	model={selectedModel}
	{groups}
	{defaultModelIds}
	onSave={handleAccessSave}
/>

<ModelDetailsModal bind:show={showDetailsModal} model={selectedModel} />
