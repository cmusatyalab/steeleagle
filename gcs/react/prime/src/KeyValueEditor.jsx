import React from 'react';
import { InputText } from 'primereact/inputtext';
import { Dropdown } from 'primereact/dropdown';
import { InputSwitch } from 'primereact/inputswitch';
import { Button } from 'primereact/button';
import { KV_TYPES, fromRows, newRow, retype } from './kvArgs.js';

// Controlled editor for a plugin's args table. Arrays and tables show as
// read-only rows (edit them in Raw TOML); they are still removable.
function KeyValueEditor({ rows, onChange, disabled = false, addLabel = 'Add arg' }) {
    const { errors } = fromRows(rows);
    const update = (id, patch) => onChange(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));

    return (
        <div className="flex flex-column gap-2">
            {rows.length === 0 && <div className="text-color-secondary text-sm">No args.</div>}
            {rows.map((row) => (
                <div key={row.id} className="flex flex-column gap-1">
                    <div className="flex gap-2 align-items-center">
                        <InputText
                            value={row.key}
                            placeholder="key"
                            onChange={(e) => update(row.id, { key: e.target.value })}
                            disabled={disabled || row.type === 'other'}
                            invalid={!!errors[row.id]}
                            style={{ width: '10rem' }}
                        />
                        {row.type === 'other' ? (
                            <span className="text-sm text-color-secondary flex-1 overflow-hidden text-overflow-ellipsis" style={{ fontFamily: 'monospace' }}>
                                {JSON.stringify(row.value)} (edit in Raw TOML)
                            </span>
                        ) : (
                            <>
                                <Dropdown
                                    value={row.type}
                                    options={KV_TYPES}
                                    onChange={(e) => onChange(rows.map((r) => (r.id === row.id ? retype(r, e.value) : r)))}
                                    disabled={disabled}
                                    style={{ width: '8rem' }}
                                />
                                {row.type === 'boolean' ? (
                                    <div className="flex-1">
                                        <InputSwitch checked={row.value} onChange={(e) => update(row.id, { value: e.value })} disabled={disabled} />
                                    </div>
                                ) : (
                                    <InputText
                                        value={row.value}
                                        placeholder="value"
                                        onChange={(e) => update(row.id, { value: e.target.value })}
                                        disabled={disabled}
                                        className="flex-1"
                                    />
                                )}
                            </>
                        )}
                        <Button
                            icon="pi pi-times"
                            text
                            rounded
                            size="small"
                            severity="danger"
                            aria-label={`Remove ${row.key || 'arg'}`}
                            onClick={() => onChange(rows.filter((r) => r.id !== row.id))}
                            disabled={disabled}
                        />
                    </div>
                    {errors[row.id] && <small className="p-error">{errors[row.id]}</small>}
                </div>
            ))}
            <div>
                <Button label={addLabel} icon="pi pi-plus" text size="small" onClick={() => onChange([...rows, newRow()])} disabled={disabled} />
            </div>
        </div>
    );
}

export default KeyValueEditor;
