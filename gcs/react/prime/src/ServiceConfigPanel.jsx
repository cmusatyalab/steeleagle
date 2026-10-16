import React from 'react';
import { Button } from 'primereact/button';
import { configGroups } from './pluginView.js';

// Read-only view of one service's config entry, shown when its row in the
// Services tab is expanded. Editing goes through the Configure dialog.
function ServiceConfigPanel({ inst, onEdit }) {
    return (
        <div className="flex flex-column gap-2 px-3 py-2">
            <div className="flex flex-wrap gap-4">
                {configGroups(inst).map(({ title, rows }) => (
                    <div key={title} style={{ minWidth: '14rem' }}>
                        <div className="font-semibold text-sm mb-1">{title}</div>
                        {rows.length === 0 && <div className="text-sm text-color-secondary">None</div>}
                        {rows.map(([label, value]) => (
                            <div key={label} className="flex gap-2 text-sm py-1" style={{ borderBottom: '1px solid var(--surface-border)' }}>
                                <span className="text-color-secondary" style={{ width: '7rem', flexShrink: 0 }}>{label}</span>
                                <span style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{value === '' ? '""' : value}</span>
                            </div>
                        ))}
                    </div>
                ))}
            </div>
            <div>
                <Button label="Edit in Configure" icon="pi pi-cog" size="small" text onClick={onEdit} />
            </div>
        </div>
    );
}

export default ServiceConfigPanel;
