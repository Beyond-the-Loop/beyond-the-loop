/**
 * Email validation utilities (business email only)
 */

export type EmailValidationError = 'required' | 'invalid_format' | 'not_business';

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

function isValidEmailFormat(email: string): boolean {
	return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function isBusinessEmail(email: string): boolean {
	const domain = email.split('@')[1]?.toLowerCase();
	return !!domain && !BLOCKED_EMAIL_DOMAINS.has(domain);
}

/**
 * Validates email and returns error code or null
 */
export function validateEmail(email: string): EmailValidationError | null {
	if (!email || email.trim() === '') {
		return 'required';
	}

	if (!isValidEmailFormat(email)) {
		return 'invalid_format';
	}

	if (!isBusinessEmail(email)) {
		return 'not_business';
	}

	return null;
}

/**
 * Maps error code to default message (can be used directly or via i18n)
 */
export function getEmailErrorMessage(error: EmailValidationError): string {
	switch (error) {
		case 'required':
			return 'Please enter your email address.';
		case 'invalid_format':
			return 'Please enter a valid email address.';
		case 'not_business':
			return 'Please use your business email address.';
	}
}
