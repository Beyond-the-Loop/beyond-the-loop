<script lang="ts">
	import { getContext } from 'svelte';
	import InfoIcon from '$lib/components/icons/InfoIcon.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Info from '$lib/components/icons/Info.svelte';
	import { WEBUI_BASE_URL } from '$lib/constants';
	import Chart from './Chart.svelte';
	import { getModelIcon } from '$lib/utils';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { getMonths } from '$lib/utils';
	import { onClickOutside } from '$lib/utils';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import ArrowRight from '$lib/components/icons/ArrowRight.svelte';
	import {
		getAcceptanceRate,
		getPowerUsers,
		getTopModels,
		getTopUsers,
		getTotalAssistants,
		getTotalMessages,
		getTotalUsers
	} from '$lib/apis/analytics';
	import { getMonthRange, getPeriodRange } from '$lib/utils';
	import { onMount } from 'svelte';
	import ChevronRight from '$lib/components/icons/ChevronRight.svelte';
	import ChevronLeft from '$lib/components/icons/ChevronLeft.svelte';
	import { Tabs } from 'bits-ui';

	const i18n = getContext('i18n');
	export let analyticsLoading = true;
	let activeTab = 'messages';

	let showUsersSortDropdown = false;
	let usersSortRef;

	let sortOptions = [
		{ value: 'credits', label: 'By credits used' },
		{ value: 'assistants', label: 'By assistants created' },
		{ value: 'messages', label: 'By messages sent' }
	];
	let selectedSortOrder = sortOptions[0];

	let showMonthsDropdown = false;
	let monthsRef;

	const periodOptions = [
		{
			label: 'This month',
			value: 'this_month'
		},
		{
			label: 'Past 30 days',
			value: 'past_30_days'
		},
		{
			label: 'Past 3 months',
			value: 'past_3_months'
		},
		{
			label: 'Past year',
			value: 'past_year'
		}
	];

	let selectedPeriod = periodOptions[0];
	let chartMessagesData = null;

	let users = [];

	const token = localStorage.token;
	const now = new Date();
	const year = now.getFullYear();
	const month = now.getMonth() + 1;
	const { start, end } = getMonthRange(year, month);

	let analytics = {};

	onMount(async () => {
		try {
			const [
				topModels,
				totalUsers,
				totalMessages,
				acceptanceRate,
				powerUsers,
				topUsers,
				totalAssistants
			] = await Promise.allSettled([
				getTopModels(token, start, end),
				getTotalUsers(token),
				getTotalMessages(token),
				getAcceptanceRate(token),
				getPowerUsers(token),
				getTopUsers(token, start, end),
				getTotalAssistants(token)
			]);

			analytics = {
				topModels:
					topModels?.status === 'fulfilled' && !topModels?.value?.message ? topModels?.value : [],
				totalUsers: totalUsers?.status === 'fulfilled' ? totalUsers?.value : {},
				totalMessages: totalMessages?.status === 'fulfilled' ? totalMessages?.value : {},
				acceptanceRate: acceptanceRate?.status === 'fulfilled' ? acceptanceRate?.value : {},
				powerUsers: powerUsers?.status === 'fulfilled' ? powerUsers?.value : {},
				topUsers: topUsers?.status === 'fulfilled' ? topUsers?.value : {},
				totalAssistants: totalAssistants?.status === 'fulfilled' ? totalAssistants?.value : {}
			};
		} catch (error) {
			console.error('Error fetching analytics:', error);
		} finally {
			analyticsLoading = false;
		}
	});

	$: {
		if (analytics?.topUsers?.top_by_credits?.length > 0) {
			users = analytics?.topUsers?.top_by_credits;
		}
		if (analytics?.totalMessages?.monthly_messages) {
			chartMessagesData = {
				labels: analytics?.totalMessages?.monthly_messages
					? getMonths(analytics?.totalMessages?.monthly_messages)
					: [],
				datasets: [
					{
						label: 'Total Messages',
						// data: ['N/A', 'N/A', 15, 20, 24, 25, 40, 48, 50, 62, 60, 70, 80],
						data: Object.values(analytics?.totalMessages?.monthly_messages),
						backgroundColor: ['#305BE4'],
						borderColor: ['#305BE4']
					}
				]
			};
		}
	}

	const chartOptions = {
		responsive: true,
		plugins: {
			legend: {
				display: false
			}
		}
		// scales: {
		// 	y: {
		// 		ticks: {
		// 			callback: function (value) {
		// 				return value + '%';
		// 			}
		// 		}
		// 	}
		// }
	};

	type User = {
		profile_image_url: string;
		email: string;
		first_name: string;
		last_name: string;
		total_credits_used: number;
		message_count: number;
		assistant_count: number;
	};

	const Anna: User = {
		profile_image_url: '',
		email: 'anna.schmidt@company.com',
		first_name: 'Anna',
		last_name: 'Schmidt',
		total_credits_used: 41.79,
		message_count: 1245,
		assistant_count: 12
	};
	const Max: User = {
		profile_image_url: '',
		email: 'max.weber@company.com',
		first_name: 'Max',
		last_name: 'Weber',
		total_credits_used: 27.32,
		message_count: 342,
		assistant_count: 3
	};
	const Lisa: User = {
		profile_image_url: '',
		email: 'lisa.mueller@company.com',
		first_name: 'Lisa',
		last_name: 'Müller',
		total_credits_used: 20.31,
		message_count: 289,
		assistant_count: 1
	};
	const Tom: User = {
		profile_image_url: '',
		email: 'tom.fischer@company.com',
		first_name: 'Tom',
		last_name: 'Fischer',
		total_credits_used: 11.93,
		message_count: 189,
		assistant_count: 1
	};
	const Sarah: User = {
		profile_image_url: '',
		email: 'sarah.koch@company.com',
		first_name: 'Sarah',
		last_name: 'Koch',
		total_credits_used: 5,
		message_count: 156,
		assistant_count: 1
	};
	const usersList = [Max, Lisa, Anna, Tom, Sarah];
	let rows = [
		{ user: usersList[0] },
		{ user: usersList[1] },
		{ user: usersList[2] },
		{ user: usersList[3] },
		{ user: usersList[4] }
	];
	type SortKey = 'user' | 'credits' | 'messages';
	type SortDir = 'asc' | 'desc';
	let sortKey: SortKey | null = null;
	let sortDir: SortDir = 'asc';
	function toggleSort(key: SortKey) {
		if (sortKey === key) {
			sortDir = sortDir === 'asc' ? 'desc' : 'asc';
		} else {
			sortKey = key;
			sortDir = 'asc';
		}
		if (key === 'credits') {
			users = analytics?.topUsers?.top_by_credits;
		} else if (key === 'messages') {
			users = analytics?.topUsers?.top_by_messages;
		} else if (key === 'user') {
			users = analytics?.topUsers?.top_by_assistants;
		}
		rows = users;
		console.log(users);
	}
</script>

<div class="pb-20">
	{#if !analyticsLoading}
		<div
			class="flex w-full justify-between items-center py-2.5 border-b border-lightGray-400 dark:border-customGray-700 my-2.5"
		>
			<div class="flex flex-col w-full">
				<div class="text-lg font-semibold">Analytics</div>
				<div class="text-xs text-lightGray-100 dark:text-customGray-300">
					{$i18n.t('Understand AI adoption in your organization')}
				</div>
			</div>
		</div>
		<!-- <div
			class="flex w-full justify-between items-center pb-2.5 border-b border-lightGray-400 dark:border-customGray-700 mb-2.5"
		> -->
		<div class="pb-1">
			<div class="flex w-full justify-between items-center">
				<div class="text-2xs text-lightGray-100 dark:text-customGray-300 font-semibold">
					{$i18n.t('COMPANY OVERVIEW')}
				</div>
			</div>
		</div>
		<div class="grid grid-cols-2 md:grid-cols-4 gap-[8px]">
			<div
				class="rounded-lg bg-lightGray-300 ring-1 ring-gray-200 dark:bg-customGray-900 p-[10px] flex flex-col justify-between items-start"
			>
				<div class="flex flex-row w-full justify-between">
					<div class="bg-blue-700 size-5 rounded-md"></div>
					<Tooltip content={$i18n.t('The total number of users.')}>
						<!-- zB offset={[0, -48]} mitgeben -->

						<div
							class="cursor-pointer w-[12px] h-[12px] rounded-full text-gray-700 dark:text-lightGray-200"
						>
							<Info className="size-3" />
						</div>
					</Tooltip>
				</div>

				<div class="pt-[6px]">
					<div class="text-xl font-semibold text-lightGray-100 dark:text-customGray-100 mb-0">
						{analytics?.totalUsers?.total_users}
					</div>
					<div class="text-xs dark:text-customGray-100/50 text-center">
						{$i18n.t('Total users')}
					</div>
				</div>
			</div>
			<div
				class="rounded-lg bg-lightGray-300 ring-1 ring-gray-200 dark:bg-customGray-900 p-[10px] flex flex-col justify-between items-start"
			>
				<div class="flex flex-row w-full justify-between">
					<div class="bg-blue-700 size-5 rounded-md"></div>
					<Tooltip
						content={$i18n.t('The proportion of users who logged in during the last month.')}
					>
						<!-- zB offset={[0, -48]} mitgeben -->

						<div
							class="cursor-pointer w-[12px] h-[12px] rounded-full text-gray-700 dark:text-lightGray-200"
						>
							<Info className="size-3" />
						</div>
					</Tooltip>
				</div>

				<div class="pt-[6px]">
					<div class="text-xl font-semibold text-lightGray-100 dark:text-customGray-100 mb-0">
						{analytics?.acceptanceRate?.adoption_rate}%
						<!-- 91.3% -->
					</div>
					<div class="text-xs dark:text-customGray-100/50 text-center">
						{$i18n.t('Acceptance rate')}
					</div>
				</div>
			</div>
			<div
				class="rounded-lg bg-lightGray-300 ring-1 ring-gray-200 dark:bg-customGray-900 p-[10px] flex flex-col justify-between items-start"
			>
				<div class="flex flex-row w-full justify-between">
					<div class="bg-blue-700 size-5 rounded-md"></div>
					<Tooltip content={$i18n.t('Users who sent 400 or more messages in the last month.')}>
						<!-- zB offset={[0, -48]} mitgeben -->

						<div
							class="cursor-pointer w-[12px] h-[12px] rounded-full text-gray-700 dark:text-lightGray-200"
						>
							<Info className="size-3" />
						</div>
					</Tooltip>
				</div>

				<div class="pt-[6px]">
					<div class="text-xl font-semibold text-lightGray-100 dark:text-customGray-100 mb-0">
						<!-- {analytics?.powerUsers?.power_users_count} -->
						3
					</div>
					<div class="text-xs dark:text-customGray-100/50 text-center">
						{$i18n.t('Power users')}
					</div>
				</div>
			</div>
			<div
				class="rounded-lg bg-lightGray-300 ring-1 ring-gray-200 dark:bg-customGray-900 p-[10px] flex flex-col justify-between items-start"
			>
				<div class="flex flex-row w-full justify-between">
					<div class="bg-blue-700 size-5 rounded-md"></div>
					<Tooltip content={$i18n.t('The number of assistants created within the company.')}>
						<!-- zB offset={[0, -48]} mitgeben -->

						<div
							class="cursor-pointer w-[12px] h-[12px] rounded-full text-gray-700 dark:text-lightGray-200"
						>
							<Info className="size-3" />
						</div>
					</Tooltip>
				</div>

				<div class="pt-[6px]">
					<div class="text-xl font-semibold text-lightGray-100 dark:text-customGray-100 mb-0">
						{analytics?.totalAssistants?.total_assistants}
					</div>
					<div class="text-xs dark:text-customGray-100/50 text-center">
						{$i18n.t('Assistants created')}
					</div>
				</div>
			</div>
		</div>

		<Tabs.Root value="users" class="rounded-card border-muted w-full shadow-card mt-6 ">
			<Tabs.List
				class="bg-gray-100 dark:bg-gray-800 rounded-lg flex flex-row p-[2px] text-xs w-fit"
			>
				<Tabs.Trigger
					value="users"
					class="dark:data-[state=active]:bg-gray-700 py-[10px] px-4 data-[state=active]:text-gray-900 text-gray-600 py-1 rounded-md flex flex-rowitems-center data-[state=active]:bg-gray-200"
					><div class="size-3 bg-gray-800 mr-2"></div>
					Users</Tabs.Trigger
				>
				<Tabs.Trigger
					value="models"
					class="dark:data-[state=active]:bg-gray-700 py-[10px] px-4 data-[state=active]:text-gray-900 text-gray-600 rounded-md flex flex-row items-center data-[state=active]:bg-gray-200"
					><div class="size-3 bg-gray-800 mr-2"></div>
					Models</Tabs.Trigger
				>
				<Tabs.Trigger
					value="assistants"
					class="dark:data-[state=active]:bg-gray-700 py-[10px] px-4 data-[state=active]:text-gray-900 text-gray-600 rounded-md flex flex-row items-center data-[state=active]:bg-gray-200"
					><div class="size-3 bg-gray-800 mr-2"></div>
					Assistants</Tabs.Trigger
				>
			</Tabs.List>
			<Tabs.Content value="users" class="select-none pt-3">
				<table class="w-full ring-1 ring-gray-200 rounded-2xl bg-lightGray-300 text-xs table-auto">
					<thead class="text-slate-500/90">
						<tr>
							<th class="w-4"></th>

							<th
								class="p-3 text-left relative hover:opacity-90 cursor-pointer select-none"
								on:click={() => toggleSort('user')}
							>
								User

								<div class="absolute left-12 top-[14px]">
									{#if sortKey === 'user'}
										{#if sortDir === 'asc'}
											<ChevronDown className="size-3" strokeWidth="2.5" />
										{:else}
											<ChevronUp className="size-3" strokeWidth="2.5" />
										{/if}
									{/if}
								</div>
							</th>

							<th
								class="p-3 text-right relative hover:opacity-90 cursor-pointer select-none"
								on:click={() => toggleSort('credits')}
							>
								Credits used

								<div class="absolute -right-1 top-[14px]">
									{#if sortKey === 'credits'}
										{#if sortDir === 'asc'}
											<ChevronDown className="size-3" strokeWidth="2.5" />
										{:else}
											<ChevronUp className="size-3" strokeWidth="2.5" />
										{/if}
									{/if}
								</div>
							</th>

							<th
								class="p-3 text-right relative hover:opacity-90 cursor-pointer pr-5 select-none"
								on:click={() => toggleSort('messages')}
							>
								Messages sent

								<div class="absolute right-1 top-[14px]">
									{#if sortKey === 'messages'}
										{#if sortDir === 'asc'}
											<ChevronDown className="size-3" strokeWidth="2.5" />
										{:else}
											<ChevronUp className="size-3" strokeWidth="2.5" />
										{/if}
									{/if}
								</div>
							</th>
						</tr>
					</thead>
					<tbody>
						{#each rows as row}
							<tr class="hover:bg-gray-50">
								<td class="w-8 border-t border-1 border-gray-200/60">
									<div class="mx-2 text-slate-500/90">
										<ChevronRight className="size-3" strokeWidth="2.5" />
									</div>
								</td>
								<td class="border-t border-1 border-gray-200/60 p-3">
									<div class="flex flex-row items-center">
										<img
											class="rounded-full size-6 object-cover mr-2.5"
											src={row.user?.profile_image_url?.startsWith(WEBUI_BASE_URL) ||
											row.user?.profile_image_url?.startsWith('https://www.gravatar.com/avatar/') ||
											row.user?.profile_image_url?.startsWith('data:')
												? row.user.profile_image_url
												: `/user.png`}
											alt="user"
										/>
										<div>
											<div class="text-xs font-semibold dark:text-customGray-100">
												{row.user.first_name}
												{row.user.last_name}
											</div>
											<div class="text-2xs text-slate-500/90">{row.user.email}</div>
										</div>
									</div>
								</td>
								<td class="border-t border-1 border-gray-200/60 p-3 text-right font-semibold"
									>€{(row.user?.total_credits_used).toFixed(2)}</td
								>
								<td class="border-t border-1 border-gray-200/60 p-3 pr-5 text-right font-semibold"
									>{row.user.message_count}</td
								>
							</tr>
						{/each}
					</tbody>
					<tfoot>
						<tr class="border-t border-1 border-gray-200/60">
							<td colspan="4" class="p-3">
								<div class="flex flex-row justify-between items-center">
									<div class="flex flex-row items-center">
										<div class="text-gray-600 pr-2">Rows per page</div>
										<select class="w-12 bg-white ring-1 rounded-md ring-gray-200 py-1 px-2">
											<option selected>5</option> <option value="10">10</option>
											<option value="15">15</option> <option value="20">20</option>
										</select>
									</div>
									<div class="flex flex-row items-center">
										<button
											class="bg-white text-gray-700 mx-[2px] flex justify-center items-center rounded-md font-semibold size-5 disabled:opacity-50"
											disabled><ChevronLeft /></button
										>
										<button class="bg-blue-600 text-white mx-[2px] rounded-md font-semibold size-6"
											>1</button
										>
										<button class="text-gray-600 mx-[2px] rounded-md font-semibold size-6">2</button
										>
										<button
											class="bg-white text-gray-900 mx-[2px] rounded-md font-semibold size-5 disabled:opacity-50 flex justify-center items-center"
											><ChevronRight className="size-3" strokeWidth="2.5" /></button
										>
									</div>
								</div>
							</td>
						</tr>
					</tfoot>
				</table>
			</Tabs.Content>
			<Tabs.Content value="models" class="select-none pt-3">
				<table class="w-full ring-1 ring-gray-200 rounded-2xl bg-lightGray-300 text-xs table-auto">
					<thead class="text-slate-500/90">
						<tr>
							<th class="w-4"></th>

							<th
								class="p-3 text-left relative hover:opacity-90 cursor-pointer select-none"
								on:click={() => toggleSort('user')}
							>
								Model

								<div class="absolute left-12 top-[14px]">
									{#if sortKey === 'user'}
										{#if sortDir === 'asc'}
											<ChevronDown className="size-3" strokeWidth="2.5" />
										{:else}
											<ChevronUp className="size-3" strokeWidth="2.5" />
										{/if}
									{/if}
								</div>
							</th>

							<th
								class="p-3 text-right relative hover:opacity-90 cursor-pointer select-none"
								on:click={() => toggleSort('credits')}
							>
								Credits used

								<div class="absolute -right-1 top-[14px]">
									{#if sortKey === 'credits'}
										{#if sortDir === 'asc'}
											<ChevronDown className="size-3" strokeWidth="2.5" />
										{:else}
											<ChevronUp className="size-3" strokeWidth="2.5" />
										{/if}
									{/if}
								</div>
							</th>

							<th
								class="p-3 text-right relative hover:opacity-90 cursor-pointer pr-5 select-none"
								on:click={() => toggleSort('messages')}
							>
								Messages sent

								<div class="absolute right-1 top-[14px]">
									{#if sortKey === 'messages'}
										{#if sortDir === 'asc'}
											<ChevronDown className="size-3" strokeWidth="2.5" />
										{:else}
											<ChevronUp className="size-3" strokeWidth="2.5" />
										{/if}
									{/if}
								</div>
							</th>
						</tr>
					</thead>
					<tbody>
						{#each rows as row}
							<tr class="hover:bg-gray-50">
								<td class="w-8 border-t border-1 border-gray-200/60">
									<div class="mx-2 text-slate-500/90">
										<ChevronRight className="size-3" strokeWidth="2.5" />
									</div>
								</td>
								<td class="border-t border-1 border-gray-200/60 p-3">
									<div class="flex flex-row items-center">
										<img
											class="rounded-full size-6 object-cover mr-2.5"
											src={row.user?.profile_image_url?.startsWith(WEBUI_BASE_URL) ||
											row.user?.profile_image_url?.startsWith('https://www.gravatar.com/avatar/') ||
											row.user?.profile_image_url?.startsWith('data:')
												? row.user.profile_image_url
												: `/user.png`}
											alt="user"
										/>
										<div>
											<div class="text-xs font-semibold dark:text-customGray-100">
												{row.user.first_name}
												{row.user.last_name}
											</div>
											<div class="text-2xs text-slate-500/90">{row.user.email}</div>
										</div>
									</div>
								</td>
								<td class="border-t border-1 border-gray-200/60 p-3 text-right font-semibold"
									>€{(row.user?.total_credits_used).toFixed(2)}</td
								>
								<td class="border-t border-1 border-gray-200/60 p-3 pr-5 text-right font-semibold"
									>{row.user.message_count}</td
								>
							</tr>
						{/each}
					</tbody>
					<tfoot>
						<tr class="border-t border-1 border-gray-200/60">
							<td colspan="4" class="p-3">
								<div class="flex flex-row justify-between items-center">
									<div class="flex flex-row items-center">
										<div class="text-gray-600 pr-2">Rows per page</div>
										<select class="w-12 bg-white ring-1 rounded-md ring-gray-200 py-1 px-2">
											<option selected>5</option> <option value="10">10</option>
											<option value="15">15</option> <option value="20">20</option>
										</select>
									</div>
									<div class="flex flex-row items-center">
										<button
											class="bg-white text-gray-700 mx-[2px] flex justify-center items-center rounded-md font-semibold size-5 disabled:opacity-50"
											disabled><ChevronLeft /></button
										>
										<button class="bg-blue-600 text-white mx-[2px] rounded-md font-semibold size-6"
											>1</button
										>
										<button class="text-gray-600 mx-[2px] rounded-md font-semibold size-6">2</button
										>
										<button
											class="bg-white text-gray-900 mx-[2px] rounded-md font-semibold size-5 disabled:opacity-50 flex justify-center items-center"
											><ChevronRight className="size-3" strokeWidth="2.5" /></button
										>
									</div>
								</div>
							</td>
						</tr>
					</tfoot>
				</table>
			</Tabs.Content>
			<Tabs.Content value="assistants" class="select-none pt-3"></Tabs.Content>
		</Tabs.Root>

		<div class="pb-1 border-t-[1px] border-lightGray-400 dark:border-customGray-700 mt-6 pt-2">
			<div class="flex w-full justify-between items-center">
				<div class="text-2xs text-lightGray-100 dark:text-customGray-300 font-semibold">
					{$i18n.t('USAGE HISTORY')}
				</div>
			</div>
		</div>
		<Tabs.Root value="monthly" class="rounded-card border-muted w-full shadow-card mt-6 ">
			<Tabs.List
				class="bg-gray-100 dark:bg-gray-800 rounded-lg flex flex-row p-[2px] text-xs w-fit"
			>
				<Tabs.Trigger
					value="monthly"
					class="dark:data-[state=active]:bg-gray-700 py-[10px] px-4 data-[state=active]:text-gray-900 text-gray-600 py-1 rounded-md items-center data-[state=active]:bg-gray-200"
				>
					Monthly</Tabs.Trigger
				>
				<Tabs.Trigger
					value="models"
					class="dark:data-[state=active]:bg-gray-700 py-[10px] px-4 data-[state=active]:text-gray-900 text-gray-600 rounded-md items-center data-[state=active]:bg-gray-200"
				>
					Yearly</Tabs.Trigger
				>
			</Tabs.List>
			<Tabs.Content value="monthly" class="select-none text-xs pt-3">
				<div class="w-full bg-lightGray-300 flex flex-col justify-start gap-2 p-2">
					This Month vs. Last Month
					<div class="text-lg font-semibold">6300</div>
					<div class="text-slate-500/90">Messages sent</div>
				</div>
			</Tabs.Content>
		</Tabs.Root>
		<div class="bg-lightGray-300 dark:bg-customGray-900 rounded-2xl p-4 pb-1 mt-5">
			<div
				class="flex w-full justify-between items-center pb-2.5 border-b border-lightGray-400 dark:border-customGray-700 mb-2.5"
			>
				<div class="flex w-full justify-between items-center">
					<div class="text-xs text-lightGray-100 dark:text-customGray-300 font-medium">
						{$i18n.t('Top users')} ({$i18n.t('This month').toLowerCase()})
					</div>
				</div>
				<div use:onClickOutside={() => (showUsersSortDropdown = false)}>
					<div class="relative" bind:this={usersSortRef}>
						<button
							type="button"
							class="flex items-center min-w-40 justify-end text-sm border-lightGray-400 dark:border-customGray-700 rounded-md bg-lightGray-300 dark:bg-customGray-900 cursor-pointer"
							on:click={() => (showUsersSortDropdown = !showUsersSortDropdown)}
						>
							<div class="flex items-center">
								<div
									class="text-xs dark:text-customGray-200 max-w-[22rem] text-left whitespace-nowrap"
								>
									{$i18n.t(selectedSortOrder?.label)}
								</div>
								<ChevronDown className="size-3" strokeWidth="2.5" />
							</div>
						</button>

						{#if showUsersSortDropdown}
							<div
								class="max-h-60 min-w-[14rem] overflow-y-auto absolute top-6 -right-2 z-50 bg-lightGray-300 dark:bg-customGray-900 border border-lightGray-400 dark:border-customGray-700 rounded-md shadow"
							>
								<div class="px-1 py-1">
									{#each sortOptions?.filter?.((item) => item?.value !== selectedSortOrder?.value) as option}
										<div
											role="button"
											tabindex="0"
											on:click={() => {
												selectedSortOrder = option;
												if (option.value === 'credits') {
													users = analytics?.topUsers?.top_by_credits;
												} else if (option.value === 'messages') {
													users = analytics?.topUsers?.top_by_messages;
												} else {
													users = analytics?.topUsers?.top_by_assistants;
												}
												showUsersSortDropdown = false;
											}}
											class="flex items-center justify-end w-full cursor-pointer text-xs text-lightGray-100 dark:text-customGray-100 px-2 py-2 hover:bg-lightGray-700 dark:hover:bg-customGray-950 rounded-md"
										>
											{$i18n.t(option?.label)}
										</div>
									{/each}
								</div>
							</div>
						{/if}
					</div>
				</div>
			</div>

			{#each users as user}
				<div class="flex items-center justify-between mb-3">
					<div class="flex items-center">
						<img
							class=" rounded-full w-3 h-3 object-cover mr-2.5"
							src={user.profile_image_url.startsWith(WEBUI_BASE_URL) ||
							user.profile_image_url.startsWith('https://www.gravatar.com/avatar/') ||
							user.profile_image_url.startsWith('data:')
								? user.profile_image_url
								: `/user.png`}
							alt="user"
						/>

						<div class="text-xs dark:text-customGray-100 mr-1 whitespace-nowrap">
							{user.first_name}
							{user.last_name}
						</div>

						<Tooltip content={user.email} className=" w-fit overflow-hidden" placement="top-end">
							<div
								class="text-xs dark:text-customGray-590 mr-1 truncate text-ellipsis whitespace-nowrap"
							>
								{user.email}
							</div>
						</Tooltip>
					</div>
					{#if selectedSortOrder.value === 'credits'}
						<div class="text-xs dark:text-customGray-590">
							€{(user?.total_credits_used).toFixed(2)}
						</div>
					{:else if selectedSortOrder.value === 'messages'}
						<div class="text-xs dark:text-customGray-590">
							{user?.message_count}
							{$i18n.t('messages')}
						</div>
					{:else}
						<div class="text-xs dark:text-customGray-590">
							{user?.assistant_count}
							{$i18n.t('assistants')}
						</div>
					{/if}
				</div>
			{/each}
		</div>
		<div class="bg-lightGray-300 dark:bg-customGray-900 rounded-2xl p-4 pb-1 mt-5">
			<div
				class="flex w-full justify-between items-center pb-2.5 border-b border-lightGray-400 dark:border-customGray-700 mb-2.5"
			>
				<div class="flex w-full justify-between items-center">
					<div class="text-xs text-lightGray-100 dark:text-customGray-300 font-medium">
						{$i18n.t('Top 3 models used')}
					</div>
				</div>
				<div use:onClickOutside={() => (showMonthsDropdown = false)}>
					<div class="relative" bind:this={monthsRef}>
						<button
							type="button"
							class="flex items-center min-w-40 justify-end text-sm border-lightGray-400 dark:border-customGray-700 rounded-md bg-lightGray-300 dark:bg-customGray-900 cursor-pointer"
							on:click={() => (showMonthsDropdown = !showMonthsDropdown)}
						>
							<div class="flex items-center">
								<div
									class="text-xs text-lightGray-100 dark:text-customGray-200 max-w-[22rem] text-left"
								>
									{$i18n.t(selectedPeriod?.label)}
								</div>
								<ChevronDown className="size-3" strokeWidth="2.5" />
							</div>
						</button>

						{#if showMonthsDropdown}
							<div
								class="max-h-60 min-w-44 overflow-y-auto absolute top-6 -right-2 z-50 bg-lightGray-300 dark:bg-customGray-900 border border-gray-300 dark:border-customGray-700 rounded-md shadow"
							>
								<div class="px-1 py-1">
									{#each periodOptions as option}
										<div
											role="button"
											tabindex="0"
											on:click={async () => {
												selectedPeriod = option;
												const { start, end } = getPeriodRange(selectedPeriod.value);
												const res = await getTopModels(localStorage.token, start, end);
												analytics = {
													...analytics,
													topModels: res?.length > 0 ? res : []
												};
												showMonthsDropdown = false;
											}}
											class="flex items-center justify-end w-full cursor-pointer text-xs dark:text-customGray-100 px-2 py-2 hover:bg-lightGray-700 dark:hover:bg-customGray-950 rounded-md"
										>
											{$i18n.t(option?.label)}
										</div>
									{/each}
								</div>
							</div>
						{/if}
					</div>
				</div>
			</div>
			{#each analytics?.topModels as model}
				<div class="flex items-center justify-between mb-3">
					<div class="flex items-center">
						<img
							class=" rounded-full w-3 h-3 object-cover mr-2.5"
							src={getModelIcon(model?.model)}
							alt="user"
						/>

						<div class="text-xs dark:text-customGray-100 mr-1 whitespace-nowrap">
							{model?.model}
						</div>
					</div>
					<div class="text-xs dark:text-customGray-590">€{(model?.credits_used).toFixed(2)}</div>
				</div>
			{/each}
		</div>
		<div class="mt-5">
			<div
				class="flex w-full justify-between items-center pb-2.5 border-b border-lightGray-400 dark:border-customGray-700 mb-2.5"
			>
				<div class="flex w-full justify-between items-center">
					<div class="text-xs text-lightGray-100 dark:text-customGray-300 font-medium">
						{$i18n.t('User activity insights')}
					</div>
				</div>
			</div>
			<div class="w-fit flex bg-lightGray-700 dark:bg-customGray-900 rounded-md mx-auto mb-2.5">
				<button
					on:click={() => (activeTab = 'messages')}
					class="{activeTab === 'messages'
						? 'text-lightGray-100 bg-lightGray-300 border-lightGray-400 dark:bg-customGray-900 rounded-md border dark:border-customGray-700'
						: 'text-lightGray-100/70'} px-6 py-2 flex-shrink-0 text-xs font-medium leading-none dark:text-customGray-100"
					>{$i18n.t('Messages')}</button
				>
			</div>
			<div>
				<div class="dark:bg-customGray-900 rounded-2xl p-4">
					<Chart type="line" data={chartMessagesData} options={chartOptions} />
				</div>
			</div>
		</div>
	{:else}
		<div class="h-[20rem] w-full flex justify-center items-center">
			<Spinner />
		</div>
	{/if}
</div>
