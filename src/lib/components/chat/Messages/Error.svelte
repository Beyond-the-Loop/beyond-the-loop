<script lang="ts">
	import Info from '$lib/components/icons/Info.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	export let content = '';

	// Strip the generic prefix added by handleOpenAIError so only the technical detail shows
	$: technicalDetail = content.includes('\n') ? content.split('\n').slice(1).join('\n').trim() : content;
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
