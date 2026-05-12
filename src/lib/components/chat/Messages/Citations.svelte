<script lang="ts">
	import { getContext } from 'svelte';
	import CitationsModal from './CitationsModal.svelte';
	import Collapsible from '$lib/components/common/Collapsible.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import MagnifyingGlass from '$lib/components/icons/MagnifyingGlass.svelte';

	const i18n = getContext('i18n');

	export let sources = [];

	let citations = [];
	let showPercentage = false;
	let showRelevance = true;

	export let showCitationModal = false;
	export let selectedCitation: any = null;
	let isCollapsibleOpen = false;

	function calculateShowRelevance(sources: any[]) {
		const distances = sources.flatMap((citation) => citation.distances ?? []);
		const inRange = distances.filter((d) => d !== undefined && d >= -1 && d <= 1).length;
		const outOfRange = distances.filter((d) => d !== undefined && (d < -1 || d > 1)).length;

		if (distances.length === 0) {
			return false;
		}

		if (
			(inRange === distances.length - 1 && outOfRange === 1) ||
			(outOfRange === distances.length - 1 && inRange === 1)
		) {
			return false;
		}

		return true;
	}

	function shouldShowPercentage(sources: any[]) {
		const distances = sources.flatMap((citation) => citation.distances ?? []);
		return distances.every((d) => d !== undefined && d >= -1 && d <= 1);
	}

	$: {
		citations = sources.reduce((acc, source) => {
			if (Object.keys(source).length === 0) {
				return acc;
			}

			source.document.forEach((document, index) => {
				const metadata = source.metadata?.[index];
				const distance = source.distances?.[index];

				// Within the same citation there could be multiple documents
				const id = metadata?.source ?? 'N/A';
				let _source = source?.source;

				if (metadata?.domain) {
					_source = { ..._source, domain: metadata.domain };
				}
				if (metadata?.used_queries) {
					_source = { ..._source, used_queries: metadata.used_queries };

				}

				const existingSource = acc.find((item) => item.id === id);

				if (existingSource) {
					existingSource.document.push(document);
					existingSource.metadata.push(metadata);
					if (distance !== undefined) existingSource.distances.push(distance);
				} else {
					acc.push({
						id: id,
						type: source.type,
						source: _source,
						document: [document],
						metadata: metadata ? [metadata] : [],
						distances: distance !== undefined ? [distance] : undefined
					});
				}
			});
			return acc;
		}, []);

		showRelevance = calculateShowRelevance(citations);
		showPercentage = shouldShowPercentage(citations);
	}
</script>

<CitationsModal
	bind:show={showCitationModal}
	citation={selectedCitation}
	{showPercentage}
	{showRelevance}
/>

{#if citations.length > 0}
	<Collapsible bind:open={isCollapsibleOpen} className="relative w-full text-sm px-3 rounded-xl pt-2 {isCollapsibleOpen ? 'bg-lightGray-200': ''} transition-colors duration-200">
		<div class="w-fit rounded-full px-4 py-[3px] text-lightGray-100 flex gap-1 items-center transition-all duration-200 ease {isCollapsibleOpen ? 'bg-lightGray-200 border-lightGray-200': 'bg-lightGray-300 border-lightGray-300 hover:bg-lightGray-200 hover:border-lightGray-200'} top-2 absolute right-0 z-10">
			<div class="flex -space-x-2 bg-inherit border-inherit">
				{#each citations.slice(0, 3) as citation, idx}
					{#if citation.source.domain}
						<img
							src={`https://www.google.com/s2/favicons?domain=${citation.source.domain}&sz=32`}
							class="rounded-full size-4 bg-inherit border border-2 border-inherit flex-shrink-0"
							alt=""
							on:error={(e) => (e.currentTarget.style.display = 'none')}
						/>
					{/if}
				{/each}
			</div>
			
			{citations.length} {$i18n.t(citations.length == 1 ? 'Source' : 'Sources')}
			  <div style="transform: rotate({isCollapsibleOpen ? 180 : 0}deg); transition: transform 0.2s ease">
					<ChevronDown strokeWidth="2" className="size-3"/>
				</div>
		</div>
		<div slot="content" class="pb-3">
		{#if citations[0].source.used_queries}
			<div class="flex flex-row items-center gap-2 px-1 py-[3px] text-xs ">
				
					<div class = "font-medium text-gray-600">
						{$i18n.t('Searched for')}
					</div>
					<div class="max-w-[75%] overflow-x-scroll no-scrollbar" style="-ms-overflow-style: none !important; scrollbar-width: none !important;">
						<div class="flex flex-row">
							{#each citations[0].source.used_queries as query}
								<div class="shrink-0 flex flex-row flex-nowrap items-center px-3 py-1">
									<MagnifyingGlass className="size-3" strokeWidth="1.5"/>
									<div class="ml-1">
									"{query}"
									</div>
								</div>
							{/each}
						</div>
					</div>
				
				
			</div>
		{/if}
			<div class="text-xs font-medium overflow-x-hidden">
				{#each citations as citation, idx}
					<button
						class="flex gap-2 w-full items-center text-lightGray-100 dark:text-customGray-100 hover:bg-lightGray-300 p-2 transition rounded-xl max-w-100"
						id="source-{citation.id}"
						on:click={() => {
							if (citation.source?.url && citation.type === 'web_search') {
								window.open(citation.source.url, '_blank', 'noopener,noreferrer');
								return;
							}
							showCitationModal = true;
							selectedCitation = citation;
						}}
					>
						{#if citations.every((c) => c.distances !== undefined)}
							<div class="text-gray-600 size-4 mr-2 flex-shrink-0">
								{idx + 1}
							</div>
						{/if}
						{#if citation.source.domain}
							<img
								src={`https://www.google.com/s2/favicons?domain=${citation.source.domain}&sz=32`}
								class="rounded-md size-4 flex-shrink-0"
								alt=""
								on:error={(e) => (e.currentTarget.style.display = 'none')}
							/>
							<div class="flex flex-col items-start">
								<div class="text-sm line-clamp-1 truncate">
									 {citation.source.name}
								</div>
								<div class="text-xs text-gray-600 line-clamp-1 truncate max-w-[720px]">
									 {citation.source.domain}
								</div>
							</div>
						{:else}
							<div class="line-clamp-1 truncate">
								{citation.source.name}
							</div>
						{/if}
					</button>
				{/each}
			</div>
		</div>
	</Collapsible>
{/if}
