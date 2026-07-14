<script lang="ts">
	import { getContext } from 'svelte';

	const i18n = getContext<any>('i18n');

	export let oauthScope: string | null | undefined;
	export let oauthGrantedScope: string | null | undefined;

	// Two dimensions to display:
	//   requested — what our authorize URL asked for (oauth_scope)
	//   granted   — what the provider actually consented to (oauth_granted_scope)
	// If the row has neither, hide the section entirely (Notion/HubSpot with
	// scope=null and no consent-time echoback fall into this bucket).
	$: requested = (oauthScope || '').split(/\s+/).filter(Boolean);
	$: grantedList = (oauthGrantedScope || '').split(/\s+/).filter(Boolean);
	$: grantedSet = new Set(grantedList);
	$: hasAnything = requested.length > 0 || grantedList.length > 0;

	// If oauth_scope is empty but the provider echoed granted scopes anyway,
	// render just the granted list (no dim/strikethrough comparison to make).
	$: rows = requested.length > 0 ? requested : grantedList;
	$: grantedCount = requested.length > 0 ? requested.filter((s) => grantedSet.has(s)).length : grantedList.length;
	$: hasComparison = requested.length > 0 && grantedList.length > 0;
</script>

{#if hasAnything}
	<div class="mt-4">
		<div class="flex items-center justify-between mb-2">
			<h4 class="text-sm font-semibold dark:text-customGray-100">
				{$i18n.t('Berechtigungen')}
			</h4>
			{#if hasComparison}
				<span class="text-xs text-lightGray-1200/60 dark:text-customGray-100/50">
					{grantedCount} / {rows.length} {$i18n.t('gewährt')}
				</span>
			{:else}
				<span class="text-xs text-lightGray-1200/60 dark:text-customGray-100/50">
					{rows.length} {$i18n.t('gewährt')}
				</span>
			{/if}
		</div>
		<ul class="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-0.5 max-h-48 overflow-y-auto border rounded p-2 dark:border-customGray-700">
			{#each rows as scope (scope)}
				{@const granted = grantedSet.has(scope)}
				<li
					class="flex items-center gap-1.5 text-xs font-mono truncate {granted
						? 'text-lightGray-100 dark:text-customGray-100'
						: 'text-lightGray-1200/40 dark:text-customGray-100/30 line-through'}"
					title={granted ? $i18n.t('Gewährt') : $i18n.t('Nicht gewährt')}
				>
					{#if granted}
						<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="text-green-500 shrink-0"><polyline points="20 6 9 17 4 12"/></svg>
					{:else}
						<span class="w-2.5 shrink-0"></span>
					{/if}
					<span class="truncate">{scope}</span>
				</li>
			{/each}
		</ul>
	</div>
{/if}
