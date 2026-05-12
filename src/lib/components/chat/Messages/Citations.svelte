<script lang="ts">
	import { getContext } from 'svelte';
	import CitationsModal from './CitationsModal.svelte';
	import Collapsible from '$lib/components/common/Collapsible.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import MagnifyingGlass from '$lib/components/icons/MagnifyingGlass.svelte';
	import { normalizeSources, type Source, type WebSearchSource, type RagSource } from '$lib/utils/sources';

	const i18n = getContext('i18n');

	export let sources = [];

	export let showCitationModal = false;
	export let selectedCitation: RagSource | null = null;
	let isCollapsibleOpen = false;

	let normalized: Source[] = [];
	let usedQueries: string[] = [];
	let showRelevance = false;
	let showPercentage = false;

	$: {
		normalized = normalizeSources(sources.filter((s) => Object.keys(s).length > 0));
		usedQueries =
			(normalized.find(
				(s): s is WebSearchSource => s.type === 'web_search' && (s.queries?.length ?? 0) > 0
			) as WebSearchSource | undefined)?.queries ?? [];
		const ragWithScores = normalized.filter(
			(s): s is RagSource => s.type === 'rag' && s.scores.length > 0
		);
		showRelevance = ragWithScores.length > 0;
		showPercentage = showRelevance && ragWithScores.every((s) => s.scores.every((d) => d >= -1 && d <= 1));
	}
</script>

<CitationsModal
	bind:show={showCitationModal}
	citation={selectedCitation}
	{showPercentage}
	{showRelevance}
/>

{#if normalized.length > 0}
	<Collapsible bind:open={isCollapsibleOpen} className="relative w-full text-sm px-3 rounded-xl pt-2 {isCollapsibleOpen ? 'bg-lightGray-200 dark:bg-customGray-900': ''} transition-colors duration-200">
		<div class="w-fit rounded-full px-4 py-[3px] text-lightGray-100 dark:text-customGray-100 flex gap-1 items-center transition-all duration-200 ease {isCollapsibleOpen ? 'bg-lightGray-200 dark:bg-customGray-800 border-lightGray-200 dark:border-customGray-800': 'bg-lightGray-300 border-lightGray-300 dark:bg-customGray-900 dark:border-customGray-900 hover:bg-lightGray-200 hover:border-lightGray-200 dark:hover:bg-customGray-800 dark:hover:border-customGray-800'} top-2 absolute right-0 z-10">
			<div class="flex -space-x-2 bg-inherit border-inherit">
				{#each normalized.slice(0, 3) as source}
					{#if source.type === 'web_search'}
						<img
							src={`https://www.google.com/s2/favicons?domain=${source.domain}&sz=32`}
							class="rounded-full size-4 bg-inherit border border-2 border-inherit flex-shrink-0"
							alt=""
							on:error={(e) => (e.currentTarget.style.display = 'none')}
						/>
					{/if}
				{/each}
			</div>

			{normalized.length} {$i18n.t(normalized.length === 1 ? 'Source' : 'Sources')}
			<div style="transform: rotate({isCollapsibleOpen ? 180 : 0}deg); transition: transform 0.2s ease">
				<ChevronDown strokeWidth="2" className="size-3" />
			</div>
		</div>

		<div slot="content" class="pb-3">
			{#if usedQueries.length > 0}
				<div class="flex flex-row items-center gap-2 px-1 py-[3px] text-xs">
					<div class="font-medium text-gray-600 dark:text-gray-500">
						{$i18n.t('Searched for')}
					</div>
					<div class="max-w-[75%] overflow-x-scroll no-scrollbar" style="-ms-overflow-style: none !important; scrollbar-width: none !important;">
						<div class="flex flex-row">
							{#each usedQueries as query}
								<div class="shrink-0 flex flex-row flex-nowrap items-center px-3 py-1">
									<MagnifyingGlass className="size-3" strokeWidth="1.5" />
									<div class="ml-1">"{query}"</div>
								</div>
							{/each}
						</div>
					</div>
				</div>
			{/if}

			<div class="text-xs font-medium overflow-x-hidden">
				{#each normalized as source, idx}
					<button
						class="flex gap-2 w-full items-center text-lightGray-100 dark:text-customGray-100 hover:bg-lightGray-300 dark:hover:bg-gray-800 p-2 transition rounded-xl max-w-100"
						on:click={() => {
							if (source.type === 'web_search') {
								window.open(source.url, '_blank', 'noopener,noreferrer');
								return;
							}
							showCitationModal = true;
							selectedCitation = source;
						}}
					>
						{#if showRelevance}
							<div class="text-gray-600 size-4 mr-2 flex-shrink-0">{idx + 1}</div>
						{/if}
						{#if source.type === 'web_search'}
							<img
								src={`https://www.google.com/s2/favicons?domain=${source.domain}&sz=32`}
								class="rounded-md size-4 flex-shrink-0"
								alt=""
								on:error={(e) => (e.currentTarget.style.display = 'none')}
							/>
							<div class="flex flex-col items-start">
								<div class="text-sm line-clamp-1 truncate">{source.title}</div>
								<div class="text-xs text-gray-600 dark:text-gray-500 line-clamp-1 truncate max-w-[720px]">{source.domain}</div>
							</div>
						{:else}
							<div class="line-clamp-1 truncate">{source.name}</div>
						{/if}
					</button>
				{/each}
			</div>
		</div>
	</Collapsible>
{/if}
