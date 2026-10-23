// @vitest-environment jsdom
/* globals global */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { postToApi } from './apiUtils.js';

function makeToast() {
    return { current: { show: vi.fn() } };
}

describe('postToApi', () => {
    beforeEach(() => {
        global.fetch = vi.fn();
    });

    it('returns the parsed JSON body on a successful response', async () => {
        global.fetch.mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ hello: 'world' }),
        });
        const toast = makeToast();

        const result = await postToApi('/api/thing', { a: 1 }, toast, 'Thing Error');

        expect(result).toEqual({ hello: 'world' });
        expect(toast.current.show).not.toHaveBeenCalled();
        expect(global.fetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/thing'),
            expect.objectContaining({
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ a: 1 }),
            })
        );
    });

    it('toasts and returns null when fetch itself throws', async () => {
        global.fetch.mockRejectedValue(new TypeError('network down'));
        const toast = makeToast();

        const result = await postToApi('/api/thing', {}, toast, 'Thing Error');

        expect(result).toBeNull();
        expect(toast.current.show).toHaveBeenCalledWith(
            expect.objectContaining({ severity: 'error', summary: 'Thing Error' })
        );
    });

    it('toasts and returns null on a non-2xx response', async () => {
        global.fetch.mockResolvedValue({
            ok: false,
            status: 500,
            json: async () => ({ detail: 'boom' }),
        });
        const toast = makeToast();

        const result = await postToApi('/api/thing', {}, toast, 'Thing Error');

        expect(result).toBeNull();
        expect(toast.current.show).toHaveBeenCalledWith(
            expect.objectContaining({ severity: 'error', summary: 'Thing Error' })
        );
    });
});
