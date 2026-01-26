<script>
	import { marked } from 'marked';
	import { replaceTokens, processResponseContent } from '$lib/utils';
	import { user } from '$lib/stores';

	import markedExtension from '$lib/utils/marked/extension';
	import markedKatexExtension from '$lib/utils/marked/katex-extension';

	import MarkdownTokens from './Markdown/MarkdownTokens.svelte';
	import { createEventDispatcher } from 'svelte';
	import { fakeLexer } from './Markdown/FakeLexer.ts';

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
		
		// Regex to match citation markers like [1], [2], etc.
		const citationRegex = /\[(\d+)]/g;
		
		// Replace markers with special tokens that can be processed by the markdown renderer
		return content.replace(citationRegex, (match, number) => {
			const citationIndex = parseInt(number, 10) - 1; // Convert to 0-based index
			if (sources[citationIndex]) {
				// Create a special token with a data-citation attribute that will be recognized by the renderer
				return ` [${match}](${sources[citationIndex].source.name} "citation")`;
			}
			return match; // If no citation exists, keep it as is
		});
	}

	marked.use(markedKatexExtension(options));
	marked.use(markedExtension(options));
	const USE_MARKDOWN = true;
	$: (async () => {
		if (!content) return;

		const processed = replaceTokens(
			processResponseContent(content),
			sourceIds,
			model?.name,
			`${$user?.first_name} ${$user?.last_name}`
		);

		const t0 = performance.now();

		tokens = USE_MARKDOWN
			? marked.lexer(processed)
			: fakeLexer(processed);

		const t1 = performance.now();

		console.log(
			`[Markdown] ${USE_MARKDOWN ? 'marked.lexer' : 'fakeLexer'} took`,
			(t1 - t0).toFixed(2),
			'ms'
		);
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
