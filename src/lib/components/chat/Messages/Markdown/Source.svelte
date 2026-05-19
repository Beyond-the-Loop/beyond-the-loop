<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { Source } from '$lib/utils/sources';

	export let token;
	export let onClick: Function = () => {};

	const sourcesStore = getContext<Writable<Source[] | null>>('web-search-sources');

	let id = '';
	function extractDataAttribute(input) {
		const match = input.match(/data="([^"]*)"/);
		return match ? match[1] : null;
	}

	$: id = extractDataAttribute(token.text);

	$: displayName = (() => {
		if (!id) return id;
		const source = ($sourcesStore ?? []).find((s) => s.type === 'rag' && s.file_id === id);
		return source?.name || id;
	})();
</script>

<button
	class="text-xs font-medium w-fit translate-y-[2px] px-2 py-0.5 dark:bg-white/5 dark:text-white/60 dark:hover:text-white bg-gray-50 text-black/60 hover:text-black transition rounded-lg"
	on:click={() => {
		onClick(id);
	}}
>
	<span class="line-clamp-1">
		{displayName}
	</span>
</button>
