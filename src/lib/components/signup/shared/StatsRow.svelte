<script lang="ts">
	const stats = [
		{ value: '500+', label: 'Teams' },
		{ value: '2M+', label: 'Nachrichten' },
		{ value: '99.9%', label: 'Uptime' }
	];
</script>

<div class="flex items-center justify-between">
	{#each stats as stat, i}
		<div class="flex flex-1 flex-col items-center text-center">
			<span class="text-xl font-bold text-[#16181D] dark:text-customGray-100">{stat.value}</span>
			<span class="mt-1 text-xs text-[#666666] dark:text-customGray-300">{stat.label}</span>
		</div>
		{#if i < stats.length - 1}
			<div class="h-10 w-px bg-gray-200 dark:bg-customGray-700"></div>
		{/if}
	{/each}
</div>
