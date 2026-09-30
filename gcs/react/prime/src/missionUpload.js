// Client side of the mission upload/deploy NDJSON streams -- see
// docs/superpowers/specs/2026-09-28-mission-upload-streaming-design.md.

// Splits buffered NDJSON text into parsed complete lines plus the trailing
// partial line still waiting for more bytes.
export function splitNdjson(buffer) {
    const parts = buffer.split('\n');
    const rest = parts.pop();
    const events = parts.filter(line => line.trim() !== '').map(line => JSON.parse(line));
    return { events, rest };
}

// Reads a fetch Response body as NDJSON, calling onEvent per event.
export async function readNdjson(response, onEvent) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const { events, rest } = splitNdjson(buffer);
        buffer = rest;
        events.forEach(onEvent);
    }
    buffer += decoder.decode();
    if (buffer.trim() !== '') onEvent(JSON.parse(buffer));
}

// POSTs and relays the NDJSON response; throws Error(detail) on non-2xx.
export async function streamUpload(url, init, onEvent) {
    const response = await fetch(url, init);
    if (!response.ok) {
        let detail = `Server error ${response.status}`;
        try {
            const body = await response.json();
            if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
        } catch { /* keep the status-code message */ }
        throw new Error(detail);
    }
    await readNdjson(response, onEvent);
}

export function initialUploadState(vehicles) {
    return {
        stage: null,
        error: null,
        errors: [],
        vehicles: Object.fromEntries(vehicles.map(v => [v, { sent: 0, total: 0, status: 'pending', details: '' }])),
    };
}

const DONE = new Set(['success', 'failed']);

export function applyUploadEvent(state, ev) {
    switch (ev.type) {
        case 'stage':
            return { ...state, stage: ev.stage };
        case 'progress': {
            const cur = state.vehicles[ev.vehicle] ?? { sent: 0, total: 0, status: 'pending', details: '' };
            if (DONE.has(cur.status)) return state;
            return { ...state, vehicles: { ...state.vehicles, [ev.vehicle]: { ...cur, sent: ev.sent, total: ev.total, status: 'uploading' } } };
        }
        case 'result': {
            const cur = state.vehicles[ev.vehicle] ?? { sent: 0, total: 0, status: 'pending', details: '' };
            return {
                ...state,
                vehicles: { ...state.vehicles, [ev.vehicle]: { ...cur, status: ev.success ? 'success' : 'failed', details: ev.details ?? '' } },
            };
        }
        case 'error':
            return { ...state, error: ev.detail, errors: ev.errors ?? [] };
        default:
            return state;
    }
}

export function isUploadFinished(state) {
    return state.error !== null || Object.values(state.vehicles).every(v => DONE.has(v.status));
}

// Called once streamUpload's promise resolves (the NDJSON stream ended
// cleanly). If some vehicle never got a result and there was no error line,
// the state would otherwise stay "in progress" forever (Dismiss disabled,
// Deploy/Upload spinning) -- surface that as a terminal error instead.
export function finishUpload(state) {
    if (!isUploadFinished(state)) {
        return applyUploadEvent(state, { type: 'error', detail: 'Stream ended before all vehicles reported a result' });
    }
    return state;
}

export function progressPercent(v) {
    if (v.status === 'success') return 100;
    return v.total > 0 ? Math.floor((v.sent * 100) / v.total) : 0;
}
