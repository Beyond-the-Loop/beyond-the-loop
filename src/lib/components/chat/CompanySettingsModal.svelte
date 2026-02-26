<script lang="ts">
	import { getContext, tick } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { models, settings, mobile } from '$lib/stores';
	import { subscription } from '$lib/stores';

	import { updateUserSettings } from '$lib/apis/users';
	import { getModels as _getModels } from '$lib/apis';
	import { goto } from '$app/navigation';

	import Modal from '../common/Modal.svelte';
	import ProfileIcon from '../icons/ProfileIcon.svelte';
    import GeneralSettings from '$lib/components/chat/Settings/CompanySettings/General.svelte';
	import GroupIcon from '../icons/GroupIcon.svelte';
	import UserManagement from './Settings/CompanySettings/UserManagement.svelte';
	import ModelControlIcon from '../icons/ModelControlIcon.svelte';
	import ModelControl from './Settings/CompanySettings/ModelControl.svelte';
	import { getUsers } from '$lib/apis/users';
	import AnalyticsIcon from '../icons/AnalyticsIcon.svelte';
	import Analytics from './Settings/CompanySettings/Analytics.svelte';
	import BillingIcon from '../icons/BillingIcon.svelte';
	import Billing from './Settings/CompanySettings/Billing.svelte';
	import { page } from '$app/stores';
	import {
		getCurrentSubscription
	} from '$lib/apis/payments';
	import BackIcon from '../icons/BackIcon.svelte';
	import DomainSettings from './Settings/CompanySettings/DomainSettings.svelte';
	import DomainSettingsIcon from '../icons/DomainSettingsIcon.svelte';

	
	const i18n = getContext('i18n');

	export let show = false;
	let selectedTab = 'general-settings';

	interface SettingsTab {
		id: string;
		title: string;
		keywords: string[];
	}

	function updateTabParam(tab) {
		const url = new URL(window.location.href);
		url.searchParams.set('tab', tab);
		url.searchParams.set('modal', 'company-settings'); 
		window.history.replaceState({}, '', url); 
	}

	const settingsTabs: SettingsTab[] = [
		{
			id: 'general-settings',
			title: 'General settings',
			keywords: [	
			]
		},
		{
			id: 'domain-settings',
			title: 'Domain settings',
			keywords: [	
			]
		},
		{
			id: 'user-management',
			title: 'User management',
			keywords: [	
			]
		},
		{
			id: 'model-control',
			title: 'Model control',
			keywords: [	
			]
		},
		{
			id: 'analytics',
			title: 'Analytics',
			keywords: [

			]
		},
		{
			id: 'billing',
			title: 'Billing',
			keywords: [
		
			]
		}
		];

	let searchDebounceTimeout;

	const searchSettings = (query: string): string[] => {
		const lowerCaseQuery = query.toLowerCase().trim();
		return settingsTabs
			.filter(
				(tab) =>
					tab.title.toLowerCase().includes(lowerCaseQuery) ||
					tab.keywords.some((keyword) => keyword.includes(lowerCaseQuery))
			)
			.map((tab) => tab.id);
	};

	const saveSettings = async (updated) => {
		await settings.set({ ...$settings, ...updated });
		await models.set(await getModels());
		await updateUserSettings(localStorage.token, { ui: $settings });
	};

	const getModels = async () => {
		return await _getModels(localStorage.token);
	};


	// Function to handle sideways scrolling
	const scrollHandler = (event) => {
		const settingsTabsContainer = document.getElementById('settings-tabs-container');
		if (settingsTabsContainer) {
			event.preventDefault(); // Prevent default vertical scrolling
			settingsTabsContainer.scrollLeft += event.deltaY; // Scroll sideways
		}
	};

	const addScrollListener = async () => {
		await tick();
		const settingsTabsContainer = document.getElementById('settings-tabs-container');
		if (settingsTabsContainer) {
			settingsTabsContainer.addEventListener('wheel', scrollHandler);
		}
	};

	const removeScrollListener = async () => {
		await tick();
		const settingsTabsContainer = document.getElementById('settings-tabs-container');
		if (settingsTabsContainer) {
			settingsTabsContainer.removeEventListener('wheel', scrollHandler);
		}
	};

	$: if (show) {
		addScrollListener();
	} else {
		removeScrollListener();
	}
	let users = [];
	const getUsersHandler = async () => {
		users = await getUsers(localStorage.token);
	};

	let autoRecharge = false;
	let subscriptionLoading = false;
	async function getSubscription() {
		subscriptionLoading = true;
		const sub = await getCurrentSubscription(localStorage.token).catch(error => {
			console.log(error);
			subscriptionLoading = false;
		});
		if(sub){
			subscription.set(sub);
			autoRecharge = sub?.auto_recharge ? sub?.auto_recharge : false;
			subscriptionLoading = false;
		}
	}


	$: if(show){
		getUsersHandler();
		getSubscription();
		const tabParam = $page.url.searchParams.get('tab');
		const resetTabs = $page.url.searchParams.get('resetTabs');
		if(resetTabs) {
			selectedTab = null;
		} else {
			selectedTab = tabParam || 'general-settings';
		}	
	}
</script>

<Modal size="md-plus" bind:show blockBackdropClick={true} className="dark:bg-customGray-800 rounded-2xl" containerClassName="bg-lightGray-250/50 dark:bg-[#1D1A1A]/50 backdrop-blur-[7.44px]">
	<div class="text-lightGray-100 dark:text-customGray-100 bg-lightGray-550 dark:bg-customGray-800 rounded-xl md:h-auto">
		<div class="px-4 md:px-7">
			<div class=" flex justify-between dark:text-white pt-5 pb-4 border-b dark:border-customGray-700">
				{#if selectedTab && $mobile}
					<button class="capitalize flex items-center" on:click={() => selectedTab = null}>
						<BackIcon className="mr-1 size-4 shrink-0"/>
						<div class="shrink-0">{$i18n.t(settingsTabs?.find(item => item?.id === selectedTab).title)}</div>
					</button>
				{:else}
					<div class="self-center">{$i18n.t('Company settings')}</div>
				{/if}
				<button
					class="self-center"
					on:click={() => {
						const url = new URL(window.location.href);
						url.search = ''; 
						goto(url.pathname, { replaceState: true });
						show = false;	
					}}
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
		</div>

		<div class="flex flex-col md:flex-row w-full pl-4 md:pl-0 pr-4 md:pr-7 md:space-x-4">
			{#if selectedTab === null || !$mobile}
				<div
					id="settings-tabs-container"
					class="rounded-bl-lg md:pl-4 md:pt-5 pr-2 tabs flex flex-col md:dark:bg-customGray-900 md:gap-1 w-full md:w-[252px] dark:text-gray-200 text-sm font-medium text-left mb-1 md:mb-0"
				>
					{#if settingsTabs.length > 0}
						{#each settingsTabs as settingsTab}
						{#if settingsTab.id === 'general-settings'}
						<button
							class="md:px-3 py-5 md:py-2.5 border-b md:border-b-0 border-lightGray-400 dark:border-customGray-700 md:rounded-md flex-1 md:flex-none text-left transition {selectedTab ===
							'general-settings'
								? 'bg-lightGray-700 dark:bg-customGray-800'
								: ' text-lightGray-100 dark:text-customGray-100 hover:bg-lightGray-700 dark:hover:bg-customGray-800 dark:hover:text-white'}"
							on:click={() => {
								selectedTab = 'general-settings';
								updateTabParam(selectedTab);
							}}
						>
							<div class="flex items-center md:mb-1">
								<div class=" self-center mr-2">
									<ProfileIcon/>
								</div>
								<div class=" self-center">{$i18n.t('General settings')}</div>
							</div>
						</button>
						{:else if settingsTab.id === 'domain-settings'}
						<button
							class="md:px-3 py-5 md:py-2.5 border-b md:border-b-0 border-lightGray-400 dark:border-customGray-700 md:rounded-md flex-1 md:flex-none text-left transition {selectedTab ===
							'domain-settings'
								? 'bg-lightGray-700 dark:bg-customGray-800'
								: ' text-lightGray-100 dark:text-customGray-100 hover:bg-lightGray-700 dark:hover:bg-customGray-800 dark:hover:text-white'}"
							on:click={() => {
								selectedTab = 'domain-settings';
								updateTabParam(selectedTab);
							}}
						>
							<div class="flex items-center md:mb-1">
								<div class=" self-center mr-2">
									<DomainSettingsIcon/>
								</div>
								<div class=" self-center">{$i18n.t('Domain settings')}</div>
							</div>
						</button>
						{:else if settingsTab.id === 'user-management'}
						<button
							class="md:px-3 py-5 md:py-2.5 border-b md:border-b-0 border-lightGray-400 dark:border-customGray-700 md:rounded-md flex-1 md:flex-none text-left transition {selectedTab ===
							'user-management'
								? 'bg-lightGray-700 dark:bg-customGray-800'
								: 'text-lightGray-100 dark:text-customGray-100 hover:bg-lightGray-700 dark:hover:bg-customGray-800 dark:hover:text-white'}"
							on:click={() => {
								selectedTab = 'user-management';
								updateTabParam(selectedTab);
							}}
						>
							<div class="flex items-center md:mb-1">
								<div class=" self-center mr-2">
									<GroupIcon/>
								</div>
								<div class=" self-center">{$i18n.t('User management')}</div>
							</div>
						</button>
						{:else if settingsTab.id === 'model-control'}
						<button
							class="md:px-3 py-5 md:py-2.5 border-b md:border-b-0 border-lightGray-400 dark:border-customGray-700 md:rounded-md flex-1 md:flex-none text-left transition {selectedTab ===
							'model-control'
								? 'bg-lightGray-700 dark:bg-customGray-800'
								: ' text-lightGray-100 dark:text-customGray-100 hover:bg-lightGray-700 dark:hover:bg-customGray-800 dark:hover:text-white'}"
							on:click={() => {
								selectedTab = 'model-control';
								updateTabParam(selectedTab);
							}}
						>
							<div class="flex items-center md:mb-1">
								<div class=" self-center mr-2">
									<ModelControlIcon/>
								</div>
								<div class=" self-center">{$i18n.t('Model control')}</div>
							</div>
						</button>
						{:else if settingsTab.id === 'analytics'}
						<button
							class="md:px-3 py-5 md:py-2.5 border-b md:border-b-0 border-lightGray-400 dark:border-customGray-700 md:rounded-md flex-1 md:flex-none text-left transition {selectedTab ===
							'analytics'
								? 'bg-lightGray-700 dark:bg-customGray-800'
								: ' text-lightGray-100 dark:text-customGray-100 hover:bg-lightGray-700 dark:hover:bg-customGray-800 dark:hover:text-white'}"
							on:click={() => {
								selectedTab = 'analytics';
								updateTabParam(selectedTab);
							}}
						>
							<div class="flex items-center md:mb-1">
								<div class=" self-center mr-2">
									<AnalyticsIcon/>
								</div>
								<div class=" self-center">{$i18n.t('Analytics')}</div>
							</div>
						</button>
						{:else if settingsTab.id === 'billing'}
						<button
							class="md:px-3 py-5 md:py-2.5 border-b md:border-b-0 border-lightGray-400 dark:border-customGray-700 md:rounded-md flex-1 md:flex-none text-left transition {selectedTab ===
							'billing'
								? 'bg-lightGray-700 dark:bg-customGray-800'
								: ' text-lightGray-100 dark:text-customGray-100 hover:bg-lightGray-700 dark:hover:bg-customGray-800 dark:hover:text-white'}"
							on:click={() => {
								selectedTab = 'billing';
								updateTabParam(selectedTab);
							}}
						>
							<div class="flex items-center md:mb-1">
								<div class=" self-center mr-2">
									<BillingIcon/>
								</div>
								<div class=" self-center">{$i18n.t('Billing')}</div>
							</div>
						</button>
						{/if}
						{/each}
					{:else}
						<div class="text-center text-gray-500 mt-4">
							{$i18n.t('No results found')}
						</div>
					{/if}
				</div>
			{/if}
			<div class="flex-1 md:min-h-[32rem]">
				{#if selectedTab === 'general-settings'}
                    <GeneralSettings
                    {getModels}
						{saveSettings}
						on:save={() => {
							toast.success($i18n.t('Settings saved successfully!'));
						}}
                    />
				{:else if selectedTab === 'domain-settings'}	
					<DomainSettings />
				{:else if selectedTab === 'user-management'}
					<UserManagement
						{users}
						{getSubscription}
						{getUsersHandler}
						on:save={() => {
							toast.success($i18n.t('Settings saved successfully!'));
						}}
					/>
				{:else if selectedTab === 'model-control'}
					<ModelControl/>
				{:else if selectedTab === 'analytics'}
					<Analytics/>
				{:else if selectedTab === 'billing'}
					<Billing bind:autoRecharge bind:subscriptionLoading/>
				{/if}
			</div>
		</div>
	</div>
</Modal>

<style>
	input::-webkit-outer-spin-button,
	input::-webkit-inner-spin-button {
		/* display: none; <- Crashes Chrome on hover */
		-webkit-appearance: none;
		margin: 0; /* <-- Apparently some margin are still there even though it's hidden */
	}

	.tabs::-webkit-scrollbar {
		display: none; /* for Chrome, Safari and Opera */
	}

	.tabs {
		-ms-overflow-style: none; /* IE and Edge */
		scrollbar-width: none; /* Firefox */
	}

	input[type='number'] {
		-moz-appearance: textfield; /* Firefox */
	}
</style>
