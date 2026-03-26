<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { flyAndScale } from '$lib/utils/transitions';
	import { getContext } from 'svelte';

	import { settings } from '$lib/stores';

	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import AdjustmentsHorizontal from '$lib/components/icons/AdjustmentsHorizontal.svelte';
	import WebSearchIcon from '$lib/components/icons/WebSearchIcon.svelte';
	import ImageGenerateIcon from '$lib/components/icons/ImageGenerateIcon.svelte';
	import CodeInterpreterIcon from '$lib/components/icons/CodeInterpreterIcon.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';

	const i18n = getContext('i18n');

	export let canWebSearch = false;
	export let canImageGen = false;
	export let canCodeInterpreter = false;

	export let webSearchEnabled = false;
	export let imageGenerationEnabled = false;
	export let codeInterpreterEnabled = false;
	export let autoToolsEnabled = false;

	let show = false;

	$: hasAnyFeature = canWebSearch || canImageGen || canCodeInterpreter;

	$: isActive =
		autoToolsEnabled || webSearchEnabled || imageGenerationEnabled || codeInterpreterEnabled;
</script>

{#if hasAnyFeature}
	<DropdownMenu.Root bind:open={show} closeFocus={false} typeahead={false}>
		<DropdownMenu.Trigger>
			<Tooltip content={$i18n.t('Tools')} placement="top">
				<button
					type="button"
					class="p-[3px] transition rounded-md focus:outline-none hover:bg-gray-100 dark:hover:bg-customGray-900 {isActive
						? 'text-blue-500 dark:text-blue-400'
						: 'text-customGray-900 dark:text-customGray-100'}"
					aria-label={$i18n.t('Tools')}
				>
					<AdjustmentsHorizontal className="size-5" />
				</button>
			</Tooltip>
		</DropdownMenu.Trigger>

		<DropdownMenu.Content
			class="w-full max-w-[220px] rounded-lg px-1 py-1 border-gray-300/30 border dark:border-customGray-700 z-50 bg-white dark:bg-customGray-900 dark:text-white shadow"
			sideOffset={15}
			alignOffset={-8}
			side="top"
			align="start"
			transition={flyAndScale}
		>
			<!-- Auto toggle -->
			<button
				class="flex w-full justify-between gap-2 items-center px-2 py-2 text-xs dark:text-customGray-100 font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-customGray-950 rounded-lg"
				on:click|preventDefault={() => {
					autoToolsEnabled = !autoToolsEnabled;
					if (autoToolsEnabled) {
						webSearchEnabled = true;
						imageGenerationEnabled = true;
						codeInterpreterEnabled = true;
					} else {
						webSearchEnabled = false;
						imageGenerationEnabled = false;
						codeInterpreterEnabled = false;
					}
				}}
			>
				<div class="flex gap-2 items-center">
					<Sparkles className="size-4" />
					{$i18n.t('Auto')}
				</div>
				<Switch state={autoToolsEnabled} small />
			</button>

			{#if canWebSearch || canImageGen || canCodeInterpreter}
				<hr class="border-black/5 dark:border-white/5 my-1" />
			{/if}

			{#if canWebSearch}
				<button
					class="flex w-full justify-between gap-2 items-center px-2 py-2 text-xs dark:text-customGray-100 font-medium cursor-pointer rounded-lg {autoToolsEnabled
						? 'opacity-40 pointer-events-none'
						: 'hover:bg-gray-50 dark:hover:bg-customGray-950'}"
					on:click|preventDefault={() => {
						if (!autoToolsEnabled) {
							webSearchEnabled = !webSearchEnabled;
						}
					}}
				>
					<div class="flex gap-2 items-center">
						<WebSearchIcon />
						{$i18n.t('Web Search')}
					</div>
					<Switch disabled={autoToolsEnabled} state={webSearchEnabled} small />
				</button>
			{/if}

			{#if canImageGen}
				<button
					class="flex w-full justify-between gap-2 items-center px-2 py-2 text-xs dark:text-customGray-100 font-medium cursor-pointer rounded-lg {autoToolsEnabled
						? 'opacity-40 pointer-events-none'
						: 'hover:bg-gray-50 dark:hover:bg-customGray-950'}"
					on:click|preventDefault={() => {
						if (!autoToolsEnabled) {
							imageGenerationEnabled = !imageGenerationEnabled;
						}
					}}
				>
					<div class="flex gap-2 items-center">
						<ImageGenerateIcon />
						{$i18n.t('Image Generation')}
					</div>
					<Switch disabled={autoToolsEnabled} state={imageGenerationEnabled} small />
				</button>
			{/if}

			{#if canCodeInterpreter}
				<button
					class="flex w-full justify-between gap-2 items-center px-2 py-2 text-xs dark:text-customGray-100 font-medium cursor-pointer rounded-lg {autoToolsEnabled
						? 'opacity-40 pointer-events-none'
						: 'hover:bg-gray-50 dark:hover:bg-customGray-950'}"
					on:click|preventDefault={() => {
						if (!autoToolsEnabled) {
							codeInterpreterEnabled = !codeInterpreterEnabled;
						}
					}}
				>
					<div class="flex gap-2 items-center">
						<CodeInterpreterIcon />
						{$i18n.t('Code Interpreter')}
					</div>
					<Switch disabled={autoToolsEnabled} state={codeInterpreterEnabled} small />
				</button>
			{/if}
		</DropdownMenu.Content>
	</DropdownMenu.Root>
{/if}
