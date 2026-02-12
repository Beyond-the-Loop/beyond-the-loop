<script lang="ts">
	import { user } from '$lib/stores';
	import { getContext } from 'svelte';
	import Selector from './ModelSelector/Selector.svelte';

	const i18n = getContext('i18n');

	export let selectedModels = [];

</script>

<div class="flex flex-col items-start bg-lightGray-800 dark:bg-customGray-800 py-[4px] px-[6px] rounded-md w-fit">
	{#each selectedModels as selectedModel, selectedModelIdx}
		<div class="flex w-full max-w-fit">
			<div class="overflow-hidden w-full">
				<div class="max-w-full">
					<Selector
						id={`${selectedModelIdx}`}
						placeholder={$i18n.t('Select a model')}
						
						showTemporaryChatControl={$user.role === 'user'
							? ($user?.permissions?.chat?.temporary ?? true)
							: true}
						bind:value={selectedModel}
					/>
				</div>
			</div>
		</div>
	{/each}
</div>
