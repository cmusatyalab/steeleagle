import { describe, it, expect, beforeEach } from 'vitest';
import {
    createSession,
    deriveTitle,
    appendMessage,
    updateMessage,
    upsertSession,
    renameSession,
    deleteSession,
    filterSessions,
    isPristine,
    makeMessage,
    loadSessions,
    saveSessions,
    STORAGE_KEY,
} from './sessionLogic.js';

describe('createSession', () => {
    it('creates a session with a system welcome message', () => {
        const s = createSession();
        expect(s.id).toBeTruthy();
        expect(s.messages).toHaveLength(1);
        expect(s.messages[0].role).toBe('system');
        expect(isPristine(s)).toBe(true);
    });

    it('honors a custom title', () => {
        expect(createSession('My chat').title).toBe('My chat');
    });
});

describe('deriveTitle', () => {
    it('falls back for empty input', () => {
        expect(deriveTitle('')).toBe('New conversation');
        expect(deriveTitle('   ')).toBe('New conversation');
    });

    it('collapses whitespace and keeps short text', () => {
        expect(deriveTitle('  hello   world ')).toBe('hello world');
    });

    it('truncates long text with an ellipsis', () => {
        const title = deriveTitle('a'.repeat(60));
        expect(title.endsWith('…')).toBe(true);
        expect(title.length).toBe(41);
    });
});

describe('appendMessage / updateMessage', () => {
    it('appends immutably and bumps updatedAt', () => {
        const s = createSession();
        const before = s.messages.length;
        const next = appendMessage(s, makeMessage('user', 'hi'));
        expect(next).not.toBe(s);
        expect(next.messages).toHaveLength(before + 1);
        expect(next.messages.at(-1).content).toBe('hi');
    });

    it('patches a message by id', () => {
        let s = createSession();
        const msg = makeMessage('assistant', '', { status: 'sending' });
        s = appendMessage(s, msg);
        const next = updateMessage(s, msg.id, { content: 'done', status: 'complete' });
        const updated = next.messages.find((m) => m.id === msg.id);
        expect(updated.content).toBe('done');
        expect(updated.status).toBe('complete');
    });

    it('marks a session non-pristine once a user message exists', () => {
        let s = createSession();
        expect(isPristine(s)).toBe(true);
        s = appendMessage(s, makeMessage('user', 'go'));
        expect(isPristine(s)).toBe(false);
    });
});

describe('upsertSession', () => {
    it('inserts a new session at the front', () => {
        const a = createSession('a');
        const b = createSession('b');
        const list = upsertSession([a], b);
        expect(list).toHaveLength(2);
        expect(list[0].id).toBe(b.id);
    });

    it('replaces an existing session in place', () => {
        const a = createSession('a');
        const updated = { ...a, title: 'renamed' };
        const list = upsertSession([a], updated);
        expect(list).toHaveLength(1);
        expect(list[0].title).toBe('renamed');
    });
});

describe('renameSession', () => {
    it('renames the matching session', () => {
        const a = createSession('a');
        const list = renameSession([a], a.id, 'New name');
        expect(list[0].title).toBe('New name');
    });

    it('ignores blank titles', () => {
        const a = createSession('a');
        const list = renameSession([a], a.id, '   ');
        expect(list[0].title).toBe('a');
    });
});

describe('deleteSession', () => {
    it('removes the session and keeps the active id when a different one is deleted', () => {
        const a = createSession('a');
        const b = createSession('b');
        const { sessions, nextActiveId } = deleteSession([a, b], b.id, a.id);
        expect(sessions).toHaveLength(1);
        expect(nextActiveId).toBe(a.id);
    });

    it('moves active to the first remaining session when the active one is deleted', () => {
        const a = createSession('a');
        const b = createSession('b');
        const { sessions, nextActiveId } = deleteSession([a, b], a.id, a.id);
        expect(sessions).toHaveLength(1);
        expect(nextActiveId).toBe(b.id);
    });

    it('returns null active id when the last session is deleted', () => {
        const a = createSession('a');
        const { sessions, nextActiveId } = deleteSession([a], a.id, a.id);
        expect(sessions).toHaveLength(0);
        expect(nextActiveId).toBeNull();
    });
});

describe('filterSessions', () => {
    it('returns all sessions for an empty query', () => {
        const list = [createSession('a'), createSession('b')];
        expect(filterSessions(list, '')).toHaveLength(2);
    });

    it('matches by title', () => {
        const list = [createSession('Patrol area B'), createSession('Track person')];
        const filtered = filterSessions(list, 'patrol');
        expect(filtered).toHaveLength(1);
        expect(filtered[0].title).toBe('Patrol area B');
    });

    it('matches by message content', () => {
        let s = createSession('Untitled');
        s = appendMessage(s, makeMessage('user', 'take off and land'));
        const filtered = filterSessions([s], 'land');
        expect(filtered).toHaveLength(1);
    });
});

describe('persistence', () => {
    beforeEach(() => {
        const store = new Map();
        globalThis.localStorage = {
            getItem: (k) => (store.has(k) ? store.get(k) : null),
            setItem: (k, v) => store.set(k, String(v)),
            removeItem: (k) => store.delete(k),
            clear: () => store.clear(),
        };
    });

    it('round-trips sessions through storage', () => {
        const sessions = [createSession('persisted')];
        saveSessions(sessions);
        const loaded = loadSessions();
        expect(loaded).toHaveLength(1);
        expect(loaded[0].title).toBe('persisted');
    });

    it('returns null when storage is empty', () => {
        expect(loadSessions()).toBeNull();
    });

    it('returns null on malformed storage', () => {
        localStorage.setItem(STORAGE_KEY, '{not json');
        expect(loadSessions()).toBeNull();
    });
});
