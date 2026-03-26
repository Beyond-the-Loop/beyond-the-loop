<script lang="ts">
	export let quote: string;
	export let name: string;
	export let role: string;
	export let initials: string;
	export let color: string;
</script>

<div class="flex flex-col justify-between rounded-xl border border-gray-200 bg-white p-5 dark:border-customGray-700 dark:bg-customGray-800">
	<p class="text-sm leading-relaxed text-[#16181D] dark:text-customGray-100">
		&bdquo;{quote}&ldquo;
	</p>
	<div class="mt-4 flex items-center gap-3">
		<div
			class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
			style="background-color: {color}"
		>
			{initials}
		</div>
		<div class="min-w-0">
			<p class="truncate text-sm font-semibold text-[#16181D] dark:text-customGray-100">{name}</p>
			<p class="truncate text-xs text-[#666666] dark:text-customGray-300">{role}</p>
		</div>
	</div>
</div>
