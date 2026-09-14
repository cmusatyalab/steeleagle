import { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble.jsx';
import { AI_DISCLAIMER, SUGGESTED_PROMPTS } from '../data/constants.js';

// Scrollable message log. Uses a native scroll container (not VirtualScroller)
// because chat bubbles have variable, dynamic heights. Auto-scrolls to the
// bottom on new messages unless the user has scrolled up to read history.
function MessageList({ messages, onApply, onSuggestion }) {
    const scrollRef = useRef(null);
    const bottomRef = useRef(null);
    const stickToBottom = useRef(true);

    function handleScroll() {
        const el = scrollRef.current;
        if (!el) return;
        const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        stickToBottom.current = distanceFromBottom < 80;
    }

    useEffect(() => {
        if (stickToBottom.current) {
            bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages]);

    const hasConversation = messages.some((m) => m.role !== 'system');

    return (
        <div className="se-chat-messages" ref={scrollRef} onScroll={handleScroll}>
            {messages.map((m) => (
                <MessageBubble key={m.id} message={m} onApply={onApply} />
            ))}

            {!hasConversation && (
                <div className="se-chat-suggestions">
                    <div className="se-chat-suggestions__label">Try asking</div>
                    <div className="se-chat-suggestions__grid">
                        {SUGGESTED_PROMPTS.map((prompt) => (
                            <button
                                key={prompt}
                                type="button"
                                className="se-chat-suggestion"
                                onClick={() => onSuggestion?.(prompt)}
                            >
                                {prompt}
                            </button>
                        ))}
                    </div>
                    <p className="se-chat-suggestions__disclaimer">{AI_DISCLAIMER}</p>
                </div>
            )}

            <div ref={bottomRef} />
        </div>
    );
}

export default MessageList;
