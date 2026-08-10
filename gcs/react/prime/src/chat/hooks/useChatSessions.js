import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import {
    createSession,
    deriveTitle,
    appendMessage,
    updateMessage,
    upsertSession,
    renameSession,
    deleteSession,
    makeMessage,
    isPristine,
    loadSessions,
    saveSessions,
    setCurrentDraft,
} from './sessionLogic.js';
import { ASSISTANT_NAME } from '../data/mockAssistant.js';

class ChatAbortError extends Error {
    constructor() {
        super('aborted');
        this.name = 'ChatAbortError';
    }
}

// Central store for the chat page: multi-session CRUD and SSE /api/chat replies.
export function useChatSessions() {
    const [sessions, setSessions] = useState(() => loadSessions() ?? [createSession()]);
    const [activeId, setActiveId] = useState(() => sessions[0]?.id ?? null);
    const [isResponding, setIsResponding] = useState(false);
    const abortRef = useRef(null);

    useEffect(() => {
        saveSessions(sessions);
    }, [sessions]);

    useEffect(
        () => () => {
            abortRef.current?.abort();
        },
        []
    );

    const activeSession = useMemo(
        () => sessions.find((s) => s.id === activeId) ?? null,
        [sessions, activeId]
    );

    const newConversation = useCallback(() => {
        const session = createSession();
        setSessions((prev) => [session, ...prev]);
        setActiveId(session.id);
    }, []);

    const selectConversation = useCallback((id) => setActiveId(id), []);

    const rename = useCallback((id, title) => {
        setSessions((prev) => renameSession(prev, id, title));
    }, []);

    const remove = useCallback(
        (id) => {
            setSessions((prev) => {
                const { sessions: remaining, nextActiveId } = deleteSession(prev, id, activeId);
                if (remaining.length === 0) {
                    const fresh = createSession();
                    setActiveId(fresh.id);
                    return [fresh];
                }
                if (nextActiveId !== activeId) setActiveId(nextActiveId);
                return remaining;
            });
        },
        [activeId]
    );

    const clearActive = useCallback(() => {
        if (!activeId) return;
        const fresh = createSession();
        setSessions((prev) =>
            prev.map((s) =>
                s.id === activeId ? { ...fresh, id: s.id, title: s.title } : s
            )
        );
    }, [activeId]);

    const sendMessage = useCallback(
        (text) => {
            const content = (text || '').trim();
            if (!content || !activeId || isResponding) return;

            const userMsg = makeMessage('user', content);
            const pendingId = `pending-${userMsg.id}`;
            const pendingMsg = makeMessage('assistant', '', {
                id: pendingId,
                status: 'sending',
                author: ASSISTANT_NAME,
            });

            let historyForApi = [];
            let draftDsl = null;

            setSessions((prev) =>
                prev.map((s) => {
                    if (s.id !== activeId) return s;
                    let next = appendMessage(s, userMsg);
                    next = appendMessage(next, pendingMsg);
                    if (isPristine(s)) next = { ...next, title: deriveTitle(content) };
                    historyForApi = next.messages
                        .filter((m) => m.role === 'user' || m.role === 'assistant')
                        .filter((m) => m.id !== pendingId)
                        .map((m) => ({ role: m.role, content: m.content || '' }));
                    draftDsl = next.currentDraft?.normalized_dsl ?? null;
                    return next;
                })
            );

            setIsResponding(true);
            const controller = new AbortController();
            abortRef.current = controller;

            let settled = false;
            const finish = (patch, draft) => {
                if (settled) return;
                settled = true;
                setSessions((prev) =>
                    prev.map((s) => {
                        if (s.id !== activeId) return s;
                        let next = updateMessage(s, pendingId, patch);
                        if (draft?.normalized_dsl) next = setCurrentDraft(next, draft);
                        return next;
                    })
                );
                setIsResponding(false);
                abortRef.current = null;
            };

            fetchEventSource('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Accept: 'text/event-stream',
                },
                body: JSON.stringify({
                    messages: historyForApi,
                    draft_dsl: draftDsl,
                }),
                signal: controller.signal,
                openWhenHidden: true,
                async onopen(response) {
                    if (response.ok) return;
                    const detail = await response.text().catch(() => '');
                    throw new Error(
                        detail || `Chat request failed (${response.status})`
                    );
                },
                onmessage(ev) {
                    if (!ev.event || !ev.data) return;
                    let data;
                    try {
                        data = JSON.parse(ev.data);
                    } catch {
                        return;
                    }
                    if (ev.event === 'done') {
                        finish(
                            {
                                content: data.content || '',
                                status: 'complete',
                                artifacts: Array.isArray(data.artifacts)
                                    ? data.artifacts
                                    : [],
                            },
                            data.draft
                        );
                    } else if (ev.event === 'error') {
                        finish({
                            content:
                                data.message ||
                                'The assistant could not complete this request.',
                            status: 'complete',
                            artifacts: [],
                        });
                    }
                },
                onerror(err) {
                    if (controller.signal.aborted) throw new ChatAbortError();
                    finish({
                        content:
                            err?.message ||
                            'Chat request failed. Check that the GCS backend is running and an LLM API key is configured.',
                        status: 'complete',
                        artifacts: [],
                    });
                    throw new ChatAbortError();
                },
            }).catch((err) => {
                if (err instanceof ChatAbortError || controller.signal.aborted) {
                    if (!settled) {
                        finish({
                            content: '(stopped)',
                            status: 'complete',
                            artifacts: [],
                        });
                    }
                    return;
                }
                finish({
                    content: err?.message || 'Chat request failed.',
                    status: 'complete',
                    artifacts: [],
                });
            });
        },
        [activeId, isResponding]
    );

    const stopResponding = useCallback(() => {
        abortRef.current?.abort();
        abortRef.current = null;
        setIsResponding(false);
        setSessions((prev) =>
            prev.map((s) => ({
                ...s,
                messages: s.messages.map((m) =>
                    m.status === 'sending'
                        ? { ...m, status: 'complete', content: m.content || '(stopped)' }
                        : m
                ),
            }))
        );
    }, []);

    const replaceSession = useCallback((session) => {
        setSessions((prev) => upsertSession(prev, session));
    }, []);

    return {
        sessions,
        activeId,
        activeSession,
        isResponding,
        newConversation,
        selectConversation,
        rename,
        remove,
        clearActive,
        sendMessage,
        stopResponding,
        replaceSession,
    };
}
