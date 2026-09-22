import ReactMarkdown from 'react-markdown';
import { Avatar } from 'primereact/avatar';
import { classNames } from 'primereact/utils';
import ApplyActionCard from './ApplyActionCard.jsx';

function formatTime(ts) {
    try {
        return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return '';
    }
}

function TypingDots() {
    return (
        <span className="se-chat-typing" aria-label="Assistant is typing">
            <span />
            <span />
            <span />
        </span>
    );
}

/** Collapse excess blank lines so Markdown doesn't leave large empty gaps. */
function normalizeAssistantMarkdown(text) {
    return (text || '').replace(/\n{3,}/g, '\n\n').trim();
}

// A single chat message. System messages render as a centered note; user and
// assistant messages render as left/right aligned bubbles with an avatar.
// Assistant content is Markdown; user content stays plain text.
function MessageBubble({ message, onApply }) {
    const { role, content, timestamp, status, artifacts } = message;

    if (role === 'system') {
        return (
            <div className="se-chat-system" role="note">
                <i className="pi pi-info-circle mr-2" />
                <span>{content}</span>
            </div>
        );
    }

    const isUser = role === 'user';
    const isSending = status === 'sending';

    return (
        <div className={classNames('se-chat-row', { 'se-chat-row--user': isUser })}>
            {!isUser && (
                <Avatar
                    image="/logo-color-beige.png"
                    shape="circle"
                    className="se-chat-avatar se-chat-avatar--assistant"
                />
            )}
            <div className="se-chat-bubble-wrap">
                <div
                    className={classNames('se-chat-bubble', {
                        'se-chat-bubble--user': isUser,
                        'se-chat-bubble--assistant': !isUser,
                    })}
                >
                    {isSending && !content ? (
                        <TypingDots />
                    ) : isUser ? (
                        <span className="se-chat-bubble__text">{content}</span>
                    ) : (
                        <div className="se-chat-bubble__md">
                            <ReactMarkdown>{normalizeAssistantMarkdown(content)}</ReactMarkdown>
                        </div>
                    )}
                </div>

                {artifacts?.length > 0 && (
                    <div className="se-chat-artifacts">
                        {artifacts.map((a) => (
                            <ApplyActionCard key={a.id} artifact={a} onApply={onApply} />
                        ))}
                    </div>
                )}

                <div className="se-chat-bubble__time">{formatTime(timestamp)}</div>
            </div>
            {isUser && (
                <Avatar
                    icon="pi pi-user"
                    shape="circle"
                    className="se-chat-avatar se-chat-avatar--user"
                />
            )}
        </div>
    );
}

export default MessageBubble;
