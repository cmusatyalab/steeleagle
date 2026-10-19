// The roster of daemons the GCS knows about, persisted in localStorage and
// shared by the Orchestrate page (which edits it) and the Flow Builder
// (which builds its palette from it). Both pages stay mounted, so a save
// notifies same-window subscribers directly; `storage` events cover other
// tabs.
//
// Persisted independently of whether a daemon is actually reachable -- the
// roster of daemons you've told the GCS about is useful on its own (e.g.
// "server1:9090 is configured but currently unreachable"), so it isn't
// tied to live connectivity state the way vehicle status is.
export const DAEMONS_STORAGE_KEY = 'steeleagle-daemons';
const CHANGE_EVENT = 'steeleagle-daemons-changed';

export function loadDaemons() {
    try {
        const raw = localStorage.getItem(DAEMONS_STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

export function saveDaemons(daemons) {
    try {
        localStorage.setItem(DAEMONS_STORAGE_KEY, JSON.stringify(daemons));
    } catch {
        // Storage full or blocked: the roster still lives in page state.
    }
    window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function subscribeDaemons(callback) {
    const onChange = () => callback(loadDaemons());
    const onStorage = (event) => {
        if (event.key === DAEMONS_STORAGE_KEY) onChange();
    };
    window.addEventListener(CHANGE_EVENT, onChange);
    window.addEventListener('storage', onStorage);
    return () => {
        window.removeEventListener(CHANGE_EVENT, onChange);
        window.removeEventListener('storage', onStorage);
    };
}
