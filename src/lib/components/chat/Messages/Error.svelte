<script lang="ts">
	import Info from '$lib/components/icons/Info.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	export let content: unknown = '';

	// Strip the generic prefix added by handleOpenAIError so only the technical detail shows.
	// Legacy chats may have persisted non-string values (e.g. `{}`) via Chat.svelte's
	// `error = { content: error }` catch branches; coerce so the panel never crashes.
	$: contentString =
		typeof content === 'string'
			? content
			: content == null
				? ''
				: (() => {
						try {
							return JSON.stringify(content);
						} catch {
							return String(content);
						}
					})();
	$: technicalDetail = contentString.includes('\n')
		? contentString.split('\n').slice(1).join('\n').trim()
		: contentString;
</script>

<div class="flex my-2 gap-2.5 border px-4 py-3 border-red-600/10 bg-red-600/10 rounded-lg">
	<div class=" self-start mt-0.5">
		{#if technicalDetail}
			<Tooltip content={technicalDetail} placement="top">
				<Info className="size-5 text-red-700 dark:text-red-400 " />
			</Tooltip>
		{:else}
			<Info className="size-5 text-red-700 dark:text-red-400" />
		{/if}
	</div>

	<div class=" self-center text-sm">
		Es ist ein Fehler aufgetreten, bitte probiere es später nochmal.
	</div>
</div>
