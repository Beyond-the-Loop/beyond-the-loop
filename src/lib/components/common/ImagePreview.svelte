<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { downloadImage } from '$lib/utils';
	import Download from '../icons/Download.svelte';

	export let show = false;
	export let src = '';
	export let alt = '';

	let mounted = false;

	let previewElement = null;

	type GalleryImage = { src: string; alt: string };

	let images: GalleryImage[] = [];
	let currentIndex = 0;

	// Click-to-zoom (magnifier that follows the cursor).
	let zoomed = false;
	let originX = 50;
	let originY = 50;

	$: current = images[currentIndex] ?? { src, alt };

	const collectImages = () => {
		const scope = document.getElementById('messages-container') ?? document;
		const els = Array.from(
			scope.querySelectorAll('img[data-cy="image"]')
		) as HTMLImageElement[];

		const seen = new Set<string>();
		const collected: GalleryImage[] = [];

		for (const el of els) {
			const s = el.getAttribute('src');
			if (!s || seen.has(s)) continue;
			seen.add(s);
			collected.push({ src: s, alt: el.getAttribute('alt') ?? '' });
		}

		if (collected.length === 0) {
			collected.push({ src, alt });
		}

		images = collected;
		const idx = images.findIndex((img) => img.src === src);
		currentIndex = idx >= 0 ? idx : 0;
	};

	const goTo = (index: number) => {
		if (images.length === 0) return;
		const count = images.length;
		currentIndex = ((index % count) + count) % count;
		zoomed = false;
	};

	const next = () => goTo(currentIndex + 1);
	const prev = () => goTo(currentIndex - 1);

	const handleKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'Escape') {
			show = false;
		} else if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
			event.preventDefault();
			next();
		} else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
			event.preventDefault();
			prev();
		}
	};

	const handleZoomMove = (event: MouseEvent) => {
		if (!zoomed) return;
		const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
		originX = ((event.clientX - rect.left) / rect.width) * 100;
		originY = ((event.clientY - rect.top) / rect.height) * 100;
	};

	onMount(() => {
		mounted = true;
	});

	$: if (show && previewElement) {
		document.body.appendChild(previewElement);
		window.addEventListener('keydown', handleKeyDown);
		document.body.style.overflow = 'hidden';
		collectImages();
	} else if (previewElement) {
		window.removeEventListener('keydown', handleKeyDown);
		document.body.removeChild(previewElement);
		document.body.style.overflow = 'unset';
	}

	onDestroy(() => {
		show = false;

		window.removeEventListener('keydown', handleKeyDown);
		document.body.style.overflow = 'unset';

		if (previewElement) {
			document.body.removeChild(previewElement);
		}
	});
</script>

{#if show}
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div
		bind:this={previewElement}
		class="modal fixed top-0 right-0 left-0 bottom-0 bg-black/100 text-white w-full min-h-screen h-screen flex z-[9999] overflow-hidden overscroll-contain"
	>
		<!-- Vertical thumbnail rail with all images of this chat -->
		{#if images.length > 1}
			<div
				class="hidden sm:flex flex-col shrink-0 w-36 h-full overflow-y-auto gap-3 p-4 border-r border-white/10"
			>
				{#each images as image, i}
					<button
						type="button"
						title={image.alt}
						aria-label={`Image ${i + 1}`}
						aria-current={i === currentIndex}
						class="relative shrink-0 w-full aspect-square rounded-xl overflow-hidden outline-none focus:outline-none transition-all duration-150 {i ===
						currentIndex
							? 'ring-2 ring-white ring-offset-2 ring-offset-black opacity-100'
							: 'opacity-50 hover:opacity-100'}"
						on:click={() => goTo(i)}
					>
						<img
							src={image.src}
							alt={image.alt}
							class="w-full h-full object-cover select-none"
							draggable="false"
						/>
					</button>
				{/each}
			</div>
		{/if}

		<div class="relative flex-1 min-w-0 h-full flex justify-center items-center p-6 sm:p-10">
			<!-- Top toolbar -->
			<div class="absolute top-0 left-0 w-full flex justify-between items-center select-none z-10 p-2">
				<div class="px-3 py-2 text-sm text-white/70 tabular-nums">
					{#if images.length > 1}
						{currentIndex + 1} / {images.length}
					{/if}
				</div>

				<div class="flex items-center gap-1">
					<button
						class="p-3 rounded-full text-white/80 hover:text-white hover:bg-white/10 transition-colors outline-none focus:outline-none"
						aria-label="Download"
						on:click={() => {
							downloadImage(current.src);
						}}
					>
						<Download className="size-6" strokeWidth="2.0"/>
					</button>

					<button
						class="p-3 rounded-full text-white/80 hover:text-white hover:bg-white/10 transition-colors outline-none focus:outline-none"
						aria-label="Close"
						on:click={() => {
							show = false;
						}}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
							stroke-width="2"
							stroke="currentColor"
							class="w-6 h-6"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			</div>

			<!-- Prev / Next controls -->
			{#if images.length > 1}
				<button
					type="button"
					aria-label="Previous image"
					class="absolute left-4 top-1/2 -translate-y-1/2 z-10 p-3 rounded-full bg-white/10 hover:bg-white/20 transition-colors outline-none focus:outline-none"
					on:click={prev}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="2"
						stroke="currentColor"
						class="w-6 h-6"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
					</svg>
				</button>

				<button
					type="button"
					aria-label="Next image"
					class="absolute right-4 top-1/2 -translate-y-1/2 z-10 p-3 rounded-full bg-white/10 hover:bg-white/20 transition-colors outline-none focus:outline-none"
					on:click={next}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="2"
						stroke="currentColor"
						class="w-6 h-6"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
					</svg>
				</button>
			{/if}

			<!-- Active image (click to toggle zoom, move cursor to pan) -->
			<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
			<img
				src={current.src}
				alt={current.alt}
				class="mx-auto max-h-full max-w-full object-scale-down select-none transition-transform duration-150 {zoomed
					? 'cursor-zoom-out scale-[2]'
					: 'cursor-zoom-in'}"
				style={zoomed ? `transform-origin: ${originX}% ${originY}%;` : ''}
				draggable="false"
				on:click={() => (zoomed = !zoomed)}
				on:mousemove={handleZoomMove}
			/>
		</div>
	</div>
{/if}
