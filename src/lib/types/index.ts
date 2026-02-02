export type AlertType = 'info' | 'warning' | 'success';

export type Alert = {
	title: string,
	message: string,
	type: AlertType
};

export enum TTS_RESPONSE_SPLIT {
	PUNCTUATION = 'punctuation',
	PARAGRAPHS = 'paragraphs',
	NONE = 'none'
}
