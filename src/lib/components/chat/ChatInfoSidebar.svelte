<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import type { PIISpan } from '$lib/apis/pii';
	import { showChatInfoSidebar } from '$lib/stores';
	import CloseIcon from '$lib/components/icons/CloseIcon.svelte';
	import PrivacySection from './ChatInfoSidebar/PrivacySection.svelte';
	import ChatHistoryVariables from './ChatInfoSidebar/ChatHistoryVariables.svelte';

	const i18n: Writable<i18nType> = getContext('i18n');

	// Privacy section data is owned by the parent (Chat.svelte) so toggle
	// indicators outside the sidebar can read the same detection state.
	export let privacyVisible: boolean = false;
	export let detectedEntities: PIISpan[] = [];
	export let releasedEntities: string[] = [];
	export let onReleasedChange: (released: string[]) => void = () => {};
	export let privacyReleasable: boolean = true;

	// History section: aggregated { original: placeholder } map collected from
	// pii_variables across all user messages of the current chat. `historyReleased`
	// is the list of originals the user explicitly released in past messages
	// (passed verbatim to the model). `historyVariableSources` maps each
	// original to the list of surfaces it was seen on (e.g. ["prompt",
	// "file:vertrag.pdf"]) — drives the source-first grouping.
	export let historyVisible: boolean = false;
	export let historyVariables: Record<string, string> = {};
	export let historyVariableSources: Record<string, string[]> = {};
	export let historyReleased: string[] = [];
</script>

{#if $showChatInfoSidebar}
	<!-- Mobile backdrop — desktop layout has space for the sidebar inline. -->
	<div
		class="fixed md:hidden z-40 top-0 right-0 left-0 bottom-0 bg-lightGray-700/40 dark:bg-black/60"
		on:mousedown={() => showChatInfoSidebar.set(false)}
	/>
{/if}

<div
	class="h-screen max-h-[100dvh] min-h-screen select-none {$showChatInfoSidebar
		? 'md:relative w-[300px] max-w-[300px] sm:w-[340px] sm:max-w-[340px]'
		: 'translate-x-[300px] sm:translate-x-[340px] w-[0px]'}
		transition-width duration-200 ease-in-out flex-shrink-0
		bg-lightGray-200 text-gayLight-100 dark:bg-customGray-950 dark:text-gray-200 text-sm
		fixed z-50 top-0 right-0 bottom-0 overflow-x-hidden border-l border-lightGray-300 dark:border-customGray-800"
	data-state={$showChatInfoSidebar}
>
	<div
		class="flex items-center justify-between px-5 pt-5 pb-3 border-b border-lightGray-300 dark:border-customGray-800"
	>
		<p class="text-lightGray-100 dark:text-white text-base font-medium">
			{$i18n.t('PII filter')}
		</p>
		<button
			type="button"
			class="hover:bg-lightGray-300 dark:hover:bg-customGray-800 rounded-md p-1 transition"
			aria-label={$i18n.t('Close')}
			on:click={() => showChatInfoSidebar.set(false)}
		>
			<CloseIcon />
		</button>
	</div>

	<div class="px-5 py-4 overflow-y-auto space-y-6" style="max-height: calc(100dvh - 4.5rem);">
		{#if privacyVisible}
			<PrivacySection
				{detectedEntities}
				{releasedEntities}
				{onReleasedChange}
				releasable={privacyReleasable}
			/>
		{/if}
		{#if historyVisible}
			<ChatHistoryVariables
				variables={historyVariables}
				variableSources={historyVariableSources}
				released={historyReleased}
			/>
		{/if}
		<!-- Future sections (e.g. files in chat) get added here as additional
			conditional blocks. The sidebar itself stays generic. -->
	</div>
</div>
