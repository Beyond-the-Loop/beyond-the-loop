<script lang="ts">
	import { getContext } from 'svelte';
	import { onClickOutside } from '$lib/utils';
	import Checkbox from '$lib/components/common/Checkbox.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import WebSearchIcon from '$lib/components/icons/WebSearchIcon.svelte';
	import ImageGenerateIcon from '$lib/components/icons/ImageGenerateIcon.svelte';
	import CodeInterpreterIcon from '$lib/components/icons/CodeInterpreterIcon.svelte';
	import CitationIcon from '$lib/components/icons/CitationIcon.svelte';
	import VisionIcon from '$lib/components/icons/VisionIcon.svelte';

	const i18n = getContext('i18n');

	export let capabilities: Record<string, boolean> = {
		websearch: false,
		image_generation: false,
		code_interpreter: false,
		vision: false,
		// usage: false,
		citations: false
	};

	const capabilityIcons = {
		websearch: WebSearchIcon,
		image_generation: ImageGenerateIcon,
		code_interpreter: CodeInterpreterIcon,
		vision: VisionIcon,
		citations: CitationIcon
	};

	const capabilityTooltips: Record<string, string> = {
		websearch: 'Shows the “Web search” option. When enabled, the assistant may browse the web and incorporate results into the response.',
		image_generation: 'Shows the “Generate image” option. When enabled, the assistant may generate images (e.g., from text descriptions).',
		code_interpreter: 'Shows the “Run code” option. When enabled, the assistant may run code (e.g., for calculations, data analysis, files).',
		vision: 'Allows the assistant to understand and analyze images.',
		citations: 'Shows citations in the response, if available.'
	};
	function toggleCapability(capability) {
		capabilities[capability] = !capabilities[capability];
	}

	let showCapabilitiesDropdown = false;
	let dropdownRef;
</script>

<div class="my-1" use:onClickOutside={() => (showCapabilitiesDropdown = false)}>
	<div class="relative" bind:this={dropdownRef}>
		<button
			type="button"
			class={`flex items-center justify-between w-full text-sm h-10 px-3 py-2 ${
				showCapabilitiesDropdown ? 'border' : ''
			} border-lightGray-400 dark:border-customGray-700 rounded-md bg-lightGray-300 dark:bg-customGray-900 cursor-pointer`}
			on:click={() => (showCapabilitiesDropdown = !showCapabilitiesDropdown)}
		>
			<span class="text-lightGray-100 dark:text-customGray-100">{$i18n.t('Tools')}</span>
			<ChevronDown className="size-3" />
		</button>

		{#if showCapabilitiesDropdown}
			<div
				class="max-h-60 pb-1 overflow-y-auto absolute z-50 w-full -mt-1 bg-lightGray-300 dark:bg-customGray-900 border-l border-r border-b border-lightGray-400 dark:border-customGray-700 rounded-b-md"
			>
				<hr class="border-t border-lightGray-400 dark:border-customGray-700 mb-2 mt-1 mx-0.5" />
				<div class="px-1">
					{#each Object.keys(capabilities) as capability}
						<Tooltip content={capabilityTooltips[capability]} placement="right">
							<div
								role="button"
								tabindex="0"
								on:click={() => toggleCapability(capability)}
								on:keydown={(e) => {
									if (e.key === 'Enter' || e.key === ' ') {
										e.preventDefault();
										toggleCapability(capability);
									}
								}}
								class="flex items-center rounded-xl w-full justify-between px-3 py-2 hover:bg-lightGray-700 dark:hover:bg-customGray-950 cursor-pointer text-sm text-lightGray-100 dark:text-customGray-100"
							>
								<div class="flex items-center gap-2">
									{#if capabilityIcons[capability]}
										<svelte:component this={capabilityIcons[capability]} className="size-4" />
									{/if}
									<span class="capitalize">{capability.replace(/_/g, ' ')}</span>
								</div>
								<Checkbox
									state={capabilities[capability] ? 'checked' : 'unchecked'}
									on:change={(e) => {
										e.stopPropagation();
										capabilities[capability] = e.detail === 'checked';
									}}
								/>
							</div>
						</Tooltip>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</div>
