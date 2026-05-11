<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { marked } from 'marked';

	import { onMount, getContext, tick, createEventDispatcher } from 'svelte';
	import { blur, fade } from 'svelte/transition';

	const dispatch = createEventDispatcher();

	import { config, user, models as _models, temporaryChatEnabled, company, showLibrary } from '$lib/stores';
	import { sanitizeResponseContent, findWordIndices } from '$lib/utils';
	import { WEBUI_BASE_URL } from '$lib/constants';

	import Suggestions from './Suggestions.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EyeSlash from '$lib/components/icons/EyeSlash.svelte';
	import MessageInput from './MessageInput.svelte';
	import ModelSelector from './ModelSelector.svelte';
	import BookIcon from '../icons/BookIcon.svelte';
	import { showChatInfoSidebar, chatInfoSidebarMode } from '$lib/stores';

	const i18n = getContext('i18n');

	export let transparentBackground = false;

	export let createMessagePair: Function;
	export let stopResponse: Function;

	export let autoScroll = false;

	export let atSelectedModel: Model | undefined;
	export let selectedModels: [''];

	export let history;

	export let prompt = '';
	export let files = [];

	export let imageGenerationEnabled = false;
	export let codeInterpreterEnabled = false;
	export let webSearchEnabled = false;
	export let autoToolsEnabled = false;
	export let isMagicLoading;
	export let initNewChatCompleted;

	// PII toggle: state + show flag + click callback are owned by the parent
	// (Chat.svelte). We just render the button and call the callback. No bind:.
	export let piiEnabled = true;
	export let showPiiToggle = false;
	export let onPiiToggle: () => void = () => {};

	// Privacy panel link (toggles the right-side sidebar). Visibility +
	// detection counts come from Chat.svelte so the text is consistent.
	export let showPiiPanel = false;
	export let piiCount = 0;
	export let piiAnonymizedCount = 0;

	let models = [];

	const selectSuggestionPrompt = async (p) => {
		let text = p;

		if (p.includes('{{CLIPBOARD}}')) {
			const clipboardText = await navigator.clipboard.readText().catch((err) => {
				toast.error($i18n.t('Failed to read clipboard contents'));
				return '{{CLIPBOARD}}';
			});

			text = p.replaceAll('{{CLIPBOARD}}', clipboardText);

			console.log('Clipboard text:', clipboardText, text);
		}

		prompt = text;

		console.log(prompt);
		await tick();

		const chatInputContainerElement = document.getElementById('chat-input-container');
		const chatInputElement = document.getElementById('chat-input');

		if (chatInputContainerElement) {
			chatInputContainerElement.style.height = '';
			chatInputContainerElement.style.height =
				Math.min(chatInputContainerElement.scrollHeight, 200) + 'px';
		}

		await tick();
		if (chatInputElement) {
			chatInputElement.focus();
			chatInputElement.dispatchEvent(new Event('input'));
		}

		await tick();
	};

	let selectedModelIdx = 0;

	$: if (selectedModels.length > 0) {
		selectedModelIdx = models.length - 1;
	}

	$: models = selectedModels.map((id) => $_models.find((m) => m.id === id));

	onMount(() => {});
	$: currentModel = $_models.find((item) => item.id === selectedModels?.[0]);
</script>

<div class="m-auto w-full max-w-6xl px-2 @2xl:px-20 translate-y-6 py-24 text-center">
	{#if $temporaryChatEnabled}
		<Tooltip
			content="This chat won't appear in history and your messages will not be saved."
			className="w-full flex justify-center mb-0.5"
			placement="top"
		>
			<div class="flex items-center gap-2 text-gray-500 font-medium text-lg my-2 w-fit">
				<EyeSlash strokeWidth="2.5" className="size-5" /> Temporary chat
			</div>
		</Tooltip>
	{/if}

	<div
		class="w-full text-3xl text-gray-800 dark:text-gray-100 font-medium text-center flex items-center gap-4 font-primary"
	>
		<div class="w-full flex flex-col justify-center items-center">
			<!-- <div class="flex flex-row justify-center gap-3 @sm:gap-3.5 w-fit px-5">
				<div class="flex flex-shrink-0 justify-center">
					<div class="flex -space-x-4 mb-0.5" in:fade={{ duration: 100 }}>
						{#each models as model, modelIdx}
							<Tooltip
								content={(models[modelIdx]?.info?.meta?.tags ?? [])
									.map((tag) => tag.name.toUpperCase())
									.join(', ')}
								placement="top"
							>
								<button
									on:click={() => {
										selectedModelIdx = modelIdx;
									}}
								>
									<img
										crossorigin="anonymous"
										src={model?.info?.meta?.profile_image_url ??
											($i18n.language === 'dg-DG'
												? `/doge.png`
												: `${WEBUI_BASE_URL}/static/favicon.png`)}
										class=" size-9 @sm:size-10 rounded-full border-[1px] border-gray-200 dark:border-none"
										alt="logo"
										draggable="false"
									/>
								</button>
							</Tooltip>
						{/each}
					</div>
				</div> 

				<div class=" text-3xl @sm:text-4xl line-clamp-1" in:fade={{ duration: 100 }}>
					{#if models[selectedModelIdx]?.name}
						{models[selectedModelIdx]?.name}
					{:else}
						{$i18n.t('Hello, {{name}}', { name: $user.name })}
					{/if}
				</div> 
			</div>  -->

			<!-- <div class="flex mt-1 mb-2">
				<div in:fade={{ duration: 100, delay: 50 }}>
					{#if models[selectedModelIdx]?.info?.meta?.description ?? null}
						<Tooltip
							className=" w-fit"
							content={marked.parse(
								sanitizeResponseContent(models[selectedModelIdx]?.info?.meta?.description ?? '')
							)}
							placement="top"
						>
							<div
								class="mt-0.5 px-2 text-sm font-normal text-gray-500 dark:text-gray-400 line-clamp-2 max-w-xl markdown"
							>
								{@html marked.parse(
									sanitizeResponseContent(models[selectedModelIdx]?.info?.meta?.description)
								)}
							</div>
						</Tooltip>

						{#if models[selectedModelIdx]?.info?.meta?.user}
							<div class="mt-0.5 text-sm font-normal text-gray-400 dark:text-gray-500">
								By
								{#if models[selectedModelIdx]?.info?.meta?.user.community}
									<a
										href="https://openwebui.com/m/{models[selectedModelIdx]?.info?.meta?.user
											.username}"
										>{models[selectedModelIdx]?.info?.meta?.user.name
											? models[selectedModelIdx]?.info?.meta?.user.name
											: `@${models[selectedModelIdx]?.info?.meta?.user.username}`}</a
									>
								{:else}
									{models[selectedModelIdx]?.info?.meta?.user.name}
								{/if}
							</div>
						{/if}
					{/if}
				</div>
			</div> -->

			<div class="relative text-base font-normal @md:max-w-3xl w-full py-3 {atSelectedModel ? 'mt-2' : ''}">
				{#if currentModel?.base_model_id}
					<div class="absolute -top-[12rem] left-1/2 tramsform -translate-x-1/2 w-[25rem] flex items-center flex-col">
						{#if !currentModel?.meta?.profile_image_url || currentModel?.meta?.profile_image_url.length > 5}
						<img
							class="w-16 h-16 rounded-lg mb-2"
							src={currentModel?.meta?.profile_image_url
								? currentModel?.meta?.profile_image_url
								: $company?.profile_image_url}
							alt={currentModel?.name}
						/>
						{:else}
							<div class="text-[3.5rem] h-11">{currentModel?.meta?.profile_image_url}</div>
						{/if}
						<div class="dark:text-customGray-100 text-base font-normal mb-2">
							{currentModel?.name}
						</div>
						{#if currentModel?.meta?.description}
						<div class="text-xs dark:text-customGray-100/50 font-normal">
							{currentModel?.meta?.description}
						</div>
						{/if}
					</div>
				{/if}
				<div class="px-2.5 mb-2.5 flex justify-between">
					<ModelSelector
						bind:selectedModels
					/>
					<div class="flex items-center gap-2">
						{#if showPiiPanel && piiCount > 0}
							<button
								type="button"
								class="flex space-x-[5px] items-center py-[3px] px-[6px] rounded-md bg-lightGray-800 dark:bg-customGray-800 min-w-fit text-xs text-lightGray-100 dark:text-customGray-100 font-medium"
								aria-label={$i18n.t('Privacy panel')}
								on:click={() => {
								if ($showChatInfoSidebar && $chatInfoSidebarMode.kind === 'composer') {
									showChatInfoSidebar.set(false);
								} else {
									chatInfoSidebarMode.set({ kind: 'composer' });
									showChatInfoSidebar.set(true);
								}
							}}
							>
								<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-3.5">
									<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m0-10.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Zm0 13.036h.008v.008H12v-.008Z" />
								</svg>
								<span>{$i18n.t('{{anonymized}} of {{total}} entities will be anonymized', { anonymized: piiAnonymizedCount, total: piiCount })}</span>
							</button>
						{/if}
						<button class="flex space-x-[5px] items-center py-[3px] px-[6px] rounded-md bg-lightGray-800 dark:bg-customGray-800 min-w-fit text-xs text-lightGray-100 dark:text-customGray-100 font-medium" on:click={() => showLibrary.set(!$showLibrary)}>
							<BookIcon /> <span>{$i18n.t('Library')}</span>
						</button>
					</div>
				</div>
				<MessageInput
					{history}
					{selectedModels}
					bind:files
					bind:prompt
					bind:autoScroll
					bind:imageGenerationEnabled
					bind:codeInterpreterEnabled
					bind:webSearchEnabled
					bind:autoToolsEnabled
					bind:atSelectedModel
					{piiEnabled}
					{showPiiToggle}
					{onPiiToggle}
					{transparentBackground}
					{stopResponse}
					{createMessagePair}
					{isMagicLoading}
					placeholder={$i18n.t('How can I help you today?')}
					on:upload={(e) => {
						dispatch('upload', e.detail);
					}}
					on:submit={(e) => {
						dispatch('submit', e.detail);
					}}
					on:magicPrompt={(e) => {
						dispatch('magicPrompt', prompt);
					}}
				/>
			</div>
		</div>
	</div>
	<div class="font-primary" in:fade={{ duration: 200, delay: 200 }}>
		<div class="mx-auto max-w-3xl min-h-[55px]">
			<Suggestions
				suggestionPrompts={models[selectedModelIdx]?.meta?.suggestion_prompts ??
					$config?.default_prompt_suggestions ??
					[]}
				inputValue={prompt}
				on:select={(e) => {
					selectSuggestionPrompt(e.detail);
				}}
			/>
		</div>
	</div>
</div>
