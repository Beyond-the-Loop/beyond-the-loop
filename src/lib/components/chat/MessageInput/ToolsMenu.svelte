<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { flyAndScale } from '$lib/utils/transitions';
	import { getContext } from 'svelte';

	import { mcpServers as _mcpServers } from '$lib/stores';
	import {
		getMCPServers,
		getConnectorCatalog,
		type MCPServerResponse,
		type MCPConnectorTemplate
	} from '$lib/apis/mcp';

	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import AdjustmentsHorizontal from '$lib/components/icons/AdjustmentsHorizontal.svelte';
	import WebSearchIcon from '$lib/components/icons/WebSearchIcon.svelte';
	import ImageGenerateIcon from '$lib/components/icons/ImageGenerateIcon.svelte';
	import CodeInterpreterIcon from '$lib/components/icons/CodeInterpreterIcon.svelte';
	import Cube from '$lib/components/icons/Cube.svelte';

	const i18n = getContext('i18n');

	export let canWebSearch = false;
	export let canImageGen = false;
	export let canCodeInterpreter = false;
	export let canMcp = false;

	export let webSearchEnabled = false;
	export let imageGenerationEnabled = false;
	export let codeInterpreterEnabled = false;

	export let mcpDisabledServerIds: string[] = [];

	let show = false;
	let mcpServerList: MCPServerResponse[] = [];

	// Map template_slug → icon_url so user-added connectors that were installed
	// from a catalog template can show the provider's logo in the list. Custom
	// (non-template) connectors fall back to the BTL logo (matches the Connectors
	// workspace page).
	let catalogIconBySlug: Record<string, string> = {};

	$: visibleMcpServers = mcpServerList.filter((s) => s.enabled);
	$: showMcpSection = canMcp && visibleMcpServers.length > 0;

	$: hasAnyFeature = canWebSearch || canImageGen || canCodeInterpreter || showMcpSection;

	$: anyMcpActive =
		showMcpSection &&
		visibleMcpServers.some((s) => !mcpDisabledServerIds.includes(s.id));

	$: isActive =
		webSearchEnabled ||
		imageGenerationEnabled ||
		codeInterpreterEnabled ||
		anyMcpActive;

	function toggleMcpServer(id: string) {
		if (mcpDisabledServerIds.includes(id)) {
			mcpDisabledServerIds = mcpDisabledServerIds.filter((x) => x !== id);
		} else {
			mcpDisabledServerIds = [...mcpDisabledServerIds, id];
		}
	}

	function isMcpServerActive(id: string): boolean {
		return !mcpDisabledServerIds.includes(id);
	}

	function iconFor(srv: MCPServerResponse): string | null {
		if (srv.template_slug && catalogIconBySlug[srv.template_slug]) {
			return catalogIconBySlug[srv.template_slug];
		}
		return null;
	}

	// Fetches require the mcp_connections workspace permission — hitting them for
	// users without it produces noisy 401s. Gate the load on `canMcp` (permission
	// AND model support) and run it once per session, lazily when both are true.
	let mcpLoaded = false;

	async function loadMcpData() {
		if (mcpLoaded) return;
		mcpLoaded = true;

		if (Array.isArray($_mcpServers)) {
			mcpServerList = $_mcpServers as MCPServerResponse[];
		} else {
			try {
				mcpServerList = (await getMCPServers(localStorage.token)) ?? [];
				_mcpServers.set(mcpServerList);
			} catch {
				mcpServerList = [];
			}
		}

		try {
			const catalog: MCPConnectorTemplate[] =
				(await getConnectorCatalog(localStorage.token)) ?? [];
			catalogIconBySlug = Object.fromEntries(
				catalog.filter((t) => t.icon_url).map((t) => [t.slug, t.icon_url])
			);
		} catch {
			catalogIconBySlug = {};
		}
	}

	$: if (canMcp) loadMcpData();
</script>

{#if hasAnyFeature}
	<DropdownMenu.Root bind:open={show} closeFocus={false} typeahead={false}>
		<DropdownMenu.Trigger>
			<Tooltip content={$i18n.t('Tools')} placement="top">
				<button
					type="button"
					class="p-[3px] transition rounded-md focus:outline-none hover:bg-gray-100 dark:hover:bg-customGray-900 {isActive
						? 'text-customBlue-500 dark:text-blue-400'
						: 'text-customGray-900 dark:text-customGray-100'}"
					aria-label={$i18n.t('Tools')}
				>
					<AdjustmentsHorizontal className="size-5" />
				</button>
			</Tooltip>
		</DropdownMenu.Trigger>

		<DropdownMenu.Content
			class="w-full max-w-[260px] rounded-lg px-1 py-1 border-gray-300/30 border dark:border-customGray-700 z-50 bg-white dark:bg-customGray-900 dark:text-white shadow"
			sideOffset={15}
			alignOffset={-8}
			side="top"
			align="start"
			transition={flyAndScale}
		>
			<div
				class="px-2 pt-1.5 pb-1 text-[10px] uppercase tracking-wide font-semibold text-lightGray-1200 dark:text-customGray-100/50"
			>
				{$i18n.t('Tools')}
			</div>

			{#if canWebSearch}
				<DropdownMenu.Item
					class="flex w-full justify-between gap-2 items-center px-2 py-2 text-xs dark:text-customGray-100 font-medium cursor-pointer rounded-lg hover:bg-gray-50 dark:hover:bg-customGray-950"
					on:click={(e) => {
						e.preventDefault();
						webSearchEnabled = !webSearchEnabled;
					}}
				>
					<div class="flex gap-2 items-center">
						<WebSearchIcon />
						{$i18n.t('Web Search')}
					</div>
					<Switch state={webSearchEnabled} small />
				</DropdownMenu.Item>
			{/if}

			{#if canImageGen}
				<DropdownMenu.Item
					class="flex w-full justify-between gap-2 items-center px-2 py-2 text-xs dark:text-customGray-100 font-medium cursor-pointer rounded-lg hover:bg-gray-50 dark:hover:bg-customGray-950"
					on:click={(e) => {
						e.preventDefault();
						imageGenerationEnabled = !imageGenerationEnabled;
					}}
				>
					<div class="flex gap-2 items-center">
						<ImageGenerateIcon />
						{$i18n.t('Image Generation')}
					</div>
					<Switch state={imageGenerationEnabled} small />
				</DropdownMenu.Item>
			{/if}

			{#if canCodeInterpreter}
				<DropdownMenu.Item
					class="flex w-full justify-between gap-2 items-center px-2 py-2 text-xs dark:text-customGray-100 font-medium cursor-pointer rounded-lg hover:bg-gray-50 dark:hover:bg-customGray-950"
					on:click={(e) => {
						e.preventDefault();
						codeInterpreterEnabled = !codeInterpreterEnabled;
					}}
				>
					<div class="flex gap-2 items-center">
						<CodeInterpreterIcon />
						{$i18n.t('Code Interpreter')}
					</div>
					<Switch state={codeInterpreterEnabled} small />
				</DropdownMenu.Item>
			{/if}

			{#if showMcpSection}
				{#if canWebSearch || canImageGen || canCodeInterpreter}
					<hr class="border-black/5 dark:border-white/5 my-1" />
				{/if}

				<DropdownMenu.Sub>
					<DropdownMenu.SubTrigger
						class="flex w-full gap-2 items-center px-2 py-2 text-xs dark:text-customGray-100 font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-customGray-950 rounded-lg"
					>
						<Cube className="size-4 shrink-0" />
						<div class="line-clamp-1 flex-1">{$i18n.t('Connectors')}</div>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							stroke-linecap="round"
							stroke-linejoin="round"
							class="w-3 h-3 flex-shrink-0 opacity-60"
						>
							<polyline points="9 18 15 12 9 6" />
						</svg>
					</DropdownMenu.SubTrigger>

					<DropdownMenu.SubContent
						class="w-full max-w-[240px] rounded-lg px-1 py-1 border-gray-300/30 border dark:border-customGray-700 z-50 bg-white dark:bg-customGray-900 dark:text-white shadow"
						sideOffset={4}
						alignOffset={-4}
					>
						<div class="max-h-64 overflow-y-auto scrollbar-hidden">
							{#each visibleMcpServers as srv (srv.id)}
								{@const iconUrl = iconFor(srv)}
								<DropdownMenu.Item
									class="flex w-full justify-between gap-2 items-center px-2 py-2 text-xs dark:text-customGray-100 font-medium cursor-pointer rounded-lg hover:bg-gray-50 dark:hover:bg-customGray-950"
									on:click={(e) => {
										e.preventDefault();
										toggleMcpServer(srv.id);
									}}
								>
									<div class="flex gap-2 items-center min-w-0">
										<img
											src={iconUrl ?? '/logo_light.png'}
											alt=""
											class="size-4 shrink-0 object-contain {iconUrl
												? ''
												: 'rounded-sm ring-1 ring-black/10 dark:ring-white/15'}"
											loading="lazy"
										/>
										<span class="truncate">{srv.name}</span>
									</div>
									<Switch state={isMcpServerActive(srv.id)} small />
								</DropdownMenu.Item>
							{/each}
						</div>
					</DropdownMenu.SubContent>
				</DropdownMenu.Sub>
			{/if}
		</DropdownMenu.Content>
	</DropdownMenu.Root>
{/if}
