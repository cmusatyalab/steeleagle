import { useState, useCallback } from 'react';
import { Handle, Position } from '@xyflow/react';
import { InputText } from 'primereact/inputtext';
import { InputNumber } from 'primereact/inputnumber';
import { Dropdown } from 'primereact/dropdown';

// Maps type_name → icon character
const TYPE_ICONS = {
    TakeOff: '🛫', Land: '🛬', ReturnToHome: '🏠',
    Patrol: '🗺', Track: '🎯', Wait: '⏱',
    Hold: '✋', ElevateToAltitude: '⬆', PrePatrolSequence: '🔄',
    SetGimbalPose: '📷', SetGlobalPosition: '📍', SetRelativePosition: '↗',
    SetHeading: '🧭', SetVelocity: '💨', PrecisionLand: '🎯',
    AvoidTask: '🚧',
};

function FieldInput({ field, value, onChange, namedAreas }) {
    if (field.type === 'boolean') {
        return (
            <Dropdown
                value={value ?? field.default ?? false}
                options={[{ label: 'true', value: true }, { label: 'false', value: false }]}
                onChange={e => onChange(e.value)}
                className="p-inputtext-sm w-full"
            />
        );
    }
    if (field.type === 'number' || field.type === 'integer') {
        return (
            <InputNumber
                value={value ?? field.default ?? 0}
                onValueChange={e => onChange(e.value)}
                className="p-inputtext-sm w-full"
                inputStyle={{ width: '100%' }}
                useGrouping={false}
            />
        );
    }
    if (field.nested_fields?.length) {
        return (
            <div style={{ border: '1px solid #2a3a4a', borderRadius: 4, padding: '6px 8px', marginTop: 2 }}>
                {field.nested_fields.map(nf => {
                    const nestedValue = value?.[nf.name];
                    const isWaypointsArea = field.object_type === 'Waypoints' && nf.name === 'area';
                    return (
                        <div key={nf.name} style={{ marginBottom: 4 }}>
                            <label style={{ fontSize: 9, color: '#888', display: 'block' }}>{nf.name}</label>
                            {isWaypointsArea ? (
                                <Dropdown
                                    value={nestedValue ?? null}
                                    options={namedAreas.length
                                        ? namedAreas.map(a => ({ label: a, value: a }))
                                        : [{ label: '(draw area on Map tab)', value: null }]
                                    }
                                    onChange={e => onChange({ ...(value || {}), [nf.name]: e.value })}
                                    className="p-inputtext-sm w-full"
                                    placeholder="Select area"
                                />
                            ) : (
                                <FieldInput
                                    field={nf}
                                    value={nestedValue}
                                    onChange={val => onChange({ ...(value || {}), [nf.name]: val })}
                                    namedAreas={namedAreas}
                                />
                            )}
                        </div>
                    );
                })}
            </div>
        );
    }
    return (
        <InputText
            value={value ?? field.default ?? ''}
            onChange={e => onChange(e.target.value)}
            className="p-inputtext-sm w-full"
        />
    );
}

function TaskNode({ data, selected }) {
    const { type_name, instance_id, params, isStart, _hasError, schema, namedAreas, onUpdate, onOpenPanel } = data;
    const [expanded, setExpanded] = useState(false);

    const icon = TYPE_ICONS[type_name] || '⚙';
    const fields = schema?.fields ?? [];
    const usePanel = fields.length > 3;

    const handleClick = useCallback(() => {
        if (usePanel) {
            onOpenPanel();
        } else {
            setExpanded(e => !e);
        }
    }, [usePanel, onOpenPanel]);

    function updateParam(fieldName, val) {
        onUpdate({ ...params, [fieldName]: val });
    }

    // Show first 2 non-default params as summary
    const summaryFields = fields.filter(f => f.required || params[f.name] !== undefined).slice(0, 2);

    return (
        <div
            onClick={handleClick}
            style={{
                background: '#1e3040',
                border: `2px solid ${_hasError ? '#ff4444' : isStart ? '#e88080' : '#4a7a9b'}`,
                borderRadius: 8,
                padding: '8px 12px',
                minWidth: 120,
                cursor: 'pointer',
                userSelect: 'none',
            }}
        >
            <Handle type="target" position={Position.Top} />
            <Handle type="source" position={Position.Bottom} />

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: summaryFields.length ? 6 : 0 }}>
                <span style={{ fontSize: 16 }}>{icon}</span>
                <span style={{ fontWeight: 'bold', color: isStart ? '#e88080' : '#fff', fontSize: 12 }}>
                    {type_name}
                </span>
                {isStart && (
                    <span style={{ fontSize: 8, background: '#e88080', color: '#000', padding: '1px 4px', borderRadius: 3, marginLeft: 'auto' }}>
                        START
                    </span>
                )}
            </div>

            {/* Instance ID */}
            <div style={{ fontSize: 9, color: '#7ecfff', marginBottom: 4 }}>{instance_id}</div>

            {/* Collapsed summary */}
            {!expanded && summaryFields.map(f => (
                <div key={f.name} style={{ fontSize: 9, background: '#0d1820', padding: '2px 5px', borderRadius: 3, marginBottom: 2, color: '#aaa' }}>
                    {f.name}: {JSON.stringify(params[f.name] ?? f.default ?? '…')}
                </div>
            ))}

            {/* Expanded inline editing (≤3 fields only) */}
            {expanded && !usePanel && (
                <div style={{ marginTop: 6 }} onClick={e => e.stopPropagation()}>
                    {fields.map(f => (
                        <div key={f.name} style={{ marginBottom: 4 }}>
                            <label style={{ fontSize: 9, color: '#aaa', display: 'block' }}>{f.name}</label>
                            <FieldInput
                                field={f}
                                value={params[f.name]}
                                onChange={val => updateParam(f.name, val)}
                                namedAreas={namedAreas}
                            />
                        </div>
                    ))}
                    {/* Instance ID edit */}
                    <div style={{ marginTop: 4 }}>
                        <label style={{ fontSize: 9, color: '#aaa', display: 'block' }}>instance id</label>
                        <InputText
                            value={instance_id}
                            onChange={e => data.onUpdateId(e.target.value)}
                            className="p-inputtext-sm w-full"
                        />
                    </div>
                </div>
            )}
        </div>
    );
}

export default TaskNode;
