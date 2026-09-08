import { useCallback, useEffect, useRef, useState } from 'react';

// Using the browser Web Speech API (SpeechRecognition).
// Store all browser-specific concerns here so the UI components stay clean.
//
// Notes:
// - Speech-to-text is only available in Chromium (webkitSpeechRecognition)
//   and recent Safari; Firefox does not support it.
// - It requires a secure context (https or localhost). Plain http on a LAN IP
//   will report unsupported.
// - Chromium sends audio to Google servers, so it needs network and is not offline.

const SpeechRecognition =
    typeof window !== 'undefined'
        ? window.SpeechRecognition || window.webkitSpeechRecognition
        : undefined;

const isSecure = typeof window !== 'undefined' ? window.isSecureContext : false;

export function isSpeechInputSupported() {
    return Boolean(SpeechRecognition) && isSecure;
}

// onResult is called with { transcript, isFinal } as the user speaks.
export function useSpeechInput({ lang = 'en-US', onResult } = {}) {
    const supported = isSpeechInputSupported();
    const [listening, setListening] = useState(false);
    const [error, setError] = useState(null);
    const recognitionRef = useRef(null);
    const onResultRef = useRef(onResult);
    const manualStopRef = useRef(false);

    // Keep the latest onResult without re-creating the recognition instance.
    useEffect(() => {
        onResultRef.current = onResult;
    }, [onResult]);

    useEffect(() => {
        if (!supported) return undefined;

        const recognition = new SpeechRecognition();
        recognition.lang = lang;
        recognition.interimResults = true;
        recognition.continuous = true;

        recognition.onresult = (event) => {
            let interim = '';
            let final = '';
            for (let i = event.resultIndex; i < event.results.length; i += 1) {
                const result = event.results[i];
                const text = result[0]?.transcript ?? '';
                if (result.isFinal) final += text;
                else interim += text;
            }
            if (final) onResultRef.current?.({ transcript: final, isFinal: true });
            if (interim) onResultRef.current?.({ transcript: interim, isFinal: false });
        };

        recognition.onerror = (event) => {
            // "aborted" / "no-speech" are benign; surface others.
            if (event.error && event.error !== 'aborted' && event.error !== 'no-speech') {
                setError(event.error);
            }
        };

        recognition.onend = () => {
            setListening(false);
        };

        recognitionRef.current = recognition;

        return () => {
            manualStopRef.current = true;
            try {
                recognition.abort();
            } catch {
                // ignore teardown errors
            }
            recognitionRef.current = null;
        };
    }, [supported, lang]);

    const start = useCallback(() => {
        const recognition = recognitionRef.current;
        if (!recognition || listening) return;
        setError(null);
        try {
            recognition.start();
            setListening(true);
        } catch {
            // start() throws if already started; keep state consistent.
            setListening(true);
        }
    }, [listening]);

    const stop = useCallback(() => {
        const recognition = recognitionRef.current;
        if (!recognition) return;
        try {
            recognition.stop();
        } catch {
            // ignore
        }
        setListening(false);
    }, []);

    const toggle = useCallback(() => {
        if (listening) stop();
        else start();
    }, [listening, start, stop]);

    return { supported, listening, error, start, stop, toggle };
}

export default useSpeechInput;
