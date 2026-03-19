<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();

	export let step: number;
	export let totalSteps: number;
</script>

<div class="mb-6 flex items-center gap-3">
	<button
		type="button"
		on:click={() => dispatch('back')}
		class="flex h-8 w-8 items-center justify-center rounded-lg text-[#16181D] transition hover:bg-gray-100 dark:text-customGray-100 dark:hover:bg-customGray-800"
	>
		<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5">
			<path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd" />
		</svg>
	</button>
	<span class="text-sm text-[#6B7280] dark:text-customGray-300">{step}/{totalSteps}</span>
</div>
