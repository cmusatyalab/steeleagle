import { useEffect, useState } from 'react';
import { Button } from 'primereact/button';
import { Tag } from 'primereact/tag';
import { Tooltip } from 'primereact/tooltip';
import { ASSISTANT_NAME } from '../data/mockAssistant.js';
import { getApiUrl } from '../../App.jsx';

// Top bar of the chat window: assistant identity, live-mode indicator and a
// clear-conversation action. Mirrors the toolbar styling used on the Plan page.
//
// "Live" is shown only when the active LLM provider has a non-empty API key.
// The provider is displayed only when mouse is hovering on it.
function ChatHeader({ title, onClear, canClear }) {
    const [llmStatus, setLlmStatus] = useState(null);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const resp = await fetch(getApiUrl('/api/chat/status'));
                if (!resp.ok) return;
                const data = await resp.json();
                if (!cancelled) setLlmStatus(data);
            } catch {
                // Backend unreachable — leave Live hidden.
            }
        })();
        return () => {
            cancelled = true;
        };
    }, []);

    const showLive = Boolean(llmStatus?.configured);
    const providerTip = llmStatus
        ? `Using ${llmStatus.label}${llmStatus.model ? ` (${llmStatus.model})` : ''}`
        : '';

    return (
        <div className="se-chat-header">
            <div className="se-chat-header__title">
                <i className="pi pi-comments mr-2" />
                <span className="se-chat-header__name">{title || ASSISTANT_NAME}</span>
                {showLive && (
                    <>
                        <Tag
                            id="se-chat-live-tag"
                            value="Live"
                            severity="success"
                            className="ml-2 se-chat-live-tag"
                        />
                        <Tooltip
                            target="#se-chat-live-tag"
                            content={providerTip}
                            position="bottom"
                        />
                    </>
                )}
            </div>
            <Button
                label="Clear"
                icon="pi pi-eraser"
                size="small"
                outlined
                disabled={!canClear}
                onClick={onClear}
                tooltip="Clear this conversation"
                tooltipOptions={{ position: 'bottom' }}
            />
        </div>
    );
}

export default ChatHeader;
