// import type { Message } from '$lib/types/chat';

type History = {
    messages: Record<string | number, Message>;
};

type Hooks = {
    onUpdate?: (message: Message) => void;
    onSentence?: (id: string | number, sentence: string) => void;
    onScroll?: () => void;
    onCommit: (message: Message) => void;
};

export class BufferedResponse {
    private buffer = '';
    private renderTimeout: ReturnType<typeof setTimeout> | null = null;
    private charPerUpdate = 0;
    private msUntilUpdate = 0;

    constructor(
        private message: Message,
        private history: History,
        private hooks: Hooks
        // private hooks: Hooks = {}
    ) {}

    add(content: string) {
        this.buffer += content;
        this.charPerUpdate = Math.max(0.5, 0.5 + 0.015 * (this.buffer.length));
        const rate = this.charPerUpdate / 8;
        const n = Math.round(this.charPerUpdate + 0.49);
        const t = n / rate;
        this.msUntilUpdate = Math.max(8, Math.min(16, Math.round(t)));
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
        // console.log('rendering!');
        if (this.buffer.length === 0) {
            this.renderTimeout = setTimeout(this.render, 100);
            return;
        }

        console.log("msUntilUpdate: ", this.msUntilUpdate, " charPerUpdate: ", this.charPerUpdate, " buffer.length: ", this.buffer.length);

        for (let i = 0; i < this.charPerUpdate && this.buffer.length > 0; i++) {
            this.message.content += this.buffer[0];
            this.buffer = this.buffer.substring(1);
        }

        this.commit();

        this.renderTimeout = setTimeout(this.render, this.msUntilUpdate);
    };

    private commit() {
        this.history.messages[this.message.id] = this.message;
        // console.log('tippen')
        this.hooks.onUpdate?.(this.message);
        this.hooks.onScroll?.();
        this.hooks.onCommit(this.message);
    }
}
