import { useState } from 'react';
import { Button } from 'primereact/button';
import { InputText } from 'primereact/inputtext';

const GEO_ICON = { Polygon: '⬡', LineString: '╱', Point: '●' };

function displayName(feature, index) {
    if (feature.properties?.name) return feature.properties.name;
    return `${feature.geometry?.type ?? 'Feature'} ${index + 1}`;
}

function FeatureList({ features, selectedFeatureId, onSelect, onDelete, onRename }) {
    const [editingId, setEditingId] = useState(null);
    const [editValue, setEditValue] = useState('');

    function startEditing(e, feature) {
        e.stopPropagation();
        setEditingId(feature.id);
        setEditValue(feature.properties?.name || '');
    }

    function commitEdit() {
        if (editingId != null) onRename(editingId, editValue.trim());
        setEditingId(null);
    }

    function cancelEdit() {
        setEditingId(null);
    }

    return (
        <div style={{
            width: 220,
            flexShrink: 0,
            background: '#1a2530',
            borderRight: '1px solid #2a3a4a',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
        }}>
            <div style={{
                padding: '8px 12px',
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.05em',
                color: '#7ecfff',
                borderBottom: '1px solid #2a3a4a',
                textTransform: 'uppercase',
                flexShrink: 0,
            }}>
                Features ({features.length})
            </div>
            {features.length === 0 && (
                <div style={{ padding: '12px', fontSize: 12, color: '#666' }}>
                    No features drawn yet.
                </div>
            )}
            {features.map((feature, index) => {
                const isSelected = feature.id === selectedFeatureId;
                return (
                    <div
                        key={feature.id}
                        onClick={() => onSelect(feature.id)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                            padding: '7px 10px',
                            cursor: 'pointer',
                            background: isSelected ? '#1e3040' : 'transparent',
                            borderBottom: '1px solid #1e2a38',
                            fontSize: 12,
                            color: isSelected ? '#fff' : '#ccc',
                        }}
                        onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = '#1e2a38'; }}
                        onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
                    >
                        <span style={{ fontSize: 14, color: '#3bb2d0', flexShrink: 0 }}>
                            {GEO_ICON[feature.geometry?.type] ?? '?'}
                        </span>
                        {editingId === feature.id ? (
                            <InputText
                                value={editValue}
                                onChange={e => setEditValue(e.target.value)}
                                placeholder="e.g. AreaB"
                                autoFocus
                                className="p-inputtext-sm"
                                style={{ flex: 1, width: 0 }}
                                onClick={e => e.stopPropagation()}
                                onBlur={commitEdit}
                                onKeyDown={e => {
                                    if (e.key === 'Enter') commitEdit();
                                    else if (e.key === 'Escape') cancelEdit();
                                }}
                            />
                        ) : (
                            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {displayName(feature, index)}
                            </span>
                        )}
                        <Button
                            icon="pi pi-pencil"
                            size="small"
                            text
                            style={{ padding: '2px 4px', flexShrink: 0 }}
                            onClick={e => startEditing(e, feature)}
                        />
                        <Button
                            icon="pi pi-trash"
                            size="small"
                            text
                            severity="danger"
                            style={{ padding: '2px 4px', flexShrink: 0 }}
                            onClick={e => { e.stopPropagation(); onDelete(feature.id); }}
                        />
                    </div>
                );
            })}
        </div>
    );
}

export default FeatureList;
