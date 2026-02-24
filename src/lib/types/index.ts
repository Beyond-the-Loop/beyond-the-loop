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

export type ChatMessage = {
	parentId: string | null;
	id: string;
	childrenIds: string[];
	role: 'user' | 'assistant' | 'system';
	content: string;
	model: string;
	modelName: string;
	sources: string[];
	modelIdx: number;
	userContext: any | null;
	timestamp: number;
};

export type ChatHistory = {
	currentId: string | null;
	messages: Record<string, ChatMessage>;
};

