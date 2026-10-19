import { describe, expect, it } from 'vitest';
import { canvasThemeVars, flowCanvasThemeVars } from './canvasTheme.js';

describe('canvasThemeVars', () => {
    it('picks light and dark values', () => {
        expect(canvasThemeVars('light')['--node-bg']).toBe('#ffffff');
        expect(canvasThemeVars('dark')['--node-bg']).toBe('#1e3040');
    });

    it('defines the same variables for both themes', () => {
        expect(Object.keys(canvasThemeVars('light'))).toEqual(Object.keys(canvasThemeVars('dark')));
    });
});

describe('flowCanvasThemeVars', () => {
    it('defines the same variables for both themes', () => {
        expect(Object.keys(flowCanvasThemeVars('light')).sort()).toEqual(Object.keys(flowCanvasThemeVars('dark')).sort());
    });

    it('covers every shared canvas variable plus its own canvas, grid, and menu colors', () => {
        for (const theme of ['light', 'dark']) {
            const keys = Object.keys(flowCanvasThemeVars(theme));
            expect(keys).toEqual(expect.arrayContaining(Object.keys(canvasThemeVars(theme))));
            expect(keys).toEqual(expect.arrayContaining(['--flow-canvas-bg', '--flow-grid', '--menu-accent']));
        }
    });

    it('uses a teal accent distinct from the FSM builder in both themes', () => {
        for (const theme of ['light', 'dark']) {
            const flow = flowCanvasThemeVars(theme);
            const fsm = canvasThemeVars(theme);
            for (const key of ['--palette-header', '--node-id-color', '--palette-bg', '--node-bg']) {
                expect(flow[key]).not.toBe(fsm[key]);
            }
        }
        expect(flowCanvasThemeVars('dark')['--palette-header']).toBe('#5eead4');
        expect(flowCanvasThemeVars('light')['--palette-header']).toBe('#0f766e');
    });
});
