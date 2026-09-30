import { describe, it, expect, vi, afterEach } from 'vitest';
import {
    splitNdjson, readNdjson, streamUpload, initialUploadState,
    applyUploadEvent, isUploadFinished, progressPercent, finishUpload,
} from './missionUpload.js';

const streamOf = (...parts) => new Response(new ReadableStream({
    start(controller) {
        const enc = new TextEncoder();
        parts.forEach(p => controller.enqueue(enc.encode(p)));
        controller.close();
    },
}));

describe('splitNdjson', () => {
    it('returns complete lines and keeps the partial tail', () => {
        const { events, rest } = splitNdjson('{"a":1}\n\n{"b":2}\n{"c"');
        expect(events).toEqual([{ a: 1 }, { b: 2 }]);
        expect(rest).toBe('{"c"');
    });
});

describe('readNdjson', () => {
    it('reassembles events split across network chunks', async () => {
        const seen = [];
        await readNdjson(streamOf('{"type":"sta', 'ge","stage":"uploading"}\n{"type":"result"', ',"vehicle":"d1"}'), e => seen.push(e));
        expect(seen).toEqual([
            { type: 'stage', stage: 'uploading' },
            { type: 'result', vehicle: 'd1' },
        ]);
    });
});

describe('streamUpload', () => {
    afterEach(() => vi.unstubAllGlobals());

    it('throws the server detail on a non-2xx response', async () => {
        vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Select at least one vehicle' }), { status: 400 })));
        await expect(streamUpload('/api/upload', {}, () => {})).rejects.toThrow('Select at least one vehicle');
    });

    it('relays events on success', async () => {
        vi.stubGlobal('fetch', vi.fn(async () => streamOf('{"type":"stage","stage":"uploading"}\n')));
        const seen = [];
        await streamUpload('/api/upload', {}, e => seen.push(e));
        expect(seen).toEqual([{ type: 'stage', stage: 'uploading' }]);
    });
});

describe('upload state', () => {
    it('starts every vehicle pending', () => {
        const s = initialUploadState(['d1', 'd2']);
        expect(s.vehicles.d1).toEqual({ sent: 0, total: 0, status: 'pending', details: '' });
        expect(isUploadFinished(s)).toBe(false);
    });

    it('tracks progress and results per vehicle', () => {
        let s = initialUploadState(['d1', 'd2']);
        s = applyUploadEvent(s, { type: 'stage', stage: 'uploading' });
        s = applyUploadEvent(s, { type: 'progress', vehicle: 'd1', sent: 50, total: 200 });
        expect(s.stage).toBe('uploading');
        expect(s.vehicles.d1.status).toBe('uploading');
        expect(progressPercent(s.vehicles.d1)).toBe(25);

        s = applyUploadEvent(s, { type: 'result', vehicle: 'd1', success: true, details: '' });
        s = applyUploadEvent(s, { type: 'result', vehicle: 'd2', success: false, details: 'mission running' });
        expect(s.vehicles.d1.status).toBe('success');
        expect(progressPercent(s.vehicles.d1)).toBe(100);
        expect(s.vehicles.d2).toMatchObject({ status: 'failed', details: 'mission running' });
        expect(isUploadFinished(s)).toBe(true);
    });

    it('ignores progress that arrives after a result', () => {
        let s = initialUploadState(['d1']);
        s = applyUploadEvent(s, { type: 'result', vehicle: 'd1', success: false, details: 'x' });
        const after = applyUploadEvent(s, { type: 'progress', vehicle: 'd1', sent: 1, total: 2 });
        expect(after).toBe(s);
    });

    it('a terminal error finishes the upload and carries compile errors', () => {
        let s = initialUploadState(['d1']);
        s = applyUploadEvent(s, { type: 'error', detail: 'Build failed', errors: [{ node_id: 'n1', message: 'bad' }] });
        expect(s.error).toBe('Build failed');
        expect(s.errors).toEqual([{ node_id: 'n1', message: 'bad' }]);
        expect(isUploadFinished(s)).toBe(true);
    });

    it('progressPercent is 0 before any total is known', () => {
        expect(progressPercent({ sent: 0, total: 0, status: 'pending' })).toBe(0);
    });
});

describe('finishUpload', () => {
    it('turns an unfinished state into a terminal error when the stream ends early', () => {
        let s = initialUploadState(['d1', 'd2']);
        s = applyUploadEvent(s, { type: 'result', vehicle: 'd1', success: true, details: '' });
        // d2 never got a result and there was no error line.
        const finished = finishUpload(s);
        expect(finished.error).toBe('Stream ended before all vehicles reported a result');
        expect(isUploadFinished(finished)).toBe(true);
        // d1's already-reported result is preserved.
        expect(finished.vehicles.d1.status).toBe('success');
    });

    it('leaves an already-finished state unchanged', () => {
        let s = initialUploadState(['d1']);
        s = applyUploadEvent(s, { type: 'result', vehicle: 'd1', success: true, details: '' });
        expect(finishUpload(s)).toBe(s);
    });

    it('leaves a state that already carries a terminal error unchanged', () => {
        let s = initialUploadState(['d1']);
        s = applyUploadEvent(s, { type: 'error', detail: 'Build failed' });
        expect(finishUpload(s)).toBe(s);
    });
});
