import { normalizeEmailValidationError } from '$lib/utils/input-validation';

const DETAILED_INVALID_EMAIL_FORMAT =
	"The email format you entered is invalid. Please double-check and make sure you're using a valid email address (e.g., yourname@example.com).";

type TranslateFn = (key: string) => string;

export function translateInviteError(error: unknown, t: TranslateFn): string {
	if (typeof error !== 'string') return t('An error occurred.');

	return error
		.replace('No invitees provided', t('No invitees provided'))
		.replace(
			'No users were invited. The following emails have issues:',
			t('No users were invited. The following emails have issues:')
		)
		.replace(/ is invalid\. /g, ` ${t('is invalid.')} `)
		.replace(
			/ is already associated with another company\./g,
			` ${t('is already associated with another company.')}`
		)
		.replace(
			new RegExp(
				DETAILED_INVALID_EMAIL_FORMAT.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'),
				'g'
			),
			t(normalizeEmailValidationError(DETAILED_INVALID_EMAIL_FORMAT))
		)
		.replace(
			/Please use your business email address\./g,
			t(normalizeEmailValidationError('Please use your business email address.'))
		);
}
