<script lang="ts">
	import { getContext } from 'svelte';
	import WebSearchIcon from '$lib/components/icons/WebSearchIcon.svelte';
	import ImageGenerateIcon from '$lib/components/icons/ImageGenerateIcon.svelte';
	import CodeInterpreterIcon from '$lib/components/icons/CodeInterpreterIcon.svelte';
	import Info from '$lib/components/icons/Info.svelte';
	import { getModelIcon } from '$lib/utils';
	import { fade } from 'svelte/transition';
	import Cube from '$lib/components/icons/Cube.svelte';

	const i18n = getContext('i18n');

	export let debug: {
		required_tools: string[];
		domain: string | null;
		task_type: string | null;
		complexity: number;
		candidates: { name: string; score: number }[];
	};

	let visible = false;
	let openUp = false;
	let hideTimer: ReturnType<typeof setTimeout>;
	let triggerEl: HTMLDivElement;

	function show() {
		clearTimeout(hideTimer);
		if (triggerEl) {
			const rect = triggerEl.getBoundingClientRect();
			const spaceBelow = window.innerHeight - rect.bottom;
			const spaceAbove = rect.top;
			openUp = spaceAbove > spaceBelow;
		}
		visible = true;
	}

	function scheduleHide() {
		hideTimer = setTimeout(() => (visible = false), 200);
	}

	const complexityKeys: Record<number, string> = {
		1: 'very easy',
		2: 'easy',
		3: 'medium',
		4: 'hard'
	};

	$: hasWebSearch = debug.required_tools.includes('web_search');
	$: hasImage = debug.required_tools.includes('image_generation');
	$: hasCode =
		debug.required_tools.includes('code_execution') ||
		debug.required_tools.includes('document_creation');
	$: hasMcp = debug.required_tools.includes('mcp');

	$: anyTool = hasWebSearch || hasImage || hasCode || hasMcp;

	$: topCandidates = debug.candidates?.slice(0, 4) ?? [];
	$: selectedModel = topCandidates[0];
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
	class="relative inline-flex items-center"
	bind:this={triggerEl}
	on:mouseenter={show}
	on:mouseleave={scheduleHide}
>
	<button
		class="text-gray-500 hover:text-gray-500 dark:hover:text-gray-300 transition-colors"
		aria-label={$i18n.t('Smart Router Details')}
		tabindex="-1"
	>
		<Info className="size-3" />
	</button>

	{#if visible}
		<!-- svelte-ignore a11y-no-static-element-interactions -->
		<div
			class="absolute {openUp ? 'bottom-full mb-2' : 'top-full mt-2'} left-0 z-50 w-72 rounded-2xl bg-white dark:bg-customGray-800 text-xs overflow-hidden"
			on:mouseenter={show}
			on:mouseleave={scheduleHide}
			transition:fade={{ duration: 100 }}
		>
			<div class="px-5 pt-5 pb-4 flex items-center gap-2">
				<img src="/smart-router.svg" class="size-3.5">
				<div class="text-2xs font-medium tracking-wide text-gray-500 dark:text-gray-500">
					Smart Router
				</div>
				<div class="ml-auto bg-lightGray-200 dark:bg-customGray-700 rounded-full px-2 text-2xs text-gray-500 dark:text-gray-500">
					v2.0
				</div>
			</div>

			<div class="px-5 pb-5">
				<!-- Analyse Grid -->
				<div class="grid grid-cols-2 gap-x-4 gap-y-4">
					<div>
						<div class="text-2xs text-gray-500 dark:text-gray-500 mb-1">{$i18n.t('Tools')}</div>
						{#if anyTool}
							<div class="flex items-center gap-2 h-[14px]">
								{#if hasWebSearch}
									<WebSearchIcon className="size-3.5 text-blue-500" />
								{/if}
								{#if hasImage}
									<ImageGenerateIcon className="size-3.5 text-blue-500" />
								{/if}
								{#if hasCode}
									<CodeInterpreterIcon className="size-3.5 text-blue-500" />
								{/if}
								{#if hasMcp}
									<Cube className="size-3.5 text-blue-500" />
								{/if}
							</div>
						{:else}
							<div class="text-xs text-gray-800 dark:text-gray-200">{$i18n.t('N/A')}</div>
						{/if}
					</div>

					<div>
						<div class="text-2xs text-gray-500 dark:text-gray-500 mb-1">{$i18n.t('Difficulty')}</div>
						<div class="text-xs text-gray-800 dark:text-gray-200">{complexityKeys[debug.complexity] ? $i18n.t(complexityKeys[debug.complexity]) : $i18n.t('N/A')}</div>
					</div>

					<div>
						<div class="text-2xs text-gray-500 dark:text-gray-500 mb-1">{$i18n.t('Topic')}</div>
						<div class="text-xs text-gray-800 dark:text-gray-200 truncate">{debug.domain ? $i18n.t(debug.domain) : $i18n.t('N/A')}</div>
					</div>

					<div>
						<div class="text-2xs text-gray-500 dark:text-gray-500 mb-1">{$i18n.t('Task')}</div>
						<div class="text-xs text-gray-800 dark:text-gray-200 truncate">{debug.task_type ?? $i18n.t('N/A')}</div>
					</div>
				</div>

				{#if selectedModel}
					<div class="mt-5 pt-4 border-t border-gray-100 dark:border-gray-800">
					<div class="bg-blue-50 dark:bg-customGray-700 rounded-md px-3 py-2">
						<div class="text-2xs text-gray-500 dark:text-gray-500 mb-1">
							{$i18n.t('Optimized for your request')}
						</div>
						<div class="flex items-center gap-2.5">
							<img src={getModelIcon(selectedModel.name)} class="size-5">
							<div class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
								{selectedModel.name}
							</div>
						</div>
					</div>
						
					</div>
				{/if}

				{#if topCandidates.length > 1}
					<div class="mt-4">
						<div class="text-2xs text-gray-500 dark:text-gray-500 mb-2">
							{$i18n.t('More matching models ↑')}
						</div>
						<div class="flex flex-col gap-2">
							{#each topCandidates.slice(1) as candidate}
								<div class="flex items-center gap-2.5 text-xs text-gray-900 dark:text-gray-100 font-medium">
									<img src={getModelIcon(candidate.name)} class="size-4 rounded-full">
									<span class="truncate">{candidate.name}</span>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
