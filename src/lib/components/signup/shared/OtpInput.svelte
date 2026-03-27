<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let length = 6;
	export let value = '';

	const dispatch = createEventDispatcher<{ change: string }>();

	let digits: string[] = Array(length).fill('');
	let refs: HTMLInputElement[] = [];

	function syncValue() {
		value = digits.join('');
		dispatch('change', value);
	}

	function handleInput(i: number) {
		digits[i] = digits[i].replace(/\D/g, '').slice(0, 1);
		if (digits[i] && i < length - 1) {
			refs[i + 1]?.focus();
		}
		syncValue();
	}

	function handleKeydown(e: KeyboardEvent, i: number) {
		if (e.key === 'Backspace' && !digits[i] && i > 0) {
			refs[i - 1]?.focus();
		}
	}

	function handlePaste(e: ClipboardEvent) {
		e.preventDefault();
		const pasted = e.clipboardData?.getData('text')?.replace(/\D/g, '').slice(0, length) || '';
		for (let i = 0; i < length; i++) {
			digits[i] = pasted[i] || '';
		}
		digits = digits;
		syncValue();
		refs[Math.min(pasted.length, length - 1)]?.focus();
	}
</script>

<div class="flex gap-1.5 sm:gap-2">
	{#each digits as _, i}
		<input
			bind:this={refs[i]}
			bind:value={digits[i]}
			on:input={() => handleInput(i)}
			on:keydown={(e) => handleKeydown(e, i)}
			on:paste={handlePaste}
			type="text"
			inputmode="numeric"
			maxlength="1"
			class="aspect-square h-auto w-0 min-w-0 flex-1 rounded-lg border border-gray-200 bg-white text-center text-base font-medium text-[#16181D] outline-none transition focus:border-customBlue-500 focus:ring-1 focus:ring-customBlue-500 sm:text-lg dark:border-customGray-700 dark:bg-customGray-900 dark:text-customGray-100"
		/>
	{/each}
</div>
