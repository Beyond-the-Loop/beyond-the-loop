import { WEBUI_API_BASE_URL } from '$lib/constants';

export type PIISpan = {
	start: number;
	end: number;
	entity_type: string;
	original: string;
	score: number;
};

export type PIIAnalyzeResponse = {
	spans: PIISpan[];
};

export const analyzePII = async (
	token: string,
	text: string,
	signal?: AbortSignal
): Promise<PIIAnalyzeResponse> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/pii/analyze`, {
		method: 'POST',
		signal,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		},
		body: JSON.stringify({ text })
	});

	if (!res.ok) {
		throw await res.json().catch(() => ({ detail: res.statusText }));
	}

	return res.json();
};
