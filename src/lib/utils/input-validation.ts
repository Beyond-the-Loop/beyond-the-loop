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

export function isBusinessEmail(email: string): boolean {
	const domain = email.split('@')[1]?.toLowerCase();
	return !!domain && !BLOCKED_EMAIL_DOMAINS.has(domain);
}
