<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { companyConfig } from '$lib/stores';
	import { updateCompanyConfigRaw } from '$lib/apis/auths';

	const i18n = getContext<any>('i18n');

	type CredField = 'client_id' | 'tenant_id' | 'client_secret';

	// Derive has_* flags from the store so they update reactively after a save
	$: m365 = ($companyConfig as any)?.config?.connectors?.['microsoft-365'] ?? {
		has_client_id: false,
		has_tenant_id: false,
		has_client_secret: false
	};

	let editingClientId = false;
	let editingTenantId = false;
	let editingClientSecret = false;

	let valueClientId = '';
	let valueTenantId = '';
	let valueClientSecret = '';

	let saving = false;

	function isEditing(field: CredField): boolean {
		if (field === 'client_id') return editingClientId;
		if (field === 'tenant_id') return editingTenantId;
		return editingClientSecret;
	}

	function getValue(field: CredField): string {
		if (field === 'client_id') return valueClientId;
		if (field === 'tenant_id') return valueTenantId;
		return valueClientSecret;
	}

	function toggleEdit(field: CredField) {
		if (field === 'client_id') {
			editingClientId = !editingClientId;
			if (!editingClientId) valueClientId = '';
		} else if (field === 'tenant_id') {
			editingTenantId = !editingTenantId;
			if (!editingTenantId) valueTenantId = '';
		} else {
			editingClientSecret = !editingClientSecret;
			if (!editingClientSecret) valueClientSecret = '';
		}
	}

	async function clearField(field: CredField) {
		saving = true;
		try {
			const key = `connectors_microsoft365_${field}`;
			const res = await updateCompanyConfigRaw(localStorage.token, { [key]: '' });
			if (res) {
				companyConfig.set(res);
				toast.success($i18n.t('Gespeichert'));
			}
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			saving = false;
		}
	}

	async function save() {
		const payload: Record<string, string> = {};
		if (editingClientId && valueClientId)
			payload['connectors_microsoft365_client_id'] = valueClientId;
		if (editingTenantId && valueTenantId)
			payload['connectors_microsoft365_tenant_id'] = valueTenantId;
		if (editingClientSecret && valueClientSecret)
			payload['connectors_microsoft365_client_secret'] = valueClientSecret;

		if (!Object.keys(payload).length) {
			toast.error($i18n.t('Keine Änderungen zum Speichern.'));
			return;
		}

		saving = true;
		try {
			const res = await updateCompanyConfigRaw(localStorage.token, payload);
			if (res) {
				companyConfig.set(res);
				editingClientId = false;
				editingTenantId = false;
				editingClientSecret = false;
				valueClientId = '';
				valueTenantId = '';
				valueClientSecret = '';
				toast.success($i18n.t('Gespeichert'));
			}
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			saving = false;
		}
	}

	const fieldLabels: Record<CredField, string> = {
		client_id: 'Client ID',
		tenant_id: 'Tenant ID',
		client_secret: 'Client Secret'
	};

	const fields: CredField[] = ['client_id', 'tenant_id', 'client_secret'];
</script>

<div class="py-4 px-1 space-y-6 text-lightGray-100 dark:text-customGray-100">
	<div>
		<h3 class="text-base font-semibold mb-1">Microsoft 365</h3>
		<p class="text-sm text-lightGray-1200/70 dark:text-customGray-100/60">
			{$i18n.t(
				'Diese Werte werden automatisch in den Microsoft-365-Konnektor eingesetzt, wenn Nutzer diesen einrichten.'
			)}
		</p>
	</div>

	{#each fields as field (field)}
		{@const hasField = m365[`has_${field}`]}
		{@const editing = isEditing(field)}
		<div>
			<label class="block text-sm font-medium mb-1">
				{fieldLabels[field]}
				{#if hasField}
					<span class="ml-2 text-green-500 text-base leading-none">✓</span>
				{/if}
			</label>
			<div class="flex gap-2 items-center">
				{#if field === 'client_secret'}
					<input
						type="password"
						class="flex-1 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent px-3 py-2 text-sm font-mono dark:text-customGray-100 outline-none focus:border-customBlue-500 disabled:opacity-50 disabled:cursor-not-allowed"
						placeholder={hasField && !editing ? '••••••••' : ''}
						disabled={hasField && !editing}
						bind:value={valueClientSecret}
					/>
				{:else if field === 'tenant_id'}
					<input
						type="text"
						class="flex-1 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent px-3 py-2 text-sm font-mono dark:text-customGray-100 outline-none focus:border-customBlue-500 disabled:opacity-50 disabled:cursor-not-allowed"
						placeholder={hasField && !editing ? '••••••••' : ''}
						disabled={hasField && !editing}
						bind:value={valueTenantId}
					/>
				{:else}
					<input
						type="text"
						class="flex-1 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-transparent px-3 py-2 text-sm font-mono dark:text-customGray-100 outline-none focus:border-customBlue-500 disabled:opacity-50 disabled:cursor-not-allowed"
						placeholder={hasField && !editing ? '••••••••' : ''}
						disabled={hasField && !editing}
						bind:value={valueClientId}
					/>
				{/if}

				{#if hasField && !editing}
					<button
						type="button"
						class="shrink-0 px-3 py-2 text-sm rounded-lg border border-lightGray-400 dark:border-customGray-700 hover:bg-lightGray-700 dark:hover:bg-customGray-800 transition"
						on:click={() => toggleEdit(field)}
					>
						{$i18n.t('Ändern')}
					</button>
					<button
						type="button"
						class="shrink-0 px-3 py-2 text-sm rounded-lg border border-red-500/40 text-red-600 dark:text-red-400 hover:bg-red-500/10 transition"
						on:click={() => clearField(field)}
					>
						{$i18n.t('Löschen')}
					</button>
				{:else if editing}
					<button
						type="button"
						class="shrink-0 px-3 py-2 text-sm rounded-lg border border-lightGray-400 dark:border-customGray-700 hover:bg-lightGray-700 dark:hover:bg-customGray-800 transition"
						on:click={() => toggleEdit(field)}
					>
						{$i18n.t('Abbrechen')}
					</button>
				{/if}
			</div>
		</div>
	{/each}

	<button
		type="button"
		class="px-4 py-2 rounded-lg bg-customBlue-500 hover:bg-customBlue-600 text-white text-sm font-medium transition disabled:opacity-50"
		disabled={saving}
		on:click={save}
	>
		{saving ? $i18n.t('Speichern…') : $i18n.t('Speichern')}
	</button>
</div>
