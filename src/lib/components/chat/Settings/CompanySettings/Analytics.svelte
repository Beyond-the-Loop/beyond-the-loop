<script lang="ts">
	import { getContext } from 'svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Info from '$lib/components/icons/Info.svelte';
	import { WEBUI_BASE_URL } from '$lib/constants';
	import Chart from './Chart.svelte';
	import { getModelIcon } from '$lib/utils';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { getMonths } from '$lib/utils';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import { subscription } from '$lib/stores';
	import {
		getEngagementScore,
		getPowerUsers,
		getTopModels,
		getTopUsers,
		getTopAssistants,
		getTotalAssistants,
		getTotalMessages,
		getTotalUsers
	} from '$lib/apis/analytics';
	import type {
		TopModelsResponse,
		TopAssistantsResponse,
		TotalUsersResponse,
		TotalMessagesResponse,
		EngagementScoreResponse,
		PowerUsersResponse,
		TopUsersResponse,
		TotalAssistantsResponse,
		TopUserItem
	} from '$lib/apis/analytics/types';
	import { getMonthRange } from '$lib/utils';
	import { onMount } from 'svelte';
	import ChevronRight from '$lib/components/icons/ChevronRight.svelte';
	import ChevronLeft from '$lib/components/icons/ChevronLeft.svelte';
	import UsersIcon from '$lib/components/icons/UsersIcon.svelte';
	import CheckCircle from '$lib/components/icons/CheckCircle.svelte';
	import LightningIcon from '$lib/components/icons/LightningIcon.svelte';
	import AssistantsIcon from '$lib/components/icons/AssistantsIcon.svelte';
	import TrendArrowIcon from '$lib/components/icons/TrendArrowIcon.svelte';
	import { Select, Pagination, Tabs } from 'bits-ui';
	import Cube from '$lib/components/icons/Cube.svelte';
	import CalendarIcon from '$lib/components/icons/CalendarIcon.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import CheckmarkIcon from '$lib/components/icons/CheckmarkIcon.svelte';

	const i18n = getContext('i18n');
	export let analyticsLoading = true;

	let chartMessagesData = null;
	let chartMessagesDataYearly = null;

	let page = 1;
	let rowsPerPage = 5;

	$: totalCount = rows?.length;
	$: startRow = (page - 1) * rowsPerPage;
	$: endRow = startRow + rowsPerPage;
	$: pagedRows = rows?.slice(startRow, endRow);
	$: totalCountModels = modelRows?.length;
	$: pagedModelRows = modelRows?.slice(startRow, endRow);

	$: totalCountAssistants = assistantRows?.length;
	$: pagedAssistantRows = assistantRows?.slice(startRow, endRow);

	let expanded = new Set<string>();

	function toggleRow(key: string) {
		expanded.has(key) ? expanded.delete(key) : expanded.add(key);
		expanded = new Set(expanded);
	}

	const token = localStorage.token;
	const now = new Date();
	const year = now.getFullYear();
	const month = now.getMonth() + 1;
	const { start, end } = getMonthRange(year, month);

	type AnalyticsState = {
		topModels: TopModelsResponse | null;
		topAssistants: TopAssistantsResponse | null;
		totalUsers: TotalUsersResponse | null;
		totalMessages: TotalMessagesResponse | null;
		engagementRate: EngagementScoreResponse | null;
		powerUsers: PowerUsersResponse | null;
		topUsers: TopUsersResponse | null;
		totalAssistants: TotalAssistantsResponse | null;
	};
	let analytics: AnalyticsState = {
		topModels: null,
		topAssistants: null,
		totalUsers: null,
		totalMessages: null,
		engagementRate: null,
		powerUsers: null,
		topUsers: null,
		totalAssistants: null
	};

	let timeSpan = 28;

	const options: { value: number; label: string }[] = [
		{ value: 7, label: 'Last 7 days' },
		{ value: 28, label: 'Last 4 weeks' },
		{ value: 365, label: 'Last year' },
		{ value: 10000, label: 'All time' }
	];
	$: localizedOptions = options.map(opt => ({    ...opt,    label: $i18n.t(opt.label),  }));
	$: selectedTimeSpan = localizedOptions.find((i) => i.value === 28);
	function addDays(date: Date, days: number) {
		const d = new Date(date);
		d.setDate(d.getDate() + days);
		return d;
	}
	function formatYYYYMMDD(d: Date) {
		const y = d.getFullYear();
		const m = String(d.getMonth() + 1).padStart(2, '0');
		const day = String(d.getDate()).padStart(2, '0');
		return `${y}-${m}-${day}`;
	}
	function handleTimeSpanChange(next) {
		selectedTimeSpan = next;
		analyticsLoading = true;
		const end = new Date(); // aktuelles Datum
		const start = addDays(end, -((selectedTimeSpan?.value ?? 28) - 1)); // inkl. heute -> 28 Tage = heute + 27 Tage zurück
		fetch_data(formatYYYYMMDD(start), formatYYYYMMDD(end));

		page = 1;
	}

	const sampleData = {
		monthly_messages: [
			{ period: '2026-01', message_count: 38 },
			{ period: '2026-02', message_count: 121 },
			{ period: '2026-03', message_count: 156 },
			{ period: '2026-04', message_count: 189 },
			{ period: '2026-05', message_count: 234 },
			{ period: '2026-06', message_count: 287 }
		],
		monthly_percentage_changes: [
			{ period: '2026-01', percentage_change: 0 },
			{ period: '2026-02', percentage_change: 218.4 },
			{ period: '2026-03', percentage_change: 28.9 },
			{ period: '2026-04', percentage_change: 21.2 },
			{ period: '2026-05', percentage_change: 23.8 },
			{ period: '2026-06', percentage_change: 22.6 }
		],
		yearly_messages: [{ period: '2026', message_count: 985 }],
		yearly_percentage_changes: [{ period: '2026', percentage_change: 0.0 }]
	};

	onMount(async () => {
		// fetch_data('2026-02-01', '2026-02-27');
		handleTimeSpanChange(selectedTimeSpan);
	});
	async function fetch_data(start_date: string, end_date: string) {
		try {
			const [
				topModels,
				topAssistants,
				totalUsers,
				totalMessages,
				engagementRate,
				powerUsers,
				topUsers,
				totalAssistants
			] = await Promise.allSettled([
				getTopModels(token, start_date, end_date),
				getTopAssistants(token, start_date, end_date),
				getTotalUsers(token),
				getTotalMessages(token),
				getEngagementScore(token),
				getPowerUsers(token),
				getTopUsers(token, start_date, end_date),
				getTotalAssistants(token)
			]);

			analytics = {
				topModels:
					topModels?.status === 'fulfilled' && !topModels?.value?.message ? topModels?.value : [],
				topAssistants: topAssistants?.status === 'fulfilled' ? topAssistants?.value : {},
				totalUsers: totalUsers?.status === 'fulfilled' ? totalUsers?.value : {},
				totalMessages: totalMessages?.status === 'fulfilled' ? totalMessages?.value : {},
				// totalMessages: sampleData,
				engagementRate: engagementRate?.status === 'fulfilled' ? engagementRate?.value : {},
				powerUsers: powerUsers?.status === 'fulfilled' ? powerUsers?.value : {},
				topUsers: topUsers?.status === 'fulfilled' ? topUsers?.value : {},
				totalAssistants: totalAssistants?.status === 'fulfilled' ? totalAssistants?.value : {}
			};
		} catch (error) {
			console.error('Error fetching analytics:', error);
		} finally {
			analyticsLoading = false;
		}
	}
	let chartOptions = null;

	$: {
		if (analytics?.topUsers != null) {
			rows = top_by_messages(analytics?.topUsers?.top_users);
		}
		if (analytics?.topModels != null) {
			modelRows = top_by_messages(analytics?.topModels.items);
		}
		if (analytics?.topAssistants != null) {
			assistantRows = top_by_messages(analytics?.topAssistants.top_assistants);
		}
		if (analytics?.totalMessages?.monthly_messages != null) {
			chartMessagesData = chart_messages_by_month();
			chartMessagesDataYearly = chart_messages_by_year();
		}
		chartOptions = {
			scales: {
				x: {
					grid: {
						drawOnChartArea: false
					},
					ticks: {
						font: {
							size: 8
						}
					}
				},
				y: {
					grid: {
						drawOnChartArea: false
					},
					ticks: {
						font: {
							size: 8
						},
						maxTicksLimit: 5
					},
					grace: '80%'
				}
			},
			barPercentage: Math.min(1.0, 0.1 + 0.18 * analytics?.totalMessages?.monthly_messages?.length),
			responsive: true,
			plugins: {
				legend: {
					display: false,
					font: {
						size: 4
					}
				}
			}
		};
	}

	let activeTab = 'users';
	$: if (activeTab) {
		page = 1;
	}
	$: searchBarPlaceholder =
		activeTab === 'users'
			? 'Search users...'
			: activeTab === 'models'
				? 'Search models...'
				: 'Search assistants...';

	let rows = null;
	let assistantRows = null;
	let modelRows = null;
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
			rows = top_by_credits(rows);
		} else if (key === 'messages') {
			rows = top_by_messages(rows);
		} else if (key === 'user') {
			rows = top_alphabetically(rows);
		}
		if (sortDir === 'desc') {
			rows.reverse();
		}
	}
	function top_by_credits(rowsToSort) {
		return [...rowsToSort].sort((a, b) => {
			return b.total_credits_used - a.total_credits_used;
		});
	}

	function top_by_messages(rowsToSort) {
		return [...rowsToSort].sort((a, b) => {
			return b.message_count - a.message_count;
		});
	}

	function top_alphabetically(rowsToSort) {
		return [...rowsToSort].sort((a, b) => {
			const lastNameCompare = a.last_name.localeCompare(b.last_name);
			if (lastNameCompare !== 0) {
				return lastNameCompare;
			}
			return a.first_name.localeCompare(b.first_name);
		});
	}

	function chart_messages_by_month() {
		return {
			labels: analytics?.totalMessages?.monthly_messages
				? getMonths(analytics?.totalMessages?.monthly_messages)
				: [],
			datasets: [
				{
					label: 'Total Messages',
					data: Object.values(
						analytics?.totalMessages?.monthly_messages?.map((item) => item.message_count) || []
					),
					backgroundColor: ['#305BE4'],
					borderColor: ['#305BE4']
				}
			]
		};
	}
	function chart_messages_by_year() {
		return {
			labels: analytics?.totalMessages?.yearly_messages
				? analytics?.totalMessages?.yearly_messages?.map((item) => item.period)
				: [],
			datasets: [
				{
					label: 'Total Messages',
					data: Object.values(
						analytics?.totalMessages?.yearly_messages?.map((item) => item.message_count) || []
					),
					backgroundColor: ['#305BE4'],
					borderColor: ['#305BE4']
				}
			]
		};
	}
	function searchFor(search: string) {
		rows = analytics?.topUsers?.top_users.filter((u) => {
			const q = search
				.trim()
				.toLowerCase()
				.normalize('NFD')
				.replace(/\p{Diacritic}/gu, ''); // entfernt z.B. ü -> u
			if (!q) return true;
			const first = u.first_name
				.toLowerCase()
				.normalize('NFD')
				.replace(/\p{Diacritic}/gu, '');
			const last = u.last_name
				.toLowerCase()
				.normalize('NFD')
				.replace(/\p{Diacritic}/gu, '');
			const full = `${first} ${last}`;
			const fullRev = `${last} ${first}`;
			return first.includes(q) || last.includes(q) || full.includes(q) || fullRev.includes(q);
		});
		modelRows = analytics?.topModels.items.filter((u) => {
			const q = search
				.trim()
				.toLowerCase()
				.normalize('NFD')
				.replace(/\p{Diacritic}/gu, '');
			if (!q) return true;
			const model = u.model
				.toLowerCase()
				.normalize('NFD')
				.replace(/\p{Diacritic}/gu, '');
			return model.includes(q);
		});
		assistantRows = analytics?.topAssistants.top_assistants.filter((u) => {
			const q = search
				.trim()
				.toLowerCase()
				.normalize('NFD')
				.replace(/\p{Diacritic}/gu, '');
			if (!q) return true;
			const assistant = u.assistant
				.toLowerCase()
				.normalize('NFD')
				.replace(/\p{Diacritic}/gu, '');
			return assistant.includes(q);
		});
	}
	function getAssistantIcon(assistantName?: string) {
		if (!assistantName) return null;
		const a = assistantRows.find((r) => r.assistant === assistantName);
		return a?.profile_image_url ?? null;
	}
</script>

<div class="pb-20">
	{#if !analyticsLoading}
		<div
			class="flex w-full justify-between items-center py-2.5 border-b border-lightGray-400 dark:border-customGray-700 my-1.5"
		>
			<div class="flex flex-col w-full">
				<div class="text-lg font-semibold">{$i18n.t('Analytics')}</div>
				<div class="text-xs text-lightGray-100">
					{$i18n.t('Understand AI adoption in your organization')}
				</div>
			</div>
		</div>
		<div class="pb-1">
			<div class="flex w-full justify-between items-center">
				<div class="text-2xs text-lightGray-100 dark:text-white font-semibold">
					{$i18n.t('Company overview')}
				</div>
			</div>
		</div>
		<div class="grid grid-cols-2 md:grid-cols-4 gap-[8px]">
			<div
				class="rounded-md bg-lightGray-300 dark:bg-customGray-900 ring-1 ring-lightGray-400 dark:ring-transparent p-[10px] flex flex-col justify-between items-start"
			>
				<div class="flex flex-row w-full justify-between">
					<UsersIcon className="size-5 text-white p-1 rounded-md bg-blue-700" />
					<Tooltip content={$i18n.t('The total number of users.')}>
						<div class="cursor-pointer w-[12px] h-[12px] rounded-full text-lightGray-100">
							<Info className="size-3" />
						</div>
					</Tooltip>
				</div>

				<div class="pt-[6px]">
					<div class="text-xl font-semibold text-lightGray-100 dark:text-white mb-0">
						{analytics?.totalUsers?.total_users}
					</div>
					<div class="text-xs text-center">
						{$i18n.t('Total users')}
					</div>
				</div>
			</div>
			<div
				class="rounded-md bg-lightGray-300 dark:bg-customGray-900 ring-1 ring-lightGray-400 dark:ring-transparent p-[10px] flex flex-col justify-between items-start"
			>
				<div class="flex flex-row w-full justify-between">
					<CheckCircle className="size-5 bg-blue-700 p-1 rounded-md text-white" />

					<Tooltip
						content={$i18n.t(
							'Measures the quality of user activity by evaluating daily interaction (logarithmically scaled) over 30 days and rewarding consistency.'
						)}
					>
						<div class="cursor-pointer w-[12px] h-[12px] rounded-full text-lightGray-100">
							<Info className="size-3" />
						</div>
					</Tooltip>
				</div>

				<div class="pt-[6px]">
					<div class="text-xl font-semibold text-lightGray-100 dark:text-white mb-0">
						{analytics?.engagementRate?.engagement_score?.toFixed(2)}%
					</div>
					<div class="text-xs text-center">
						{$i18n.t('Engagement')}
					</div>
				</div>
			</div>
			<div
				class="rounded-md bg-lightGray-300 dark:bg-customGray-900 ring-1 ring-lightGray-400 dark:ring-transparent p-[10px] flex flex-col justify-between items-start"
			>
				<div class="flex flex-row w-full justify-between">
					<LightningIcon className="bg-blue-700 size-5 rounded-md text-white p-1" />
					<Tooltip content={$i18n.t('Users who sent 400 or more messages in the last month.')}>
						<div class="cursor-pointer w-[12px] h-[12px] rounded-full text-lightGray-100">
							<Info className="size-3" />
						</div>
					</Tooltip>
				</div>

				<div class="pt-[6px]">
					<div class="text-xl font-semibold text-lightGray-100 dark:text-white mb-0">
						{analytics?.powerUsers?.power_users_count}
					</div>
					<div class="text-xs text-center">
						{$i18n.t('Power users')}
					</div>
				</div>
			</div>
			<div
				class="rounded-md bg-lightGray-300 dark:bg-customGray-900 ring-1 ring-lightGray-400 dark:ring-transparent p-[10px] flex flex-col justify-between items-start"
			>
				<div class="flex flex-row w-full justify-between">
					<AssistantsIcon className="bg-blue-700 size-5 rounded-md text-white p-1" />
					<Tooltip content={$i18n.t('The number of assistants created within the company.')}>
						<!-- zB offset={[0, -48]} mitgeben -->
						<div class="cursor-pointer w-[12px] h-[12px] rounded-full text-lightGray-100">
							<Info className="size-3" />
						</div>
					</Tooltip>
				</div>

				<div class="pt-[6px]">
					<div class="text-xl font-semibold text-lightGray-100 dark:text-white mb-0">
						{analytics?.totalAssistants?.total_assistants}
					</div>
					<div class="text-xs text-center">
						{$i18n.t('Assistants')}
					</div>
				</div>
			</div>
		</div>

		<Tabs.Root bind:value={activeTab} class="rounded-card border-muted w-full shadow-card mt-4 ">
			<Tabs.List
				class="bg-lightGray-400/60 dark:bg-customGray-900 rounded-md flex flex-row p-[2px] text-xs w-fit font-medium"
			>
				<Tabs.Trigger
					value="users"
					class=" py-[10px] px-3 data-[state=active]:text-lightGray-100 dark:data-[state=active]:text-white  text-lightGray-100/75 dark:text-white/75 py-1 rounded-md flex flex-row items-center data-[state=active]:bg-lightGray-400 dark:data-[state=active]:bg-gray-900 "
					><UsersIcon className="size-3 mr-2" />
					{$i18n.t('Users')}</Tabs.Trigger
				>
				<Tabs.Trigger
					value="models"
					class=" py-[10px] px-3 data-[state=active]:text-lightGray-100 dark:data-[state=active]:text-white  text-lightGray-100/75 dark:text-white/75 rounded-md flex flex-row items-center data-[state=active]:bg-lightGray-400 dark:data-[state=active]:bg-gray-900 "
					><Cube className="size-3 mr-2" />
					{$i18n.t('Models')}</Tabs.Trigger
				>
				<Tabs.Trigger
					value="assistants"
					class=" py-[10px] px-3 data-[state=active]:text-lightGray-100 dark:data-[state=active]:text-white  text-lightGray-100/75 dark:text-white/75 rounded-md flex flex-row items-center data-[state=active]:bg-lightGray-400 dark:data-[state=active]:bg-gray-900 "
					><AssistantsIcon className="size-3 mr-2" />
					{$i18n.t('Assistants')}</Tabs.Trigger
				>
			</Tabs.List>
			<div
				class="w-full mt-4 ring-1 ring-lightGray-400 dark:ring-transparent rounded-md gap-3 p-2 bg-lightGray-300 dark:bg-customGray-900 text-2xs flex flex-row items-center"
			>
				<Select.Root
					onSelectedChange={handleTimeSpanChange}
					selected={selectedTimeSpan}
					items={localizedOptions}
					portal={null}
				>
					<Select.Trigger
						class="flex items-center gap-2 rounded-md bg-white dark:bg-gray-900  px-2 py-[6px] ring-1 ring-lightGray-400 dark:ring-transparent "
						aria-label="Choose range..."
					>
						<CalendarIcon className="size-4 text-lightGray-100/60 dark:text-white/60" />
						<Select.Value />
						<ChevronDown
							className="ml-auto size-3 text-lightGray-100/60 dark:text-white/60"
							strokeWidth="2.5"
						/>
					</Select.Trigger>

					<Select.Content
						class="mt-1 rounded-md bg-white dark:bg-customGray-900 ring-1 ring-lightGray-400 dark:ring-transparent shadow-sm z-50"
					>
						{#each localizedOptions as opt (opt.value)}
							<Select.Item
								value={opt.value}
								label={opt.label}
								class="flex cursor-pointer items-center gap-2 p-2 text-xs outline-none data-[highlighted]:bg-lightGray-400 dark:bg-gray-900 "
							>
								{opt.label}
								<Select.ItemIndicator class="w-4">
									<CheckmarkIcon className="size-4" />
								</Select.ItemIndicator>
							</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>

				<div
					class="flex-1 relative bg-white dark:bg-gray-900 ring-1 ring-lightGray-400 dark:ring-transparent rounded-md flex flex-row items-center"
				>
					<div class="pl-2 py-[6px] absolute left-0">
						<Search className="size-4 text-lightGray-100/60 dark:text-white/60 " />
					</div>

					<input
						type="text"
						class=" px-2 pl-8 py-[6px] flex-1 placeholder-lightGray-100/75 dark:placeholder-white/75 rounded-md dark:bg-transparent"
						placeholder={$i18n.t(searchBarPlaceholder)}
						on:input={(e) => searchFor(e.target.value)}
					/>
				</div>
			</div>
			<Tabs.Content value="users" class="select-none pt-3">
				<table
					class="w-full ring-1 ring-lightGray-400 dark:ring-transparent rounded-md bg-lightGray-300 dark:bg-customGray-900 text-xs table-auto"
				>
					<thead class="text-lightGray-100/60 dark:text-white/60">
						<tr>
							<th class="w-4"></th>

							<th
								class="p-2 justify-left flex font-medium relative hover:opacity-80 cursor-pointer select-none {sortKey ===
								'user'
									? 'text-lightGray-100/75 dark:text-white/75 hover:opacity-100'
									: ''}"
								on:click={() => toggleSort('user')}
							>	
								<div class="flex flex-row items-center gap-1 w-fit">
									{$i18n.t('User')}
									<div class="">
										{#if sortKey === 'user'}
											{#if sortDir === 'asc'}
												<ChevronDown className="size-3 mt-[2px]" strokeWidth="2.5" />
											{:else}
												<ChevronUp className="size-3" strokeWidth="2.5" />
											{/if}
										{/if}
									</div>
								</div>
								

								
							</th>
							{#if $subscription.plan != 'free' && $subscription.plan != 'premium'}
								<th
									class="p-2 text-right font-medium relative hover:opacity-80 cursor-pointer select-none {sortKey ===
									'credits'
										? 'text-lightGray-100/75 dark:text-white/75 hover:opacity-100'
										: ''}"
									on:click={() => toggleSort('credits')}
								>
									{$i18n.t('Credits used')}

									<div class="absolute -right-2 top-[10px]">
										{#if sortKey === 'credits'}
											{#if sortDir === 'asc'}
												<ChevronDown className="size-3 mt-[1px]" strokeWidth="2.5" />
											{:else}
												<ChevronUp className="size-3" strokeWidth="2.5" />
											{/if}
										{/if}
									</div>
								</th>
							{/if}

							<th
								class="p-2 text-right font-medium relative hover:opacity-80 cursor-pointer pr-5 select-none {sortKey ===
								'messages'
									? 'text-lightGray-100/75 dark:text-white/75 hover:opacity-100'
									: ''}"
								on:click={() => toggleSort('messages')}
							>
								{$i18n.t('Messages sent')}

								<div class="absolute right-1 top-[10px]">
									{#if sortKey === 'messages'}
										{#if sortDir === 'asc'}
												<ChevronDown className="size-3 mt-[1px]" strokeWidth="2.5" />
											{:else}
												<ChevronUp className="size-3" strokeWidth="2.5" />
											{/if}
									{/if}
								</div>
							</th>
						</tr>
					</thead>
					<tbody>
						{#each pagedRows as row (row.user_id)}
							{@const key = row.user_id}
							<tr
								class="hover:bg-lightGray-200 dark:hover:bg-customGray-800 cursor-pointer"
								on:click={() => toggleRow(key)}
								aria-expanded={expanded.has(key)}
							>
								<td class="w-8 border-t border-1 border-gray-200/60 dark:border-customGray-700">
									<div class="mx-2 text-lightGray-100/60 dark:text-white/60">
										{#if expanded.has(key)}
											<ChevronDown className="size-3" strokeWidth="2.5" />
										{:else}
											<ChevronRight className="size-3" strokeWidth="2.5" />
										{/if}
									</div>
								</td>
								<td class="border-t border-1 border-gray-200/60 dark:border-customGray-700 p-2">
									<div class="flex flex-row items-center">
										<img
											class="rounded-full size-6 object-cover mr-2.5"
											src={row.profile_image_url?.startsWith(WEBUI_BASE_URL) ||
											row.profile_image_url?.startsWith('https://www.gravatar.com/avatar/') ||
											row.profile_image_url?.startsWith('data:')
												? row.profile_image_url
												: `/user.png`}
											alt="user"
										/>
										<div>
											<div class="text-xs font-semibold">
												{row.first_name}
												{row.last_name}
											</div>
											<div class="text-2xs text-lightGray-100/60 dark:text-white/60">
												{row.email}
											</div>
										</div>
									</div>
								</td>
								{#if $subscription.plan != 'free' && $subscription.plan != 'premium'}
									<td
										class="border-t border-1 border-gray-200/60 dark:border-customGray-700 p-2 text-right min-w-[100px] font-semibold"
										>€{row.total_credits_used.toFixed(2)}</td
									>
								{/if}
								<td
									class="border-t border-1 border-gray-200/60 dark:border-customGray-700 p-2 pr-5 text-right min-w-[150px] font-semibold"
									>{row.message_count}</td
								>
							</tr>
							{#if expanded.has(key)}
								<tr class="bg-lightGray-300 dark:bg-customGray-900">
									<td
										colspan={$subscription.plan != 'free' && $subscription.plan != 'premium'
											? 4
											: 3}
										class="pr-2"
									>
										<div
											class="rounded-md  overflow-hidden ml-auto w-[90%]"
										>
											<div
												class="grid grid-cols-1 md:grid-cols-3 text-xs dark:bg-transparent"
											>
												<div
													class="p-3 dark:bg-gray-950/20 flex flex-col  border-lightGray-400 dark:border-customGray-700"
												>
													<div class="text-lightGray-100/75 font-medium dark:text-white/60 mb-1">
														{$i18n.t('Engagement Score')}
													</div>
													<div class="text-sm font-semibold flex-grow flex items-center">{row.engagement_score ?? '0'} %</div>
												</div>

												<div
													class="p-3  border-lightGray-400 dark:border-customGray-700"
												>
													<div class="text-lightGray-100/75 font-medium dark:text-white/60 mb-2">
														{$i18n.t('Top assistant')}
													</div>
													<div class="flex items-center gap-2">
														{#if row.top_assistant && getAssistantIcon(row.top_assistant).length > 5}
															<img
																class="rounded-md size-6 object-cover shrink-0"
																src={getAssistantIcon(row.top_assistant)}
																alt=""
															/>
														{:else if row.top_assistant}
															<div
																class="text-[1.0rem] bg-blue-400/20 flex justify-center items-center size-6 rounded-md shrink-0"
															>
																{getAssistantIcon(row.top_assistant)}
															</div>
														{/if}
														<div class="font-semibold">{row.top_assistant ?? '-'}</div>
													</div>
												</div>

												<div class="p-3 flex flex-col">
													<div class="text-lightGray-100/75 font-medium dark:text-white/60 mb-2">{$i18n.t('Top model')}</div>
													<div class="flex items-center gap-2 flex-grow">
														{#if row.top_model}
															<img
																class="rounded-full size-6 object-cover"
																src={getModelIcon(row.top_model)}
																alt=""
															/>
														{/if}
														<div class="font-semibold">{row.top_model ?? '-'}</div>
													</div>
												</div>
											</div>
										</div>
									</td>
								</tr>
							{/if}
						{/each}
					</tbody>
					<tfoot>
						<tr class="border-t border-1 border-gray-200/60 dark:border-customGray-700">
							<td colspan={$subscription.plan != 'free' && $subscription.plan != 'premium'
											? 4
											: 3} class="p-2 pl-5">
							
								<div class="flex flex-row justify-between items-center">
									<div class="flex flex-row items-center">
										<div class="text-lightGray-100/75 dark:text-white/75 pr-2 text-2xs">
											{$i18n.t('Rows per page')}
										</div>
										<select
											bind:value={rowsPerPage}
											on:change={() => (page = 1)}
											class="w-12 bg-white dark:bg-gray-900 ring-1 rounded-md ring-lightGray-400 dark:ring-transparent py-1 px-2"
										>
											<option value={5}>5</option>
											<option value={10}>10</option>
											<option value={15}>15</option>
											<option value={20}>20</option>
										</select>
									</div>

									<Pagination.Root
										count={totalCount}
										perPage={rowsPerPage}
										bind:page
										siblingCount={1}
										let:pages
										let:range
									>
										<div
											class="flex flex-row items-center gap-2 text-lightGray-100/75 dark:text-white/75"
										>
											<Pagination.PrevButton
												class="inline-flex size-6 items-center justify-center rounded-md ring-1 ring-lightGray-400 dark:ring-transparent  bg-white dark:bg-gray-900 text-xs disabled:opacity-50"
											>
												<ChevronLeft className="size-3" strokeWidth="2.5" />
											</Pagination.PrevButton>

											<div class="flex items-center gap-2">
												{#each pages as p (p.key)}
													{#if p.type === 'ellipsis'}
														<span class="px-2 text-lightGray-100/75 dark:text-white/75 select-none"
															>…</span
														>
													{:else}
														<Pagination.Page
															page={p}
															class="page inline-flex text-lightGray-100/75 dark:text-white/75 size-6 font-semibold items-center justify-center rounded-md text-xs
													data-[selected]:bg-blue-500 data-selected:text-white"
														>
															<style>
																.page[data-selected] {
																	background: #1d4ed8; /* blue-700 */
																	color: white;
																}
															</style>
															{p.value}
														</Pagination.Page>
													{/if}
												{/each}
											</div>

											<Pagination.NextButton
												class="inline-flex size-6 items-center justify-center rounded-md ring-1 ring-lightGray-400 dark:ring-transparent  bg-white dark:bg-gray-900 disabled:opacity-50"
											>
												<ChevronRight className="size-3 " strokeWidth="2.5" />
											</Pagination.NextButton>
										</div>
									</Pagination.Root>
								</div>
							</td>
						</tr>
					</tfoot>
				</table>
			</Tabs.Content>
			<Tabs.Content value="models" class="select-none pt-3">
				<table
					class="w-full ring-1 ring-lightGray-400 dark:ring-transparent rounded-md bg-lightGray-300 dark:bg-customGray-900 text-xs table-auto"
				>
					<thead class="text-lightGray-100/60 dark:text-white/60">
						<tr>
							<th class="pl-5 p-2 text-left font-medium select-none"> {$i18n.t('Model')} </th>
							{#if $subscription.plan != 'free' && $subscription.plan != 'premium'}
								<th class="p-2 text-right font-medium relative select-none"> {$i18n.t('Credits used')} </th>
							{/if}
							<th class="p-2 text-right font-medium relative pr-5 select-none"> {$i18n.t('Messages sent')} </th>
						</tr>
					</thead>
					<tbody>
						{#each pagedModelRows as row}
							<tr class="hover:bg-lightGray-200 dark:hover:bg-customGray-800">
								<td
									class="pl-5 border-t border-1 border-gray-200/60 dark:border-customGray-700 p-2"
								>
									<div class="flex flex-row items-center">
										<img
											class="rounded-full size-6 object-cover mr-2.5"
											src={getModelIcon(row.model)}
											alt="model"
										/>
										<div class="text-xs font-semibold">
											{row.model}
										</div>
									</div>
								</td>
								{#if $subscription.plan != 'free' && $subscription.plan != 'premium'}
									<td
										class="border-t border-1 border-gray-200/60 dark:border-customGray-700 p-2 text-right min-w-[100px] font-semibold"
										>€{row.credits_used.toFixed(2)}</td
									>
								{/if}
								<td
									class="border-t border-1 border-gray-200/60 dark:border-customGray-700 p-2 pr-5 text-right min-w-[150px] font-semibold"
									>{row.message_count}</td
								>
							</tr>
						{/each}
					</tbody>
					<tfoot>
						<tr class="border-t border-1 border-gray-200/60 dark:border-customGray-700">
							<td colspan={$subscription.plan != 'free' && $subscription.plan != 'premium'
											? 3
											: 2} class="p-2 pl-5">
								<div class="flex flex-row justify-between items-center">
									<div class="flex flex-row items-center">
										<div class="text-lightGray-100/75 dark:text-white/75 pr-2 text-2xs">
											{$i18n.t('Rows per page')}
										</div>
										<select
											bind:value={rowsPerPage}
											class="w-12 bg-white dark:bg-gray-900 ring-1 rounded-md ring-lightGray-400 dark:ring-transparent py-1 px-2"
										>
											<option value={5}>5</option> <option value={10}>10</option>
											<option value={15}>15</option> <option value={20}>20</option>
										</select>
									</div>
									<Pagination.Root
										count={totalCountModels}
										perPage={rowsPerPage}
										bind:page
										siblingCount={1}
										let:pages
										let:range
									>
										<div
											class="flex flex-row items-center gap-2 text-lightGray-100/75 dark:text-white/75"
										>
											<Pagination.PrevButton
												class="inline-flex size-6 items-center justify-center rounded-md ring-1 ring-lightGray-400 dark:ring-transparent  bg-white dark:bg-gray-900 text-xs disabled:opacity-50"
											>
												<ChevronLeft className="size-3" strokeWidth="2.5" />
											</Pagination.PrevButton>

											<div class="flex items-center gap-2">
												{#each pages as p (p.key)}
													{#if p.type === 'ellipsis'}
														<span class="px-2 text-lightGray-100/75 dark:text-white/75 select-none"
															>…</span
														>
													{:else}
														<Pagination.Page
															page={p}
															class="page inline-flex text-lightGray-100/75 dark:text-white/75 size-6 font-semibold items-center justify-center rounded-md text-xs
													data-[selected]:bg-blue-500 data-selected:text-white"
														>
															<style>
																.page[data-selected] {
																	background: #1d4ed8; /* blue-700 */
																	color: white;
																}
															</style>
															{p.value}
														</Pagination.Page>
													{/if}
												{/each}
											</div>

											<Pagination.NextButton
												class="inline-flex size-6 items-center justify-center rounded-md ring-1 ring-lightGray-400 dark:ring-transparent  bg-white dark:bg-gray-900 disabled:opacity-50"
											>
												<ChevronRight className="size-3 " strokeWidth="2.5" />
											</Pagination.NextButton>
										</div>
									</Pagination.Root>
								</div>
							</td>
						</tr>
					</tfoot>
				</table>
			</Tabs.Content>
			<Tabs.Content value="assistants" class="select-none pt-3">
				<table
					class="w-full ring-1 ring-lightGray-400 dark:ring-transparent rounded-md bg-lightGray-300 dark:bg-customGray-900 text-xs table-auto"
				>
					<thead class="text-lightGray-100/60 dark:text-white/60">
						<tr>
							<th class="p-2 text-left font-medium select-none pl-5">{$i18n.t('Rank')}</th>

							<th class="p-2 text-left font-medium select-none"> {$i18n.t('Assistant')} </th>

							<th class="p-2 text-right font-medium select-none pr-5"> {$i18n.t('Messages sent')} </th>
						</tr>
					</thead>
					<tbody>
						{#each pagedAssistantRows as row, index}
							<tr class="hover:bg-lightGray-200 dark:hover:bg-customGray-800">
								<td
									class="border-t border-1 p-2 border-gray-200/60 dark:border-customGray-700 pl-5"
								>
									<!-- (row index) -->
									{#if index + 1 == 1}
										<div
											class="rounded-full bg-blue-700 size-6 font-semibold flex items-center justify-center text-white"
										>
											1
										</div>
									{:else}
										<div
											class="rounded-full bg-lightGray-300 dark:bg-customGray-900 size-6 font-semibold flex items-center justify-center text-lightGray-100/60 dark:text-white/60"
										>
											{index + 1}
										</div>
									{/if}
								</td>
								<td class="border-t border-1 border-gray-200/60 dark:border-customGray-700 p-2">
									<div class="flex flex-row items-center">
										{#if !row.profile_image_url || row.profile_image_url.length > 5}
											<img
												src={row.profile_image_url}
												alt="modelfile profile"
												class="rounded-md size-6 object-cover mr-2.5"
											/>
										{:else}
											<div
												class="text-[1.0rem] bg-blue-400/20 flex justify-center items-center size-6 rounded-md object-cover mr-2.5"
											>
												{row.profile_image_url}
											</div>
										{/if}
										<div class="text-xs font-medium">
											{row.assistant}
										</div>
									</div>
								</td>
								<td
									class="border-t border-1 border-gray-200/60 dark:border-customGray-700 p-2 pr-5 text-right min-w-[150px] font-semibold"
									>{row.message_count}</td
								>
							</tr>
						{/each}
					</tbody>
					<tfoot>
						<tr class="border-t border-1 border-gray-200/60 dark:border-customGray-700">
							<td colspan="3" class="p-2 pl-5">
								<div class="flex flex-row justify-between items-center">
									<div class="flex flex-row items-center">
										<div class="text-lightGray-100/75 dark:text-white/75 pr-2 text-2xs">
											{$i18n.t('Rows per page')}
										</div>
										<select
											class="w-12 bg-white dark:bg-gray-900 ring-1 rounded-md ring-lightGray-400 dark:ring-transparent py-1 px-2"
										>
											<option selected>5</option> <option value="10">10</option>
											<option value="15">15</option> <option value="20">20</option>
										</select>
									</div>
									<Pagination.Root
										count={totalCountAssistants}
										perPage={rowsPerPage}
										bind:page
										siblingCount={1}
										let:pages
										let:range
									>
										<div
											class="flex flex-row items-center gap-2 text-lightGray-100/75 dark:text-white/75"
										>
											<Pagination.PrevButton
												class="inline-flex size-6 items-center justify-center rounded-md ring-1 ring-lightGray-400 dark:ring-transparent  bg-white dark:bg-gray-900 text-xs disabled:opacity-50"
											>
												<ChevronLeft className="size-3" strokeWidth="2.5" />
											</Pagination.PrevButton>

											{#if totalCountAssistants > 0}
												<div class="flex items-center gap-2">
													{#each pages as p (p.key)}
														{#if p.type === 'ellipsis'}
															<span
																class="px-2 text-lightGray-100/75 dark:text-white/75 select-none"
																>…</span
															>
														{:else}
															<Pagination.Page
																page={p}
																class="page inline-flex text-lightGray-100/75 dark:text-white/75 size-6 font-semibold items-center justify-center rounded-md text-xs
													data-[selected]:bg-blue-500 data-selected:text-white"
															>
																<style>
																	.page[data-selected] {
																		background: #1d4ed8; /* blue-700 */
																		color: white;
																	}
																</style>
																{p.value}
															</Pagination.Page>
														{/if}
													{/each}
												</div>
											{/if}

											<Pagination.NextButton
												class="inline-flex size-6 items-center justify-center rounded-md ring-1 ring-lightGray-400 dark:ring-transparent  bg-white dark:bg-gray-900 disabled:opacity-50"
											>
												<ChevronRight className="size-3 " strokeWidth="2.5" />
											</Pagination.NextButton>
										</div>
									</Pagination.Root>
								</div>
							</td>
						</tr>
					</tfoot>
				</table>
			</Tabs.Content>
		</Tabs.Root>

		<div class="border-t-[1px] border-lightGray-400 dark:border-customGray-700 mt-6 pt-1">
			<div class="flex w-full justify-between items-center">
				<div class="text-2xs text-lightGray-100 dark:text-white font-semibold">
					{$i18n.t('Usage history')}
				</div>
			</div>
		</div>
		<Tabs.Root value="monthly" class="rounded-card border-muted w-full shadow-card mt-1 ">
			<Tabs.List
				class="bg-lightGray-400/60 dark:bg-customGray-900 rounded-md flex flex-row p-[2px] text-xs w-fit font-medium"
			>
				<Tabs.Trigger
					value="monthly"
					class=" py-[10px] px-3 data-[state=active]:text-lightGray-100 dark:data-[state=active]:text-white text-lightGray-100/75 dark:text-white/75 py-1 rounded-md items-center data-[state=active]:bg-lightGray-400 dark:data-[state=active]:bg-gray-900 "
				>
					{$i18n.t('Monthly')}</Tabs.Trigger
				>
				<Tabs.Trigger
					value="yearly"
					class=" py-[10px] px-3 data-[state=active]:text-lightGray-100 dark:data-[state=active]:text-white text-lightGray-100/75 dark:text-white/75 rounded-md items-center data-[state=active]:bg-lightGray-400 dark:data-[state=active]:bg-gray-900 "
				>
					{$i18n.t('Yearly')}</Tabs.Trigger
				>
			</Tabs.List>
			<Tabs.Content value="monthly" class="select-none text-xs pt-3">
				<div
					class=" relative w-full bg-lightGray-300 dark:bg-customGray-900 flex flex-col justify-start gap-1 p-2 ring-1 ring-lightGray-400 dark:ring-transparent rounded-md"
				>
					{$i18n.t('This month')} {#if analytics?.totalMessages?.monthly_messages?.length > 1}
						vs. {$i18n.t('last month')}{/if}
					<div class="text-lg font-semibold">
						{analytics?.totalMessages?.monthly_messages?.at(-1)?.message_count || 0}
					</div>
					<div class="text-lightGray-100/60 dark:text-white/60">{$i18n.t('Messages sent')}</div>
					<div class="absolute top-2 right-3 text-blue-700 gap-1 flex flex-row items-center">
						{#if analytics?.totalMessages?.monthly_percentage_changes?.at(-1)?.percentage_change < 0}
							<TrendArrowIcon flipped="true" className="text-red-500 size-4" />
							<div class="text-red-500">
								{analytics?.totalMessages?.monthly_percentage_changes?.at(-1)?.percentage_change}%
							</div>
						{:else if analytics?.totalMessages?.monthly_messages?.length <= 1}{:else}
							<TrendArrowIcon className="mt-[2px] text-blue-700 size-4" />
							<div>
								+{analytics?.totalMessages?.monthly_percentage_changes?.at(-1)?.percentage_change}%
							</div>
						{/if}
					</div>
				</div>
				<div
					class="mt-5 bg-lightGray-300 dark:bg-customGray-900 ring-1 ring-lightGray-400 dark:ring-transparent rounded-md"
				>
					<div>
						<div class="text-2xs font-semibold pt-2 px-3">Messages over time</div>
						<div class=" rounded-md px-3">
							<Chart type="bar" data={chartMessagesData} options={chartOptions} />
						</div>
					</div>
				</div>
			</Tabs.Content>
			<Tabs.Content value="yearly" class="select-none text-xs pt-3">
				<div
					class=" relative w-full bg-lightGray-300 dark:bg-customGray-900 flex flex-col justify-start gap-1 p-2 ring-1 ring-lightGray-400 dark:ring-transparent rounded-md"
				>
					{$i18n.t('This year')} {#if analytics?.totalMessages?.yearly_messages?.length > 1}
						vs. {$i18n.t('last year')}{/if}
					<div class="text-lg font-semibold">
						{analytics?.totalMessages?.yearly_messages?.at(-1)?.message_count || 0}
					</div>
					<div class="text-lightGray-100/60 dark:text-white/60">{$i18n.t('Messages sent')}</div>
					<div class="absolute top-2 right-3 text-blue-700 gap-1 flex flex-row items-center">
						{#if analytics?.totalMessages?.yearly_percentage_changes?.at(-1)?.percentage_change > 0}
							<TrendArrowIcon flipped="true" className="text-red-500 size-4" />
							<div class="text-red-500">
								{analytics?.totalMessages?.yearly_percentage_changes?.at(-1)?.percentage_change}%
							</div>
						{:else if analytics?.totalMessages?.yearly_messages?.length <= 1}{:else}
							<TrendArrowIcon className="mt-[2px] text-blue-700 size-4" />
							<div>
								+{analytics?.totalMessages?.yearly_percentage_changes?.at(-1)?.percentage_change}%
							</div>
						{/if}
					</div>
				</div>
				<div
					class="mt-5 bg-lightGray-300 dark:bg-customGray-900 ring-1 ring-lightGray-400 dark:ring-transparent rounded-md"
				>
					<div>
						<div class="text-2xs font-semibold pt-2 px-3">Messages over time</div>
						<div class=" rounded-md px-3">
							<Chart
								type="bar"
								data={chartMessagesDataYearly}
								options={{
									...chartOptions,
									barPercentage: Math.min(
										1.0,
										0.1 + 0.18 * (analytics?.totalMessages?.yearly_messages?.length ?? 0)
									)
								}}
							/>
						</div>
					</div>
				</div>
			</Tabs.Content>
		</Tabs.Root>
	{:else}
		<div class="h-[20rem] w-full flex justify-center items-center">
			<Spinner />
		</div>
	{/if}
</div>
