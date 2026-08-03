import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
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
} from './sessionLogic.js';
import { mockAssistantReply, ASSISTANT_NAME } from '../data/mockAssistant.js';

// Central store for the chat page: multi-session CRUD, message sending and a
// mock assistant reply. Components consume this hook and never touch
// localStorage or the reply generator directly.
export function useChatSessions() {
    const [sessions, setSessions] = useState(() => loadSessions() ?? [createSession()]);
    const [activeId, setActiveId] = useState(() => sessions[0]?.id ?? null);
    const [isResponding, setIsResponding] = useState(false);
    const replyTimer = useRef(null);

    useEffect(() => {
        saveSessions(sessions);
    }, [sessions]);

    useEffect(() => () => clearTimeout(replyTimer.current), []);

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
        setSessions((prev) => prev.map((s) => (s.id === activeId ? { ...fresh, id: s.id, title: s.title } : s)));
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

            setSessions((prev) =>
                prev.map((s) => {
                    if (s.id !== activeId) return s;
                    let next = appendMessage(s, userMsg);
                    next = appendMessage(next, pendingMsg);
                    if (isPristine(s)) next = { ...next, title: deriveTitle(content) };
                    return next;
                })
            );

            setIsResponding(true);
            const { content: replyText, artifacts } = mockAssistantReply(content);
            replyTimer.current = setTimeout(() => {
                setSessions((prev) =>
                    prev.map((s) =>
                        s.id === activeId
                            ? updateMessage(s, pendingId, {
                                  content: replyText,
                                  status: 'complete',
                                  artifacts,
                              })
                            : s
                    )
                );
                setIsResponding(false);
            }, 650);
        },
        [activeId, isResponding]
    );

    const stopResponding = useCallback(() => {
        clearTimeout(replyTimer.current);
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

    // Expose upsert so callers/tests can inject sessions if needed later.
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
