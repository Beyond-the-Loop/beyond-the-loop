<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ShieldCheck from '$lib/components/icons/ShieldCheck.svelte';

	const i18n: Writable<i18nType> = getContext('i18n');

	// { original: placeholder } map for a single user message — pulled from
	// `pii_variables` on that message. PIISession guarantees stable placeholder
	// assignment within a chat, so this is just the slice for one turn.
	export let variables: Record<string, string> = {};

	// Map { original: [source, ...] } — sources are strings like "prompt"
	// or "file:vertrag.pdf". One entity can come from multiple surfaces (e.g.
	// typed prompt AND a document); we render it under each source.
	export let variableSources: Record<string, string[]> = {};

	// Originals the user explicitly released for this message — passed
	// verbatim to the model rather than being replaced with a placeholder.
	export let released: string[] = [];

	// Defense-in-depth: even if released and variables share an entity (case/
	// whitespace differences), drop it from variables.
	const normalize = (s: string) => s.trim().toLowerCase();

	$: releasedSorted = (released ?? []).slice().sort((a, b) => a.localeCompare(b));
	$: releasedNormalized = new Set((released ?? []).map(normalize));

	// True when this message has neither anonymized variables nor released
	// entities — surfaced as an explicit empty-state hint so the sidebar
	// doesn't look broken when opened on an edge-case message.
	$: isEmpty =
		Object.keys(variables ?? {}).length === 0 && releasedSorted.length === 0;

	// Build groups keyed by source. Each entry can appear in multiple groups
	// if the entity was seen from multiple surfaces.
	$: groupedBySource = (() => {
		const out: Record<string, { placeholder: string; original: string; type: string }[]> = {};
		for (const [original, placeholder] of Object.entries(variables)) {
			if (releasedNormalized.has(normalize(original))) continue;
			const sources = variableSources[original] ?? [];
			const match = /^\[\[([A-Z_]+)_\d+\]\]$/.exec(placeholder);
			const type = match ? match[1] : 'OTHER';
			for (const src of sources) {
				(out[src] ??= []).push({ placeholder, original, type });
			}
		}
		// Stable order within each source: by type, then by placeholder number.
		for (const list of Object.values(out)) {
			list.sort((a, b) => {
				if (a.type !== b.type) return a.type.localeCompare(b.type);
				return a.placeholder.localeCompare(b.placeholder, undefined, { numeric: true });
			});
		}
		return out;
	})();

	// Source order: prompt first, then files alphabetically.
	$: sourceOrder = (() => {
		const keys = Object.keys(groupedBySource);
		return keys.sort((a, b) => {
			if (a === 'prompt' && b !== 'prompt') return -1;
			if (b === 'prompt' && a !== 'prompt') return 1;
			return a.localeCompare(b);
		});
	})();

	const entityLabels: Record<string, string> = {
		PERSON: 'Name',
		LOCATION: 'Standort',
		ORG: 'Organisation',
		EMAIL: 'E-Mail',
		PHONE: 'Telefon',
		DATUM: 'Datum',
		CARD: 'Kreditkarte',
		IBAN: 'IBAN',
		BIC: 'BIC',
		IP: 'IP',
		URL: 'URL',
		STEUERID: 'Steuer-ID',
		SVNR: 'SV-Nummer',
		ADDRESS: 'Adresse'
	};

	function sourceLabel(src: string): string {
		if (src === 'prompt') return $i18n.t('From the prompt');
		if (src.startsWith('file:')) {
			const name = src.slice(5) || 'unbekannt';
			return $i18n.t('From {{name}}', { name });
		}
		return src;
	}

	// Group entries within a single source by entity type so the visual
	// hierarchy is "Source → Type → entries".
	function groupByType(entries: { placeholder: string; original: string; type: string }[]) {
		const out: Record<string, { placeholder: string; original: string }[]> = {};
		for (const e of entries) {
			(out[e.type] ??= []).push({ placeholder: e.placeholder, original: e.original });
		}
		return out;
	}
</script>

<div class="space-y-4">
	<div class="flex items-center gap-2">
		<ShieldCheck className="size-4 text-customBlue-500 dark:text-blue-400" />
		<h3 class="text-sm font-medium text-lightGray-100 dark:text-white">
			{$i18n.t('Used in this prompt')}
		</h3>
	</div>

	{#if isEmpty}
		<p class="text-xs text-gray-500 dark:text-gray-400 italic px-1">
			{$i18n.t('No variables were anonymized in this message.')}
		</p>
	{:else}
		<p class="text-[11px] text-gray-500 dark:text-gray-400 leading-snug">
			{$i18n.t(
				'These variables were anonymized in this message. The model only saw the placeholder.'
			)}
		</p>
	{/if}

	{#if releasedSorted.length > 0}
		<div class="space-y-1.5">
			<div class="text-[10px] uppercase tracking-wide text-amber-600 dark:text-amber-400 px-1">
				{$i18n.t('Released')}
			</div>
			<p class="text-[11px] text-gray-500 dark:text-gray-400 leading-snug px-1">
				{$i18n.t(
					'You released these entities — they were sent to the model verbatim instead of being replaced with a placeholder.'
				)}
			</p>
			{#each releasedSorted as value (value)}
				<div
					class="flex w-full items-center justify-between gap-2 px-3 py-2 rounded-md border bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800/40 text-xs"
				>
					<span class="truncate text-left flex-1 min-w-0 text-amber-900 dark:text-amber-100">
						{value}
					</span>
					<span
						class="text-[10px] uppercase tracking-wide text-amber-700 dark:text-amber-400 flex-shrink-0"
					>
						{$i18n.t('released')}
					</span>
				</div>
			{/each}
		</div>
	{/if}

	{#each sourceOrder as src (src)}
		<div class="space-y-2">
			<div
				class="text-[11px] font-medium text-gray-700 dark:text-gray-200 px-1 truncate"
			>
				{sourceLabel(src)}
			</div>
			{#each Object.entries(groupByType(groupedBySource[src])) as [type, entries]}
				<div class="space-y-1.5">
					<div class="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400 px-1">
						{entityLabels[type] ?? type}
					</div>
					{#each entries as entry (entry.placeholder)}
						<Tooltip content={entry.placeholder} placement="left">
							<div
								class="flex w-full items-center justify-between gap-2 px-3 py-2 rounded-md border bg-gray-100 dark:bg-customGray-800 border-gray-200 dark:border-customGray-700 text-xs"
							>
								<span
									class="truncate text-left flex-1 min-w-0 text-gray-800 dark:text-gray-100"
								>
									{entry.original}
								</span>
								<span
									class="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400 flex-shrink-0"
								>
									{$i18n.t('protected')}
								</span>
							</div>
						</Tooltip>
					{/each}
				</div>
			{/each}
		</div>
	{/each}
</div>
