<script lang="ts">
	export let className = 'size-4';
	export let color = 'currentColor';
	export let flipped = false;
</script>

<svg
	class={className}
	viewBox="0 0 9 9"
	style={flipped ? 'transform: scaleY(-1);' : ''}
	fill="none"
	xmlns="http://www.w3.org/2000/svg"
>
	<path
		d="M7.3973 2.3537L4.53925 5.21174L2.85805 3.53054L0.672485 5.71611"
		stroke={color}
		stroke-width="0.672481"
		stroke-linecap="round"
		stroke-linejoin="round"
	/>
	<path
		d="M5.37988 2.3537H7.39733V4.37114"
		stroke={color}
		stroke-width="0.672481"
		stroke-linecap="round"
		stroke-linejoin="round"
	/>
</svg>
