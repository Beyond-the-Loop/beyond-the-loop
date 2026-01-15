<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import { subscription } from '$lib/stores';
	import {
		rechargeFlexCredits,
		updateAutoRecharge,
		getCurrentSubscription,
		redirectToCustomerPortal,
		createPricingTable, redirectToPremiumSubscriptionCheckout
	} from '$lib/apis/payments';
	import dayjs from 'dayjs';
	import { toast } from 'svelte-sonner';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { goto } from '$app/navigation';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import UnlimitedPlanIcon from '$lib/components/icons/UnlimitedPlanIcon.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import CloseIcon from '$lib/components/icons/CloseIcon.svelte';

	const i18n = getContext('i18n');
	export let autoRecharge = false;
	export let subscriptionLoading = false;
	let showBuyFlexCredits = false;

	let mounted = false;
	export let plans = [];
	onMount(() => {
		mounted = true;
		const url = new URL(window.location.href);

		const rechargeParam = url.searchParams.get('recharge');

		if (rechargeParam === 'open'){
			showBuyFlexCredits = true;
		}
	})

	async function goToCustomerPortal() {
		const res = await redirectToCustomerPortal(localStorage.token).catch((error) => {
			console.log(error)
		});
		console.log(res);
		if (res) {
			window.location.href = res.url;
		}
	}

	async function goToPremiumSubscriptionCheckout() {
		const res = await redirectToPremiumSubscriptionCheckout(localStorage.token).catch((error) => {
			console.log(error)
		});
		if (res) {
			window.location.href = res.url;
		}
	}

	async function fetchCurrentSubscription() {
		const sub = await getCurrentSubscription(localStorage.token)
		.catch(error => {
			console.log(error)
			
		});
		subscription.set(sub);
	}

	async function pollForCreditChange(previous, interval = 2000, timeout = 20000) {
		const start = Date.now();

		return new Promise((resolve, reject) => {
			const check = async () => {
				try {
					const res = await getCurrentSubscription(localStorage.token);

					if (res.flex_credits_remaining !== previous) {
						subscription.set(res);
						resolve();
					} else if (Date.now() - start >= timeout) {
						reject(new Error('Timeout: Credit not updated'));
					} else {
						setTimeout(check, interval);
					}
				} catch (err) {
					reject(err);
				}
			};

			check();
		});
	}

	async function recharge () {
		const res = await rechargeFlexCredits(localStorage.token).catch((error) =>
			console.log(error)
		);
		if(res.payment_intent) {
			toast.success($i18n.t(res.message))
		}
		await pollForCreditChange($subscription?.flex_credits_remaining, 2000, 20000);
		
	}
	
	$: currentPlan = plans?.find((item) => item.id === $subscription?.plan);

	$: seatsWidth = $subscription?.seats ? $subscription?.seats_taken > $subscription?.seats ? '100%' : `${($subscription?.seats_taken/$subscription?.seats*100)}%` : '100%';
	$: creditsWidth = $subscription?.credits_remaining ? `${(((currentPlan?.credits_per_month - $subscription?.credits_remaining)/currentPlan?.credits_per_month) * 100)}%` : '100%';

	$: {
		if(showBuyFlexCredits === false && mounted){
			const url = new URL(window.location.href);
			url.searchParams.delete('recharge'); 
			window.history.replaceState({}, '', `${url.pathname}${url.search}`);
		}
	}
	$: console.log($subscription, 'subscription')

	let showStripeTable = false;
	let clientSecret = '';
	let pricingTableId = '';
	let publishableKey = '';

	const createTable = async () => {
		try {
			const res = await createPricingTable(localStorage.token);
			if(res) {
				clientSecret = res.client_secret;
				pricingTableId = res.pricing_table_id;
				publishableKey = res.publishable_key;
				showStripeTable = true;
			}
		} catch(err) {
			console.log(err)
		}
	}
</script>


<ConfirmDialog
	bind:show={showBuyFlexCredits}
	title={$i18n.t('Buy credits?')}
	on:confirm={recharge}
	on:cancel={() => {
		const url = new URL(window.location.href);
		url.searchParams.delete('recharge'); 
		window.history.replaceState({}, '', `${url.pathname}${url.search}`);
	}}
>
	<div class=" text-sm text-gray-500 flex-1 line-clamp-3">
		{$i18n.t('You will be charged for')} <span class="  font-semibold">€{(20).toFixed(2)}</span>.
	</div>
</ConfirmDialog>

<Modal
	bind:show={showStripeTable}
	size="lg"
	containerClassName="bg-lightGray-250/50 dark:bg-[#1D1A1A]/50 backdrop-blur-[6px]"
	>
	<div class="flex justify-end border-b border-lightGray-400 dark:border-customGray-700 px-4 py-2">
		<button type="button" class="dark:text-white" on:click={() => {
			showStripeTable = false;
			}}>
			<CloseIcon />
		</button>
	</div>
	<div class="p-4">
		<stripe-pricing-table pricing-table-id={pricingTableId} publishable-key={publishableKey} customer-session-client-secret={clientSecret}>
		</stripe-pricing-table>
	</div>
</Modal>

{#if !subscriptionLoading}
	<!-- {#if !$subscription?.plan}
	<div class="flex justify-between items-center mt-4 mb-4">
		<div class="text-sm">Your subscription has expired</div>
		<button
			on:click={createTable}
			class="flex items-center justify-center rounded-mdx bg-lightGray-300 dark:bg-customGray-900 border-lightGray-400 text-lightGray-100 font-medium hover:bg-lightGray-700 dark:hover:bg-customGray-950 border dark:border-customGray-700 px-4 py-3 text-xs dark:text-customGray-200"
		>
			{$i18n.t('Update Subscription')}
		</button>
	</div>
	{:else} -->
	<div class="pb-20">
		<div
			class="font-medium flex w-full justify-between items-center py-2.5 border-b border-lightGray-400 dark:border-customGray-700 mb-2.5"
		>
			<div class="flex w-full justify-between items-center">
				<div class="text-xs text-lightGray-100 dark:text-customGray-300">{$i18n.t('Current plan')}</div>
			</div>
		</div>
		<div class="rounded-2xl bg-lightGray-300 dark:bg-customGray-900 pt-4 px-4 mb-2.5">
			<div class="flex items-center justify-between pb-2.5 {$subscription?.plan !== 'unlimited' && $subscription?.plan !== 'free' ? 'border-b' : ''} dark:border-customGray-700">
				<div class="flex items-center gap-2.5">
					{#if $subscription?.plan !== "unlimited" && $subscription?.image_url}
						<img src="{$subscription.image_url}" alt="" class="w-[50px] h-[50px] object-cover rounded-mdx" />
					{:else if $subscription?.plan === 'unlimited' || $subscription?.plan === 'free'}
					<div
						class="flex justify-center items-center w-[50px] h-[50px] bg-[#DA702C] dark:bg-[#A54300] rounded-mdx text-[#FFD6A8] dark:text-[#FFD8A8]"
					>
						<UnlimitedPlanIcon className="size-6" />
				</div>
					{/if}
					<div class="flex items-center gap-2.5">
						<div class="text-sm text-lightGray-100 dark:text-customGray-100 capitalize">
								{$i18n.t($subscription?.plan?.replace('_monthly', '').replace('_yearly', '').replace('_two', ''))}
						</div>
						{#if $subscription?.plan && $subscription.plan.includes("monthly")}
							<div
								class="flex justify-center items-center text-xs bg-lightGray-400 dark:text-customGray-590 dark:bg-customGray-800 px-2 py-1 rounded-mdx"
							>
								{$i18n.t('Monthly')}
							</div>
						{/if}
						{#if $subscription?.plan && $subscription.plan.includes("yearly")}
							<div
								class="flex justify-center items-center text-xs bg-lightGray-400 dark:text-customGray-590 dark:bg-customGray-800 px-2 py-1 rounded-mdx"
							>
								{$subscription.plan.includes('two_yearly')
									? $i18n.t('Two yearly')
									: $i18n.t('Yearly')}
							</div>
						{/if}
						{#if $subscription.status === 'canceled'}
							<div
								class="flex justify-center items-center text-xs bg-lightGray-400 dark:text-customGray-590 dark:bg-customGray-800 px-2 py-1 rounded-mdx"
							>
								{$i18n.t('Expired')}
							</div>
						{/if}
					</div>
				</div>
				{#if $subscription?.plan !== 'unlimited' && $subscription?.plan !== 'free'}
					{#if $subscription?.status === "canceled"}
						<button
							on:click={createTable}
							class="flex items-center justify-center rounded-mdx bg-lightGray-300 dark:bg-customGray-900 border-lightGray-400 text-lightGray-100 font-medium hover:bg-lightGray-700 dark:hover:bg-customGray-950 border dark:border-customGray-700 px-4 py-3 text-xs dark:text-customGray-200"
						>
							{$i18n.t('Subscribe')}
						</button>
					{:else}
						<button
							on:click={() => {
								goToCustomerPortal()
							}}
							class="flex items-center justify-center rounded-mdx bg-lightGray-300 dark:bg-customGray-900 border-lightGray-400 text-lightGray-100 font-medium hover:bg-lightGray-700 dark:hover:bg-customGray-950 border dark:border-customGray-700 px-4 py-3 text-xs dark:text-customGray-200"
						>
							{$i18n.t('Manage subscription')}
						</button>
					{/if}	
				{/if}
				{#if $subscription?.plan === 'free'}
					<button
							on:click={() => {
								goToPremiumSubscriptionCheckout()
							}}
							class="flex items-center justify-center rounded-mdx bg-lightGray-300 dark:bg-customGray-900 border-lightGray-400 text-lightGray-100 font-medium hover:bg-lightGray-700 dark:hover:bg-customGray-950 border dark:border-customGray-700 px-4 py-3 text-xs dark:text-customGray-200"
						>
							{$i18n.t('Upgrade')}
						</button>
				{/if}
			</div>
			{#if $subscription?.plan !== "unlimited" && $subscription?.plan !== 'free'}
				<div class="flex items-center justify-between pt-2.5 pb-3">
					<div class="text-xs text-lightGray-100 dark:text-customGray-100">{$i18n.t('Billing details')}</div>
					{#if $subscription.status === 'canceled'}
						<div class="text-xs dark:text-customGray-590">Expired since {dayjs($subscription?.canceled_at * 1000)?.format('DD.MM.YYYY')}</div>
					{:else}
						{#if $subscription?.cancel_at_period_end}
						<div class="text-xs dark:text-customGray-590">
							Active until {dayjs($subscription?.end_date * 1000)?.format('DD.MM.YYYY')}
						</div>
					{:else if !$subscription?.is_trial}
						<div class="text-xs dark:text-customGray-590">
							{$subscription?.plan?.includes('yearly') ? 'Yearly' : 'Monthly'} (renews {dayjs($subscription?.next_billing_date * 1000)?.format('DD.MM.YYYY')})
						</div>
					{:else}
						<div class="text-xs dark:text-customGray-590">
							{$i18n.t('Trial ends')} {dayjs($subscription?.trial_end * 1000)?.format('DD.MM.YYYY')}
						</div>
					{/if}
					{/if}
				</div>
			{/if}
		</div>

		<div class="rounded-2xl bg-lightGray-300 dark:bg-customGray-900 pt-4 px-4 pb-4 mb-2.5">
			<div class="flex items-center justify-between {$subscription?.plan !== 'unlimited' ? 'pb-3' : ''}">
				<div class="text-xs dark:text-customGray-300 font-medium">{$i18n.t('Seats')}</div>
				<div class="text-xs dark:text-customGray-590">
					{#if $subscription?.plan === 'unlimited'}
						<span
							class="dark:text-customGray-590 capitalize">{$i18n.t($subscription?.seats)} {$i18n.t('Included').toLowerCase()}</span
						>
					{:else}
						<span class="text-xs text-lightGray-100 dark:text-customGray-100">{$subscription?.seats_taken} {$i18n.t('used')}</span>
						{#if $subscription?.plan !== 'free' && $subscription?.plan !== 'premium'}
							<span class="dark:text-customGray-590">/ {$subscription?.seats} {$i18n.t('Included').toLowerCase()}</span>
						{/if}
					{/if}
				</div>
			</div>
			{#if $subscription?.plan !== "unlimited" }
			<div class="relative w-full h-1 rounded-sm bg-lightGray-700 dark:bg-customGray-800">
				<div style={`width: ${seatsWidth};`} class="absolute left-0 h-1 rounded-sm bg-[#024D15]/80 dark:bg-[#024D15]"></div>
			</div>
			{/if}
		</div>
		{#if $subscription?.plan !== 'unlimited' && $subscription?.plan !== 'free' && $subscription?.plan !== 'premium'}
			<div class="rounded-2xl bg-lightGray-300 dark:bg-customGray-900 pt-4 px-4 pb-4 mb-2.5">
				<div class="flex items-center justify-between pb-2.5 border-b dark:border-customGray-700 mb-5">
					<div class="text-xs dark:text-customGray-300 font-medium">{$i18n.t('Base credits')}</div>
					<div class="text-xs dark:text-customGray-590">
						<span class="text-xs text-lightGray-100 dark:text-customGray-100">€{(currentPlan?.credits_per_month - $subscription?.credits_remaining)?.toFixed(2)} {$i18n.t('used')}</span><span
							class="dark:text-customGray-590">/ €{($subscription.custom_credit_amount || currentPlan?.credits_per_month).toFixed(2)} {$i18n.t('Included').toLowerCase()}</span
						>
					</div>
				</div>
				<div class="relative w-full h-1 rounded-sm bg-lightGray-700 dark:bg-customGray-800 mb-2.5">
					<div style={`width: ${creditsWidth};`} class="absolute left-0 h-1 rounded-sm bg-[#024D15]/80 dark:bg-[#024D15]"></div>
				</div>
				<div class="flex items-center justify-between pt-2.5">
					{#if !$subscription?.is_trial && $subscription?.cancel_at_period_end !== true && $subscription?.status !== "canceled"}
						<div class="text-xs dark:text-customGray-590">
							{$i18n.t('Credits will reset on')} {dayjs($subscription?.next_billing_date * 1000)?.format('DD.MM.YYYY')}
						</div>
					{:else}
						<div></div>
					{/if}
					<button
						on:click={() => {
							const url = new URL(window.location.href);
							url.searchParams.set('modal', 'company-settings');
							url.searchParams.set('tab', 'analytics');
							goto(`${url.pathname}${url.search}`, { replaceState: false });
						}}
						class="flex items-center justify-center rounded-[10px] bg-lightGray-300 dark:bg-customGray-900 border-lightGray-400 text-lightGray-100 font-medium hover:bg-lightGray-700 dark:hover:bg-customGray-950 border dark:border-customGray-700 px-4 py-2 text-xs dark:text-customGray-200"
					>
						{$i18n.t('View usage details')}
					</button>
				</div>
			</div>
		{/if}

		{#if !$subscription?.is_trial && $subscription.plan !== 'free' && $subscription.plan !== 'premium'}
			<div class="rounded-2xl bg-lightGray-300 dark:bg-customGray-900 pt-4 px-4 pb-4">
				<div class="flex items-center justify-between {$subscription?.status !== 'canceled' && 'border-b dark:border-customGray-700 pb-2.5'}">
					<div class="text-xs dark:text-customGray-300 font-medium">{$i18n.t('Flex credits')}</div>
					<div class="text-xs dark:text-customGray-590">
						<!-- <span class="text-xs dark:text-customGray-100">0 {$i18n.t('used')}</span> -->
						<span
							class="text-lightGray-100 dark:text-customGray-100">€{($subscription?.flex_credits_remaining ? $subscription?.flex_credits_remaining : 0).toFixed(2)} {$i18n.t('remaining')}</span
						>
					</div>
				</div>
				{#if $subscription?.status !== 'canceled'}
					<div class="flex items-center justify-between pt-2.5">
						<div class="flex items-center">
							<Tooltip content={$i18n.t('When enabled, 20€ in credits will be automatically purchased and added to your account once your balance drops to 80% of your base credit amount.')}>
								<div class="text-xs dark:text-customGray-590 mr-2.5 cursor-pointer">{$i18n.t('Auto recharge')}</div>
							</Tooltip>
							
							<Switch bind:state={autoRecharge} on:change={async (e) => {
								const res = await updateAutoRecharge(localStorage.token, e.detail).catch(error => console.log(error))
								toast.success($i18n.t(res.message))
								fetchCurrentSubscription()
							}} />
							<div class="text-xs dark:text-customGray-590 ml-2.5">
								{#if autoRecharge}
									{$i18n.t('On')}
								{:else}
									{$i18n.t('Off')}
								{/if}
							</div>
						</div>
						<button
							on:click={() => {
								showBuyFlexCredits = true;
								const url = new URL(window.location.href);
								url.searchParams.set('recharge', 'open'); 
								window.history.replaceState({}, '', `${url.pathname}${url.search}`);
							}}
							class="flex items-center justify-center rounded-[10px] bg-lightGray-300 dark:bg-customGray-900 border-lightGray-400 text-lightGray-100 font-medium hover:bg-lightGray-700 dark:hover:bg-customGray-950 border dark:border-customGray-700 px-8 py-2 text-xs dark:text-customGray-200"
						>
							{$i18n.t('Buy credits')}
						</button>
					</div>
				{/if}
			</div>
		{/if}
		{#if subscription.status !== 'canceled' && $subscription?.plan !== 'unlimited' && $subscription?.plan !== 'free'}
			<div
			class="flex w-full justify-between items-center py-2.5 border-b border-lightGray-400 dark:border-customGray-700 mb-2.5"
			>
				<div class="flex w-full justify-between items-center">
					<div class="text-xs text-lightGray-100 dark:text-customGray-300 font-medium">{$i18n.t('Billing')}</div>
				</div>
			</div>
			<button
				on:click={() => {
					goToCustomerPortal()
				}}
				class="flex items-center justify-center rounded-mdx bg-lightGray-300 dark:bg-customGray-900 border-lightGray-400 text-lightGray-100 font-medium hover:bg-lightGray-700 dark:hover:bg-customGray-950 border dark:border-customGray-700 px-4 py-3 text-xs dark:text-customGray-200"
			>
				{$i18n.t('View invoices')}
			</button>
		{/if}
	</div>
	<!-- {/if}	 -->
{:else}
	<div class="h-[20rem] w-full flex justify-center items-center">
		<Spinner />
	</div>
{/if}
