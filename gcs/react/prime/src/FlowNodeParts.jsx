import { SELECTED_COLOR, ERROR_COLOR, nodeBorderColor, statusText } from './flowView.js';

// The frame both flow node types share: border colored by validation state,
// kind and label header, children, and a status line (output type, or why
// the node doesn't resolve). Hovering shows the node's issues.
export function NodeShell({ kind, label, data, selected, children }) {
    const { resolution, errors, warnings } = data;
    const issues = [...errors, ...warnings];
    return (
        <div
            title={issues.length ? issues.join('\n') : undefined}
            style={{
                background: 'var(--node-bg)',
                border: `2px solid ${nodeBorderColor(data)}`,
                borderRadius: 8,
                padding: '8px 12px',
                minWidth: 150,
                userSelect: 'none',
                boxShadow: selected ? `0 0 0 2px ${SELECTED_COLOR}` : undefined,
            }}
        >
            <div style={{ fontSize: 9, color: 'var(--node-id-color)', textTransform: 'uppercase', letterSpacing: 1 }}>{kind}</div>
            <div style={{ fontWeight: 'bold', fontSize: 12, color: 'var(--node-text)' }}>{label}</div>
            {children}
            <div style={{ fontSize: 9, marginTop: 4, color: resolution && !resolution.resolved ? ERROR_COLOR : 'var(--node-id-color)' }}>
                {statusText(resolution, data.forwarded)}
            </div>
        </div>
    );
}
