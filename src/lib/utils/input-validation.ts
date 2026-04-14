export enum EmailValidationErrorMessage {
	Required = 'Please enter your email address.',
	InvalidFormat = 'Please enter a valid email address.',
	DetailedInvalidFormat = "The email format you entered is invalid. Please double-check and make sure you're using a valid email address (e.g., yourname@example.com).",
	NotBusiness = 'Please use your business email address.'
}

const EMAIL_VALIDATION_ERROR_ALIASES: Record<string, EmailValidationErrorMessage> = {
	'Invalid email format.': EmailValidationErrorMessage.InvalidFormat,
	'INVALID_EMAIL_FORMAT': EmailValidationErrorMessage.InvalidFormat,
	'NOT_BUSINESS_EMAIL': EmailValidationErrorMessage.NotBusiness,
	[EmailValidationErrorMessage.Required]: EmailValidationErrorMessage.Required,
	[EmailValidationErrorMessage.InvalidFormat]: EmailValidationErrorMessage.InvalidFormat,
	[EmailValidationErrorMessage.DetailedInvalidFormat]: EmailValidationErrorMessage.InvalidFormat,
	[EmailValidationErrorMessage.NotBusiness]: EmailValidationErrorMessage.NotBusiness
};

function extractErrorMessage(error: unknown): string {
	if (typeof error === 'string') return error;

	if (error && typeof error === 'object' && 'detail' in error) {
		const detail = (error as { detail?: unknown }).detail;
		if (typeof detail === 'string') return detail;
	}

	return '';
}

export function normalizeEmailValidationError(error: unknown): string {
	const message = extractErrorMessage(error);
	if (!message) return '';
	return EMAIL_VALIDATION_ERROR_ALIASES[message] ?? message;
}

export function isRequired(value: string): boolean {
	return !!value.trim();
}

const EMAIL_FORMAT_REGEX = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$/;

export function isValidEmail(email: string): { valid: boolean; error: string } {
	const trimmed = email.trim();
	if (!trimmed) return { valid: false, error: EmailValidationErrorMessage.Required };
	if (!EMAIL_FORMAT_REGEX.test(trimmed))
		return { valid: false, error: EmailValidationErrorMessage.InvalidFormat };
	return { valid: true, error: '' };
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
	const emailResult = isValidEmail(data.email);
	if (!emailResult.valid) return { email: emailResult.error };
	return null;
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
	password: string;
	position: string;
	phone: string;
}): { firstName?: string; lastName?: string; password?: string; position?: string; phone?: string } | null {
	const errors: { firstName?: string; lastName?: string; password?: string; position?: string; phone?: string } = {};

	if (!isRequired(data.first_name)) errors.firstName = 'First name is required.';
	if (!isRequired(data.last_name)) errors.lastName = 'Last name is required.';

	const pwResult = isValidPassword(data.password);
	if (!pwResult.valid) errors.password = pwResult.error;

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
