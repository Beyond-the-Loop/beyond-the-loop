<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Modal from './Modal.svelte';
	import {
		getUserEntities,
		transferUserEntities,
		deleteUserById,
		getUsers,
		type TransferItem
	} from '$lib/apis/users';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let show = false;
	export let userId = '';
	export let userName = '';

	type EntityItem = { id: string; name: string };
	type AssignmentMap = Record<string, string>;

	let users: any[] = [];
	let models: EntityItem[] = [];
	let prompts: EntityItem[] = [];
	let knowledge: EntityItem[] = [];
	let loading = true;
	let deleting = false;

	let modelAssignments: AssignmentMap = {};
	let promptAssignments: AssignmentMap = {};
	let knowledgeAssignments: AssignmentMap = {};

	$: if (show && userId) {
		loadData();
	}

	async function loadData() {
		loading = true;
		try {
			const [entities, userList] = await Promise.allSettled([
				getUserEntities(localStorage.token, userId),
				getUsers(localStorage.token)
			]);

			if (entities.status === 'fulfilled') {
				models = entities.value.models;
				prompts = entities.value.prompts;
				knowledge = entities.value.knowledge;
			}

			// getUsers requires admin rights — non-admins deleting themselves get an empty list
			users =
				userList.status === 'fulfilled'
					? userList.value.filter((u: any) => u.id !== userId)
					: [];

			modelAssignments = Object.fromEntries(models.map((m) => [m.id, '']));
			promptAssignments = Object.fromEntries(prompts.map((p) => [p.id, '']));
			knowledgeAssignments = Object.fromEntries(knowledge.map((k) => [k.id, '']));
		} catch (e) {
			console.error(e);
		}
		loading = false;
	}

	async function handleConfirm() {
		deleting = true;
		try {
			const assignments: TransferItem[] = [];

			for (const [id, newUserId] of Object.entries(modelAssignments)) {
				if (newUserId)
					assignments.push({ entity_type: 'model', entity_id: id, new_user_id: newUserId });
			}
			for (const [id, newUserId] of Object.entries(promptAssignments)) {
				if (newUserId)
					assignments.push({ entity_type: 'prompt', entity_id: id, new_user_id: newUserId });
			}
			for (const [id, newUserId] of Object.entries(knowledgeAssignments)) {
				if (newUserId)
					assignments.push({ entity_type: 'knowledge', entity_id: id, new_user_id: newUserId });
			}

			if (assignments.length > 0) {
				await transferUserEntities(localStorage.token, userId, assignments);
			}

			await deleteUserById(localStorage.token, userId);

			dispatch('confirm');
			show = false;
		} catch (e) {
			toast.error(`${e}`);
		}
		deleting = false;
	}

	function getUserDisplayName(u: any) {
		const name = [u.first_name, u.last_name].filter(Boolean).join(' ');
		return name || u.email;
	}

	const hasEntities = () => models.length > 0 || prompts.length > 0 || knowledge.length > 0;
</script>

<Modal bind:show size="md" blockBackdropClick={deleting}>
	<div class="flex flex-col gap-5 px-6 py-5 text-sm text-gray-800 dark:text-gray-200">
		<!-- Header -->
		<div class="flex flex-col gap-1">
			<h2 class="text-base font-semibold text-gray-900 dark:text-white">
				{$i18n.t('Delete user')}
			</h2>
			<p class="text-gray-500 dark:text-customGray-300 text-xs">
				{#if userName}
					{$i18n.t('You are about to delete')}
					<span class="font-semibold text-gray-800 dark:text-gray-100">{userName}</span>.
				{/if}
				{$i18n.t('This action cannot be undone.')}
			</p>
		</div>

		{#if loading}
			<div class="flex items-center justify-center py-6">
				<div
					class="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600 dark:border-customGray-600 dark:border-t-gray-300"
				/>
			</div>
		{:else if hasEntities()}
			<div class="flex flex-col gap-4">
				<p class="text-xs text-gray-500 dark:text-customGray-300">
					{$i18n.t(
						'The following items belong to this user. Select a new owner for each item or leave it empty to delete it along with the user.'
					)}
				</p>

				<!-- Assistants -->
				{#if models.length > 0}
					<div class="flex flex-col gap-2">
						<h3 class="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-customGray-400">
							{$i18n.t('Assistants')}
						</h3>
						<div class="flex flex-col gap-1.5">
							{#each models as model}
								<div
									class="flex items-center justify-between gap-3 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-white dark:bg-customGray-900 px-3 py-2"
								>
									<span class="truncate text-xs font-medium text-gray-800 dark:text-gray-100"
										>{model.name}</span
									>
									<select
										bind:value={modelAssignments[model.id]}
										class="min-w-[160px] max-w-[200px] rounded-md border border-lightGray-400 dark:border-customGray-700 bg-lightGray-200 dark:bg-customGray-950 px-2 py-1 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
									>
										<option value="">{$i18n.t('Will be deleted')}</option>
										{#each users as u}
											<option value={u.id}>{getUserDisplayName(u)}</option>
										{/each}
									</select>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Prompts -->
				{#if prompts.length > 0}
					<div class="flex flex-col gap-2">
						<h3 class="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-customGray-400">
							{$i18n.t('Prompts')}
						</h3>
						<div class="flex flex-col gap-1.5">
							{#each prompts as prompt}
								<div
									class="flex items-center justify-between gap-3 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-white dark:bg-customGray-900 px-3 py-2"
								>
									<span class="truncate text-xs font-medium text-gray-800 dark:text-gray-100"
										>{prompt.name}</span
									>
									<select
										bind:value={promptAssignments[prompt.id]}
										class="min-w-[160px] max-w-[200px] rounded-md border border-lightGray-400 dark:border-customGray-700 bg-lightGray-200 dark:bg-customGray-950 px-2 py-1 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
									>
										<option value="">{$i18n.t('Will be deleted')}</option>
										{#each users as u}
											<option value={u.id}>{getUserDisplayName(u)}</option>
										{/each}
									</select>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Knowledge Bases -->
				{#if knowledge.length > 0}
					<div class="flex flex-col gap-2">
						<h3 class="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-customGray-400">
							{$i18n.t('Knowledge bases')}
						</h3>
						<div class="flex flex-col gap-1.5">
							{#each knowledge as kb}
								<div
									class="flex items-center justify-between gap-3 rounded-lg border border-lightGray-400 dark:border-customGray-700 bg-white dark:bg-customGray-900 px-3 py-2"
								>
									<span class="truncate text-xs font-medium text-gray-800 dark:text-gray-100"
										>{kb.name}</span
									>
									<select
										bind:value={knowledgeAssignments[kb.id]}
										class="min-w-[160px] max-w-[200px] rounded-md border border-lightGray-400 dark:border-customGray-700 bg-lightGray-200 dark:bg-customGray-950 px-2 py-1 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
									>
										<option value="">{$i18n.t('Will be deleted')}</option>
										{#each users as u}
											<option value={u.id}>{getUserDisplayName(u)}</option>
										{/each}
									</select>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{:else}
			<p class="text-xs text-gray-500 dark:text-customGray-300">
				{$i18n.t('This user has no assistants, prompts, or knowledge bases.')}
			</p>
		{/if}

		<!-- Actions -->
		<div class="flex justify-end gap-2 pt-1">
			<button
				type="button"
				disabled={deleting}
				on:click={() => {
					show = false;
					dispatch('cancel');
				}}
				class="px-4 py-2 text-xs font-medium rounded-lg border border-lightGray-400 dark:border-customGray-700 text-gray-700 dark:text-customGray-200 bg-white dark:bg-customGray-900 hover:bg-lightGray-300 dark:hover:bg-customGray-950 transition disabled:opacity-50"
			>
				{$i18n.t('Cancel')}
			</button>
			<button
				type="button"
				disabled={deleting || loading}
				on:click={handleConfirm}
				class="px-4 py-2 text-xs font-medium rounded-lg bg-red-500 hover:bg-red-600 text-white transition disabled:opacity-50 flex items-center gap-2"
			>
				{#if deleting}
					<div
						class="h-3 w-3 animate-spin rounded-full border-2 border-white/40 border-t-white"
					/>
				{/if}
				{$i18n.t('Delete user')}
			</button>
		</div>
	</div>
</Modal>
