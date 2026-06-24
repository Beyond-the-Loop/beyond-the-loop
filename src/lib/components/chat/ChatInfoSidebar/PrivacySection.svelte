<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import type { PIISpan } from '$lib/apis/pii';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ShieldCheck from '$lib/components/icons/ShieldCheck.svelte';

	const i18n: Writable<i18nType> = getContext('i18n');

	export let detectedEntities: PIISpan[] = [];
	export let releasedEntities: string[] = [];
	export let onReleasedChange: (released: string[]) => void = () => {};
	// When false, entities render as read-only chips (no click-to-release).
	// Driven by `pii.allow_disable_in_chat` — without it the backend silently
	// forces released[] back to empty anyway, so showing clickable chips would
	// just mislead the user.
	export let releasable: boolean = true;
	// True when the prompt has changed since the last analysis run.
	export let stale: boolean = false;
	// Manually added entities — always anonymized, removable by the user.
	export let manualPIIEntities: string[] = [];
	export let onManualChange: (updated: string[]) => void = () => {};

	// Distinct originals only — duplicates collapse into one row, since release
	// applies to all occurrences of the same string in this chat.
	$: uniqueDetected = (() => {
		const seen = new Set<string>();
		const out: PIISpan[] = [];
		for (const span of detectedEntities) {
			if (!seen.has(span.original)) {
				seen.add(span.original);
				out.push(span);
			}
		}
		return out;
	})();

	$: groupedDetected = (() => {
		const groups: Record<string, PIISpan[]> = {};
		for (const span of uniqueDetected) {
			(groups[span.entity_type] ??= []).push(span);
		}
		return groups;
	})();

	$: protectedCount = uniqueDetected.filter(
		(s) => !releasedEntities.includes(s.original)
	).length;

	function toggleEntity(original: string) {
		const isReleased = releasedEntities.includes(original);
		const next = isReleased
			? releasedEntities.filter((e) => e !== original)
			: [...releasedEntities, original];
		onReleasedChange(next);
	}

	// Display labels for entity types. Keys match the raw types emitted by the
	// openai/privacy-filter model (see backend SUPPORTED_ENTITIES).
	const entityLabels: Record<string, string> = {
		private_person: 'Name',
		private_address: 'Adresse',
		private_email: 'E-Mail',
		private_phone: 'Telefon',
		private_url: 'URL',
		private_date: 'Datum',
		account_number: 'Kontonummer',
		secret: 'Geheimnis'
	};
</script>

<div class="space-y-4">
	<div class="flex items-center gap-2">
		<ShieldCheck className="size-4 text-amber-600 dark:text-amber-400" />
		<h3 class="text-sm font-medium text-lightGray-100 dark:text-white">
			{$i18n.t('Current input')}
		</h3>
	</div>

	{#if uniqueDetected.length > 0}
		<div
			class="rounded-lg p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/40"
		>
			<div class="flex justify-between text-xs font-medium text-amber-700 dark:text-amber-300">
				<span>
					{uniqueDetected.length}
					{uniqueDetected.length === 1
						? $i18n.t('entity detected')
						: $i18n.t('entities detected')}
				</span>
				<span>{protectedCount} {$i18n.t('protected')}</span>
			</div>
			<p class="text-[11px] text-amber-700/80 dark:text-amber-300/70 mt-1.5 leading-snug">
				{$i18n.t(
					'Protected entities are replaced with placeholders before being sent to the model.'
				)}
			</p>
		</div>

		{#each Object.entries(groupedDetected) as [type, spans]}
			<div class="space-y-1.5">
				<div
					class="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400 px-1"
				>
					{entityLabels[type] ?? type}
				</div>
				{#each spans as span (span.original)}
					{@const released = releasedEntities.includes(span.original)}
					{#if releasable}
						<Tooltip
							content={released
								? $i18n.t('Released — click to re-anonymize in future messages')
								: $i18n.t('Will be anonymized — click to release for this chat')}
							placement="left"
						>
							<button
								type="button"
								class="flex w-full items-center justify-between gap-2 px-3 py-2 rounded-md border text-xs transition {released
									? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800/40 text-red-800 dark:text-red-200'
									: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800/40 text-amber-900 dark:text-amber-100 hover:bg-amber-100 dark:hover:bg-amber-900/30'}"
								on:click={() => toggleEntity(span.original)}
							>
								<span
									class="font-mono truncate text-left flex-1 {released ? 'line-through' : ''}"
								>
									{span.original}
								</span>
								<span class="text-[10px] uppercase tracking-wide flex-shrink-0">
									{released ? $i18n.t('released') : $i18n.t('protected')}
								</span>
							</button>
						</Tooltip>
					{:else}
						<div
							class="flex w-full items-center justify-between gap-2 px-3 py-2 rounded-md border text-xs {released
								? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800/40 text-red-800 dark:text-red-200'
								: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800/40 text-amber-900 dark:text-amber-100'}"
						>
							<span
								class="font-mono truncate text-left flex-1 {released ? 'line-through' : ''}"
							>
								{span.original}
							</span>
							<span class="text-[10px] uppercase tracking-wide flex-shrink-0">
								{released ? $i18n.t('released') : $i18n.t('protected')}
							</span>
						</div>
					{/if}
				{/each}
			</div>
		{/each}
	{:else}
		<p class="text-xs text-gray-500 dark:text-gray-400 italic px-1">
			{$i18n.t('No personal data detected in your current input.')}
		</p>
	{/if}

	{#if manualPIIEntities.length > 0}
		<div class="space-y-1.5">
			<div class="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400 px-1">
				{$i18n.t('Manual')}
			</div>
			{#each manualPIIEntities as entity (entity)}
				<div class="flex w-full items-center justify-between gap-2 px-3 py-2 rounded-md border text-xs bg-customBlue-50 dark:bg-customBlue-900/20 border-customBlue-200 dark:border-customBlue-800/40 text-customBlue-900 dark:text-customBlue-100">
					<span class="font-mono truncate text-left flex-1">{entity}</span>
					<button
						type="button"
						class="text-[10px] flex-shrink-0 text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition"
						aria-label={$i18n.t('Remove')}
						on:click={() => onManualChange(manualPIIEntities.filter(e => e !== entity))}
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="size-3.5">
							<path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
						</svg>
					</button>
				</div>
			{/each}
		</div>
	{/if}

	{#if uniqueDetected.length > 0}
		<p class="text-[11px] text-gray-500 dark:text-gray-500 leading-snug pt-2 border-t border-gray-200 dark:border-customGray-800">
			{#if releasable}
				{$i18n.t(
					'Click an entry to release it from the filter for the rest of this chat.'
				)}
			{:else}
				{$i18n.t(
					'Anonymization is enforced for your account — entries cannot be released.'
				)}
			{/if}
		</p>
	{/if}
</div>
