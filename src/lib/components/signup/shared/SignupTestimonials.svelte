<script lang="ts">
	import TestimonialCard from './TestimonialCard.svelte';
	import StatsRow from './StatsRow.svelte';

	interface Testimonial {
		quote: string;
		name: string;
		role: string;
		color: string;
	}

	const AVATAR_PALETTE = [
		'#2563EB', // blue
		'#F59E0B', // amber
		'#7C3AED', // violet
		'#059669', // emerald
		'#E11D48', // rose
		'#0D9488'  // teal
	] as const;

	function getInitials(name: string): string {
		return name
			.split(' ')
			.map((part) => part[0])
			.join('')
			.toUpperCase()
			.slice(0, 2);
	}

	const testimonials: Testimonial[] = [
		{
			quote: 'Wir erleben eine spürbare Zeitersparnis, weil alle KI-Tools, Wissen, Chats und Zuständigkeiten zentral verfügbar sind.',
			name: 'Stephan Sigloch',
			role: 'Geschäftsführer, KlickPiloten',
			color: AVATAR_PALETTE[0]
		},
		{
			quote: 'Beyond Chat ermöglicht uns einen schnellen und unkomplizierten Einstieg für alle Mitarbeitenden.',
			name: 'Sebastian Becker',
			role: 'Vertriebsleitung, Creditreform Hamburg',
			color: AVATAR_PALETTE[1]
		},
		{
			quote: 'Wir müssen keine Lizenzen mehr rationieren. Jetzt kann jeder im Team mit KI arbeiten. Sicher und zentral verwaltet.',
			name: 'Markus Oeller',
			role: 'Co-Geschäftsführer, 1SP Agency',
			color: AVATAR_PALETTE[2]
		},
		{
			quote: 'Beyond Chat ist für uns zum zentralen Produktivitätswerkzeug geworden, das wir im Arbeitsalltag bei vielfältigen Aufgaben einsetzen.',
			name: 'Alissa Steinseifer',
			role: 'Business Developerin, Schaffrath',
			color: AVATAR_PALETTE[3]
		},
		{
			quote: 'Wir sind bewusst von ChatGPT gewechselt – wegen besserem Datenschutz, mehr Flexibilität und echter technologischer Redundanz.',
			name: 'Patrick Bierhals',
			role: 'Executive Director, AI & Tech, Cobalt DE',
			color: AVATAR_PALETTE[4]
		},
		{
			quote: 'Durch unsere eigenen Assistenten spare ich pro LinkedIn-Post rund vier Stunden – das hat meinen kompletten Workflow revolutioniert.',
			name: 'Katharina Fiegen',
			role: 'Marketing & Communications, AI.GROUP',
			color: AVATAR_PALETTE[5]
		}
	];
</script>

<div class="flex min-h-screen flex-col justify-center bg-[#F7F7F8] px-10 py-12 dark:bg-customGray-900">
	<!-- Inhalte ausgeblendet – Struktur bleibt erhalten für spätere Inhalte -->
	<!-- <div class="mx-auto w-full max-w-[44rem]">
		<h2 class="text-2xl font-bold leading-tight tracking-tight text-[#16181D] dark:text-customGray-100">
			Geliebt von KMUs im gesamten Dachraum.
		</h2>
		<p class="mt-2 text-sm text-[#666666] dark:text-customGray-300">
			Über 500 Teams vertrauen auf Beyond the Loop für ihre tägliche Arbeit mit KI.
		</p>

		<div class="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
			{#each testimonials as testimonial}
				<TestimonialCard
					quote={testimonial.quote}
					name={testimonial.name}
					role={testimonial.role}
					initials={getInitials(testimonial.name)}
					color={testimonial.color}
				/>
			{/each}
		</div>

		<div class="mt-10 border-t border-gray-200 pt-8 dark:border-customGray-700">
			<StatsRow />
		</div>
	</div> -->
</div>
