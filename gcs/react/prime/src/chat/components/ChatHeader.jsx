import { useEffect, useState } from 'react';
import { Button } from 'primereact/button';
import { Tag } from 'primereact/tag';
import { Tooltip } from 'primereact/tooltip';
import { ASSISTANT_NAME } from '../data/constants.js';
import { getApiUrl } from '../../App.jsx';

// Top bar of the chat window

// Live: active LLM provider has a non-empty API key (provider shown on hover).
// Offline: backend unreachable, or the configured provider has no API key.
function ChatHeader({ title, onClear, canClear }) {
    const [llmStatus, setLlmStatus] = useState(null);
    const [offline, setOffline] = useState(false);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const resp = await fetch(getApiUrl('/api/chat/status'));
                if (!resp.ok) {
                    if (!cancelled) setOffline(true);
                    return;
                }
                const data = await resp.json();
                if (!cancelled) {
                    setLlmStatus(data);
                    setOffline(false);
                }
            } catch {
                if (!cancelled) setOffline(true);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, []);

    const showLive = Boolean(llmStatus?.configured);
    const showNoKey = Boolean(llmStatus) && !llmStatus.configured;
    const providerTip = llmStatus
        ? `Using ${llmStatus.label}${llmStatus.model ? ` (${llmStatus.model})` : ''}`
        : '';
    const noKeyTip = llmStatus?.label
        ? `No API key configured for ${llmStatus.label}`
        : 'No API key configured';

    return (
        <div className="se-chat-header">
            <div className="se-chat-header__title">
                <i className="pi pi-comments mr-2" />
                <span className="se-chat-header__name">{title || ASSISTANT_NAME}</span>
                {offline && (
                    <>
                        <Tag
                            id="se-chat-live-tag"
                            value="Offline"
                            severity="danger"
                            className="ml-2 se-chat-live-tag"
                        />
                        <Tooltip
                            target="#se-chat-live-tag"
                            content="Chat backend is unreachable"
                            position="bottom"
                        />
                    </>
                )}
                {!offline && showNoKey && (
                    <>
                        <Tag
                            id="se-chat-live-tag"
                            value="Offline"
                            severity="danger"
                            className="ml-2 se-chat-live-tag"
                        />
                        <Tooltip
                            target="#se-chat-live-tag"
                            content={noKeyTip}
                            position="bottom"
                        />
                    </>
                )}
                {!offline && showLive && (
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
