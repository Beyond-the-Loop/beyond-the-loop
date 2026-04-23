<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { getContext } from 'svelte';
	import { models as storeModels } from '$lib/stores';
	import { getModelIcon } from '$lib/utils';
	import Modal from '$lib/components/common/Modal.svelte';

	const i18n: Writable<i18nType> = getContext('i18n');

	export let show = false;
	export let model: any = null;
	export let groups: any[] = [];
	export let defaultModelIds: string[] = [];
	export let onSave: (modelId: string, accessControl: any, isActive: boolean) => void = () => {};

	type Mode = 'all' | 'groups' | 'disabled';

	let mode: Mode = 'all';
	let selectedGroupIds: string[] = [];

	$: isDefault =
		Array.isArray(defaultModelIds) &&
		defaultModelIds.length > 0 &&
		$storeModels?.find((m: any) => m?.name === defaultModelIds[0])?.id === model?.id;

	// Sync local state when model changes / modal opens
	$: if (show && model) {
		if (!model.is_active) {
			mode = 'disabled';
			selectedGroupIds = [];
		} else if (model.access_control === null) {
			mode = 'all';
			selectedGroupIds = [];
		} else {
			mode = 'groups';
			selectedGroupIds = [
				...(model.access_control?.read?.group_ids ?? []),
				...(model.access_control?.write?.group_ids ?? [])
			];
		}
	}

	function toggleGroup(id: string) {
		selectedGroupIds = selectedGroupIds.includes(id)
			? selectedGroupIds.filter((g) => g !== id)
			: [...selectedGroupIds, id];
	}

	function save() {
		if (!model) return;

		let accessControl: any = null;
		let isActive = true;

		if (mode === 'disabled') {
			isActive = false;
		} else if (mode === 'all') {
			accessControl = null;
		} else {
			accessControl = {
				read: { group_ids: [...selectedGroupIds], user_ids: [] },
				write: { group_ids: [], user_ids: [] }
			};
		}

		onSave(model.id, accessControl, isActive);
		show = false;
	}

	function cancel() {
		show = false;
	}

	const groupDotPalette = [
		'bg-blue-500',
		'bg-purple-500',
		'bg-emerald-500',
		'bg-amber-500',
		'bg-pink-500',
		'bg-sky-500',
		'bg-orange-500',
		'bg-teal-500'
	];
	function dotColor(seed: string): string {
		let h = 0;
		for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
		return groupDotPalette[Math.abs(h) % groupDotPalette.length];
	}
</script>

<Modal
	size="sm"
	bind:show
	className="dark:bg-customGray-800 rounded-2xl"
	containerClassName="bg-lightGray-250/50 dark:bg-[#1D1A1A]/50 backdrop-blur-[7.44px]"
>
	<div class="bg-lightGray-550 dark:bg-customGray-800 rounded-xl">
		<!-- Header -->
		<div class="flex items-center gap-3 px-5 pt-5 pb-4">
			{#if model}
				<img
					src={getModelIcon(model.name)}
					alt={model.name}
					class="shrink-0 w-9 h-9 object-contain"
				/>
				<div class="text-base font-semibold text-lightGray-100 dark:text-white truncate flex-1">
					{model.name}
				</div>
			{/if}
			<button
				type="button"
				aria-label="close"
				class="text-[#8A8B8D] dark:text-customGray-300 hover:text-lightGray-100 dark:hover:text-white"
				on:click={cancel}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-5 h-5"
				>
					<path
						d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
					/>
				</svg>
			</button>
		</div>

		<div class="px-5 pb-2 text-xs text-[#8A8B8D] dark:text-customGray-300 border-t border-lightGray-400 dark:border-customGray-700 pt-4">
			{$i18n.t('Zugriff')}
		</div>

		<!-- Options -->
		<div class="px-5 pb-5 space-y-1.5">
			<!-- Alle Nutzer -->
			<div
				role="button"
				tabindex="0"
				aria-pressed={mode === 'all'}
				class="w-full text-left rounded-lg border cursor-pointer transition-colors duration-150 bg-[#F3F4F6] dark:bg-customGray-900 {mode === 'all'
					? 'border-customBlue-500 dark:border-blue-500 bg-blue-50 dark:bg-blue-500/10'
					: 'border-lightGray-400 dark:border-customGray-700 hover:border-lightGray-650 dark:hover:border-customGray-500'}"
				on:click={() => (mode = 'all')}
				on:keydown={(e) => {
					if (e.key === 'Enter' || e.key === ' ') {
						e.preventDefault();
						mode = 'all';
					}
				}}
			>
				<div class="flex items-start justify-between gap-3 p-3">
					<div class="min-w-0">
						<div class="text-sm font-medium text-lightGray-100 dark:text-white">
							{$i18n.t('Alle Nutzer')}
						</div>
						<div class="text-xs text-[#8A8B8D] dark:text-customGray-300 mt-0.5">
							{$i18n.t('Für alle Workspace-Mitglieder verfügbar')}
						</div>
					</div>
					{#if mode === 'all'}
						<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="shrink-0 mt-1 text-customBlue-600 dark:text-blue-400">
							<polyline points="20 6 9 17 4 12" />
						</svg>
					{/if}
				</div>
			</div>

			<!-- Bestimmte Gruppen (standalone card) -->
			<div
				role="button"
				tabindex="0"
				aria-pressed={mode === 'groups'}
				class="w-full text-left rounded-lg border cursor-pointer transition-colors duration-150 bg-[#F3F4F6] dark:bg-customGray-900 {mode === 'groups'
					? 'border-customBlue-500 dark:border-blue-500 bg-blue-50 dark:bg-blue-500/10'
					: 'border-lightGray-400 dark:border-customGray-700 hover:border-lightGray-650 dark:hover:border-customGray-500'}"
				on:click={() => (mode = 'groups')}
				on:keydown={(e) => {
					if (e.key === 'Enter' || e.key === ' ') {
						e.preventDefault();
						mode = 'groups';
					}
				}}
			>
				<div class="flex items-start justify-between gap-3 p-3">
					<div class="min-w-0">
						<div class="text-sm font-medium text-lightGray-100 dark:text-white">
							{$i18n.t('Bestimmte Gruppen')}
						</div>
						<div class="text-xs text-[#8A8B8D] dark:text-customGray-300 mt-0.5">
							{$i18n.t('Zugriff auf ausgewählte Gruppen beschränken')}
						</div>
					</div>
					{#if mode === 'groups'}
						<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="shrink-0 mt-1 text-customBlue-600 dark:text-blue-400">
							<polyline points="20 6 9 17 4 12" />
						</svg>
					{/if}
				</div>
			</div>

			<!-- Group list (rendered OUTSIDE the Bestimmte Gruppen card, between the cards) -->
			{#if mode === 'groups'}
				<div class="pl-3 flex flex-col gap-1 max-h-[7rem] overflow-y-auto custom-scrollbar pr-1">
					{#if groups.length === 0}
						<div class="text-xs text-[#8A8B8D] dark:text-customGray-300 italic px-2 py-2">
							{$i18n.t('Keine Gruppen verfügbar')}
						</div>
					{:else}
						{#each groups as group (group.id)}
							{@const checked = selectedGroupIds.includes(group.id)}
							<div
								role="button"
								tabindex="0"
								aria-pressed={checked}
								class="flex items-center justify-between gap-2 px-3 py-2 rounded-md border cursor-pointer transition-colors duration-150 {checked
									? 'border-customBlue-500/40 dark:border-blue-500/40 bg-blue-50 dark:bg-blue-500/10'
									: 'border-lightGray-400 dark:border-customGray-700 bg-[#F3F4F6] dark:bg-customGray-900/50 hover:border-lightGray-650 dark:hover:border-customGray-500'}"
								on:click={() => toggleGroup(group.id)}
								on:keydown={(e) => {
									if (e.key === 'Enter' || e.key === ' ') {
										e.preventDefault();
										toggleGroup(group.id);
									}
								}}
							>
								<div class="flex items-center gap-2 min-w-0">
									<span class="inline-block w-2 h-2 rounded-full {dotColor(group.id ?? group.name ?? '')} shrink-0"></span>
									<span class="text-xs text-lightGray-100 dark:text-white truncate">{group.name}</span>
								</div>
								<div
									class="shrink-0 w-4 h-4 rounded-[3px] flex items-center justify-center {checked
										? 'bg-customBlue-600 dark:bg-blue-500'
										: 'border border-lightGray-650 dark:border-customGray-500 bg-transparent'}"
								>
									{#if checked}
										<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
											<polyline points="20 6 9 17 4 12" />
										</svg>
									{/if}
								</div>
							</div>
						{/each}
					{/if}
				</div>
			{/if}

			<!-- Deaktiviert -->
			<div
				role="button"
				tabindex={isDefault ? -1 : 0}
				aria-pressed={mode === 'disabled'}
				aria-disabled={isDefault}
				class="w-full text-left rounded-lg border transition-colors duration-150 bg-[#F3F4F6] dark:bg-customGray-900 {isDefault
					? 'opacity-50 cursor-not-allowed'
					: 'cursor-pointer'} {mode === 'disabled'
					? 'border-red-500 bg-red-50 dark:bg-red-500/10'
					: 'border-lightGray-400 dark:border-customGray-700 ' + (isDefault ? '' : 'hover:border-lightGray-650 dark:hover:border-customGray-500')}"
				on:click={() => {
					if (!isDefault) mode = 'disabled';
				}}
				on:keydown={(e) => {
					if (!isDefault && (e.key === 'Enter' || e.key === ' ')) {
						e.preventDefault();
						mode = 'disabled';
					}
				}}
			>
				<div class="flex items-start justify-between gap-3 p-3">
					<div class="min-w-0">
						<div
							class="text-sm font-medium {mode === 'disabled'
								? 'text-red-600 dark:text-red-400'
								: 'text-lightGray-100 dark:text-white'}"
						>
							{$i18n.t('Deaktiviert')}
						</div>
						<div class="text-xs mt-0.5 text-[#8A8B8D] dark:text-customGray-300">
							{isDefault
								? $i18n.t('Standardmodell kann nicht deaktiviert werden')
								: $i18n.t('Modell ist für niemanden verfügbar')}
						</div>
					</div>
					{#if mode === 'disabled'}
						<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="shrink-0 mt-1 text-red-600 dark:text-red-400">
							<polyline points="20 6 9 17 4 12" />
						</svg>
					{/if}
				</div>
			</div>
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-end gap-2 px-5 py-4 border-t border-lightGray-400 dark:border-customGray-700">
			<button
				type="button"
				class="px-4 py-2 text-sm font-medium text-lightGray-100 dark:text-customGray-100 bg-[#F3F4F6] dark:bg-customGray-900 border border-lightGray-400 dark:border-customGray-700 hover:border-lightGray-650 dark:hover:border-customGray-500 rounded-md transition-colors"
				on:click={cancel}
			>
				{$i18n.t('Abbrechen')}
			</button>
			<button
				type="button"
				class="px-4 py-2 text-sm font-medium text-white bg-customBlue-600 hover:bg-customBlue-500 dark:bg-blue-600 dark:hover:bg-blue-500 rounded-md transition-colors"
				on:click={save}
			>
				{$i18n.t('Speichern')}
			</button>
		</div>
	</div>
</Modal>
