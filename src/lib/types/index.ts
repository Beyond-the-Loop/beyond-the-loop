export type Banner = {
	id: string;
	type: string;
	title?: string;
	content: string;
	url?: string;
	dismissible?: boolean;
	timestamp: number;
};

export enum TTS_RESPONSE_SPLIT {
	PUNCTUATION = 'punctuation',
	PARAGRAPHS = 'paragraphs',
	NONE = 'none'
}

export type Message = {  
    parentId: string | null;  
    id: string; 
    childrenIds: string[];  
    role: 'user' | 'assistant' | 'system';  
    content: string;  
    model: string;  
    modelName: string;  
    modelIdx: number;  
    userContext: any | null;  
    timestamp: number;
};

export type History = {
    currentId: string | null;
    messages: Record<string, Message>;
};

