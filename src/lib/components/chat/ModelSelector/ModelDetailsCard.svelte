<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { modelsInfo } from '$lib/stores';
	import { getContext } from 'svelte';
	import { getModelIcon } from '$lib/utils';
	import { regionFlag, regionLabel } from '../../../../data/modelsInfo';

	const i18n: Writable<i18nType> = getContext('i18n');

	export let name: string = '';
	export let showClose: boolean = false;
	export let onClose: (() => void) | null = null;

	$: info = $modelsInfo?.[name] ?? null;
	$: orgName = (info?.organization ?? '') as string;
	$: description = (info?.description ?? '') as string;
	$: intelligence = toScore(info?.intelligence_score);
	$: speed = toScore(info?.speed);
	$: contextWindow = info?.context_window ?? null;
	$: knowledgeCutoff = formatCutoff(info?.knowledge_cutoff);
	$: hosted = (info?.hosted_in ?? null) as string | null;
	$: multimodal = Boolean(info?.multimodal);

	function toScore(v: unknown): number {
		const n = Number(v);
		if (!isFinite(n) || n <= 0) return 0;
		return Math.max(0, Math.min(5, n));
	}

	function formatCutoff(v: unknown): string | null {
		if (!v) return null;
		const d = new Date(v as string);
		if (isNaN(d.getTime())) return String(v);
		try {
			return d.toLocaleString(undefined, { year: 'numeric', month: 'long' });
		} catch {
			return String(v);
		}
	}
</script>

<!-- Header -->
<div class="flex items-center gap-3 mb-3">
	<img
		src={getModelIcon(name)}
		alt={name}
		class="shrink-0 w-9 h-9 object-contain"
	/>
	<div class="min-w-0 flex-1">
		<div class="text-sm font-semibold truncate">{name}</div>
		{#if orgName}
			<div class="text-2xs text-lightGray-900 dark:text-customGray-300 leading-tight mt-0.5">
				{orgName}
			</div>
		{/if}
	</div>
	{#if showClose}
		<button
			type="button"
			aria-label="close"
			class="text-[#8A8B8D] dark:text-customGray-300 hover:text-lightGray-100 dark:hover:text-white"
			on:click={() => onClose && onClose()}
		>
			<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
				<path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
			</svg>
		</button>
	{/if}
</div>

{#if description}
	<p class="text-xs text-lightGray-100 dark:text-customGray-100 leading-relaxed mb-3">
		{$i18n.t(description)}
	</p>
{/if}

{#if intelligence > 0 || speed > 0}
	<div class="space-y-2 mb-3">
		{#if intelligence > 0}
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-1.5 text-xs text-lightGray-900 dark:text-customGray-300">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
						<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
					</svg>
					<span>{$i18n.t('Intelligenz')}</span>
				</div>
				<div class="flex items-center gap-0.5">
					{#each Array(5) as _, i}
						<div class="w-1 h-3 rounded-sm {i < Math.round(intelligence) ? 'bg-customBlue-600 dark:bg-blue-500' : 'bg-lightGray-400 dark:bg-customGray-700'}"></div>
					{/each}
				</div>
			</div>
		{/if}
		{#if speed > 0}
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-1.5 text-xs text-lightGray-900 dark:text-customGray-300">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
						<path d="M13 2 3 14h9l-1 8 10-12h-9z" />
					</svg>
					<span>{$i18n.t('Geschwindigkeit')}</span>
				</div>
				<div class="flex items-center gap-0.5">
					{#each Array(5) as _, i}
						<div class="w-1 h-3 rounded-sm {i < Math.round(speed) ? 'bg-customBlue-600 dark:bg-blue-500' : 'bg-lightGray-400 dark:bg-customGray-700'}"></div>
					{/each}
				</div>
			</div>
		{/if}
	</div>
{/if}

{#if contextWindow || knowledgeCutoff}
	<div class="grid grid-cols-2 gap-3 pt-3 border-t border-lightGray-400 dark:border-customGray-700">
		{#if contextWindow}
			<div class="flex flex-col gap-0.5 min-w-0">
				<span class="text-2xs text-lightGray-900 dark:text-customGray-300">{$i18n.t('Kontextfenster')}</span>
				<span class="text-xs font-medium truncate">{contextWindow}</span>
			</div>
		{/if}
		{#if knowledgeCutoff}
			<div class="flex flex-col gap-0.5 min-w-0">
				<span class="text-2xs text-lightGray-900 dark:text-customGray-300">{$i18n.t('Knowledge Cutoff')}</span>
				<span class="text-xs font-medium truncate">{knowledgeCutoff}</span>
			</div>
		{/if}
	</div>
{/if}

{#if hosted}
	<div class="flex items-center justify-between pt-2.5 text-xs">
		<span class="text-lightGray-900 dark:text-customGray-300">{$i18n.t('Hosting')}</span>
		<span class="flex items-center gap-1.5">
			<span class="text-sm leading-none">{regionFlag(hosted)}</span>
			<span class="font-medium">{regionLabel(hosted)}</span>
		</span>
	</div>
{/if}

<div class="flex items-center justify-between pt-2 text-xs">
	<span class="text-lightGray-900 dark:text-customGray-300">{$i18n.t('Modalitäten')}</span>
	<span class="flex items-center gap-3">
		<span class="flex items-center gap-1">
			<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
				<path d="M4 7V5h16v2M9 20h6M12 5v15" />
			</svg>
			<span class="font-medium">{$i18n.t('Text')}</span>
		</span>
		{#if multimodal}
			<span class="flex items-center gap-1">
				<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
					<rect x="3" y="3" width="18" height="18" rx="2" />
					<circle cx="9" cy="9" r="1.5" />
					<path d="m21 15-5-5L5 21" />
				</svg>
				<span class="font-medium">{$i18n.t('Bild')}</span>
			</span>
		{/if}
	</span>
</div>
