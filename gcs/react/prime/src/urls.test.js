import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { getImagerySocketUrl } from './urls.js';

describe('getImagerySocketUrl', () => {
    beforeEach(() => {
        vi.stubGlobal('window', { location: { protocol: 'http:', host: 'gcs.example:8002' } });
    });
    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('is null when no vehicle is selected, so no socket is opened', () => {
        expect(getImagerySocketUrl('')).toBeNull();
        expect(getImagerySocketUrl(null)).toBeNull();
    });

    it('points at the selected vehicle\'s imagery stream', () => {
        expect(getImagerySocketUrl('alpha-1')).toBe('ws://gcs.example:8002/ws/imagery/remote/alpha-1');
    });
});
