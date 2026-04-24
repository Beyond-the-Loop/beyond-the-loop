<script lang="ts">
	import { createEventDispatcher, getContext, onMount, onDestroy, tick } from 'svelte';
	import { fly } from 'svelte/transition';
	import {
		COUNTRIES,
		getDefaultCountry,
		filterCountries,
		type Country
	} from '$lib/constants/countries';

	const i18n = getContext<import('svelte/store').Writable<import('i18next').i18n>>('i18n');
	const dispatch = createEventDispatcher<{ input: string }>();

	export let value = '';
	export let hasError = false;
	export let placeholder = '';
	export let id = 'phone';

	let selectedCountry: Country = getDefaultCountry();
	let nationalNumber = '';
	let searchQuery = '';
	let open = false;
	let searchInputEl: HTMLInputElement;
	let phoneInputEl: HTMLInputElement;
	let highlightedIndex = 0;
	let listEl: HTMLDivElement;
	let wrapperEl: HTMLDivElement;

	// Parse initial value if provided (e.g. "+49 123456")
	function parseInitialValue() {
		if (!value) return;
		let bestMatch: Country | undefined;
		for (const country of COUNTRIES) {
			if (
				value.startsWith(country.dialCode) &&
				(!bestMatch || country.dialCode.length > bestMatch.dialCode.length)
			) {
				bestMatch = country;
			}
		}
		if (bestMatch) {
			selectedCountry = bestMatch;
			nationalNumber = value.slice(bestMatch.dialCode.length).trim();
		} else {
			nationalNumber = value;
		}
	}

	parseInitialValue();

	function syncValue() {
		const trimmed = nationalNumber.replace(/^\s+/, '');
		value = trimmed ? `${selectedCountry.dialCode} ${trimmed}` : '';
		dispatch('input', value);
	}

	function toggleDropdown() {
		open = !open;
		if (open) {
			highlightedIndex = 0;
			searchQuery = '';
			tick().then(() => searchInputEl?.focus());
		}
	}

	function selectCountry(country: Country) {
		selectedCountry = country;
		open = false;
		searchQuery = '';
		syncValue();
		tick().then(() => phoneInputEl?.focus());
	}

	function handleSearchKeydown(e: KeyboardEvent) {
		const filtered = filteredCountries;
		if (!filtered.length) return;

		if (e.key === 'ArrowDown') {
			e.preventDefault();
			highlightedIndex = (highlightedIndex + 1) % filtered.length;
			scrollToHighlighted();
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			highlightedIndex = (highlightedIndex - 1 + filtered.length) % filtered.length;
			scrollToHighlighted();
		} else if (e.key === 'Enter') {
			e.preventDefault();
			selectCountry(filtered[highlightedIndex]);
		} else if (e.key === 'Escape') {
			e.preventDefault();
			open = false;
			phoneInputEl?.focus();
		}
	}

	function scrollToHighlighted() {
		tick().then(() => {
			const el = listEl?.querySelector(`[data-index="${highlightedIndex}"]`);
			el?.scrollIntoView({ block: 'nearest' });
		});
	}

	function handleClickOutside(e: MouseEvent) {
		if (open && wrapperEl && !wrapperEl.contains(e.target as Node)) {
			open = false;
		}
	}

	onMount(() => {
		document.addEventListener('mousedown', handleClickOutside);
	});

	onDestroy(() => {
		if (typeof document !== 'undefined') {
			document.removeEventListener('mousedown', handleClickOutside);
		}
	});

	$: filteredCountries = searchQuery.trim()
		? COUNTRIES.filter((c) => {
				const q = searchQuery.toLowerCase().trim();
				return (
					c.name.toLowerCase().includes(q) ||
					$i18n.t(c.name).toLowerCase().includes(q) ||
					c.dialCode.includes(q) ||
					c.iso.toLowerCase().includes(q)
				);
			})
		: COUNTRIES;
</script>

<div bind:this={wrapperEl} class="relative">
	<!-- Combined Input Container -->
	<div
		class="flex h-12 w-full rounded-lg border transition
			{hasError
			? 'border-red-500 focus-within:border-red-500 focus-within:ring-1 focus-within:ring-red-500'
			: 'border-gray-200 focus-within:border-customBlue-500 focus-within:ring-1 focus-within:ring-customBlue-500 dark:border-customGray-700'}
			bg-[#F1F1F1] dark:bg-customGray-800"
	>
		<!-- Country Code Trigger -->
		<button
			type="button"
			class="flex shrink-0 items-center gap-1.5 border-r border-gray-200 px-3
				transition-colors dark:border-customGray-700
				hover:bg-[#E8E8E8] dark:hover:bg-customGray-700
				rounded-l-lg focus:outline-none"
			aria-label="Select country code"
			aria-expanded={open}
			on:click={toggleDropdown}
		>
			<span class="text-base leading-none">{selectedCountry.flag}</span>
			<svg
				class="h-3 w-3 text-gray-500 dark:text-customGray-400 transition-transform"
				class:rotate-180={open}
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 20 20"
				fill="currentColor"
			>
				<path
					fill-rule="evenodd"
					d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
					clip-rule="evenodd"
				/>
			</svg>
			<span class="text-sm font-medium text-[#16181D] dark:text-white">
				{selectedCountry.dialCode}
			</span>
		</button>

		<!-- Phone Number Input -->
		<input
			bind:this={phoneInputEl}
			{id}
			type="tel"
			inputmode="tel"
			autocomplete="tel-national"
			class="h-full w-full min-w-0 rounded-r-lg bg-transparent px-4 text-sm text-[#16181D] outline-none
				placeholder:text-gray-400
				dark:text-white dark:placeholder:text-customGray-300"
			placeholder={placeholder || $i18n.t('Enter phone number')}
			bind:value={nationalNumber}
			on:input={() => {
				nationalNumber = nationalNumber.replace(/[^\d\s\-()]/g, '');
				syncValue();
			}}
			on:keydown={(e) => {
				if (e.key.length === 1 && !/[\d\s\-()]/.test(e.key) && !e.ctrlKey && !e.metaKey) {
					e.preventDefault();
				}
			}}
		/>
	</div>

	<!-- Dropdown (opens upward) -->
	{#if open}
		<div
			class="absolute bottom-[calc(100%+6px)] left-0 z-[9999] w-72 rounded-lg border border-gray-200
				bg-white shadow-xl dark:border-customGray-700 dark:bg-customGray-800"
			transition:fly={{ y: 8, duration: 150 }}
		>
			<!-- Search -->
			<div class="border-b border-gray-100 p-2 dark:border-customGray-700">
				<div class="flex items-center gap-2 rounded-md bg-[#F1F1F1] px-3 py-2 dark:bg-customGray-700">
					<svg
						class="h-4 w-4 shrink-0 text-gray-400 dark:text-customGray-400"
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="2"
						stroke="currentColor"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
						/>
					</svg>
					<input
						bind:this={searchInputEl}
						bind:value={searchQuery}
						on:keydown={handleSearchKeydown}
						class="w-full bg-transparent text-sm text-[#16181D] outline-none placeholder:text-gray-400
							dark:text-white dark:placeholder:text-customGray-400"
						placeholder={$i18n.t('Search country...')}
					/>
				</div>
			</div>

			<!-- Country List -->
			<div bind:this={listEl} class="max-h-56 overflow-y-auto overscroll-contain p-1">
				{#each filteredCountries as country, i (country.iso)}
					<button
						type="button"
						data-index={i}
						class="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors
							{i === highlightedIndex
							? 'bg-gray-100 dark:bg-customGray-700'
							: 'hover:bg-gray-50 dark:hover:bg-customGray-700/50'}
							{selectedCountry.iso === country.iso
							? 'font-medium text-customBlue-500'
							: 'text-[#16181D] dark:text-white'}"
						on:click={() => selectCountry(country)}
						on:mouseenter={() => (highlightedIndex = i)}
					>
						<span class="text-base leading-none">{country.flag}</span>
						<span class="flex-1 truncate">{$i18n.t(country.name)}</span>
						<span class="shrink-0 text-xs text-gray-500 dark:text-customGray-400">
							{country.dialCode}
						</span>
					</button>
				{:else}
					<p class="px-3 py-4 text-center text-sm text-gray-400 dark:text-customGray-400">
						{$i18n.t('No countries found')}
					</p>
				{/each}
			</div>
		</div>
	{/if}
</div>
