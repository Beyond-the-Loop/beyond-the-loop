<script>
	import { modelsInfo } from '../../../../data/modelsInfo';
	import { getContext, onMount } from 'svelte';
    import InfoIcon from '$lib/components/icons/InfoIcon.svelte';
	import CheckmarkIcon from '$lib/components/icons/CheckmarkIcon.svelte';

	const i18n = getContext('i18n');
	export let hoveredItem = null;

	let knowledgeCutoff = null;

	$: {
		if (modelsInfo?.[hoveredItem?.name]?.knowledge_cutoff) {
			const date = new Date(modelsInfo?.[hoveredItem?.name]?.knowledge_cutoff);

			const formatted = date.toLocaleString('default', {
				year: 'numeric',
				month: 'long'
			});
			knowledgeCutoff = formatted;
		}
	}
let tooltipEl;
let triggerEl;
let placeAbove = false;

function positionTooltip() {
	if (!tooltipEl || !triggerEl) return;

	const tooltipRect = tooltipEl.getBoundingClientRect();
	const triggerRect = triggerEl.getBoundingClientRect();

	const spaceBelow = window.innerHeight - triggerRect.bottom;
	const spaceAbove = triggerRect.top;

	placeAbove = spaceBelow < tooltipRect.height && spaceAbove > tooltipRect.height;
}

onMount(() => {
	window.addEventListener('resize', positionTooltip);
	window.addEventListener('scroll', positionTooltip, true);

	return () => {
		window.removeEventListener('resize', positionTooltip);
		window.removeEventListener('scroll', positionTooltip, true);
	};
});
</script>


<div bind:this={triggerEl}
on:mouseenter={positionTooltip} class="ml-1 cursor-pointer group relative flex justify-center items-center w-[18px] h-[18px] rounded-full text-white dark:text-white bg-customBlue-600 dark:bg-customGray-700">
    <InfoIcon className="size-6" />
	<div
	bind:this={tooltipEl}
	class={`invisible group-hover:visible absolute -left-7 md:left-0 px-3 py-1 left-full ml-2 w-[23rem] p-2 rounded-xl border border-lightGray-400 dark:border-customGray-700 bg-lightGray-550 dark:bg-customGray-900 text-sm text-gray-800 dark:text-white z-50 shadow
		${placeAbove ? 'bottom-full mb-2' : 'top-0'}`}
	>
		<div class="mb-1.5 text-xs font-medium text-lightGray-100 dark:text-customGray-100">{hoveredItem?.name}/<span class="text-lightGray-900 dark:text-white/50 font-normal">{modelsInfo?.[hoveredItem?.name]?.organization}</span></div>
		<div>
			<p class="text-xs text-lightGray-100 dark:text-customGray-100 {!modelsInfo?.[hoveredItem?.name]?.multimodal && !modelsInfo?.[hoveredItem?.name]?.reasoning && "mb-2"}">
				{$i18n.t(modelsInfo?.[hoveredItem?.name]?.description)}
			</p>
		</div>
		<div class="flex items-center gap-x-3">
			{#if modelsInfo?.[hoveredItem?.name]?.multimodal}
				<div class="py-2.5 flex items-center">
					<div class="mr-1.5 cursor-pointer flex justify-center items-center w-[18px] h-[18px] rounded-full text-white dark:text-white bg-customBlue-600 dark:bg-customGray-700">
						<CheckmarkIcon className="size-6" />
					</div>
					<p class="text-xs dark:text-customGray-100">{$i18n.t('Multimodal')}</p>
				</div>
			{/if}
			{#if modelsInfo?.[hoveredItem?.name]?.reasoning}
				<div class="py-2.5 flex items-center">
					<div class="mr-1.5 cursor-pointer flex justify-center items-center w-[18px] h-[18px] rounded-full text-white dark:text-white bg-customBlue-600 dark:bg-customGray-700">
						<CheckmarkIcon className="size-6" />
					</div>
					<p class="text-xs dark:text-customGray-100">{$i18n.t('Reasoning')}</p>
				</div>
			{/if}
			{#if modelsInfo?.[hoveredItem?.name]?.zdr}
				<div class="py-2.5 flex items-center">
					<div class="mr-1.5 cursor-pointer flex justify-center items-center w-[18px] h-[18px] rounded-full text-white dark:text-white bg-customBlue-600 dark:bg-customGray-700">
						<CheckmarkIcon className="size-6" />
					</div>
					<p class="text-xs dark:text-customGray-100">{$i18n.t('Zero Data Retention')}</p>
				</div>
			{/if}
		</div>
		<div class="grid grid-cols-3 gap-y-4 gap-x-2 border-t border-lightGray-400 dark:border-customGray-700">
			<div class="flex flex-col items-center py-2">
				{#if modelsInfo?.[hoveredItem?.name]?.hosted_in}
					<p class="text-xs dark:text-customGray-100">{modelsInfo?.[hoveredItem?.name]?.hosted_in}</p>
					<p class="text-2xs text-lightGray-900 dark:text-white/50">{$i18n.t('Hosted in')}</p>
				{/if}
			</div>
			<div class="flex flex-col items-center py-2 border-r border-l border-lightGray-400 dark:border-customGray-700">
				<p class="text-xs dark:text-customGray-100">
					{#if knowledgeCutoff}
						{knowledgeCutoff}	
					{:else}
						N/A
					{/if}
				</p>
				<p class="text-2xs text-lightGray-900 dark:text-white/50">{$i18n.t('Knowledge cutoff')}</p>
			</div>
			<div class="flex flex-col items-center py-2">
				<p class="text-xs dark:text-customGray-100">
					{#if modelsInfo?.[hoveredItem?.name]?.context_window}
						{modelsInfo?.[hoveredItem?.name]?.context_window}
					{:else}
						N/A
					{/if}
				</p>
				<p class="text-2xs text-lightGray-900 dark:text-white/50">{$i18n.t('Context window')}</p>
			</div>
		</div>
	</div>
</div>
