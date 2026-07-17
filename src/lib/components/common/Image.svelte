<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { copyToClipboard, downloadImage } from '$lib/utils';
	import ImagePreview from './ImagePreview.svelte';
	import Download from '$lib/components/icons/Download.svelte';
	import Clipboard from '$lib/components/icons/Clipboard.svelte';
	import Tooltip from './Tooltip.svelte';

	const i18n = getContext('i18n');

	export let src = '';
	export let alt = '';
	export let caption = '';

	export let className = ' w-full outline-none focus:outline-none';
	export let imageClassName = 'rounded-xl';
	export let showDownload = false;

	const copyCaption = async () => {
		if (await copyToClipboard(caption)) {
			toast.success($i18n.t('Copying to clipboard was successful!'));
		}
	};

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
		<img
			src={_src}
			{alt}
			title={caption || undefined}
			class="w-full not-prose {imageClassName}"
			draggable="false"
			data-cy="image"
		/>
	</button>

	{#if showDownload}
		<div
			class="absolute top-2 right-2 opacity-0 group-hover/image:opacity-100 focus-within:opacity-100 transition-opacity duration-150"
		>
			<Tooltip content={$i18n?.t('Download')}>
				<button
					type="button"
					aria-label={$i18n?.t('Download')}
					class="p-1.5 rounded-lg bg-white/70 hover:bg-white text-black dark:bg-black/50 dark:hover:bg-black/70 dark:text-white backdrop-blur-sm shadow-sm transition-colors outline-none focus:outline-none"
					on:click|stopPropagation={() => downloadImage(_src, caption || undefined)}
				>
					<Download className="size-4" strokeWidth = "2" />
				</button>
			</Tooltip>
		</div>
	{/if}

</div>

<ImagePreview bind:show={showImagePreview} src={_src} {alt} {caption} />
