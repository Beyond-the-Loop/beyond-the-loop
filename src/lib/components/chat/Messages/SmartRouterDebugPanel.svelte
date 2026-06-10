<script lang="ts">
	import WebSearchIcon from '$lib/components/icons/WebSearchIcon.svelte';
	import ImageGenerateIcon from '$lib/components/icons/ImageGenerateIcon.svelte';
	import CodeInterpreterIcon from '$lib/components/icons/CodeInterpreterIcon.svelte';
	import Cube from '$lib/components/icons/Cube.svelte';
	import Info from '$lib/components/icons/Info.svelte';

	export let debug: {
		required_tools: string[];
		domain: string | null;
		task_type: string | null;
		complexity: number;
		candidates: { name: string; score: number }[];
	};

	let visible = false;
	let hideTimer: ReturnType<typeof setTimeout>;

	function show() {
		clearTimeout(hideTimer);
		visible = true;
	}

	function scheduleHide() {
		hideTimer = setTimeout(() => (visible = false), 200);
	}

	const complexityStrings: Record<number, string> = {
		1: 'very easy',
		2: 'easy',
		3: 'medium',
		4: 'hard'
	};

	const complexityClass: Record<number, string> = {
		1: 'text-green-500 dark:text-green-400',
		2: 'text-lime-500 dark:text-lime-400',
		3: 'text-yellow-500 dark:text-yellow-400',
		4: 'text-red-500 dark:text-red-400'
	};

	$: hasWebSearch = debug.required_tools.includes('web_search');
	$: hasImage = debug.required_tools.includes('image_generation');
	$: hasCode =
		debug.required_tools.includes('code_execution') ||
		debug.required_tools.includes('document_creation');
	$: hasMCP = 
		debug.required_tools.includes('mcp_connector');
	$: anyTool = hasWebSearch || hasImage || hasCode || hasMCP;
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
	class="relative inline-flex items-center"
	on:mouseenter={show}
	on:mouseleave={scheduleHide}
>
	<button
		class="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300 transition-colors"
		aria-label="Smart Router Details"
		tabindex="-1"
	>
		<Info className="size-3" />
	</button>

	{#if visible}
		<!-- svelte-ignore a11y-no-static-element-interactions -->
		<div
			class="absolute top-full left-0 mt-1.5 z-50 w-64 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg p-3 text-xs"
			on:mouseenter={show}
			on:mouseleave={scheduleHide}
		>
			<div class="text-2xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-2.5">
				Smart Router Panel (Entwickler)
			</div>

			<!-- Tools -->
			{#if anyTool}
				<div class="flex items-center gap-2 mb-2.5">
					<WebSearchIcon
						className="size-3.5 {hasWebSearch
							? 'text-blue-500'
							: 'text-gray-300 dark:text-gray-600'}"
					/>
					<ImageGenerateIcon
						className="size-3.5 {hasImage
							? 'text-blue-500'
							: 'text-gray-300 dark:text-gray-600'}"
					/>
					<CodeInterpreterIcon
						className="size-3.5 {hasCode
							? 'text-blue-500'
							: 'text-gray-300 dark:text-gray-600'}"
					/>
					<Cube
						className="size-3.5 {hasMCP
							? 'text-blue-500'
							: 'text-gray-300 dark:text-gray-600'}"
					/>
				</div>
			{:else}
				<div class="flex items-center gap-2 mb-2.5 text-gray-300 dark:text-gray-600">
					<WebSearchIcon className="size-3.5" />
					<ImageGenerateIcon className="size-3.5" />
					<CodeInterpreterIcon className="size-3.5" />
					<Cube className="size-3.5"/>
				</div>
			{/if}

			<!-- Badges -->
			<div class="flex flex-wrap gap-1 mb-2.5">
				{#if debug.complexity != null}
					<span
						class="px-1.5 py-0.5 rounded-md bg-gray-100 dark:bg-gray-800 font-medium {complexityClass[debug.complexity] ?? ''}"
					>
						{complexityStrings[debug.complexity]}
					</span>
				{/if}
				{#if debug.domain}
					<span
						class="px-1.5 py-0.5 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300"
					>
						{debug.domain}
					</span>
				{/if}
				{#if debug.task_type}
					<span
						class="px-1.5 py-0.5 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300"
					>
						{debug.task_type}
					</span>
				{/if}
			</div>

			<!-- Candidates -->
			{#if debug.candidates?.length}
				<div class="text-2xs text-gray-400 dark:text-gray-500 mb-1">
					Modelle · Arena-Score ↑
				</div>
				<div class="overflow-y-auto max-h-36 space-y-px">
					{#each debug.candidates as candidate, i}
						<div
							class="flex items-center justify-between rounded-md px-1.5 py-0.5 {i === 0
								? 'bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 font-medium'
								: 'text-gray-600 dark:text-gray-400'}"
						>
							<span class="truncate">{candidate.name}</span>
							<span class="ml-2 shrink-0 tabular-nums text-gray-400 dark:text-gray-500 font-normal">
								{candidate.score}
							</span>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>
