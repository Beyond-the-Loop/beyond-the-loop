<script lang="ts">
	import mermaid from 'mermaid';

	import { v4 as uuidv4 } from 'uuid';

 import { getContext, onMount, createEventDispatcher } from 'svelte';
	import { copyToClipboard } from '$lib/utils';

	import 'highlight.js/styles/github-dark.min.css';

	import CodeEditor from '$lib/components/common/CodeEditor.svelte';
	import SvgPanZoom from '$lib/components/common/SVGPanZoom.svelte';
	import { toast } from 'svelte-sonner';
	import CopyMessageIcon from '$lib/components/icons/CopyMessageIcon.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let id = '';


export let token;
export let lang = '';
export let code = '';

	export let className = 'my-2';
	export let editorClassName = '';
	export let stickyButtonsClassName = 'top-8';

	let _code = '';
	$: if (code) {
		updateCode();
	}

	const updateCode = () => {
		_code = code;
	};

	let _token = null;

	let mermaidHtml = null;

	const saveCode = () => {
		code = _code;
		dispatch('save', code);
	};

	const copyCode = async () => {
		await copyToClipboard(code);
		toast.success($i18n.t('Copied code to clipboard!'));
	};

	const drawMermaidDiagram = async () => {
		try {
			if (await mermaid.parse(code)) {
				const { svg } = await mermaid.render(`mermaid-${uuidv4()}`, code);
				mermaidHtml = svg;
			}
		} catch (error) {
			console.log('Error:', error);
		}
	};

	const render = async () => {
		if (lang === 'mermaid' && (token?.raw ?? '').slice(-4).includes('```')) {
			(async () => {
				await drawMermaidDiagram();
			})();
		}
	};

	$: if (token) {
		if (JSON.stringify(token) !== JSON.stringify(_token)) {
			_token = token;
		}
	}

	$: if (_token) {
		render();
	}

	$: dispatch('code', { lang, code });

	// Attributes no longer drive execution; view-only mode.

	onMount(async () => {
		console.log('codeblock', lang, code);

		if (lang) {
			dispatch('code', { lang, code });
		}
		if (document.documentElement.classList.contains('dark')) {
			mermaid.initialize({
				startOnLoad: true,
				theme: 'dark',
				securityLevel: 'loose'
			});
		} else {
			mermaid.initialize({
				startOnLoad: true,
				theme: 'default',
				securityLevel: 'loose'
			});
		}
	});
</script>

<div>
	<div class="relative {className} flex flex-col rounded-lg" dir="ltr">
		{#if lang === 'mermaid'}
			{#if mermaidHtml}
				<SvgPanZoom
					className=" border border-gray-50 dark:border-gray-850 rounded-lg max-h-fit overflow-hidden"
					svg={mermaidHtml}
					content={_token.text}
				/>
			{:else}
				<pre class="mermaid">{code}</pre>
			{/if}
		{:else}
			<div class="text-lightGray-100 absolute pl-4 py-1 top-2 text-sm font-medium dark:text-customGray-100">
				{lang}
			</div>

  	<div
				class="{stickyButtonsClassName} mb-1 py-1 pr-2.5 flex items-center justify-end z-10 text-sm text-black dark:text-white"
			>
				<div class="flex items-center gap-1 translate-y-[5px]">
					<Tooltip content={$i18n.t('Copy')}>
						<button
							class="copy-code-button bg-transparent border-none hover:bg-lightGray-300 dark:hover:bg-customGray-950 transition rounded-md px-1.5 py-1.5 mb-0.5"
							on:click={copyCode}>
								<CopyMessageIcon/>
								</button
							>
					</Tooltip>
				</div>
			</div>

			<div
				class="language-{lang} rounded-t-lg border border-lightGray-400 dark:border-customGray-700 -mt-8 {editorClassName ? editorClassName : 'rounded-b-lg'} overflow-hidden"
			>
				<div class=" pt-8 bg-lightGray-700 dark:bg-gray-850"></div>
				<CodeEditor
					value={code}
					{id}
					{lang}
					on:save={() => {
						saveCode();
					}}
					on:change={(e) => {
						_code = e.detail.value;
					}}
				/>
			</div>

			<!-- View-only: no execution output or plots -->
		{/if}
	</div>
</div>
