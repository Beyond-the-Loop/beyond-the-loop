import i18n from '$lib/i18n';

export enum EmailValidationErrorMessage {
  NotBusiness = 'Please use your business email address.',
}

const BLOCKED_EMAIL_DOMAINS = new Set([
	'gmail.com',
	'googlemail.com',
	'yahoo.com',
	'yahoo.de',
	'hotmail.com',
	'hotmail.de',
	'outlook.com',
	'outlook.de',
	'live.com',
	'live.de',
	'aol.com',
	'icloud.com',
	'me.com',
	'mac.com',
	'gmx.de',
	'gmx.net',
	'web.de',
	't-online.de',
	'freenet.de',
	'mail.com',
	'protonmail.com',
	'proton.me',
	'zoho.com'
]);

export function isRequired(value: string): boolean {
	return !!value.trim();
}

export function isBusinessEmail(email: string): boolean {
	const domain = email.split('@')[1]?.toLowerCase();
	return !!domain && !BLOCKED_EMAIL_DOMAINS.has(domain);
}

export function isValidPassword(value: string): { valid: boolean; error: string } {
	const trimmed = value.trim();

	if (!trimmed) {
		return { valid: false, error: 'Password is required.' };
	}

	const strongPasswordRegex = /^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{8,}$/;

	if (!strongPasswordRegex.test(trimmed)) {
		return { valid: false, error: 'Password must be 8+ characters, with a number, capital letter, and symbol.' };
	}

	return { valid: true, error: '' };
}


export function isValidPhoneNumber(value: string): { valid: boolean; error: string } {
	const trimmed = value.trim();

	if (!trimmed) {
		return { valid: false, error: 'Phone number is required.' };
	}

	if (/[^\d+\s\-()]/.test(trimmed)) {
		return { valid: false, error: 'Phone number contains invalid characters.' };
	}

	if (!trimmed.startsWith('+')) {
		return { valid: false, error: 'Phone number must start with a country code (e.g. +49).' };
	}

	const digits = trimmed.replace(/\D/g, '');

	if (digits.length < 7) {
		return { valid: false, error: 'Phone number is too short.' };
	}

	if (digits.length > 15) {
		return { valid: false, error: 'Phone number is too long.' };
	}

	return { valid: true, error: '' };
}


export function validateEmailStep(data: { email: string }): { email?: string } | null {
	const errors: { email?: string } = {};

	if (!isRequired(data.email)) {
		errors.email = 'Please enter your email address.';
	} else if (!isBusinessEmail(data.email)) {
		errors.email = 'Please use your business email address.';
	}

	return Object.keys(errors).length ? errors : null;
}

export function validateVerifyStep(data: { code: string; codeLength: number }): { code?: string } | null {
	if (data.code.length !== data.codeLength) {
		return { code: 'Please enter the complete 9-digit code.' };
	}
	return null;
}

export function validatePersonalStep(data: {
	first_name: string;
	last_name: string;
	position: string;
	phone: string;
}): { firstName?: string; lastName?: string; position?: string; phone?: string } | null {
	const errors: { firstName?: string; lastName?: string; position?: string; phone?: string } = {};

	if (!isRequired(data.first_name)) errors.firstName = 'First name is required.';
	if (!isRequired(data.last_name)) errors.lastName = 'Last name is required.';
	if (!isRequired(data.position)) errors.position = 'Position is required.';

	const phoneResult = isValidPhoneNumber(data.phone);
	if (!phoneResult.valid) errors.phone = phoneResult.error;

	return Object.keys(errors).length ? errors : null;
}

export function validateWorkspaceStep(data: {
	workspace_name: string;
	subdomain: string;
}): { workspaceName?: string; subdomain?: string } | null {
	const errors: { workspaceName?: string; subdomain?: string } = {};

	if (!isRequired(data.workspace_name)) errors.workspaceName = 'Workspace name is required.';
	if (!isRequired(data.subdomain)) errors.subdomain = 'Subdomain is required.';

	return Object.keys(errors).length ? errors : null;
}
