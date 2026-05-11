<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import type { PIISpan } from '$lib/apis/pii';
	import { showChatInfoSidebar, chatInfoSidebarMode } from '$lib/stores';
	import CloseIcon from '$lib/components/icons/CloseIcon.svelte';
	import PrivacySection from './ChatInfoSidebar/PrivacySection.svelte';
	import ChatHistoryVariables from './ChatInfoSidebar/ChatHistoryVariables.svelte';

	const i18n: Writable<i18nType> = getContext('i18n');

	// Composer-mode data — live detection on the current prompt, owned by
	// Chat.svelte so external indicators (orange link) read the same state.
	export let detectedEntities: PIISpan[] = [];
	export let releasedEntities: string[] = [];
	export let onReleasedChange: (released: string[]) => void = () => {};
	export let privacyReleasable: boolean = true;

	// Message-mode data — sliced from one user message's `pii_variables`,
	// `pii_variable_sources` and `pii_released_entities_actual` by the parent.
	// Null when the referenced message no longer exists (e.g. deleted).
	export let messageVariables: Record<string, string> | null = null;
	export let messageVariableSources: Record<string, string[]> = {};
	export let messageReleased: string[] = [];
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
			{$i18n.t('Anonymization')}
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
		{#if $chatInfoSidebarMode.kind === 'composer'}
			<PrivacySection
				{detectedEntities}
				{releasedEntities}
				{onReleasedChange}
				releasable={privacyReleasable}
			/>
		{:else if messageVariables !== null}
			<ChatHistoryVariables
				variables={messageVariables}
				variableSources={messageVariableSources}
				released={messageReleased}
			/>
		{/if}
	</div>
</div>
