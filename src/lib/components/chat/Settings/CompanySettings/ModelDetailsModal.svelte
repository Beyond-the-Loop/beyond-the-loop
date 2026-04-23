<script lang="ts">
	import Modal from '$lib/components/common/Modal.svelte';
	import ModelDetailsCard from '../../ModelSelector/ModelDetailsCard.svelte';

	export let show = false;
	export let model: any = null;
</script>

<Modal
	size="sm"
	bind:show
	className="dark:bg-customGray-800 rounded-2xl"
	containerClassName="bg-lightGray-250/50 dark:bg-[#1D1A1A]/50 backdrop-blur-[7.44px]"
>
	<div class="bg-lightGray-550 dark:bg-customGray-800 rounded-xl p-5 text-lightGray-100 dark:text-white">
		<ModelDetailsCard name={model?.name ?? ''} showClose onClose={() => (show = false)} />
	</div>
</Modal>
