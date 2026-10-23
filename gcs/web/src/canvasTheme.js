// CSS variables read by the node and palette components shared by the FSM
// Builder and Flow Builder canvases.
export function canvasThemeVars(theme) {
    const light = theme === 'light';
    return {
        '--node-bg':            light ? '#ffffff' : '#1e3040',
        '--node-text':          light ? '#111827' : '#ffffff',
        '--node-id-color':      light ? '#1d4ed8' : '#7ecfff',
        '--node-chip-bg':       light ? '#f1f5f9' : '#0d1820',
        '--node-chip-text':     light ? '#475569' : '#aaaaaa',
        '--palette-bg':         light ? '#f8fafc' : '#1a2530',
        '--palette-border':     light ? '#e2e8f0' : '#2a3a4a',
        '--palette-header':     light ? '#1d4ed8' : '#7ecfff',
        '--palette-item-text':  light ? '#1e293b' : '#ffffff',
        '--palette-item-div':   light ? '#e2e8f0' : '#1e2a38',
        '--palette-item-hover': light ? '#dbeafe' : '#1e3040',
    };
}

// The Flow Builder's variant: the same variables recolored teal (with its
// own canvas background, grid, and context-menu accent), so a dataflow
// never reads as an FSM at a glance.
export function flowCanvasThemeVars(theme) {
    const light = theme === 'light';
    return {
        ...canvasThemeVars(theme),
        '--node-bg':            light ? '#f7fdfc' : '#163234',
        '--node-id-color':      light ? '#0f766e' : '#5eead4',
        '--node-chip-bg':       light ? '#f0fdfa' : '#0b1d1c',
        '--palette-bg':         light ? '#f0fdfa' : '#122826',
        '--palette-border':     light ? '#99f6e4' : '#1f4744',
        '--palette-header':     light ? '#0f766e' : '#5eead4',
        '--palette-item-div':   light ? '#ccfbf1' : '#1a3634',
        '--palette-item-hover': light ? '#ccfbf1' : '#1d3f3c',
        '--flow-canvas-bg':     light ? '#f5fbfa' : '#0d1a1a',
        '--flow-grid':          light ? '#d5efeb' : '#1b3332',
        '--menu-accent':        '#2a9d8f',
    };
}
