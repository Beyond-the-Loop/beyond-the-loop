<script>
	import { marked } from 'marked';
	import { replaceTokens, processResponseContent } from '$lib/utils';
	import { user } from '$lib/stores';
	import { setContext } from 'svelte';
	import { writable } from 'svelte/store';

	import markedExtension from '$lib/utils/marked/extension';
	import markedKatexExtension from '$lib/utils/marked/katex-extension';

	import MarkdownTokens from './Markdown/MarkdownTokens.svelte';
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();

	export let id;
	export let content;
	export let model = null;
	export let save = false;
	export let sources = null;

	export let sourceIds = [];
	export let onSourceClick = () => {};

	let tokens = [];

	const options = {
		throwOnError: false
	};

	const sourcesStore = writable(sources);
	setContext('web-search-sources', sourcesStore);
	$: sourcesStore.set(sources);

	function linkifyCitations(content, sources) {
		if (!content || !sources || sources.length === 0) return content;

		const citationRegex = /\[(\d+(?:,\s*\d+)*)\]/g;

		return content.replace(citationRegex, (match, indicesStr) => {
			const indices = indicesStr.split(',').map((s) => parseInt(s.trim(), 10));
			const firstIdx = indices[0] - 1;
			if (!sources[firstIdx]) return match;

			if (sources[firstIdx].type === 'web_search') {
				return `<cite data-idx="${indices.join(',')}"></cite>`;
			} else {
				// RAG and legacy sources: keep existing number-badge behaviour
				return ` [${match}](${sources[firstIdx].metadata[0].source} "${sources[firstIdx].source.name}")`;
			}
		});
	}

	marked.use(markedKatexExtension(options));
	marked.use(markedExtension(options));

	$: (async () => {
		if (content) {
			const processedContent = sources ? linkifyCitations(content, sources) : content;
			tokens = marked.lexer(
				replaceTokens(processResponseContent(processedContent), sourceIds, model?.name, `${$user?.first_name} ${$user?.last_name}`)
			);
		}
	})();
</script>

{#key id}
	<MarkdownTokens
		{tokens}
		{id}
		{save}
		{onSourceClick}
		on:update={(e) => {
			dispatch('update', e.detail);
		}}
		on:code={(e) => {
			dispatch('code', e.detail);
		}}
	/>
{/key}
