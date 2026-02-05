// import type { Message } from '$lib/types/chat';

type History = {
    messages: Record<string | number, Message>;
};

type Hooks = {
    onCommit: (message: Message) => void;
};

export class BufferedResponse {
    private buffer = '';
    private renderTimeout: ReturnType<typeof setTimeout> | null = null;

    constructor(
        private message: Message,
        private history: History,
        private hooks: Hooks
        // private hooks: Hooks = {}
    ){}

    add(content: string) {
        this.buffer += content;
        if (this.renderTimeout === null) {
            this.render();
        }
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

        const charPerUpdate = Math.max(0.5, 0.5 + 0.015 * (this.buffer.length));
        const rate = charPerUpdate / 8;
        const n = Math.round(charPerUpdate + 0.49);
        const t = n / rate;
        const msUntilUpdate = Math.max(8, Math.min(16, Math.round(t)));

        for (let i = 0; i < charPerUpdate && this.buffer.length > 0; i++) {
            this.message.content += this.buffer[0];
            this.buffer = this.buffer.substring(1);
        }

        this.commit();

        this.renderTimeout = setTimeout(this.render, msUntilUpdate);
    };

    private commit() {
        this.history.messages[this.message.id] = this.message;
        this.hooks.onCommit(this.message);
    }
}
