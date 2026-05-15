export type WebSearchSource = {
	type: 'web_search';
	title: string;
	url: string;
	domain: string;
	snippet: string; // Currently unused, we might display cited_text snippets in the future
	queries?: string[];
};

export type RagSource = {
	type: 'rag';
	name: string;
	file_id: string;
	snippets: string[];
	scores: number[];
};

export type Source = WebSearchSource | RagSource;

// LEGACY ADAPTER — safe to remove once chats older than ~3 months are no longer displayed
function isLegacySource(s: any): boolean {
	return s != null && 'source' in s && s.source !== null && typeof s.source === 'object';
}

export function normalizeSource(s: any): Source {
	if (!isLegacySource(s)) return s as Source;

	if (s.type === 'web_search') {
		return {
			type: 'web_search',
			title: s.source?.name ?? '',
			url: s.source?.url ?? s.metadata?.[0]?.source ?? '',
			domain: s.metadata?.[0]?.domain ?? '',
			snippet: '',
			queries: s.metadata?.[0]?.used_queries,
		};
	}

	return {
		type: 'rag',
		name: s.source?.name ?? '',
		file_id: s.metadata?.[0]?.source ?? '',
		snippets: s.document ?? [],
		scores: s.distances ?? [],
	};
}

export function normalizeSources(sources: any[]): Source[] {
	return sources.map(normalizeSource);
}

export function getSourceIds(sources: any[]): string[] {
	return normalizeSources(sources).flatMap((s) => {
		if (s.type === 'rag') return s.file_id ? [s.file_id] : [];
		if (s.type === 'web_search') return s.url ? [s.url] : [];
		return [];
	});
}
