import { useState, useCallback } from 'react';
import { InputTextarea } from 'primereact/inputtextarea';
import { Button } from 'primereact/button';

// Message input area: auto-resizing textarea plus send/stop controls.
// Enter sends, Shift+Enter inserts a newline.
function ChatComposer({ onSend, onStop, isResponding, disabled }) {
    const [value, setValue] = useState('');

    const submit = useCallback(() => {
        const text = value.trim();
        if (!text || isResponding || disabled) return;
        onSend(text);
        setValue('');
    }, [value, isResponding, disabled, onSend]);

    const onKeyDown = useCallback(
        (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
            }
        },
        [submit]
    );

    return (
        <div className="se-chat-composer">
            <InputTextarea
                className="se-chat-composer__input"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Describe a mission or ask about the GCS…"
                autoResize
                rows={1}
                disabled={disabled}
                aria-label="Chat message"
            />
            {isResponding ? (
                <Button
                    icon="pi pi-stop"
                    severity="secondary"
                    className="se-chat-composer__btn"
                    onClick={onStop}
                    tooltip="Stop"
                    tooltipOptions={{ position: 'top' }}
                    aria-label="Stop response"
                />
            ) : (
                <Button
                    icon="pi pi-send"
                    className="se-chat-composer__btn"
                    onClick={submit}
                    disabled={!value.trim() || disabled}
                    tooltip="Send (Enter)"
                    tooltipOptions={{ position: 'top' }}
                    aria-label="Send message"
                />
            )}
        </div>
    );
}

export default ChatComposer;
