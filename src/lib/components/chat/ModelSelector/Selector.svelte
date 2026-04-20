<script lang="ts">
	import { flyAndScale } from '$lib/utils/transitions';
	import { onMount, getContext } from 'svelte';

	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import Search from '$lib/components/icons/Search.svelte';

	import { user, models, mobile } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import { splitStream } from '$lib/utils';
	import { getModels } from '$lib/apis';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import StarRating from './IntelligenceRating.svelte';
	import SpeedRating from './SpeedRating.svelte';
	import { mapModelsToOrganizations } from '../../../../data/modelsInfo';
	import { getModelIcon } from '$lib/utils';
	import CostRating from './CostRating.svelte';
	import { subscription, modelsInfo } from '$lib/stores';
	import { DropdownMenu } from 'bits-ui';
	import WebSearchIcon from '$lib/components/icons/WebSearchIcon.svelte';
	import ImageGenerateIcon from '$lib/components/icons/ImageGenerateIcon.svelte';
	import LightBlub from '$lib/components/icons/LightBlub.svelte';
	import Document from '$lib/components/icons/Document.svelte';
	import CodeInterpreterIcon from '$lib/components/icons/CodeInterpreterIcon.svelte';
	import EuIcon from '$lib/components/icons/EuIcon.svelte';
	import AdjustmentsHorizontal from '$lib/components/icons/AdjustmentsHorizontal.svelte';

	const i18n = getContext('i18n');

	export let id = '';
	export let value = '';
	export let placeholder = 'Select a model';
	export let searchEnabled = true;
	export let searchPlaceholder = $i18n.t('Search a model');

	export let triggerClassName = 'text-xs';

	let show = false;

	let selectedModel = '';

	$: selectedModel = $models.map((model) => ({
		value: model.id,
		label: model.name,
		model: model
	})).find((item) => item.value === value) ?? '';

	let searchValue = '';
	let selectedModelIdx = 0;

	$: modelGroups = mapModelsToOrganizations($modelsInfo);
	$: desiredOrder = Object.values(modelGroups).flat();
	$: orderMap = new Map(desiredOrder.map((name, index) => [name, index]));
	let filteredSourceItems = []
	$: filteredSourceItems = (() => {
		const allItems = $models.map((model) => ({
				value: model.id,
				label: model.name,
				model: model
			}))
			.filter?.((item) => !item?.model?.name?.toLowerCase()?.includes('arena'));

		let items;
		if ($user?.permissions?.chat?.assistants_only) {
			// Assistants-only mode: show only assistants whose base model is active, no Smart Router
			items = allItems.filter((item) =>
				item.model?.base_model_id != null &&
				item.model?.is_active !== false &&
				item.model?.name !== 'Smart Router'
			) ?? [];
		} else {
			const baseItems = allItems?.filter((item) => item.model?.base_model_id == null) ?? [];
			const hasNonSmartRouterBase = baseItems.some((item) => item?.model?.name !== 'Smart Router');

			// Fall back to assistants when no base models are available
			items = hasNonSmartRouterBase
				? baseItems
				: (allItems?.filter((item) => item.model?.base_model_id != null) ?? []);
		}

		const hasNonSmartRouter = items.some((item) => item?.model?.name !== 'Smart Router');
		return items
			.filter((item) => item?.model?.name !== 'Smart Router' || hasNonSmartRouter)
			.sort((a, b) => {
				if (a?.model?.name === 'Smart Router') return -1;
				if (b?.model?.name === 'Smart Router') return 1;
				return (orderMap.get(a?.model?.name) ?? Infinity) - (orderMap.get(b?.model?.name) ?? Infinity);
			});
	})();

	$: filteredItems = (() => {
		let items = filteredSourceItems;

		if (searchValue) {
			items = items.filter(item =>
				item?.model?.name?.toLowerCase()?.includes(searchValue?.toLowerCase())
			);
		}
		if (webSearchFilter) {
			items = items.filter(item =>
				$modelsInfo?.[item.label]?.supports_web_search
			);
		}
		if (codeExecutionFilter) {
			items = items.filter(item =>
				$modelsInfo?.[item.label]?.supports_code_execution
			);
		}
		if (imageGenFilter) {
			items = items.filter(item =>
				$modelsInfo?.[item.label]?.supports_image_generation
			);
		}

		return items;
	})();


	let webSearchFilter = false;
	let codeExecutionFilter = false;
	let imageGenFilter = false;

	// In assistants-only mode: auto-select the first assistant if current value is missing/invalid
	$: if ($user?.permissions?.chat?.assistants_only && filteredSourceItems.length > 0) {
		const currentValid = filteredSourceItems.some((item) => item.value === value);
		if (!currentValid) {
			value = filteredSourceItems[0].value;
		}
	}

	let hoveredItem = null;
	let hoverTimeout: ReturnType<typeof setTimeout> | null = null;
	function setHoverTimeout(){
		hoverTimeout = setTimeout(() =>{
			hoveredItem = null;
		}, 200);
	} 

	let knowledgeCutoff = null;

	$: {
		if ($modelsInfo?.[hoveredItem?.label]?.knowledge_cutoff) {
			const date = new Date($modelsInfo?.[hoveredItem?.label]?.knowledge_cutoff);

			const formatted = date.toLocaleString('default', {
				year: 'numeric',
				month: 'long'
			});
			knowledgeCutoff = formatted;
		} else {
			knowledgeCutoff = null;
		}
	}

	let baseModel = null;

	$: {
		if (selectedModel?.model?.base_model_id) {
			baseModel = $models.map((model) => ({
				value: model.id,
				label: model.name,
				model: model
			})).find((item) => item?.model?.id === selectedModel?.model?.base_model_id);
		}
	}

</script>
<DropdownMenu.Root
	bind:open={show}
	onOpenChange={async () => {
		searchValue = '';
		selectedModelIdx = 0;
		window.setTimeout(() => document.getElementById('model-search-input')?.focus(), 0);
	}}
	closeFocus={false}
>
	{#if !selectedModel?.model?.base_model_id}
		<DropdownMenu.Trigger
			class="relative w-full flex"
			aria-label={placeholder}
			id="model-selector-{id}-button"
		>
			<div
				class="flex w-full text-left px-0.5 outline-none bg-transparent truncate {triggerClassName} justify-between dark:text-customGray-100 placeholder-gray-400 focus:outline-none"
			>
				{#if selectedModel}
					<img
						src={getModelIcon(selectedModel.label)}
						alt="Model"
						class="rounded-full size-4 self-center mr-2"
					/>
					{selectedModel.label}
				{:else}
					{placeholder}
				{/if}
				<ChevronDown className=" self-center ml-2 size-2" strokeWidth="2" />
			</div>
		</DropdownMenu.Trigger>
	{:else}
		<div
			class="flex w-full text-left px-0.5 outline-none bg-transparent truncate {triggerClassName} justify-between placeholder-gray-400 focus:outline-none"
		>
			{#if selectedModel}
				<img
					src={getModelIcon(baseModel?.model?.name)}
					alt="Model"
					class="rounded-full size-4 self-center mr-2"
				/>
				<!-- {selectedModel.label} -->
				{baseModel?.model?.name}
			{:else}
				{placeholder}
			{/if}
		</div>
	{/if}

	<DropdownMenu.Content
		class=" z-40 {$mobile
			? `w-[15rem]`
			: ``} justify-start rounded-xl border dark:border-customGray-700 bg-lightGray-550 border-lightGray-400 dark:bg-customGray-900 dark:text-white shadow-lg  outline-none"
		transition={flyAndScale}
		side={$mobile ? 'bottom' : 'bottom-start'}
		sideOffset={5}
	>
		<slot>
			{#if searchEnabled}
			<div class="flex items-center">
				<div class="flex items-center relative gap-2.5 px-2.5 mt-2.5 mb-3">
					<div class="absolute left-5 text-customGray-300">
						<Search className="size-3" strokeWidth="2.5" />
					</div>

					<input
						id="model-search-input"
						bind:value={searchValue}
						class="max-w-[142px] text-xs bg-transparent outline-none pl-7 h-[25px] rounded-lg border border-lightGray-400 dark:border-customGray-700 placeholder:text-xs"
						placeholder={searchPlaceholder}
						autocomplete="off"
						on:keydown={(e) => {
							if (e.code === 'Enter' && filteredItems.length > 0) {
								value = filteredItems[selectedModelIdx].value;
								show = false;
								return; // dont need to scroll on selection
							} else if (e.code === 'ArrowDown') {
								selectedModelIdx = Math.min(selectedModelIdx + 1, filteredItems.length - 1);
							} else if (e.code === 'ArrowUp') {
								selectedModelIdx = Math.max(selectedModelIdx - 1, 0);
							} else {
								// if the user types something, reset to the top selection.
								selectedModelIdx = 0;
							}

							const item = document.querySelector(`[data-arrow-selected="true"]`);
							item?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
						}}
					/>
				</div>
				<div class="flex items-center justify-end w-full mr-3">
					<DropdownMenu.Root>
						<DropdownMenu.Trigger class="flex items-center cursor-pointer p-[2px] hover:bg-gray-100 dark:hover:bg-customGray-950 rounded-md">
							<Tooltip content={$i18n.t('Filter')} placement="top">
								<AdjustmentsHorizontal className="size-5 {webSearchFilter || codeExecutionFilter || imageGenFilter ? 'text-blue-500': 'text-gray-500'}" />
							</Tooltip>
						</DropdownMenu.Trigger>

						<DropdownMenu.Content
							class="flex items-center gap-2 p-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-lightGray-550 dark:bg-customGray-900 shadow-lg z-50"
							transition={flyAndScale}
							side="bottom"
							sideOffset={0}
						>
							<Tooltip content={$i18n.t('Web Search')} placement="top">
							<button
								class={webSearchFilter ? 'text-blue-500' : 'text-gray-500'}
								on:click={() => {
								webSearchFilter = !webSearchFilter;
								}}
							>
								<WebSearchIcon className="size-4" />
							</button>
							</Tooltip>
							<Tooltip content={$i18n.t('Code Interpreter')} placement="top">
                                <button class="{codeExecutionFilter ? 'text-blue-500' : 'text-gray-500'}"
                                    on:click={() => {
                                        codeExecutionFilter = !codeExecutionFilter;
                                    }}
                                >
                                    <CodeInterpreterIcon className="size-4" />
                                </button>
                            </Tooltip>
                            <Tooltip content={$i18n.t('Image Generation')} placement="top">
                                <button class="{imageGenFilter ? 'text-blue-500' : 'text-gray-500'}"
                                    on:click={() => {
                                        imageGenFilter = !imageGenFilter;
                                    }}
                                >
                                    <ImageGenerateIcon className="size-4" />
                                </button>
                            </Tooltip>
						</DropdownMenu.Content>
					</DropdownMenu.Root>
				</div>
				
			</div>
			{/if}

			<div class="px-[3px] my-2 h-[280px] overflow-y-auto">
					{#each filteredItems as item, index}
						<button
							aria-label="model-item"
							class="flex w-full text-left line-clamp-1 select-none items-center rounded-button py-[5px] px-2 text-sm outline-none transition-all duration-75 rounded-lg
						{value === item.value ? 'bg-lightGray-700 dark:bg-customGray-950' : ''}
						{!item.model?.is_active || item.model?.fair_usage_limit_reached ? 'opacity-50 cursor-not-allowed pointer-events-none text-gray-400 dark:text-gray-600' : 'text-lightGray-100 dark:text-customGray-100 hover:bg-lightGray-700 dark:hover:bg-customGray-950 dark:hover:text-white'}"

							data-arrow-selected={index === selectedModelIdx}
							on:mouseenter={() => {
								hoveredItem = item;
								if(hoverTimeout)
								{
									clearTimeout(hoverTimeout); 
									hoverTimeout = null;
								}
								}}
							on:mouseleave={setHoverTimeout}
							on:click={() => {
								value = item.value;
								selectedModelIdx = index;

								show = false;
							}}
							disabled={!item.model?.is_active || item.model?.fair_usage_limit_reached}
						>
							<div class="flex flex-col">
								{#if $mobile && (item?.model?.meta?.tags ?? []).length > 0}
									<div class="flex gap-0.5 self-start h-full mb-1.5 -translate-x-1">
										{#each item.model?.meta.tags as tag}
											<div
												class=" text-xs font-bold px-1 rounded uppercase line-clamp-1 bg-gray-500/20 text-gray-700 dark:text-gray-200"
											>
												{tag.name}
											</div>
										{/each}
									</div>
								{/if}
								<div class="flex items-center gap-2">
									<div class="flex items-center min-w-fit">
										<div class="line-clamp-1">
											<div class="flex items-center min-w-fit">
												<img
													src={getModelIcon(item.label)}
													alt="Model"
													class="rounded-full size-5 flex items-center mr-2"
												/>
												<div class="text-xs w-[112px]">
													<span>{item.label}</span>
													{#if !item.model?.is_active}
														<span class="text-[0.4rem] ml-[-2px] align-super">Premium</span>
													{:else if item.model?.fair_usage_limit_reached}
														<span class="text-[0.4rem] ml-[-2px] align-super">Limit reached</span>
													{/if}
												</div>
											</div>
										</div>
									</div>
								</div>
							</div>
							{#if value === item.value}
								<div class="ml-auto pl-2 pr-2 md:pr-0 text-lightGray-100 dark:text-customGray-100">
									<svg
										width="13"
										height="14"
										viewBox="0 0 9 10"
										fill="none"
										xmlns="http://www.w3.org/2000/svg"
									>
										<path
											d="M4.16004 6.27718C4.08868 6.27718 4.02088 6.24863 3.97093 6.19868L2.96115 5.1889C2.85768 5.08542 2.85768 4.91415 2.96115 4.81068C3.06463 4.7072 3.2359 4.7072 3.33937 4.81068L4.16004 5.63135L5.99405 3.79733C6.09753 3.69386 6.2688 3.69386 6.37227 3.79733C6.47575 3.90081 6.47575 4.07208 6.37227 4.17555L4.34915 6.19868C4.2992 6.24863 4.2314 6.27718 4.16004 6.27718Z"
											fill="currentColor"
										/>
									</svg>
								</div>
							{/if}
							{#if $modelsInfo?.[item?.label]?.hosted_in == 'EU'}
								<div class="w-3 ml-auto opacity-80 dark:opacity-100">
										<EuIcon className="size-3"/>
								</div>
							{/if}
						</button>
					{:else}
						<div>
							<div class="block px-3 py-2 text-sm text-gray-700 dark:text-gray-100">
								{$i18n.t('No results found')}
							</div>
						</div>
					{/each}
				
				{#if hoveredItem && !$mobile}
					<div
						role="tooltip"
						class=" shadow-lg absolute flex flex-col h-[100%] left-full ml-1 top-0 w-[23rem] p-2.5 rounded-xl border border-lightGray-400 bg-lightGray-550 dark:border-customGray-700 dark:bg-customGray-900 text-sm text-gray-800 dark:text-white z-50"
						on:mouseenter={() => {
							if(hoverTimeout)
							{
								clearTimeout(hoverTimeout); 
								hoverTimeout = null;
							}}}
						on:mouseleave={setHoverTimeout}
					>
						<div class="mb-1.5 text-xs font-medium text-lightGray-100 dark:text-customGray-100">{hoveredItem?.label}{" "}<span class="text-lightGray-900 dark:text-white/50 font-normal">/{" "}{$modelsInfo?.[hoveredItem?.label]?.organization || "Beyond the Loop"}</span></div>
						<div>
							<p class="text-xs text-lightGray-100 dark:text-customGray-100">
								{#if hoveredItem.label == "Smart Router"}
								{$i18n.t("Selects the optimal AI model for each request automatically. To do this, we analyze how complex your request is, match it against the strengths of our models, and choose the most efficient model for the task.")}
								{:else}
								{$i18n.t($modelsInfo?.[hoveredItem?.label]?.description)}
								{/if}
							</p>
						</div>
					{#if hoveredItem.label != "Smart Router"}
						{@const m = $modelsInfo?.[hoveredItem?.label]}
						<div class="grid grid-cols-2 mt-auto">
							<div class="flex flex-col items-center mb-3">
								<div class="mb-1.5 text-lightGray-900 dark:text-white/50 tracking-wide text-2xs">{$i18n.t('MODALITIES')}</div>
								<div class="flex items-center gap-2">
									<Tooltip content={$i18n.t('Text')} placement="bottom">
										<div class="size-7 p-auto border border-gray-200 rounded-lg bg-lightGray-300 text-lightGray-100/80 dark:border-customGray-700  dark:bg-customGray-800 dark:text-lightGray-200 text-[0.9em] font-serif flex items-center justify-center">T</div>
									</Tooltip>
									{#if m?.supports_document_input}
										<Tooltip content={$i18n.t('Documents')} placement="bottom">
											<div class="size-7 p-auto border border-gray-200 rounded-lg bg-lightGray-300 text-lightGray-100/80 dark:border-customGray-700 dark:bg-customGray-800 dark:text-lightGray-200 text-xs flex items-center justify-center"> <Document className="size-4"/></div>
										</Tooltip>
									{/if}
									{#if m?.supports_image_input}
										<Tooltip content={$i18n.t('Images')} placement="bottom">
											<div class="size-7 p-auto border border-gray-200 rounded-lg bg-lightGray-300 text-lightGray-100/80 dark:border-customGray-700 dark:bg-customGray-800 dark:text-lightGray-200 text-xs flex items-center justify-center"> <ImageGenerateIcon className="size-4"/></div>
										</Tooltip>
									{/if}
								</div>
							</div>
							<div class="border-l border-lightGray-400 dark:border-customGray-700">
								<div class="flex flex-col items-center mb-3">
									<div class="mb-1.5 text-lightGray-900 dark:text-white/50 tracking-wide text-2xs">{$i18n.t('TOOLS')}</div>
									<div class="flex items-center gap-2">
										{#if m?.supports_web_search}
										<Tooltip content={$i18n.t('Web Search')} placement="bottom">
											<div class="size-7 border border-blue-200 dark:border-customGray-700 rounded-lg bg-blue-50 dark:bg-customGray-800 text-blue-500 dark:text-blue-400 text-xs flex items-center justify-center"> <WebSearchIcon className="size-4"/></div>
										</Tooltip>
										{/if}
										{#if m?.supports_image_generation}
											<Tooltip content={$i18n.t('Image Generation')} placement="bottom">
												<div class="size-7 border border-blue-200 dark:border-customGray-700 rounded-lg bg-blue-50 dark:bg-customGray-800 text-blue-500 dark:text-blue-400 text-xs flex items-center justify-center"> <ImageGenerateIcon className="size-4"/></div>
											</Tooltip>
										{/if}
										{#if m?.supports_code_execution}
											<Tooltip content={$i18n.t('Code execution')} placement="bottom">
												<div class="size-7 border border-blue-200 dark:border-customGray-700 rounded-lg bg-blue-50 dark:bg-customGray-800 text-blue-500 dark:text-blue-400 text-xs flex items-center justify-center"> <CodeInterpreterIcon className="size-4"/></div>
											</Tooltip>
										{/if}
										{#if m?.reasoning}
											<Tooltip content={$i18n.t('Reasoning')} placement="bottom">
												<div class="size-7 border border-blue-200 dark:border-customGray-700 rounded-lg bg-blue-50 dark:bg-customGray-800 text-blue-500 dark:text-blue-400 text-xs flex items-center justify-center"> <LightBlub className="size-4"/></div>
											</Tooltip>
										{/if}
									</div>
								</div>
							</div>
							
						</div>
						<div class="grid grid-cols-3 gap-y-4 gap-x-2 pt-3 border-t border-lightGray-400 dark:border-customGray-700">
							{#if $subscription?.plan !== 'free' && $subscription?.plan !== 'premium'}
								<div class="flex flex-col items-center text-xs {!m?.costFactor && "justify-end"}">
									{#if m?.costFactor != null}
										<CostRating rating={m?.costFactor} />
									{:else}
										N/A
									{/if}
									<p class="text-2xs text-lightGray-900 dark:text-white/50">{$i18n.t('Cost')}</p>
								</div>
							{:else}
								<div class="flex flex-col items-center text-xs justify-end">
									{#if m?.category != null}
										{m?.category}
									{:else}
										N/A
									{/if}
									<p class="text-2xs text-lightGray-900 dark:text-white/50">{$i18n.t('Fair Usage category')}</p>
								</div>
							{/if}
							<div class="flex flex-col items-center text-xs {!m?.intelligence_score && "justify-end"}">
								{#if m?.intelligence_score}
									<StarRating rating={m?.intelligence_score} />
								{:else}
									N/A
								{/if}
								<p class="text-2xs text-lightGray-900 dark:text-white/50">{$i18n.t('Intelligence score')}</p>
							</div>
							<div class="flex flex-col items-center text-xs {!m?.speed && "justify-end"}">
								{#if m?.speed}
									<SpeedRating rating={m?.speed} tokens_per_second={m?.tokens_per_second} />
								{:else}
									N/A
								{/if}
								<p class="text-2xs text-lightGray-900 dark:text-white/50">{$i18n.t('Tokens/second')}</p>
							</div>
							<div class="flex flex-col items-center py-2">
								{#if m?.hosted_in}
									<p class="text-xs dark:text-customGray-100">{m?.hosted_in}</p>
									<p class="text-2xs text-lightGray-900 dark:text-white/50">{$i18n.t('Hosted in')}</p>
								{/if}
							</div>
							<div class="flex flex-col items-center py-2">
								<p class="text-xs dark:text-customGray-100">
									{#if knowledgeCutoff}
										{knowledgeCutoff
											.trim()
											.split(/\s+/)
											.map(w => $i18n.t(w))
											.join(' ')
										}
									{:else}
										N/A
									{/if}

								</p>
								<p class="text-2xs text-lightGray-900 dark:text-white/50">{$i18n.t('Knowledge cutoff')}</p>
							</div>
							<div class="flex flex-col items-center py-2">
								<p class="text-xs dark:text-customGray-100">
									{#if m?.context_window}
										{m?.context_window}
									{:else}
										N/A
									{/if}
								</p>
								<p class="text-2xs text-lightGray-900 dark:text-white/50">{$i18n.t('Context window')}</p>
							</div>
						</div>

					{/if}

					</div>
				{/if}

			</div>

			<!-- {#if showTemporaryChatControl}
				<hr class="border-gray-50 dark:border-gray-800" />

				<div class="flex items-center mx-2 my-2">
					<button
						class="flex justify-between w-full font-medium line-clamp-1 select-none items-center rounded-button py-2 px-3 text-sm text-gray-700 dark:text-gray-100 outline-none transition-all duration-75 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg cursor-pointer data-[highlighted]:bg-muted"
						on:click={async () => {
							temporaryChatEnabled.set(!$temporaryChatEnabled);
							await goto('/');
							const newChatButton = document.getElementById('new-chat-button');
							setTimeout(() => {
								newChatButton?.click();
							}, 0);

							// add 'temporary-chat=true' to the URL
							if ($temporaryChatEnabled) {
								history.replaceState(null, '', '?temporary-chat=true');
							} else {
								history.replaceState(null, '', location.pathname);
							}

							show = false;
						}}
					>
						<div class="flex gap-2.5 items-center">
							<ChatBubbleOval className="size-4" strokeWidth="2.5" />

							{$i18n.t(`Temporary chat`)}
						</div>

						<div>
							<Switch state={$temporaryChatEnabled} />
						</div>
					</button>
				</div>
			{/if} -->

			<div class="hidden w-[42rem]" />
			<div class="hidden w-[32rem]" />
		</slot>
	</DropdownMenu.Content>
</DropdownMenu.Root>
