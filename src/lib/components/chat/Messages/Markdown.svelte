<script>
	import { marked } from 'marked';
	import { replaceTokens, processResponseContent } from '$lib/utils';
	import { user } from '$lib/stores';

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

	// Function to handle citation linking
	function linkifyCitations(content, sources) {
		if (!content || !sources || sources.length === 0) return content;

		// Matches both [1] and grouped [1, 3, 7] markers
		const citationRegex = /\[(\d+(?:,\s*\d+)*)\]/g;

		// Replace markers with special tokens that can be processed by the markdown renderer
		return content.replace(citationRegex, (match, indicesStr) => {
			const indices = indicesStr.split(',').map((s) => parseInt(s.trim(), 10));
			const firstIdx = indices[0] - 1;
			if (!sources[firstIdx]) return match;

			if (sources[firstIdx].type === 'web_search') {
				const validSources = indices.map((i) => sources[i - 1]).filter(Boolean);
				const href = validSources[0].source?.url || validSources[0].metadata?.[0]?.source;
				if (!href) return match;

				// Encode domain~~title~~url per source, "|||" between sources
				const encoded = validSources
					.map((s) => {
						const domain = (s.metadata?.[0]?.domain || s.source?.name || '?').replace(/~~/g, ' ');
						const title = (s.source?.name || '').replace(/~~/g, ' ').replace(/\|\|\|/g, ' ');
						const url = s.source?.url || s.metadata?.[0]?.source || '';
						return `${domain}~~${title}~~${url}`;
					})
					.join('|||');

				return ` [ref](${href} "__CITE__:${encoded}")`;
			} else {
				// RAG and legacy sources: keep existing number-badge behaviour
				if (sources[firstIdx]) {
					return ` [${match}](${sources[firstIdx].metadata[0].source} "${sources[firstIdx].source.name}")`;
				}
				return match;
			}
		});
	}

	marked.use(markedKatexExtension(options));
	marked.use(markedExtension(options));

	$: (async () => {
		if (content) {
			// Process citations before passing to marked lexer
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
