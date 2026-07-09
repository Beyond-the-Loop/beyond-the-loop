<script lang="ts">
	import Fuse from 'fuse.js';

	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';
	import {
		WEBUI_NAME,
		mcpServers as _mcpServers,
		showSidebar,
		mobile,
		user,
		companyConfig
	} from '$lib/stores';

	import {
		getMCPServers,
		getMCPServer,
		createMCPServer,
		updateMCPServer,
		deleteMCPServer,
		testMCPServerConnection,
		testExistingMCPServerConnection,
		startMCPOAuth,
		disconnectMCPOAuth,
		getConnectorCatalog,
		installConnectorTemplate,
		type MCPServerForm,
		type MCPServerResponse,
		type TestConnectionResult,
		type MCPConnectorTemplate
	} from '$lib/apis/mcp';

	import DeleteConfirmDialog from '../common/ConfirmDialog.svelte';
	import Modal from '../common/Modal.svelte';
	import Spinner from '../common/Spinner.svelte';

	import Search from '../icons/Search.svelte';
	import Plus from '../icons/Plus.svelte';
	import ShowSidebarIcon from '../icons/ShowSidebarIcon.svelte';
	import BackIcon from '../icons/BackIcon.svelte';
	import CloseIcon from '../icons/CloseIcon.svelte';

	import MCPServerMenu from './MCPServers/MCPServerMenu.svelte';

	const i18n = getContext('i18n') as any;

	let loaded = false;
	let servers: MCPServerResponse[] = [];

	// Catalog (Library)
	let catalog: MCPConnectorTemplate[] = [];
	let showCatalogModal = false;
	let selectedTemplate: MCPConnectorTemplate | null = null;
	let installing = false;
	// Per-install credentials prompted when the template advertises
	// requires_user_credentials / requires_tenant_id (Microsoft 365).
	let installClientId = '';
	let installClientSecret = '';
	let installTenantId = '';

	// Company-level M365 defaults set in the Konnektoren tab.
	$: companyM365 = ($companyConfig as any)?.config?.connectors?.['microsoft-365'] ?? {
		has_client_id: false,
		has_tenant_id: false,
		has_client_secret: false
	};

	let query = '';
	let showInput = false;
	let fuse: Fuse<any> | null = null;

	let hoveredId: string | null = null;
	let menuIdOpened: string | null = null;

	// Delete confirm
	let showDeleteConfirm = false;
	let selectedItem: MCPServerResponse | null = null;

	// Create/edit modal
	let showEditor = false;
	let editingId: string | null = null;
	let editingServer: MCPServerResponse | null = null;
	let form: MCPServerForm = blankForm();
	let saving = false;
	let connecting = false;
	let showAdvancedOauth = false;
	// Tracks rows that the editor created silently as a draft (so OAuth has a
	// row to hang its PKCE state on). Used by the orphan-cleanup watcher: if
	// the user closes the editor without completing OAuth, we delete the row
	// we silently created. We never delete rows that pre-existed the session.
	let createdInThisSession = false;

	// In-editor test
	let testing = false;
	let testResult: TestConnectionResult | null = null;

	// Tools checkbox list state (edit modal)
	let modalTools: Array<{ name: string; description: string; enabled: boolean }> = [];
	let toolsLoading = false;
	let toolsError: string | null = null;
	let toolsStale = false;

	function blankForm(): MCPServerForm {
		return {
			name: '',
			description: '',
			url: '',
			transport: 'streamable_http',
			auth_type: null,
			auth_token: '',
			enabled: true,
			oauth_issuer_url: '',
			oauth_scope: '',
			oauth_client_id: '',
			oauth_client_secret: ''
		};
	}

	function onAuthTypeChange(e: Event) {
		const v = (e.currentTarget as HTMLSelectElement).value;
		form.auth_type = v === 'none' ? null : (v as 'bearer' | 'oauth');
		if (form.auth_type !== 'bearer') form.auth_token = '';
		if (form.auth_type !== 'oauth') {
			form.oauth_issuer_url = '';
			form.oauth_scope = '';
			form.oauth_client_id = '';
			form.oauth_client_secret = '';
		}
	}

	function formatExpiresIn(unixSec: number | null | undefined): string {
		if (!unixSec) return '';
		const now = Date.now() / 1000;
		const delta = unixSec - now;
		if (delta < 0) return $i18n.t('expired');
		if (delta < 60) return $i18n.t('expires in <1 min');
		if (delta < 3600) return $i18n.t('expires in {{n}} min', { n: Math.floor(delta / 60) });
		return $i18n.t('expires in {{n}} h', { n: Math.floor(delta / 3600) });
	}

	// Library templates and custom servers render in ONE unified grid,
	// connected-first then alphabetical. A "template" item has no server row
	// until the user connects; a "custom" item is always backed by a row.
	type CombinedItem =
		| {
				kind: 'template';
				id: string;
				name: string;
				description: string;
				template: MCPConnectorTemplate;
				row: MCPServerResponse | null;
				active: boolean;
		  }
		| {
				kind: 'custom';
				id: string;
				name: string;
				description: string;
				server: MCPServerResponse;
				active: boolean;
		  };

	function isCustomActive(s: MCPServerResponse): boolean {
		if (!s.enabled) return false;
		if (s.auth_type === 'bearer') return s.has_auth_token;
		if (s.auth_type === 'oauth') return s.has_oauth_access_token;
		return true; // no-auth servers are always "active" when enabled
	}

	$: customServers = servers.filter((s) => !s.template_slug);

	$: combinedItems = (() => {
		const items: CombinedItem[] = [];
		for (const tpl of catalog) {
			const row = servers.find((s) => s.template_slug === tpl.slug) ?? null;
			items.push({
				kind: 'template',
				id: `template-${tpl.slug}`,
				name: tpl.name,
				description: tpl.description,
				template: tpl,
				row,
				active: !!(row && row.has_oauth_access_token)
			});
		}
		for (const srv of customServers) {
			items.push({
				kind: 'custom',
				id: srv.id,
				name: srv.name,
				description: srv.description ?? srv.url,
				server: srv,
				active: isCustomActive(srv)
			});
		}
		// Active first, then alphabetical by name.
		items.sort((a, b) => {
			if (a.active !== b.active) return a.active ? -1 : 1;
			return a.name.localeCompare(b.name);
		});
		return items;
	})();

	$: if (combinedItems) {
		fuse = new Fuse(combinedItems, { keys: ['name', 'description'] }) as any;
	}

	$: filteredCombined = query && fuse
		? (fuse.search(query).map((e: any) => e.item) as CombinedItem[])
		: combinedItems;

	async function reload() {
		try {
			servers = (await getMCPServers(localStorage.token)) ?? [];
			_mcpServers.set(servers);
		} catch (e) {
			toast.error(`${e}`);
		}
	}

	function openCreate() {
		editingId = null;
		editingServer = null;
		form = blankForm();
		testResult = null;
		showAdvancedOauth = false;
		createdInThisSession = false;
		modalTools = [];
		toolsLoading = false;
		toolsError = null;
		toolsStale = false;
		showEditor = true;
	}

	function openEdit(srv: MCPServerResponse) {
		editingId = srv.id;
		editingServer = srv;
		form = {
			name: srv.name,
			description: srv.description ?? '',
			url: srv.url,
			transport: srv.transport,
			auth_type: srv.auth_type as 'bearer' | 'oauth' | null,
			auth_token: '',
			enabled: srv.enabled,
			oauth_issuer_url: srv.oauth_issuer_url ?? '',
			oauth_scope: srv.oauth_scope ?? '',
			oauth_client_id: '',
			oauth_client_secret: ''
		};
		testResult = null;
		showAdvancedOauth = false;
		createdInThisSession = false;
		showEditor = true;
	}

	async function refreshEditingServer() {
		if (!editingId) return;
		try {
			editingServer = await getMCPServer(localStorage.token, editingId);
			// Mirror updated OAuth status back into the visible form fields
			if (editingServer) {
				form.oauth_issuer_url = editingServer.oauth_issuer_url ?? '';
				form.oauth_scope = editingServer.oauth_scope ?? '';
			}
		} catch (e) {
			// Non-fatal — leave the stale view
			console.warn('reload editing server', e);
		}
	}

	/**
	 * Normalise the form into the shape the backend expects. Empty OAuth
	 * fields become `null` so the backend treats them as "not set" rather
	 * than as empty strings — important for `client_id` (null = run DCR)
	 * and `scope` (null = request none).
	 */
	function buildSavePayload(): MCPServerForm {
		const payload: MCPServerForm = { ...form };
		if (payload.auth_type !== 'oauth') {
			payload.oauth_issuer_url = null;
			payload.oauth_scope = null;
			payload.oauth_client_id = null;
			payload.oauth_client_secret = null;
		} else {
			payload.oauth_issuer_url = (payload.oauth_issuer_url || '').trim() || null;
			payload.oauth_scope = (payload.oauth_scope || '').trim() || null;
			payload.oauth_client_id = (payload.oauth_client_id || '').trim() || null;
			payload.oauth_client_secret = (payload.oauth_client_secret || '').trim() || null;
		}
		return payload;
	}

	async function save() {
		if (!form.name.trim() || !form.url.trim()) {
			toast.error($i18n.t('Name and URL are required.'));
			return;
		}
		if (form.auth_type === 'bearer' && !editingId && !form.auth_token?.trim()) {
			toast.error($i18n.t('Bearer auth requires a token.'));
			return;
		}
		saving = true;
		try {
			if (editingId) {
				// For OAuth connectors the row already exists (connectOAuth
				// silently created it). For others we may also be editing an
				// existing row. Either way: PATCH.
				const payload = buildSavePayload();
				if (modalTools.length > 0) {
					payload.tools = modalTools.map((t) => ({ name: t.name, enabled: t.enabled }));
				}
				await updateMCPServer(localStorage.token, editingId, payload);
				toast.success($i18n.t('Connector updated'));
			} else {
				// Reached only for non-OAuth connectors — OAuth ones get
				// persisted by connectOAuth and so always have editingId set
				// by the time Save becomes clickable.
				await createMCPServer(localStorage.token, buildSavePayload());
				toast.success($i18n.t('Connector created'));
			}
			showEditor = false;
			await reload();
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			saving = false;
		}
	}

	/**
	 * Open the OAuth authorize URL in a popup and wait (postMessage or polled
	 * popup-closed) for completion. Returns true when the provider reported
	 * success. Used by both the editor's "Connect" button and the Library's
	 * one-click install flow.
	 */
	function runOAuthFlow(serverId: string): Promise<boolean> {
		return new Promise(async (resolve) => {
			let startResp;
			try {
				startResp = await startMCPOAuth(localStorage.token, serverId);
			} catch (e) {
				toast.error(`${e}`);
				resolve(false);
				return;
			}
			const popup = window.open(
				startResp.authorize_url,
				'mcp-oauth',
				'width=520,height=720,menubar=no,toolbar=no,location=yes,status=no'
			);
			if (!popup) {
				toast.error($i18n.t('Popup blocked. Please allow popups and try again.'));
				resolve(false);
				return;
			}

			let settled = false;
			const finish = (success: boolean) => {
				if (settled) return;
				settled = true;
				window.removeEventListener('message', handler);
				window.clearInterval(pollId);
				resolve(success);
			};
			const handler = (event: MessageEvent) => {
				if (event.origin !== window.location.origin) return;
				const data = event.data;
				if (!data || data.type !== 'mcp-oauth-done') return;
				if (data.server_id && data.server_id !== serverId) return;
				if (data.success) {
					toast.success($i18n.t('Connected.'));
				} else {
					toast.error(data.message || $i18n.t('Connection failed.'));
				}
				finish(!!data.success);
			};
			window.addEventListener('message', handler);

			// Fallback: popup closed without a postMessage. Could be (a) the
			// user cancelled, or (b) the OAuth callback IS on a different
			// origin than the workspace page (typical in dev: backend on
			// :8080, Vite on :5173) and the `event.origin` check filtered
			// the success message out. Re-check the row server-side before
			// declaring failure.
			const pollId = window.setInterval(async () => {
				if (settled) return;
				if (!popup.closed) return;
				window.clearInterval(pollId);
				try {
					const fresh = await getMCPServer(localStorage.token, serverId);
					if (fresh?.has_oauth_access_token) {
						toast.success($i18n.t('Connected.'));
						finish(true);
						return;
					}
				} catch {}
				finish(false);
			}, 500);
		});
	}

	async function connectOAuth() {
		// We need a name + URL even for the silent-draft path, since the row
		// has to satisfy the backend's NOT-NULL constraints.
		if (!form.name.trim() || !form.url.trim()) {
			toast.error($i18n.t('Name and URL are required.'));
			return;
		}
		connecting = true;
		try {
			if (!editingId) {
				// Silently persist a draft so the backend has a row to hang
				// PKCE state and tokens off. Tagged with createdInThisSession
				// so the editor-closed watcher cleans it up again if the user
				// bails before OAuth completes.
				const saved = await createMCPServer(localStorage.token, buildSavePayload());
				editingId = saved.id;
				editingServer = saved;
				createdInThisSession = true;
			} else {
				// Editing an existing row: persist the latest form values
				// (name, URL, issuer, scope, …) before launching OAuth, so the
				// popup runs against the current config — not the stale row.
				const updated = await updateMCPServer(
					localStorage.token,
					editingId,
					buildSavePayload()
				);
				editingServer = updated;
			}
			// Track whether this was a reconnect of an already-working server,
			// so we don't blow away a healthy connection when the user simply
			// closes the reconnect popup without finishing.
			const wasConnected = !!editingServer?.has_oauth_access_token;
			const success = await runOAuthFlow(editingId);
			if (!success && !wasConnected) {
				// Initial connect was cancelled or failed — wipe the row (and
				// the DCR client at the provider) and close the editor so the
				// next attempt starts from a clean slate.
				const orphanId = editingId;
				try {
					await disconnectMCPOAuth(localStorage.token, orphanId);
				} catch {}
				editingId = null;
				editingServer = null;
				createdInThisSession = false;
				showEditor = false;
			} else {
				await refreshEditingServer();
			}
			await reload();
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			connecting = false;
		}
	}

	function openCatalogModal(template: MCPConnectorTemplate) {
		selectedTemplate = template;
		installClientId = '';
		installClientSecret = '';
		installTenantId = '';
		showCatalogModal = true;
	}

	async function installFromTemplate() {
		if (!selectedTemplate) return;
		if (selectedTemplate.requires_user_credentials && !installClientId.trim() && !companyM365.has_client_id) {
			toast.error($i18n.t('Client ID is required.'));
			return;
		}
		if (selectedTemplate.requires_tenant_id && !installTenantId.trim() && !companyM365.has_tenant_id) {
			toast.error($i18n.t('Tenant ID is required.'));
			return;
		}
		installing = true;
		try {
			const server = await installConnectorTemplate(
				localStorage.token,
				selectedTemplate.slug,
				{
					client_id: installClientId.trim() || undefined,
					client_secret: installClientSecret.trim() || undefined,
					tenant_id: installTenantId.trim() || undefined
				}
			);
			// Don't wipe a healthy reconnect attempt if the user just closes
			// the popup — only clean up rows that came in fresh.
			const wasConnected = !!server.has_oauth_access_token;
			// Drop straight into the OAuth popup — the user expects "one click".
			const success = await runOAuthFlow(server.id);
			if (!success && !wasConnected) {
				// Initial connect cancelled or failed — wipe the row (+ DCR
				// client at provider) so the next install starts clean.
				try {
					await disconnectMCPOAuth(localStorage.token, server.id);
				} catch {}
			}
			await reload();
			// Leave the modal open so the user sees the updated Connected state.
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			installing = false;
		}
	}

	async function disconnectTemplate() {
		if (!selectedTemplate) return;
		const row = templateRowFor(selectedTemplate);
		if (!row) return;
		try {
			await disconnectMCPOAuth(localStorage.token, row.id);
			toast.success($i18n.t('Disconnected.'));
			await reload();
		} catch (e) {
			toast.error(`${e}`);
		}
	}

	async function disconnectOAuth() {
		if (!editingId) return;
		try {
			await disconnectMCPOAuth(localStorage.token, editingId);
			toast.success($i18n.t('Disconnected.'));
			await refreshEditingServer();
			await reload();
		} catch (e) {
			toast.error(`${e}`);
		}
	}

	async function runTestFromForm() {
		testing = true;
		testResult = null;
		try {
			testResult = await testMCPServerConnection(localStorage.token, form);
		} catch (e) {
			testResult = { success: false, transport: form.transport, message: `${e}` };
		} finally {
			testing = false;
		}
	}

	async function fetchTools() {
		if (!editingServer?.id) return;
		toolsLoading = true;
		toolsError = null;
		toolsStale = false;
		try {
			const r = await testExistingMCPServerConnection(localStorage.token, editingServer.id);
			if (r.success && r.tools) {
				const stored = new Map(
					(editingServer.tools || []).map((t) => [t.name, t.enabled])
				);
				modalTools = r.tools.map((t) => ({
					name: t.name,
					description: t.description || '',
					enabled: stored.has(t.name) ? !!stored.get(t.name) : true
				}));
			} else {
				// Fall back to cached tools
				modalTools = (editingServer.tools || []).map((t) => ({
					name: t.name,
					description: (t as any).description || '',
					enabled: t.enabled
				}));
				toolsStale = true;
				toolsError = r.message || 'Verbindung fehlgeschlagen';
			}
		} catch (e) {
			modalTools = (editingServer.tools || []).map((t) => ({
				name: t.name,
				description: (t as any).description || '',
				enabled: t.enabled
			}));
			toolsStale = true;
			toolsError = (e as Error).message;
		} finally {
			toolsLoading = false;
		}
	}

	async function testServer(srv: MCPServerResponse) {
		const t = toast.loading($i18n.t('Testing {{name}}...', { name: srv.name }));
		try {
			const r = await testExistingMCPServerConnection(localStorage.token, srv.id);
			toast.dismiss(t);
			if (r.success) {
				const toolStr = r.tools && r.tools.length > 0 ? ` (${r.tools.length} tools)` : '';
				toast.success($i18n.t('{{name}}: OK', { name: srv.name }) + toolStr);
			} else {
				toast.error($i18n.t('{{name}}: {{msg}}', { name: srv.name, msg: r.message ?? 'failed' }));
			}
		} catch (e) {
			toast.dismiss(t);
			toast.error(`${e}`);
		}
	}

	async function confirmDelete() {
		if (!selectedItem) return;
		try {
			await deleteMCPServer(localStorage.token, selectedItem.id);
			toast.success($i18n.t('Connector deleted'));
			await reload();
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			showDeleteConfirm = false;
			selectedItem = null;
		}
	}

	onMount(async () => {
		await reload();
		try {
			catalog = (await getConnectorCatalog(localStorage.token)) ?? [];
		} catch (e) {
			console.warn('catalog load', e);
			catalog = [];
		}
		loaded = true;
	});

	function templateRowFor(template: MCPConnectorTemplate): MCPServerResponse | null {
		return servers.find((s) => s.template_slug === template.slug) ?? null;
	}

	function isConnected(template: MCPConnectorTemplate): boolean {
		const row = templateRowFor(template);
		return !!(row && row.has_oauth_access_token);
	}

	// Reactive views of the selected template's state — re-evaluate whenever
	// `servers` changes (e.g. after reload() following install/disconnect), so
	// the modal flips between Connected and Not-Connected layouts on its own.
	$: selectedRow = (() => {
		if (!selectedTemplate || !servers) return null;
		const slug = selectedTemplate.slug;
		return servers.find((s) => s.template_slug === slug) ?? null;
	})();
	$: selectedConnected = !!(selectedRow && selectedRow.has_oauth_access_token);

	// Editor-closed watcher: when the editor closes by ANY route — Cancel,
	// X, Esc, backdrop-click — and we created a draft row in this session
	// that never got an OAuth token, delete the orphan. Catches every close
	// path via `bind:show={showEditor}` on the Modal.
	let prevShowEditor = false;
	$: {
		if (prevShowEditor && !showEditor) {
			if (
				createdInThisSession &&
				editingId &&
				editingServer &&
				!editingServer.has_oauth_access_token
			) {
				const orphanId = editingId;
				deleteMCPServer(localStorage.token, orphanId)
					.then(() => reload())
					.catch(() => {});
			}
			createdInThisSession = false;
		}
		prevShowEditor = showEditor;
	}

	// Auto-fetch tools when the edit modal opens for an existing server.
	// `lastFetchedForId` prevents re-entry when reload() reassigns editingServer
	// with the same id (which would otherwise trigger a second concurrent POST).
	let lastFetchedForId: string | null = null;
	$: if (showEditor && editingServer?.id && editingServer.id !== lastFetchedForId) {
		lastFetchedForId = editingServer.id;
		fetchTools();
	}
	$: if (!showEditor) lastFetchedForId = null;

	// Manual reload from the "Neu laden" button — forces a refetch even when the
	// server id hasn't changed since the last auto-fetch.
	function manualFetchTools() {
		lastFetchedForId = null;
		fetchTools();
	}

	let scrollContainer: HTMLDivElement;

	function updateScrollHeight() {
		const header = document.getElementById('mcp-header');
		const filters = document.getElementById('mcp-filters');
		if (header && filters && scrollContainer) {
			const totalOffset = header.offsetHeight + filters.offsetHeight;
			scrollContainer.style.height = `calc(100dvh - ${totalOffset}px)`;
		}
	}

	onMount(() => {
		window.addEventListener('resize', updateScrollHeight);
		return () => {
			window.removeEventListener('resize', updateScrollHeight);
		};
	});

	$: if (loaded) {
		setTimeout(() => {
			updateScrollHeight();
		}, 0);
	}
</script>

<svelte:head>
	<title>
		{$i18n.t('Connectors')} | {$WEBUI_NAME}
	</title>
</svelte:head>

{#if loaded}
	<DeleteConfirmDialog
		bind:show={showDeleteConfirm}
		title={$i18n.t('Delete connector?')}
		message={selectedItem ? selectedItem.name : ''}
		on:confirm={confirmDelete}
	/>

	<!-- Create / Edit modal -->
	<Modal
		size="md"
		containerClassName="bg-lightGray-250/50 dark:bg-[#1D1A1A]/50 backdrop-blur-[6px]"
		bind:show={showEditor}
	>
		<div class="px-8 py-6 bg-lightGray-550 dark:bg-customGray-800 rounded-2xl">
			<div class="flex justify-between items-center pb-2.5">
				<div
					class="text-left text-base font-medium dark:text-customGray-100 text-lightGray-1500 leading-[1.2]"
				>
					{editingId ? $i18n.t('Edit connector') : $i18n.t('New connector')}
				</div>
				<button
					type="button"
					class="dark:text-white"
					on:click={() => {
						showEditor = false;
					}}
				>
					<CloseIcon />
				</button>
			</div>

			<div class="max-h-[60vh] overflow-y-auto pr-1 space-y-3.5">
				<label class="block">
					<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
						{$i18n.t('Name')}
					</span>
					<input
						type="text"
						class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm dark:text-customGray-100 outline-none focus:border-customBlue-500"
						bind:value={form.name}
						placeholder="Notion, Linear, ..."
					/>
				</label>

				<label class="block">
					<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
						{$i18n.t('Description')}
					</span>
					<input
						type="text"
						class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm dark:text-customGray-100 outline-none focus:border-customBlue-500"
						bind:value={form.description}
					/>
				</label>

				<label class="block">
					<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
						{$i18n.t('URL')}
					</span>
					<input
						type="url"
						class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm font-mono dark:text-customGray-100 outline-none focus:border-customBlue-500"
						bind:value={form.url}
						placeholder="https://mcp.example.com/..."
					/>
				</label>

				<div class="grid grid-cols-2 gap-3.5">
					<label class="block">
						<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
							{$i18n.t('Transport')}
						</span>
						<select
							class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm dark:text-customGray-100 outline-none"
							bind:value={form.transport}
						>
							<option value="streamable_http">Streamable HTTP</option>
							<option value="sse">SSE</option>
						</select>
					</label>

					<label class="block">
						<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
							{$i18n.t('Auth')}
						</span>
						<select
							class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm dark:text-customGray-100 outline-none"
							value={form.auth_type ?? 'none'}
							on:change={onAuthTypeChange}
						>
							<option value="none">{$i18n.t('No auth')}</option>
							<option value="bearer">{$i18n.t('Bearer token')}</option>
							<option value="oauth">{$i18n.t('OAuth 2.0')}</option>
						</select>
					</label>
				</div>

				{#if form.auth_type === 'bearer'}
					<label class="block">
						<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
							{$i18n.t('Bearer token')}
							{#if editingId}
								<span class="text-lightGray-1200/70 dark:text-customGray-100/40">
									— {$i18n.t('leave empty to keep existing')}
								</span>
							{/if}
						</span>
						<input
							type="password"
							class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm font-mono dark:text-customGray-100 outline-none focus:border-customBlue-500"
							bind:value={form.auth_token}
							placeholder={editingId ? '••••••••' : ''}
							autocomplete="off"
						/>
					</label>
				{/if}

				{#if form.auth_type === 'oauth'}
					<div class="space-y-3 rounded-lg border border-lightGray-400 dark:border-customGray-700 p-3">
						<label class="block">
							<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
								{$i18n.t('Issuer URL')}
								<span class="text-lightGray-1200/70 dark:text-customGray-100/40">
									— {$i18n.t('optional, defaults to the server URL')}
								</span>
							</span>
							<input
								type="url"
								class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm font-mono dark:text-customGray-100 outline-none focus:border-customBlue-500"
								bind:value={form.oauth_issuer_url}
								placeholder="https://attio.com"
							/>
						</label>

						<label class="block">
							<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
								{$i18n.t('Scope')}
								<span class="text-lightGray-1200/70 dark:text-customGray-100/40">
									— {$i18n.t('space-separated, optional')}
								</span>
							</span>
							<input
								type="text"
								class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm font-mono dark:text-customGray-100 outline-none focus:border-customBlue-500"
								bind:value={form.oauth_scope}
								placeholder="records:read records:write"
							/>
						</label>

						<button
							type="button"
							class="text-xs underline text-lightGray-1200 dark:text-customGray-100/60 hover:text-lightGray-100 dark:hover:text-customGray-100"
							on:click={() => (showAdvancedOauth = !showAdvancedOauth)}
						>
							{showAdvancedOauth
								? $i18n.t('Hide advanced (manual client credentials)')
								: $i18n.t('Show advanced (manual client credentials)')}
						</button>

						{#if showAdvancedOauth}
							<div class="space-y-2 pt-1">
								<p class="text-xs text-lightGray-1200/80 dark:text-customGray-100/50">
									{$i18n.t(
										'Leave blank to register a new client via Dynamic Client Registration (recommended). Only fill these in if the provider requires a manually-issued client.'
									)}
								</p>
								<label class="block">
									<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
										client_id
									</span>
									<input
										type="text"
										class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm font-mono dark:text-customGray-100 outline-none focus:border-customBlue-500"
										bind:value={form.oauth_client_id}
										autocomplete="off"
									/>
								</label>
								<label class="block">
									<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
										client_secret
										{#if editingServer?.has_oauth_client_secret}
											<span class="text-lightGray-1200/70 dark:text-customGray-100/40">
												— {$i18n.t('leave empty to keep existing')}
											</span>
										{/if}
									</span>
									<input
										type="password"
										class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm font-mono dark:text-customGray-100 outline-none focus:border-customBlue-500"
										bind:value={form.oauth_client_secret}
										placeholder={editingServer?.has_oauth_client_secret ? '••••••••' : ''}
										autocomplete="off"
									/>
								</label>
							</div>
						{/if}

						<div class="border-t border-lightGray-400 dark:border-customGray-700 pt-3">
							{#if editingServer?.has_oauth_access_token}
								<div class="text-xs dark:text-customGray-100 mb-2">
									<span class="font-medium">{$i18n.t('Connected')}</span>
									{#if editingServer.oauth_granted_scope}
										<div class="text-lightGray-1200 dark:text-customGray-100/60 mt-1">
											{$i18n.t('Scope')}: {editingServer.oauth_granted_scope}
										</div>
									{/if}
									{#if editingServer.oauth_access_token_expires_at}
										<div class="text-lightGray-1200 dark:text-customGray-100/60">
											{formatExpiresIn(editingServer.oauth_access_token_expires_at)}
										</div>
									{/if}
								</div>
								{#if editingServer?.scope_mismatch}
									<div class="mb-3 rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-900">
										Neue Rechte verfügbar. Bitte neu verbinden.
									</div>
								{/if}
								<div class="flex gap-2">
									<button
										type="button"
										class="text-xs px-3 py-1.5 rounded-lg border border-lightGray-400 dark:border-customGray-700 hover:bg-lightGray-700 dark:hover:bg-customGray-950 dark:text-customGray-100 disabled:opacity-50"
										class:ring-2={editingServer?.scope_mismatch}
										class:ring-yellow-400={editingServer?.scope_mismatch}
										on:click={connectOAuth}
										disabled={connecting}
									>
										{connecting ? $i18n.t('Connecting...') : $i18n.t('Reconnect')}
									</button>
									<button
										type="button"
										class="text-xs px-3 py-1.5 rounded-lg border border-lightGray-400 dark:border-customGray-700 hover:bg-lightGray-700 dark:hover:bg-customGray-950 dark:text-customGray-100"
										on:click={disconnectOAuth}
									>
										{$i18n.t('Disconnect')}
									</button>
								</div>
							{:else}
								<button
									type="button"
									class="text-xs px-3 py-1.5 rounded-lg bg-customBlue-500 text-white hover:bg-customBlue-700 disabled:opacity-50"
									on:click={connectOAuth}
									disabled={connecting || !form.name.trim() || !form.url.trim()}
								>
									{connecting ? $i18n.t('Connecting...') : $i18n.t('Connect with OAuth')}
								</button>
							{/if}
							{#if editingServer?.oauth_last_error}
								<div class="mt-2 text-xs text-red-600 dark:text-red-400">
									{editingServer.oauth_last_error}
								</div>
							{/if}
						</div>
					</div>
				{/if}

				<label class="flex items-center gap-2 text-sm dark:text-customGray-100">
					<input type="checkbox" class="accent-blue-500" bind:checked={form.enabled} />
					{$i18n.t('Enabled')}
				</label>

				{#if editingServer?.id}
					<div class="border-t border-lightGray-400 dark:border-customGray-700 pt-3">
						<div class="flex items-center justify-between mb-2">
							<h4 class="text-sm font-semibold dark:text-customGray-100">Tools</h4>
							<div class="flex items-center gap-2">
								{#if editingServer?.tools_fetched_at}
									<span class="text-xs text-lightGray-1200 dark:text-customGray-100/50">
										Zuletzt aktualisiert: {new Date(editingServer.tools_fetched_at * 1000).toLocaleString()}
									</span>
								{/if}
								<button
									type="button"
									class="text-xs underline text-lightGray-1200 dark:text-customGray-100/60 hover:text-lightGray-100 dark:hover:text-customGray-100 disabled:opacity-40"
									disabled={toolsLoading}
									on:click={manualFetchTools}
								>
									Neu laden
								</button>
							</div>
						</div>

						{#if toolsStale}
							<div class="mb-2 rounded border border-yellow-300 bg-yellow-50 px-2 py-1 text-xs text-yellow-800">
								Konnte Verbindung nicht testen — zeige zuletzt bekannte Tools.
							</div>
						{/if}

						{#if toolsLoading}
							<div class="text-sm text-lightGray-1200 dark:text-customGray-100/50">Lade Tools…</div>
						{:else if modalTools.length === 0}
							<div class="text-sm text-lightGray-1200 dark:text-customGray-100/50">Keine Tools bekannt.</div>
						{:else}
							<div class="flex items-center gap-2 mb-2 text-xs">
								<button
									type="button"
									class="underline text-lightGray-1200 dark:text-customGray-100/60 hover:text-lightGray-100 dark:hover:text-customGray-100"
									on:click={() => (modalTools = modalTools.map((t) => ({ ...t, enabled: true })))}
								>
									Alle aktivieren
								</button>
								<span class="text-lightGray-1200 dark:text-customGray-100/40">·</span>
								<button
									type="button"
									class="underline text-lightGray-1200 dark:text-customGray-100/60 hover:text-lightGray-100 dark:hover:text-customGray-100"
									on:click={() => (modalTools = modalTools.map((t) => ({ ...t, enabled: false })))}
								>
									Alle deaktivieren
								</button>
							</div>
							<ul class="space-y-1 max-h-64 overflow-y-auto border border-lightGray-400 dark:border-customGray-700 rounded p-2">
								{#each modalTools as tool (tool.name)}
									<li class="flex items-start gap-2">
										<input type="checkbox" bind:checked={tool.enabled} class="mt-1 accent-blue-500" />
										<div>
											<div class="text-sm font-medium dark:text-customGray-100">{tool.name}</div>
											{#if tool.description}
												<div class="text-xs text-lightGray-1200 dark:text-customGray-100/50">{tool.description}</div>
											{/if}
										</div>
									</li>
								{/each}
							</ul>
						{/if}
					</div>
				{/if}

				<div class="border-t border-lightGray-400 dark:border-customGray-700 pt-3">
					<div class="flex items-center gap-2 flex-wrap">
						<button
							type="button"
							class="text-xs px-3 py-1.5 rounded-lg border border-lightGray-400 dark:border-customGray-700 hover:bg-lightGray-700 dark:hover:bg-customGray-950 dark:text-customGray-100 disabled:opacity-50"
							disabled={testing || !form.url || (form.auth_type === 'oauth' && !editingServer?.has_oauth_access_token)}
							on:click={runTestFromForm}
						>
							{testing ? $i18n.t('Testing...') : $i18n.t('Test connection')}
						</button>
						{#if testResult}
							<span
								class="text-xs {testResult.success
									? 'text-green-600 dark:text-green-400'
									: 'text-red-600 dark:text-red-400'}"
							>
								{testResult.message ?? (testResult.success ? 'OK' : 'Failed')}
								{#if testResult.tools && testResult.tools.length > 0}
									<span class="text-lightGray-1200 dark:text-customGray-100/60">
										({testResult.tools.slice(0, 5).map((t) => t.name).join(', ')}{testResult.tools.length > 5
											? '…'
											: ''})
									</span>
								{/if}
							</span>
						{/if}
					</div>
				</div>
			</div>

			<div class="mt-5 flex items-center justify-end gap-2">
				<button
					class="text-sm px-3 py-1.5 rounded-lg hover:bg-lightGray-700 dark:hover:bg-customGray-950 dark:text-customGray-100"
					on:click={() => (showEditor = false)}
				>
					{$i18n.t('Cancel')}
				</button>
				<button
					class="text-sm px-3 py-1.5 rounded-lg bg-customBlue-500 text-white hover:bg-customBlue-700 disabled:opacity-50"
					disabled={saving ||
						(form.auth_type === 'oauth' && !editingServer?.has_oauth_access_token)}
					on:click={save}
				>
					{saving ? $i18n.t('Saving...') : editingId ? $i18n.t('Save') : $i18n.t('Create')}
				</button>
			</div>
		</div>
	</Modal>

	<!-- Catalog install (one-click for DCR-capable providers) -->
	<Modal
		size="sm"
		containerClassName="bg-lightGray-250/50 dark:bg-[#1D1A1A]/50 backdrop-blur-[6px]"
		bind:show={showCatalogModal}
	>
		{#if selectedTemplate}
			<div class="px-8 py-6 bg-lightGray-550 dark:bg-customGray-800 rounded-2xl">
				<div class="flex justify-between items-start pb-3">
					<div class="flex items-center gap-3">
						{#if selectedTemplate.icon_url}
							<img
								src={selectedTemplate.icon_url}
								alt=""
								class="size-10 object-contain"
								loading="lazy"
							/>
						{/if}
						<div
							class="text-left text-base font-medium dark:text-customGray-100 text-lightGray-1500 leading-[1.2]"
						>
							{selectedTemplate.name}
						</div>
					</div>
					<button
						type="button"
						class="dark:text-white"
						on:click={() => (showCatalogModal = false)}
					>
						<CloseIcon />
					</button>
				</div>

				<div class="text-sm text-lightGray-1400/80 dark:text-customGray-100/80 mb-4">
					{$i18n.t(selectedTemplate.description)}
				</div>

				{#if selectedConnected}
					<div class="rounded-lg border border-green-500/30 bg-green-50/40 dark:bg-green-950/30 p-3 text-xs dark:text-customGray-100">
						<div class="flex items-center gap-2 leading-none font-medium">
							<span class="size-1.5 rounded-full bg-green-500"></span>
							{$i18n.t('Connected')}
						</div>
						{#if selectedRow?.oauth_last_error}
							<div class="text-red-600 dark:text-red-400 mt-1">
								{selectedRow.oauth_last_error}
							</div>
						{/if}
					</div>
				{:else}
					{#if selectedTemplate.requires_tenant_id || selectedTemplate.requires_user_credentials}
						<div class="space-y-3 mb-3">
							{#if selectedTemplate.requires_tenant_id}
								<label class="block">
									<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
										{$i18n.t('Tenant ID')}
										{#if companyM365.has_tenant_id}
											<span class="ml-1 text-green-500">✓</span>
										{/if}
									</span>
									{#if companyM365.has_tenant_id}
										<input
											type="text"
											class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm font-mono outline-none cursor-not-allowed opacity-60"
											disabled
											value=""
											placeholder="••••••••"
											autocomplete="off"
										/>
										<p class="text-xs text-lightGray-1200/60 dark:text-customGray-100/40 mt-1">
											{$i18n.t('Wird aus Company-Einstellungen übernommen')}
										</p>
									{:else}
										<input
											type="text"
											class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm font-mono dark:text-customGray-100 outline-none focus:border-customBlue-500"
											bind:value={installTenantId}
											placeholder="00000000-0000-0000-0000-000000000000"
											autocomplete="off"
										/>
									{/if}
								</label>
							{/if}
							{#if selectedTemplate.requires_user_credentials}
								<label class="block">
									<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
										{$i18n.t('Client ID')}
										{#if companyM365.has_client_id}
											<span class="ml-1 text-green-500">✓</span>
										{/if}
									</span>
									{#if companyM365.has_client_id}
										<input
											type="text"
											class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm font-mono outline-none cursor-not-allowed opacity-60"
											disabled
											value=""
											placeholder="••••••••"
											autocomplete="off"
										/>
										<p class="text-xs text-lightGray-1200/60 dark:text-customGray-100/40 mt-1">
											{$i18n.t('Wird aus Company-Einstellungen übernommen')}
										</p>
									{:else}
										<input
											type="text"
											class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm font-mono dark:text-customGray-100 outline-none focus:border-customBlue-500"
											bind:value={installClientId}
											placeholder="00000000-0000-0000-0000-000000000000"
											autocomplete="off"
										/>
									{/if}
								</label>
								<label class="block">
									<span class="text-xs text-lightGray-1200 dark:text-customGray-100/70">
										{$i18n.t('Client Secret')}
										{#if companyM365.has_client_secret}
											<span class="ml-1 text-green-500">✓</span>
										{:else}
											<span class="text-lightGray-1200/70 dark:text-customGray-100/40">
												— {$i18n.t('optional')}
											</span>
										{/if}
									</span>
									{#if companyM365.has_client_secret}
										<input
											type="password"
											class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm font-mono outline-none cursor-not-allowed opacity-60"
											disabled
											value=""
											placeholder="••••••••"
											autocomplete="off"
										/>
										<p class="text-xs text-lightGray-1200/60 dark:text-customGray-100/40 mt-1">
											{$i18n.t('Wird aus Company-Einstellungen übernommen')}
										</p>
									{:else}
										<input
											type="password"
											class="mt-1 w-full px-3 py-2 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent text-sm font-mono dark:text-customGray-100 outline-none focus:border-customBlue-500"
											bind:value={installClientSecret}
											autocomplete="off"
										/>
									{/if}
								</label>
							{/if}
							<div class="text-xs text-lightGray-1200/80 dark:text-customGray-100/50">
								{$i18n.t(
									'Register your own app in your provider portal and paste the resulting IDs here. Use the redirect URI: {{uri}}',
									{ uri: selectedTemplate.oauth_redirect_uri }
								)}
								{#if selectedTemplate.credentials_help_url}
									<a
										class="underline ml-1"
										href={selectedTemplate.credentials_help_url}
										target="_blank"
										rel="noopener noreferrer"
									>
										{$i18n.t('Learn more')}
									</a>
								{/if}
							</div>
						</div>
					{:else}
						<div class="text-xs text-lightGray-1200/70 dark:text-customGray-100/50">
							{$i18n.t(
								'Clicking Connect will open {{name}} in a popup. After you authorize the connection, the popup closes automatically.',
								{ name: selectedTemplate.name }
							)}
						</div>
					{/if}
				{/if}

				{#if selectedTemplate.slug === 'microsoft-365'}
					<div
						class="mt-4 pt-3 border-t border-lightGray-400 dark:border-customGray-700 text-xs text-lightGray-1200/80 dark:text-customGray-100/60"
					>
						{$i18n.t('Need help with setup?')}
						<a
							class="underline ml-1"
							href="https://beyond-the-loop.notion.site/m365-mcp"
							target="_blank"
							rel="noopener noreferrer"
						>
							{$i18n.t('Book a joint setup session')}
						</a>
					</div>
				{/if}

				<div class="flex items-center justify-end gap-2 mt-5">
					{#if selectedConnected}
						<button
							class="text-sm px-3 py-1.5 rounded-lg hover:bg-lightGray-700 dark:hover:bg-customGray-950 dark:text-customGray-100"
							on:click={() => (showCatalogModal = false)}
						>
							{$i18n.t('Close')}
						</button>
						<button
							class="text-sm px-3 py-1.5 rounded-lg bg-red-500/10 text-red-700 dark:text-red-300 border border-red-500/30 hover:bg-red-500/20"
							on:click={disconnectTemplate}
						>
							{$i18n.t('Disconnect')}
						</button>
					{:else}
						<button
							class="text-sm px-3 py-1.5 rounded-lg hover:bg-lightGray-700 dark:hover:bg-customGray-950 dark:text-customGray-100"
							on:click={() => (showCatalogModal = false)}
						>
							{$i18n.t('Cancel')}
						</button>
						<button
							class="text-sm px-3 py-1.5 rounded-lg bg-customBlue-500 text-white hover:bg-customBlue-700 disabled:opacity-50"
							disabled={installing}
							on:click={installFromTemplate}
						>
							{installing
								? $i18n.t('Connecting...')
								: $i18n.t('Connect {{name}}', { name: selectedTemplate.name })}
						</button>
					{/if}
				</div>
			</div>
		{/if}
	</Modal>

	<!-- Header -->
	<div
		id="mcp-header"
		class="pl-4 md:pl-[22px] pr-4 py-2.5 border-b dark:border-customGray-700"
	>
		<div class="flex justify-between items-center">
			<div class="flex items-center">
				<div class="{$showSidebar ? 'md:hidden' : ''} self-center flex flex-none items-center">
					{#if $mobile}
						<button class="flex items-center gap-1" on:click={() => history.back()}>
							<BackIcon />
							<div
								class="flex items-center md:self-center text-base font-medium leading-none px-0.5 text-lightGray-100 dark:text-customGray-100"
							>
								{$i18n.t('Connectors')}
							</div>
						</button>
					{:else}
						<button
							id="sidebar-toggle-button"
							class="cursor-pointer p-1.5 flex rounded-xl hover:bg-gray-100 dark:hover:bg-gray-850 transition"
							on:click={() => {
								showSidebar.set(!$showSidebar);
							}}
							aria-label="Toggle Sidebar"
						>
							<div class=" m-auto self-center">
								<ShowSidebarIcon />
							</div>
						</button>
					{/if}
				</div>
				{#if !$mobile}
					<div
						class="flex items-center md:self-center text-lightGray-100 dark:text-customGray-100 text-base font-medium leading-none px-0.5"
					>
						{$i18n.t('Connectors')}
					</div>
				{/if}
			</div>

			<div class="flex">
				<div
					class="flex flex-1 items-center p-2.5 rounded-lg mr-1 border border-lightGray-400 dark:border-customGray-700 hover:bg-lightGray-700 dark:hover:bg-customGray-950 dark:hover:text-white transition"
				>
					<button
						on:click={() => {
							showInput = !showInput;
							if (!showInput) query = '';
						}}
						aria-label="Toggle Search"
					>
						<Search className="size-3.5" />
					</button>
					{#if showInput}
						<input
							class="w-[5rem] md:w-full text-xs outline-none bg-transparent leading-none pl-2 text-lightGray-100 dark:text-customGray-100"
							bind:value={query}
							placeholder={$i18n.t('Search connectors')}
							autofocus
							on:blur={() => {
								if (query.trim() === '') showInput = false;
							}}
						/>
					{/if}
				</div>
				{#if $user?.permissions?.workspace?.mcp_connections}
					<div>
						<button
							class=" px-2 py-2.5 md:w-[220px] rounded-lg leading-none border border-lightGray-400 dark:border-customGray-700 hover:bg-lightGray-700 dark:hover:bg-customGray-950 text-lightGray-100 dark:text-customGray-200 dark:hover:text-white transition font-medium text-xs flex items-center justify-center space-x-1"
							on:click={openCreate}
							type="button"
						>
							<Plus className="size-3.5" />
							<span>{$i18n.t('Create new')}</span>
						</button>
					</div>
				{/if}
			</div>
		</div>
	</div>

	<!-- Unified connector grid: library templates + user-added connectors, active first -->
	<div class="pl-4 md:pl-[22px] pr-4">
		<div id="mcp-filters" class="py-3"></div>

		<div
			id="mcp-scroll-container"
			bind:this={scrollContainer}
			class="overflow-y-scroll pr-[3px]"
		>
			{#if filteredCombined.length < 1}
				<div class="flex h-[calc(100dvh-200px)] w-full justify-center items-center">
					<div class="text-sm dark:text-customGray-100/50">
						{$i18n.t('No connectors added yet')}
					</div>
				</div>
			{/if}
			<div class="mb-2 gap-2 grid lg:grid-cols-2 xl:grid-cols-3" id="mcp-list">
				{#each filteredCombined as item (item.id)}
					<button
						type="button"
						on:mouseenter={() => (hoveredId = item.id)}
						on:mouseleave={() => (hoveredId = null)}
						class="relative flex flex-col gap-y-1 cursor-pointer w-full text-left px-3 py-2 bg-lightGray-550 dark:bg-customGray-800 rounded-2xl transition {item.kind === 'custom' && !item.server.enabled
							? 'opacity-70'
							: ''}"
						on:click={() => {
							if (item.kind === 'template') openCatalogModal(item.template);
							else openEdit(item.server);
						}}
					>
						<div class="w-full">
							<div class="flex items-start justify-between gap-2">
								<div class="flex items-center gap-2 flex-wrap min-w-0">
									{#if item.kind === 'template' && item.template.icon_url}
										<img
											src={item.template.icon_url}
											alt=""
											class="shrink-0 size-6 object-contain"
											loading="lazy"
										/>
									{:else if item.kind === 'custom'}
										<img
											src="/logo_light.png"
											alt=""
											class="shrink-0 size-6 object-contain rounded ring-1 ring-black/10 dark:ring-white/15"
											loading="lazy"
										/>
									{/if}
									{#if item.active}
										<span
											class="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide bg-green-100 dark:bg-green-950 text-green-800 dark:text-green-300 px-1.5 py-0.5 rounded"
										>
											<span class="size-1.5 rounded-full bg-green-500"></span>
											{$i18n.t('Connected')}
										</span>
									{/if}
									{#if item.kind === 'custom' && !item.server.enabled}
										<div
											class="flex items-center text-xs dark:bg-customGray-900 px-[6px] py-[3px] rounded-md bg-lightGray-400 font-medium text-lightGray-100 dark:text-customGray-300"
										>
											{$i18n.t('Disabled')}
										</div>
									{/if}
								</div>

								{#if item.kind === 'custom'}
									<div
										class="{hoveredId === item.id || menuIdOpened === item.id
											? 'md:visible'
											: 'md:invisible'} shrink-0"
									>
										<MCPServerMenu
											on:edit={() => openEdit(item.server)}
											on:test={() => testServer(item.server)}
											on:delete={() => {
												selectedItem = item.server;
												showDeleteConfirm = true;
											}}
											on:openMenu={() => (menuIdOpened = item.id)}
											on:closeMenu={() => (menuIdOpened = null)}
										/>
									</div>
								{/if}
							</div>

							<div class="self-center flex-1 px-0.5 mb-1 mt-2">
								<div
									class="text-left line-clamp-2 h-fit text-base {hoveredId === item.id ||
									menuIdOpened === item.id
										? 'dark:text-white'
										: 'dark:text-customGray-100'} text-lightGray-100 leading-[1.2] mb-1.5"
								>
									{item.name}
								</div>
								{#if item.kind === 'custom'}
									<div
										class="text-left overflow-hidden text-ellipsis line-clamp-1 text-xs font-mono text-lightGray-1200 dark:text-customGray-100/50 mb-1"
									>
										{item.server.url}
									</div>
								{/if}
								<div
									class="text-left overflow-hidden text-ellipsis line-clamp-2 text-xs text-lightGray-1200 dark:text-customGray-100/50 mb-2"
								>
									{item.kind === 'template' ? $i18n.t(item.description) : item.description}
								</div>
							</div>
						</div>
						{#if (item.kind === 'template' && item.row?.scope_mismatch) || (item.kind === 'custom' && item.server.scope_mismatch)}
							<span
								class="absolute top-2 right-2 h-2.5 w-2.5 rounded-full bg-yellow-400"
								title="Neue Rechte verfügbar — bitte neu verbinden"
							></span>
						{/if}
					</button>
				{/each}
			</div>

			<div class="text-xs text-lightGray-1200 dark:text-customGray-100/50 pb-4 pt-1">
				{$i18n.t('Connector not listed?')}
				<a
					class="underline ml-1 hover:text-lightGray-100 dark:hover:text-customGray-100"
					href="https://beyond-the-loop.notion.site/mcp"
					target="_blank"
					rel="noopener noreferrer"
				>
					{$i18n.t('Request it for the library')}
				</a>
			</div>
		</div>
	</div>
{:else}
	<div class="w-full h-full flex justify-center items-center">
		<Spinner />
	</div>
{/if}
