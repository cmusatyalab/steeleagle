// Pure, framework-free session logic used by useChatSessions.
// Keeping these functions pure makes the conversation model easy to unit test
// and keeps React components free of storage/branching concerns.

import { nextId, WELCOME_MESSAGE, ASSISTANT_NAME } from '../data/mockAssistant.js';

export const STORAGE_KEY = 'se-chat-sessions';

export function makeMessage(role, content, extra = {}) {
    return {
        id: nextId('msg'),
        role,
        content,
        timestamp: Date.now(),
        status: 'complete',
        artifacts: [],
        ...extra,
    };
}

export function createSession(title = 'New conversation') {
    const now = Date.now();
    return {
        id: nextId('conv'),
        title,
        createdAt: now,
        updatedAt: now,
        currentDraft: null,
        messages: [
            makeMessage('system', WELCOME_MESSAGE, { author: ASSISTANT_NAME }),
        ],
    };
}

/** Attach or clear the last known-good draft DSL for a session. */
export function setCurrentDraft(session, draft) {
    const normalized =
        draft && typeof draft.normalized_dsl === 'string' && draft.normalized_dsl.trim()
            ? { normalized_dsl: draft.normalized_dsl.trim() }
            : null;
    return {
        ...session,
        updatedAt: Date.now(),
        currentDraft: normalized,
    };
}

// Derive a short human-friendly title from the first user message.
export function deriveTitle(text) {
    const clean = (text || '').trim().replace(/\s+/g, ' ');
    if (!clean) return 'New conversation';
    return clean.length > 40 ? `${clean.slice(0, 40)}…` : clean;
}

// Returns a new session with the message appended and updatedAt bumped.
export function appendMessage(session, message) {
    return {
        ...session,
        updatedAt: Date.now(),
        messages: [...session.messages, message],
    };
}

// Returns a new session with a single message patched by id.
export function updateMessage(session, messageId, patch) {
    return {
        ...session,
        updatedAt: Date.now(),
        messages: session.messages.map((m) =>
            m.id === messageId ? { ...m, ...patch } : m
        ),
    };
}

// Whether a session still only holds the initial system welcome message.
export function isPristine(session) {
    return session.messages.every((m) => m.role === 'system');
}

// Replace (or insert) a session in the list, keeping list ordering stable.
export function upsertSession(sessions, session) {
    const exists = sessions.some((s) => s.id === session.id);
    return exists
        ? sessions.map((s) => (s.id === session.id ? session : s))
        : [session, ...sessions];
}

export function renameSession(sessions, id, title) {
    const clean = (title || '').trim();
    if (!clean) return sessions;
    return sessions.map((s) =>
        s.id === id ? { ...s, title: clean, updatedAt: Date.now() } : s
    );
}

// Remove a session and compute which session should become active next.
// Returns { sessions, nextActiveId }.
export function deleteSession(sessions, id, activeId) {
    const remaining = sessions.filter((s) => s.id !== id);
    let nextActiveId = activeId;
    if (activeId === id) {
        nextActiveId = remaining.length ? remaining[0].id : null;
    }
    return { sessions: remaining, nextActiveId };
}

// Case-insensitive filter across title and message content.
export function filterSessions(sessions, query) {
    const q = (query || '').trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((s) => {
        if (s.title.toLowerCase().includes(q)) return true;
        return s.messages.some((m) => m.content.toLowerCase().includes(q));
    });
}

export function loadSessions() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed) || parsed.length === 0) return null;
        return parsed;
    } catch {
        return null;
    }
}

export function saveSessions(sessions) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch {
        // Ignore quota/serialization errors; persistence is best-effort.
    }
}
