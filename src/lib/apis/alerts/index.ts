import type { Alert } from '$lib/types';
import { WEBUI_BASE_URL } from '$lib/constants';

export const getAlert = async (): Promise<Alert> => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/alert`)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};