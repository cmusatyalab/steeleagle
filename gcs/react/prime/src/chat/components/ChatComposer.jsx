import { useState, useCallback, useRef } from 'react';
import { InputTextarea } from 'primereact/inputtextarea';
import { Button } from 'primereact/button';
import { classNames } from 'primereact/utils';
import { useSpeechInput } from '../hooks/useSpeechInput.js';

// Message input area: mic button, auto-resizing textarea, and send/stop controls. 
// Enter sends, Shift+Enter inserts a newline.
// Voice input only fills the textarea; it doensn't auto-send the prompt.
function ChatComposer({ onSend, onStop, isResponding, disabled }) {
    const [value, setValue] = useState('');
    const textareaRef = useRef(null);
    // committedRef: the real text, excluding the live interim speech guess.
    // anchorRef: index into committedRef where new speech is spliced. Stays at the latest caret.
    // interimLenRef: length of the interim guess currently shown at the anchor,
    //   used to translate display caret positions back into committed text.
    const committedRef = useRef('');
    const anchorRef = useRef(0);
    const interimLenRef = useRef(0);

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

    const placeCaret = useCallback((pos) => {
        requestAnimationFrame(() => {
            const el = textareaRef.current;
            if (!el) return;
            el.focus();
            try {
                el.setSelectionRange(pos, pos);
            } catch {
                // setSelectionRange can throw if element isn't ready; ignore.
            }
        });
    }, []);

    // Normalize a recognized fragment for insertion at the anchor: strip any
    // leading whitespace the recognizer adds, then prepend a single space only
    // when the preceding character isn't already whitespace.
    const prefixFragment = useCallback((transcript) => {
        const cleaned = transcript.replace(/^\s+/, '');
        const a = anchorRef.current;
        const prev = committedRef.current[a - 1];
        const needsSpace = a > 0 && prev && !/\s/.test(prev);
        return (needsSpace ? ' ' : '') + cleaned;
    }, []);

    // Show committed text with the interim guess spliced in at the anchor, and
    // keep the caret right after the inserted text so it stays visible.
    const render = useCallback(
        (interimText) => {
            const a = anchorRef.current;
            const committed = committedRef.current;
            setValue(committed.slice(0, a) + interimText + committed.slice(a));
            interimLenRef.current = interimText.length;
            placeCaret(a + interimText.length);
        },
        [placeCaret]
    );

    const handleResult = useCallback(
        ({ transcript, isFinal }) => {
            const text = prefixFragment(transcript);
            if (isFinal) {
                const a = anchorRef.current;
                const committed = committedRef.current;
                committedRef.current = committed.slice(0, a) + text + committed.slice(a);
                anchorRef.current = a + text.length;
                render('');
            } else {
                render(text);
            }
        },
        [render, prefixFragment]
    );

    const { supported, listening, toggle } = useSpeechInput({
        lang: 'en-US',
        onResult: handleResult,
    });

    // Re-anchor to the user's latest caret while listening. The display may
    // contain an interim guess of length `il` inserted at the current anchor,
    // so map the display caret back into committed-text coordinates.
    const syncAnchorFromCaret = useCallback(() => {
        if (!listening) return;
        const el = textareaRef.current;
        if (!el) return;
        const disp = el.selectionStart ?? 0;
        const a = anchorRef.current;
        const il = interimLenRef.current;
        if (disp <= a) anchorRef.current = disp;
        else if (disp >= a + il) anchorRef.current = disp - il;
        else anchorRef.current = a; // caret landed inside the interim → snap to anchor
    }, [listening]);

    const onInputChange = useCallback(
        (e) => {
            setValue(e.target.value);
            if (listening) {
                // Manual typing while dictating: adopt the new text and caret.
                committedRef.current = e.target.value;
                anchorRef.current = e.target.selectionStart ?? e.target.value.length;
                interimLenRef.current = 0;
            }
        },
        [listening]
    );

    const onMicClick = useCallback(() => {
        if (!listening) {
            // Seed the caret snapshot so speech is spliced at the cursor.
            const el = textareaRef.current;
            committedRef.current = value;
            anchorRef.current = el?.selectionStart ?? value.length;
            interimLenRef.current = 0;
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
                ref={textareaRef}
                className="se-chat-composer__input"
                value={value}
                onChange={onInputChange}
                onKeyDown={onKeyDown}
                onSelect={syncAnchorFromCaret}
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
