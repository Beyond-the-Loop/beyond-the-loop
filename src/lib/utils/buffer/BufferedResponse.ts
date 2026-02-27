import type { ChatMessage, ChatHistory } from "$lib/types/index.ts";

type BufferedResponseHook = {
    onCommit: (message: ChatMessage) => void;
};

export class BufferedResponse {
    private buffer: string = '';
    private renderTimeout: ReturnType<typeof setTimeout> | null = null;

    constructor(
        private message: ChatMessage,
        private history: ChatHistory,
        private hook: BufferedResponseHook
    ) { }

    add_content(content: string) {
        this.buffer += content;
        if (this.renderTimeout === null) {
            this.render();
        }
    }

		add_sources(sources: string[]) {
			this.message.sources = sources;
    }

    flushImmediate(content: string) {
        this.message.content = content;
        this.buffer = '';
        this.commit();
    }

    stop() {
        if (this.renderTimeout) {
            clearTimeout(this.renderTimeout);
            this.renderTimeout = null;
        }
        this.buffer = '';
    }

    private render = () => {
        if (this.buffer.length === 0) {
            this.renderTimeout = setTimeout(this.render, 100);
            return;
        }

        const charPerUpdate = Math.max(0.5, 0.5 + 4*0.015 * (this.buffer.length));
        const rate = charPerUpdate / 32;
        const n = Math.round(charPerUpdate + 0.49);
        const t = n / rate;
        const msUntilUpdate = Math.max(32, Math.min(64, Math.round(t)));

        for (let i = 0; i < charPerUpdate && this.buffer.length > 0; i++) {
            this.message.content += this.buffer[0];
            this.buffer = this.buffer.substring(1);
        }

        this.commit();

        this.renderTimeout = setTimeout(this.render, msUntilUpdate);
    };

    private commit() {
        this.history.messages[this.message.id] = this.message;
        this.hook.onCommit(this.message);
    }
}
