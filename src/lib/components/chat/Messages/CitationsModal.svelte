<script lang="ts">
	import { getContext } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import type { RagSource } from '$lib/utils/sources';

	const i18n = getContext('i18n');

	export let show = false;
	export let citation: RagSource | null = null;
	export let showPercentage = false;
	export let showRelevance = true;

	function calculatePercentage(score: number) {
		if (score < 0) return 0;
		if (score > 1) return 100;
		return Math.round(score * 10000) / 100;
	}

	function getRelevanceColor(percentage: number) {
		if (percentage >= 80)
			return 'bg-green-200 dark:bg-green-800 text-green-800 dark:text-green-200';
		if (percentage >= 60)
			return 'bg-yellow-200 dark:bg-yellow-800 text-yellow-800 dark:text-yellow-200';
		if (percentage >= 40)
			return 'bg-orange-200 dark:bg-orange-800 text-orange-800 dark:text-orange-200';
		return 'bg-red-200 dark:bg-red-800 text-red-800 dark:text-red-200';
	}

	type SnippetEntry = { document: string; score: number | undefined };

	let snippetEntries: SnippetEntry[] = [];

	$: if (citation) {
		snippetEntries = (citation.snippets ?? []).map((snippet, i) => ({
			document: snippet,
			score: citation!.scores?.[i]
		}));
		if (snippetEntries.every((e) => e.score !== undefined)) {
			snippetEntries = [...snippetEntries].sort(
				(a, b) => (b.score ?? Infinity) - (a.score ?? Infinity)
			);
		}
	}
</script>

<Modal size="lg" bind:show>
	<div>
		<div class=" flex justify-between dark:text-gray-300 px-5 pt-4 pb-2">
			<div class=" text-lg font-medium self-center capitalize">
				{$i18n.t('Citation')}
			</div>
			<button
				class="self-center"
				on:click={() => {
					show = false;
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-5 h-5"
				>
					<path
						d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
					/>
				</svg>
			</button>
		</div>

		<div class="flex flex-col md:flex-row w-full px-6 pb-5 md:space-x-4">
			<div
				class="flex flex-col w-full dark:text-gray-200 overflow-y-scroll max-h-[22rem] scrollbar-hidden"
			>
				{#each snippetEntries as entry, entryIdx}
					<div class="flex flex-col w-full">
						<div class="text-sm font-medium dark:text-gray-300">
							{$i18n.t('Source')}
						</div>

						{#if citation?.name}
							<Tooltip
								className="w-fit"
								content={$i18n.t('Open file')}
								placement="top-start"
								tippyOptions={{ duration: [500, 0] }}
							>
								<div class="text-sm dark:text-gray-400 flex items-center gap-2 w-fit">
									<a
										class="hover:text-gray-500 hover:dark:text-gray-100 underline flex-grow"
										href={citation.file_id
											? `${WEBUI_API_BASE_URL}/files/${citation.file_id}/content`
											: '#'}
										target="_blank"
									>
										{citation.name}
									</a>
								</div>
							</Tooltip>

							{#if showRelevance}
								<div class="text-sm font-medium dark:text-gray-300 mt-2">
									{$i18n.t('Relevance')}
								</div>
								{#if entry.score !== undefined}
									<Tooltip
										className="w-fit"
										content={$i18n.t('Semantic distance to query')}
										placement="top-start"
										tippyOptions={{ duration: [500, 0] }}
									>
										<div class="text-sm my-1 dark:text-gray-400 flex items-center gap-2 w-fit">
											{#if showPercentage}
												{@const percentage = calculatePercentage(entry.score)}
												<span class={`px-1 rounded font-medium ${getRelevanceColor(percentage)}`}>
													{percentage.toFixed(2)}%
												</span>
												<span class="text-gray-500 dark:text-gray-500">
													({entry.score.toFixed(4)})
												</span>
											{:else}
												<span class="text-gray-500 dark:text-gray-500">
													{entry.score.toFixed(4)}
												</span>
											{/if}
										</div>
									</Tooltip>
								{:else}
									<div class="text-sm dark:text-gray-400">
										{$i18n.t('No distance available')}
									</div>
								{/if}
							{/if}
						{:else}
							<div class="text-sm dark:text-gray-400">
								{$i18n.t('No source available')}
							</div>
						{/if}
					</div>

					<div class="flex flex-col w-full">
						<div class=" text-sm font-medium dark:text-gray-300 mt-2">
							{$i18n.t('Content')}
						</div>
						<pre class="text-sm dark:text-gray-400 whitespace-pre-line">{entry.document}</pre>
					</div>

					{#if entryIdx !== snippetEntries.length - 1}
						<hr class=" dark:border-gray-850 my-3" />
					{/if}
				{/each}
			</div>
		</div>
	</div>
</Modal>
