<script lang="ts">
	import { Pagination } from 'bits-ui';
	import { createEventDispatcher } from 'svelte';

	import ChevronLeft from '../icons/ChevronLeft.svelte';
	import ChevronRight from '../icons/ChevronRight.svelte';

	export let page = 0;
	export let count = 0;
	export let perPage = 15;
</script>

<div class="flex justify-center">
	<Pagination.Root bind:page {count} {perPage} let:pages>
		<div class="my-2 flex items-center">
			<Pagination.PrevButton
				class="mr-[20px] inline-flex size-8 items-center justify-center rounded-[9px] bg-transparent hover:bg-gray-50 dark:hover:bg-gray-850 active:scale-98 disabled:cursor-not-allowed disabled:text-gray-400 dark:disabled:text-gray-700 hover:disabled:bg-transparent dark:hover:disabled:bg-transparent"
			>
				<ChevronLeft className="size-3" strokeWidth="2" />
			</Pagination.PrevButton>
			<div class="flex items-center gap-2">
				{#each pages as page (page.key)}
					{#if page.type === 'ellipsis'}
						<div class="text-sm text-foreground-alt">...</div>
					{:else}
						<Pagination.Page
							{page}
							class="inline-flex size-8 items-center justify-center rounded-[9px] bg-transparent text-xs font-medium active:scale-98 disabled:cursor-not-allowed disabled:opacity-50 hover:disabled:bg-transparent data-[selected]:bg-lightGray-400 data-[selected]:text-lightGray-100  dark:data-[selected]:bg-customGray-950 dark:data-[selected]:text-white dark:text-customGray-100 transition"
						>
							{page.value}
						</Pagination.Page>
					{/if}
				{/each}
			</div>
			<Pagination.NextButton
				class="ml-[20px]  inline-flex size-8 items-center justify-center rounded-[9px] bg-transparent hover:bg-gray-50 dark:hover:bg-gray-850 active:scale-98 disabled:cursor-not-allowed disabled:text-gray-400 dark:disabled:text-gray-700 hover:disabled:bg-transparent dark:hover:disabled:bg-transparent"
			>
				<ChevronRight className="size-3" strokeWidth="2" />
			</Pagination.NextButton>
		</div>
	</Pagination.Root>
</div>
