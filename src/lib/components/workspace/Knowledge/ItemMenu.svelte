<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { flyAndScale } from '$lib/utils/transitions';
	import { getContext, createEventDispatcher } from 'svelte';
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Pencil from '$lib/components/icons/Pencil.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Tags from '$lib/components/chat/Tags.svelte';
	import Share from '$lib/components/icons/Share.svelte';
	import ArchiveBox from '$lib/components/icons/ArchiveBox.svelte';
	import DocumentDuplicate from '$lib/components/icons/DocumentDuplicate.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';
	import ArrowUpCircle from '$lib/components/icons/ArrowUpCircle.svelte';
	import EllipsisHorizontal from '$lib/components/icons/EllipsisHorizontal.svelte';
	import DeleteIcon from '$lib/components/icons/DeleteIcon.svelte';
	import MessageEditIcon from '$lib/components/icons/MessageEditIcon.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let onClose: Function = () => {};

	export let item;

	let show = false;
</script>

<Dropdown
	bind:show
	on:change={(e) => {
		if (e.detail === false) {
			dispatch('closeMenu');
			onClose();
		}
	}}
	align="end"
>
		<slot
			><button
				class="self-center w-fit text-sm px-0.5 h-[21px] dark:text-white rounded-md"
				type="button"
				on:click={(e) => {
					e.stopPropagation();
					dispatch('openMenu');
					show = true;
				}}
			>
				<EllipsisHorizontal className="size-5" />
			</button>
		</slot>


	<div slot="content">
		<DropdownMenu.Content
			class="w-full max-w-[160px] rounded-lg px-1 py-1.5 border border-lightGray-400 dark:border-customGray-700 z-50 bg-gray-50 dark:bg-customGray-900 dark:text-white shadow"
			sideOffset={-2}
			side="bottom"
			align="end"
			transition={flyAndScale}
		>	
			<DropdownMenu.Item>
				<a
					class="flex w-full items-center gap-2 self-center text-xs font-medium text-lightGray-100 dark:text-customGray-100 px-3 py-2 dark:hover:bg-customGray-950 dark:hover:text-white hover:bg-lightGray-700 rounded-md"
					type="button"
					href={`/workspace/knowledge/${item.id}`}
				>
					<MessageEditIcon width={14} height={13}/>
					<div class="flex items-center">{$i18n.t('Edit')}</div>
				</a>
			</DropdownMenu.Item>
			<DropdownMenu.Item
				class="flex  gap-2  items-center px-3 py-2 text-xs font-medium text-lightGray-100 dark:text-customGray-100 cursor-pointer hover:bg-lightGray-700 dark:hover:bg-customGray-950 rounded-md dark:hover:text-white"
				on:click={() => {
					dispatch('delete');
				}}
			>
				<DeleteIcon />
				<div class="flex items-center">{$i18n.t('Delete')}</div>
			</DropdownMenu.Item>
		</DropdownMenu.Content>
	</div>
</Dropdown>
