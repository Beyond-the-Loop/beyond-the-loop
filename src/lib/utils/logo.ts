import { WEBUI_API_BASE_URL } from '$lib/constants';

/**
 * Fetches company logo by email domain via backend endpoint.
 * Returns a base64 data URL if found, or empty string on failure.
 */
export async function fetchLogoByEmail(email: string): Promise<string> {
	try {
		const res = await fetch(
			`${WEBUI_API_BASE_URL}/companies/logo?email=${encodeURIComponent(email)}`
		);
		if (!res.ok) return '';
		const data = await res.json();
		return data.logo || '';
	} catch {
		return '';
	}
}
