<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { user, mcpServers as _mcpServers } from '$lib/stores';
	import { onClickOutside } from '$lib/utils';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Cube from '$lib/components/icons/Cube.svelte';
	import { getMCPServers, type MCPServerResponse } from '$lib/apis/mcp';

	const i18n = getContext('i18n') as any;

	// Model capability (read by parent). Indicator hides itself when this is falsy.
	export let selectedModelInfo: any = null;

	// Chat-scoped client state — owned by Chat.svelte, bound here.
	export let mcpEnabled: boolean = true;
	export let mcpDisabledServerIds: string[] = [];

	let servers: MCPServerResponse[] = [];
	let loaded = false;
	let open = false;
	let containerEl: HTMLDivElement;

	// Only enabled servers count for the chat; disabled-by-owner ones never appear.
	$: visibleServers = servers.filter((s) => s.enabled);
	$: activeCount =
		mcpEnabled
			? visibleServers.filter((s) => !mcpDisabledServerIds.includes(s.id)).length
			: 0;
	$: show =
		!!selectedModelInfo?.supports_mcp &&
		!!$user &&
		$user?.permissions?.workspace?.mcp_connections &&
		visibleServers.length > 0;

	function toggleServer(id: string) {
		if (mcpDisabledServerIds.includes(id)) {
			mcpDisabledServerIds = mcpDisabledServerIds.filter((x) => x !== id);
		} else {
			mcpDisabledServerIds = [...mcpDisabledServerIds, id];
		}
	}

	function isServerActive(id: string): boolean {
		return mcpEnabled && !mcpDisabledServerIds.includes(id);
	}

	onMount(async () => {
		// Reuse the cached list if available; otherwise fetch.
		if (Array.isArray($_mcpServers)) {
			servers = $_mcpServers as MCPServerResponse[];
		} else {
			try {
				servers = (await getMCPServers(localStorage.token)) ?? [];
				_mcpServers.set(servers);
			} catch {
				servers = [];
			}
		}
		loaded = true;
	});
</script>

{#if loaded && show}
	<div
		class="relative"
		bind:this={containerEl}
		use:onClickOutside={() => {
			open = false;
		}}
	>
		<Tooltip
			content={mcpEnabled
				? $i18n.t('{{count}} connector(s) active for this chat', { count: activeCount })
				: $i18n.t('Connectors disabled for this chat')}
		>
			<button
				type="button"
				aria-label={$i18n.t('Connectors')}
				aria-haspopup="true"
				aria-expanded={open}
				class="bg-transparent hover:bg-gray-100 dark:hover:bg-customGray-900 transition rounded-md p-[3px] outline-none focus:outline-none flex items-center gap-1 {mcpEnabled
					? 'text-customBlue-500 dark:text-blue-400'
					: 'text-gray-400 dark:text-gray-500'}"
				on:click={() => (open = !open)}
			>
				<Cube className="w-5 h-5" />
				{#if mcpEnabled && activeCount > 0}
					<span class="text-[10px] font-medium leading-none">{activeCount}</span>
				{/if}
			</button>
		</Tooltip>

		{#if open}
			<div
				class="absolute bottom-full mb-2 right-0 w-72 z-50 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3"
			>
				<div class="flex items-center justify-between mb-2">
					<div class="text-sm font-semibold">{$i18n.t('Connectors')}</div>
					<label class="flex items-center gap-2 text-xs cursor-pointer">
						<input
							type="checkbox"
							class="accent-blue-500"
							bind:checked={mcpEnabled}
						/>
						<span>{$i18n.t('On for this chat')}</span>
					</label>
				</div>

				{#if !mcpEnabled}
					<div class="text-xs text-gray-500 dark:text-gray-400">
						{$i18n.t('Connectors are off for this chat. Toggle on above to enable.')}
					</div>
				{:else}
					<div class="space-y-1 max-h-72 overflow-y-auto">
						{#each visibleServers as srv (srv.id)}
							<button
								type="button"
								class="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left hover:bg-gray-100 dark:hover:bg-gray-800"
								on:click={() => toggleServer(srv.id)}
							>
								<input
									type="checkbox"
									class="accent-blue-500 pointer-events-none"
									checked={isServerActive(srv.id)}
									tabindex="-1"
								/>
								<div class="flex-1 min-w-0">
									<div class="text-xs font-medium truncate">{srv.name}</div>
									<div class="text-[10px] text-gray-500 truncate">{srv.url}</div>
								</div>
							</button>
						{/each}
					</div>
				{/if}

				<div
					class="mt-3 pt-2 border-t border-gray-200 dark:border-gray-700 text-[10px] text-gray-500"
				>
					{$i18n.t('Per-chat toggles are not persisted.')}
				</div>
			</div>
		{/if}
	</div>
{/if}
