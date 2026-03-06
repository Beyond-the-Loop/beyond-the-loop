<script lang="ts">
	import { createEventDispatcher, tick } from 'svelte';
	import { Switch } from 'bits-ui';
	export let state = true;
	export let small = false;

	const dispatch = createEventDispatcher();

	$: dispatch('change', state);
</script>

<Switch.Root
	bind:checked={state}
	class="flex shrink-0 cursor-pointer items-center rounded-full px-[3px] mx-[1px] transition {small ? 'h-4 min-h-4 w-7' : 'h-5 min-h-5 w-9'} {state
		? 'bg-white'
		: 'bg-gray-200 dark:bg-transparent'} outline outline-1 outline-lightGray-400 dark:outline-gray-800"
>
	<Switch.Thumb
		class="pointer-events-none block shrink-0 rounded-full {small ? 'size-3' : 'size-4'} {state
		? 'bg-customBlue-600'
		: 'bg-white dark:bg-gray-200'} transition-transform {small ? 'data-[state=checked]:translate-x-2.5' : 'data-[state=checked]:translate-x-3.5'} data-[state=unchecked]:translate-x-0 data-[state=unchecked]:shadow-mini"
	/>
</Switch.Root>
