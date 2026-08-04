import { useState, useCallback, useRef } from 'react';
import { InputTextarea } from 'primereact/inputtextarea';
import { Button } from 'primereact/button';
import { classNames } from 'primereact/utils';
import { useSpeechInput } from '../hooks/useSpeechInput.js';

// Message input area: mic button (voice-to-text), auto-resizing textarea, and
// send/stop controls. Enter sends, Shift+Enter inserts a newline.
// Voice input only fills the textarea; it never auto-sends.
function ChatComposer({ onSend, onStop, isResponding, disabled }) {
    const [value, setValue] = useState('');
    // Text present in the box when dictation started; recognized speech is
    // appended to this so voice continues after any typed text.
    const baseRef = useRef('');

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

    const handleResult = useCallback(({ transcript, isFinal }) => {
        if (isFinal) {
            baseRef.current = baseRef.current + transcript;
            setValue(baseRef.current);
        } else {
            // Live preview: base text plus the current interim guess.
            setValue(baseRef.current + transcript);
        }
    }, []);

    const { supported, listening, toggle } = useSpeechInput({
        lang: 'en-US',
        onResult: handleResult,
    });

    const onMicClick = useCallback(() => {
        if (!listening) {
            // Snapshot existing text; add a space so speech doesn't run into it.
            baseRef.current = value ? value.trimEnd() + ' ' : '';
        }
        toggle();
    }, [listening, value, toggle]);

    const micTooltip = !supported
        ? 'Voice input needs Chrome/Edge on localhost or https'
        : listening
          ? 'Stop dictation'
          : 'Start voice input';

    return (
        <div className="se-chat-composer">
            <Button
                icon="pi pi-microphone"
                severity={listening ? 'danger' : 'secondary'}
                outlined={!listening}
                className={classNames('se-chat-composer__mic', {
                    'se-chat-composer__mic--recording': listening,
                })}
                onClick={onMicClick}
                disabled={disabled || !supported}
                tooltip={micTooltip}
                tooltipOptions={{ position: 'top' }}
                aria-label={listening ? 'Stop voice input' : 'Start voice input'}
            />
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
