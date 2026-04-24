<script lang="ts">
	import { onMount } from 'svelte';
	import QuestionMarkCircle from '$lib/components/icons/QuestionMarkCircle.svelte';
	import ModelDetailsCard from './ModelDetailsCard.svelte';

	export let hoveredItem: any = null;

	let tooltipEl: HTMLElement;
	let triggerEl: HTMLElement;
	let placeAbove = false;
	let alignRight = false;

	function positionTooltip() {
		if (!tooltipEl || !triggerEl) return;
		const tRect = tooltipEl.getBoundingClientRect();
		const trigRect = triggerEl.getBoundingClientRect();

		const spaceBelow = window.innerHeight - trigRect.bottom;
		const spaceAbove = trigRect.top;
		placeAbove = spaceBelow < tRect.height + 16 && spaceAbove > tRect.height + 16;

		const spaceRight = window.innerWidth - trigRect.left;
		alignRight = spaceRight < tRect.width + 16;
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

<div
	bind:this={triggerEl}
	role="presentation"
	on:mouseenter={positionTooltip}
	class="group relative inline-flex items-center ml-1"
>
	<span
		class="p-0.5 -m-0.5 text-lightGray-900 dark:text-customGray-300 group-hover:text-lightGray-100 dark:group-hover:text-white transition-colors cursor-pointer flex items-center"
		aria-label="Modelldetails"
	>
		<QuestionMarkCircle className="size-3.5" strokeWidth="1.5" />
	</span>

	<div
		class="invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-opacity duration-100 absolute z-50 {alignRight
			? 'right-0'
			: 'left-0'} {placeAbove ? 'bottom-full pb-2' : 'top-full pt-2'}"
	>
		<div
			bind:this={tooltipEl}
			class="w-[20rem] rounded-2xl border border-lightGray-400 dark:border-customGray-700 bg-lightGray-550 dark:bg-[#1D1A1A]/95 backdrop-blur-md shadow-xl p-4 text-lightGray-100 dark:text-white"
		>
			<ModelDetailsCard name={hoveredItem?.name ?? ''} />
		</div>
	</div>
</div>
