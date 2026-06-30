<script lang="ts">
	import { getContext } from 'svelte';
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { downloadImage } from '$lib/utils';
	import ImagePreview from './ImagePreview.svelte';
	import Download from '$lib/components/icons/Download.svelte';
	import Tooltip from './Tooltip.svelte';

	const i18n = getContext('i18n');

	export let src = '';
	export let alt = '';

	export let className = ' w-full outline-none focus:outline-none';
	export let imageClassName = 'rounded-xl';
	export let showDownload = false;

	let _src = '';
	$: _src = src.startsWith('/') ? `${WEBUI_BASE_URL}${src}` : src;

	let showImagePreview = false;
</script>

<div class="relative group/image {className}">
	<button
		class="w-full outline-none focus:outline-none"
		on:click={() => {
			showImagePreview = true;
		}}
		type="button"
	>
		<img src={_src} {alt} class="w-full {imageClassName}" draggable="false" data-cy="image" />
	</button>

	{#if showDownload}
		<div
			class="absolute top-2 right-2 opacity-0 group-hover/image:opacity-100 focus-within:opacity-100 transition-opacity duration-150"
		>
			<Tooltip content={$i18n?.t('Download')}>
				<button
					type="button"
					aria-label={$i18n?.t('Download')}
					class="p-1.5 rounded-xl bg-white/70 hover:bg-white text-black dark:bg-black/50 dark:hover:bg-black/70 dark:text-white backdrop-blur-sm shadow-sm transition-colors outline-none focus:outline-none"
					on:click|stopPropagation={() => downloadImage(_src)}
				>
					<Download className="size-4" strokeWidth = "2" />
				</button>
			</Tooltip>
		</div>
	{/if}
</div>

<ImagePreview bind:show={showImagePreview} src={_src} {alt} />
