<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { createEventDispatcher, getContext, onMount } from 'svelte';
	import { getLanguages } from '$lib/i18n';
	import { config, mobile, settings, theme, user } from '$lib/stores';
	import { onClickOutside } from '$lib/utils';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import { getVoices as _getVoices } from '$lib/apis/audio';
	import ManageModal from './Personalization/ManageModal.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import SystemIcon from '$lib/components/icons/SystemIcon.svelte';
	import DarkIcon from '$lib/components/icons/DarkIcon.svelte';
	import LightIcon from '$lib/components/icons/LightIcon.svelte';

	const dispatch = createEventDispatcher();

	const i18n = getContext('i18n');

	export let saveSettings: Function;

	// General
	let themes = ['dark', 'light', 'rose-pine dark', 'rose-pine-dawn light', 'oled-dark'];
	let selectedTheme = 'system';

	let languages: Awaited<ReturnType<typeof getLanguages>> = [];
	let lang = $i18n.language;
	let system = '';

	onMount(async () => {
		selectedTheme = localStorage.theme ?? 'system';

		languages = await getLanguages();

		system = $settings.system ?? '';

		if ($settings?.audio?.tts?.defaultVoice === $config.audio.tts.voice) {
			voice = $settings?.audio?.tts?.voice ?? $config.audio.tts.voice ?? '';
		} else {
			voice = $config.audio.tts.voice ?? '';
		}

		await getVoices();
	});

	const applyTheme = (_theme: string) => {
		let themeToApply = _theme === 'oled-dark' ? 'dark' : _theme;

		if (_theme === 'system') {
			themeToApply = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
		}

		if (themeToApply === 'dark' && !_theme.includes('oled')) {
			document.documentElement.style.setProperty('--color-gray-800', '#333');
			document.documentElement.style.setProperty('--color-gray-850', '#262626');
			document.documentElement.style.setProperty('--color-gray-900', '#171717');
			document.documentElement.style.setProperty('--color-gray-950', '#0d0d0d');
		}

		themes
			.filter((e) => e !== themeToApply)
			.forEach((e) => {
				e.split(' ').forEach((e) => {
					document.documentElement.classList.remove(e);
				});
			});

		themeToApply.split(' ').forEach((e) => {
			document.documentElement.classList.add(e);
		});

		const metaThemeColor = document.querySelector('meta[name="theme-color"]');
		if (metaThemeColor) {
			if (_theme.includes('system')) {
				const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
					? 'dark'
					: 'light';
				metaThemeColor.setAttribute('content', systemTheme === 'light' ? '#ffffff' : '#171717');
			} else {
				metaThemeColor.setAttribute(
					'content',
					_theme === 'dark'
						? '#171717'
						: _theme === 'oled-dark'
							? '#000000'
							: _theme === 'her'
								? '#983724'
								: '#ffffff'
				);
			}
		}
	};

	const themeChangeHandler = (_theme: string) => {
		theme.set(_theme);
		localStorage.setItem('theme', _theme);
		if (_theme.includes('oled')) {
			document.documentElement.style.setProperty('--color-gray-800', '#101010');
			document.documentElement.style.setProperty('--color-gray-850', '#050505');
			document.documentElement.style.setProperty('--color-gray-900', '#000000');
			document.documentElement.style.setProperty('--color-gray-950', '#000000');
			document.documentElement.classList.add('dark');
		}
		applyTheme(_theme);
		selectedTheme = _theme;
	};
	let showLanguageDropdown = false;
	let languageDropdownRef;

	let selectedLanguage;

	$: selectedLanguage = languages?.find(item => item.code.toLowerCase() === lang.toLowerCase());

	// Audio
	let nonLocalVoices = true;

	let STTEngine = '';

	let voices = [];
	let voice = '';

	// Audio speed control
	let playbackRate = 1;

	const getVoices = async () => {
		if ($config.audio.tts.engine === '') {
			const getVoicesLoop = setInterval(async () => {
				voices = speechSynthesis.getVoices();

				// do your loop
				if (voices.length > 0) {
					clearInterval(getVoicesLoop);
				}
			}, 100);
		} else {
			const res = await _getVoices(localStorage.token).catch((e) => {
				toast.error(`${e}`);
			});

			if (res) {
				voices = res.voices;
			}
		}
	};

	let showVoiceDropdown = false;
	let voiceDropdownRef;

	let showManageModal = false;

	// Addons
	let enableMemory = false;

	onMount(async () => {
		enableMemory = $settings?.memory ?? false;
	});

</script>

<ManageModal bind:show={showManageModal} />

<div class="flex flex-col h-full justify-between text-sm pt-5 pb-5">
	<div class="">
		<div class="">
			<div class="my-1" use:onClickOutside={() => (showLanguageDropdown = false)}>
				<div class="relative" bind:this={languageDropdownRef}>
					<button
						type="button"
						class={`flex items-center justify-between w-full text-sm h-12 px-3 py-2 ${
							showLanguageDropdown ? 'border' : ''
						} border-lightGray-400 dark:border-customGray-700 rounded-md bg-lightGray-300 dark:bg-customGray-900 cursor-pointer`}
						on:click={() => {
							showLanguageDropdown = !showLanguageDropdown
							}}
					>
						<span class="text-lightGray-100 dark:text-customGray-100"
						>{$i18n.t('Language')}</span
						>
						<div class="flex items-center gap-2 text-xs text-lightGray-100 dark:text-customGray-100/50">
							{$i18n.t(selectedLanguage?.['title_translation_key'])}
							<ChevronDown className="size-3" />
						</div>
					</button>

					{#if showLanguageDropdown}
						<div
							class="max-h-40 overflow-y-auto absolute z-50 w-full -mt-1 bg-lightGray-300 pb-1 dark:bg-customGray-900 border-l border-r border-b border-lightGray-400 dark:border-customGray-700 rounded-b-md"
						>
							<hr class="border-t border-lightGray-400 dark:border-customGray-700 mb-2 mt-1 mx-0.5" />
							<div class="px-1">
								{#each languages as language}
									<button
										class="px-3 py-2 flex items-center gap-2 w-full rounded-xl text-sm hover:bg-gray-100 dark:hover:bg-customGray-950 dark:text-customGray-100 cursor-pointer text-gray-900"
										on:click={() => {
											$i18n.changeLanguage(language['code']);
											selectedLanguage = language;
											showLanguageDropdown = false;
										}}
									>
										{$i18n.t(language['title_translation_key'])}
									</button>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			</div>
			<div>
				<div class="my-1" use:onClickOutside={() => (showVoiceDropdown = false)}>
					<div class="relative" bind:this={voiceDropdownRef}>
						<button
							type="button"
							class={`flex items-center justify-between w-full bg-lightGray-300 text-sm h-12 px-3 py-2 ${
								showVoiceDropdown ? 'border' : ''
							} border-lightGray-400 dark:border-customGray-700 rounded-md bg-lightGray-300 dark:bg-customGray-900 cursor-pointer`}
							on:click={() => {
								showVoiceDropdown = !showVoiceDropdown
								}}
						>
							<span class="text-lightGray-100 dark:text-customGray-100"
							>{$i18n.t('Voice for audio output')}</span>
							<div class="flex items-center gap-2 text-xs text-lightGray-100 dark:text-customGray-100/50">
								<div class="flex items-center gap-2 text-xs text-lightGray-100 dark:text-customGray-100/50 capitalize">
									{voice}
									<ChevronDown className="size-3" />
								</div>
						</button>

						{#if showVoiceDropdown}
							<div
								class="max-h-40 overflow-y-auto absolute z-50 w-full -mt-1 pb-1 bg-lightGray-300 dark:bg-customGray-900 border-l border-r border-b border-gray-300 dark:border-customGray-700 rounded-b-md shadow"
							>
								<hr class="border-t border-lightGray-400 dark:border-customGray-700 mb-2 mt-1 mx-0.5" />
								<div class="px-1">
									{#each voices.filter((v) => nonLocalVoices || v.localService === true) as _voice}
										<button
											class="px-3 py-2 flex items-center gap-2 w-full rounded-xl text-sm hover:bg-gray-100 dark:hover:bg-customGray-950 dark:text-customGray-100 cursor-pointer capitalize text-gray-900"
											on:click={() => {
												voice = _voice.name;
												saveSettings({
													audio: {
														stt: {
															engine: STTEngine !== '' ? STTEngine : undefined
														},
														tts: {
															playbackRate: playbackRate,
															voice: _voice.name !== '' ? _voice.name : undefined,
															defaultVoice: $config?.audio?.tts?.voice ?? '',
															nonLocalVoices: $config.audio.tts.engine === '' ? nonLocalVoices : undefined
														}
													}
												});
												showVoiceDropdown = false;
											}}
										>
											{_voice.name}
										</button>
									{/each}
								</div>
							</div>
						{/if}
					</div>
				</div>
			</div>
			<div
				class="flex w-full justify-between items-center py-2.5 border-b border-lightGray-400 dark:border-customGray-700 mb-2"
			>
				<div class="flex w-full justify-between items-center">
					<div class="text-xs text-lightGray-100 dark:text-customGray-300">{$i18n.t('Theme')}</div>
				</div>
			</div>

			<div class="flex gap-x-2.5 min-h-[90px]">
				<div on:click={() => themeChangeHandler('system')}
						 class="w-full relative rounded-lg {selectedTheme === "system" ? "border-2 border-[#305BE4]" : ""}">

				<img class="rounded-lg max-w-full h-full" src="/system.png" alt="system theme" />
				<div class="flex items-center pl-2.5 absolute bottom-[0.625rem] text-customGray-550 text-xs">
					<SystemIcon className="size-3.5 mr-1" />
					{#if ($mobile)}
						{$i18n.t('System')}
					{:else}
						{$i18n.t('System (Default)')}
					{/if}

				</div>
			</div>
			<div on:click={() => themeChangeHandler('light')}
					 class="w-full relative rounded-lg {selectedTheme === "light" ? "border-2 border-[#305BE4]" : ""}">

			<img class="rounded-lg max-w-full h-full" src="/light.png" alt="light theme" />
			<div class="flex items-center pl-2.5 absolute bottom-[0.625rem] text-customGray-550 text-xs">
				<LightIcon className="size-3.5 mr-1" />
				{$i18n.t('Light')}
			</div>
		</div>
		<div on:click={() => themeChangeHandler('dark')}
				 class="w-full relative rounded-lg {selectedTheme === "dark" ? "border-2 border-[#305BE4]" : ""}">

		<img class="rounded-lg max-w-full h-full" src="/dark.png" alt="dark theme" />
		<div class="flex items-center pl-2.5 absolute bottom-[0.625rem] text-customGray-550 text-xs">
			<DarkIcon className="size-3.5 mr-1" />
			{$i18n.t('Dark')}
		</div>
	</div>
</div>
</div>

{#if $user.role === 'admin' || $user?.permissions.chat?.controls}
	<div
		class="flex w-full justify-between items-center py-2.5 border-b border-lightGray-400 dark:border-customGray-700 mb-2"
	>
		<div class="flex w-full justify-between items-center">
			<div class="text-xs text-lightGray-100 dark:text-customGray-300">{$i18n.t('Custom instructions')}</div>
		</div>
	</div>

	<div class="relative w-full bg-lightGray-300 dark:bg-customGray-900 rounded-md mb-2.5">
		{#if system}
			<div
				class="text-xs absolute left-2 top-1 text-lightGray-100/50 dark:text-customGray-100/50">{$i18n.t('System prompt')}</div>
		{/if}
		<textarea
			bind:value={system}
			placeholder={$i18n.t('System prompt')}
			class="px-2.5 py-2 text-sm {system ? "pt-4" : "pt-2"} text-lightGray-100 placeholder:text-lightGray-100 w-full h-20 bg-transparent dark:text-white dark:placeholder:text-customGray-100 outline-none"
					rows="4"
				/>
			</div>
	<div class="text-xs text-gray-600 dark:text-customGray-100/50 mb-5">
		<div>
			{$i18n.t('Adding a system prompt shapes LLM responses to better fit specific objectives.')}
		</div>
	</div>


	<div class="mb-2.5">
		<div
			class="flex items-center justify-between mb-1 w-full bg-lightGray-300 dark:bg-customGray-900 rounded-md h-12 px-2.5 py-2">

			<div class="text-sm text-lightGray-100 dark:text-customGray-100">
				{$i18n.t('Memory')}
			</div>

			<div class="">
				<Switch
					bind:state={enableMemory}
					on:change={async () => {
								saveSettings({ memory: enableMemory });
							}}
				/>
			</div>
		</div>
	</div>

	<div class="text-xs text-gray-600 dark:text-customGray-100/50">
		<div>
			{$i18n.t(
				"You can personalize your interactions with LLMs by adding memories through the 'Manage' button below, making them more helpful and tailored to you."
			)}
		</div>
	</div>

	<div class="mt-3 mb-1 ml-1">
		<button
			type="button"
			class=" text-xs w-[132px] h-10 px-3 py-2 transition rounded-lg bg-lightGray-300 border-lightGray-400 text-lightGray-100 font-medium hover:bg-lightGray-700 dark:bg-customGray-900 dark:hover:bg-customGray-950 dark:text-customGray-200 border dark:border-customGray-700 flex justify-center items-center"
			on:click={() => {
						showManageModal = true;
					}}
		>
			{$i18n.t('Manage')}
		</button>
	</div>
{/if}
</div>

<div class="flex justify-end pt-3 text-sm font-medium">
	<button
		class=" text-xs w-[168px] h-10 px-3 py-2 transition rounded-lg bg-lightGray-300 border-lightGray-400 text-lightGray-100 font-medium hover:bg-lightGray-700 dark:bg-customGray-900 dark:hover:bg-customGray-950 dark:text-customGray-200 border dark:border-customGray-700 flex justify-center items-center"
		type="submit"
		on:click={() => {
				saveSettings({
					system: system !== '' ? system : undefined
				});
				dispatch('save');
			}}
	>
		{$i18n.t('Save')}
	</button>
</div>
</div>
