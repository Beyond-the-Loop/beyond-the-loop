<script lang="ts">
	import { getContext } from 'svelte';
	import CitationsModal from './CitationsModal.svelte';
	import Collapsible from '$lib/components/common/Collapsible.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import MagnifyingGlass from '$lib/components/icons/MagnifyingGlass.svelte';

	const i18n = getContext('i18n');

	export let sources = [];

	let citations = [];
	let showPercentage = false;
	let showRelevance = true;

	let showCitationModal = false;
	let selectedCitation: any = null;
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
				console.log(_source.name);

				// if (metadata?.name) {
				// 	_source = { ..._source, name: metadata.name };
				// }
				if (metadata?.domain) {
					_source = { ..._source, domain: metadata.domain };
				}

				// if (id.startsWith('http://') || id.startsWith('https://')) {
				// 	_source = { ..._source, ...(!metadata?.name ? { name: id } : {}), url: id };
				// }

				const existingSource = acc.find((item) => item.id === id);

				if (existingSource) {
					existingSource.document.push(document);
					existingSource.metadata.push(metadata);
					if (distance !== undefined) existingSource.distances.push(distance);
				} else {
					acc.push({
						id: id,
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
	<Collapsible bind:open={isCollapsibleOpen} className="mt-2 relative w-full text-sm px-2 py-1 rounded-xl {isCollapsibleOpen ? 'bg-lightGray-200': ''}">
		<div class="w-fit rounded-full px-4 py-1 text-lightGray-100 hover:bg-lightGray-200 flex gap-1 items-center {isCollapsibleOpen ? 'bg-lightGray-200': ''} ml-auto absolute right-0 top-2">
			<div class="flex -space-x-2">
				{#each citations.slice(0, 3) as citation, idx}
					{#if citation.source.domain}
						<img
							src={`https://www.google.com/s2/favicons?domain=${citation.source.domain}&sz=32`}
							class="rounded-full size-4 border border-lightGray-300 border-2 flex-shrink-0"
							alt=""
							on:error={(e) => (e.currentTarget.style.display = 'none')}
						/>
					{/if}
				{/each}
			</div>
			
			{citations.length} Quellen
			{#if isCollapsibleOpen}
				<ChevronUp strokeWidth="2" className="size-3"/>
			{:else}
				<ChevronDown strokeWidth="2" className="size-3"/>
			{/if}
		</div>
		<div slot="content">
		<div class="flex flex-row items-center gap-2 px-1 py-2 overflow-x-hidden max-w-[80%] truncate">
			<div class = "text-xs font-medium text-gray-600">
				Gesucht nach
			</div>
			<div class="flex flex-row items-center w-fit px-3 py-1 rounded-full text-xs">
				<MagnifyingGlass className="size-3" strokeWidth="1.5"/>
				<div class="ml-1">
				"goldpreis aktuell mai 2026"
				</div>
				
			</div>
			<div class="flex flex-row items-center w-fit px-3 py-1 gap-1 rounded-full text-xs">
				<MagnifyingGlass className="size-3" strokeWidth="1.5"/>
				<div class="ml-1">
				"gold kaufen euro pro gramm"
				</div>
				
			</div>
			<div class="flex flex-row items-center w-fit px-3 py-1 gap-1 rounded-full text-xs">
				<MagnifyingGlass className="size-3" strokeWidth="1.5"/>
				<div class="ml-1">
				"goldpreis prognose entwicklung"
				</div>
				
			</div>
		</div>
			<div class="text-xs font-medium">
				{#each citations as citation, idx}
					<button
						class="flex gap-2 items-center text-lightGray-100 dark:text-customGray-100 p-2 transition rounded-xl max-w-100"
						on:click={() => {
							if (citation.source?.url) {
								window.open(citation.source.url, '_blank', 'noopener,noreferrer');
								return;
							}
							showCitationModal = true;
							selectedCitation = citation;
						}}
					>
						{#if citations.every((c) => c.distances !== undefined)}
							<div class="text-gray-600 size-4 mr-2">
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
									<!-- {citation.source.domain} -->
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
