<script lang="ts">
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { fade } from 'svelte/transition';
	import DOMPurify from 'dompurify';

	export let sources: { domain: string; title: string; url: string }[];

	let showPopover = false;
	let popoverAbove = true;
	let badgeEl: HTMLElement;
	let hideTimeout: ReturnType<typeof setTimeout>;

	function onMouseEnter() {
		clearTimeout(hideTimeout);
		if (badgeEl) popoverAbove = badgeEl.getBoundingClientRect().top > 140;
		showPopover = true;
	}

	function onMouseLeave() {
		hideTimeout = setTimeout(() => (showPopover = false), 200);
	}
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<span
	class="relative inline-flex select-none"
	bind:this={badgeEl}
	on:mouseenter={onMouseEnter}
	on:mouseleave={onMouseLeave}
>
	<a
		href={sources[0]?.url}
		target="_blank"
		rel="nofollow"
		class="!no-underline inline-flex justify-center text-xs leading-0 items-center gap-1 px-[.4rem] py-[.1rem] bg-lightGray-400 hover:bg-lightGray-200 border border-transparent hover:border-gray-200 transition dark:bg-[#2d2f2f] text-lightGray-100 dark:text-customGray-100 border-lightGray-500 rounded-lg mr-1"
	>
		<img
			src={`https://www.google.com/s2/favicons?domain=${sources[0]?.domain}&sz=32`}
			class="rounded-full size-3 flex-shrink-0"
			alt=""
			on:error={(e) => (e.currentTarget.style.display = 'none')}
		/>
		{sources[0]?.domain}
		{#if sources.length > 1}
			<span class="opacity-60">+{sources.length - 1}</span>
		{/if}
	</a>

	{#if showPopover}
		<div
			class="absolute left-1/2 -translate-x-1/2 {popoverAbove
				? 'bottom-full mb-1'
				: 'top-full mt-1'} z-50 w-80 rounded-lg bg-lightGray-300 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 overflow-hidden p-1 flex flex-col gap-0.5"
			transition:fade={{ duration: 100 }}
		>
			{#each sources as source}
				<a
					href={source.url}
					target="_blank"
					rel="nofollow"
					class="flex rounded-lg flex-col gap-0.5 p-2.5 px-4 hover:bg-lightGray-400 dark:hover:bg-gray-800 transition-colors !no-underline"
				>
					<span class="text-sm font-medium text-lightGray-100 dark:text-gray-100 line-clamp-2">
						{@html DOMPurify.sanitize(source.title)}
					</span>
					<div class="flex items-center gap-1">
						<img
							src={`https://www.google.com/s2/favicons?domain=${source.domain}&sz=48`}
							class="size-4 rounded-full flex-shrink-0"
							alt=""
							on:error={(e) => (e.currentTarget.style.display = 'none')}
						/>
						<span class="text-xs text-gray-500 dark:text-gray-400 truncate">
							{source.domain}
						</span>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</span>
