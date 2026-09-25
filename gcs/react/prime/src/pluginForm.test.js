import { describe, it, expect } from 'vitest';
import { PLUGIN_CATEGORIES, emptyInstallForm, validateInstallForm, installRequestBody } from './pluginForm.js';

const valid = {
    name: 'parrot_anafi',
    repo: 'https://example.com/plugins.git',
    ref: 'main',
    subpath: 'drivers/parrot_anafi',
    category: 'driver',
};

describe('validateInstallForm', () => {
    it('accepts a complete, well-formed form', () => {
        expect(validateInstallForm(valid)).toEqual({});
    });

    it('treats subpath as optional', () => {
        expect(validateInstallForm({ ...valid, subpath: '' })).toEqual({});
    });

    it('requires name, repo, ref and category', () => {
        const errors = validateInstallForm(emptyInstallForm());
        expect(Object.keys(errors).sort()).toEqual(['category', 'name', 'ref', 'repo']);
    });

    it('rejects names that could escape the install directory or hide', () => {
        for (const name of ['../evil', 'a/b', '.hidden', 'has space', '-lead', 'a\\b']) {
            expect(validateInstallForm({ ...valid, name }).name, name).toBeTruthy();
        }
    });

    it('rejects names over 64 characters', () => {
        expect(validateInstallForm({ ...valid, name: 'a'.repeat(65) }).name).toBeTruthy();
        expect(validateInstallForm({ ...valid, name: 'a'.repeat(64) }).name).toBeUndefined();
    });

    it('rejects absolute or parent-traversing subpaths', () => {
        for (const subpath of ['/abs', '../up', 'a/../../up', '..']) {
            expect(validateInstallForm({ ...valid, subpath }).subpath, subpath).toBeTruthy();
        }
        expect(validateInstallForm({ ...valid, subpath: 'a/b.c/d' }).subpath).toBeUndefined();
    });

    it('rejects an unknown category', () => {
        expect(validateInstallForm({ ...valid, category: 'bogus' }).category).toBeTruthy();
        for (const category of PLUGIN_CATEGORIES) {
            expect(validateInstallForm({ ...valid, category }).category).toBeUndefined();
        }
    });

    it('treats whitespace-only fields as empty', () => {
        expect(validateInstallForm({ ...valid, repo: '   ' }).repo).toBeTruthy();
    });
});

describe('installRequestBody', () => {
    it('trims every text field and adds the daemon address', () => {
        const body = installRequestBody('host:9090', {
            name: ' p ', repo: ' r ', ref: ' main ', subpath: ' sub ', category: 'extra',
        });
        expect(body).toEqual({ address: 'host:9090', name: 'p', repo: 'r', ref: 'main', subpath: 'sub', category: 'extra' });
    });
});
