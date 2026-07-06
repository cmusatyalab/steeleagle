import { Button } from 'primereact/button';

const GEO_ICON = { Polygon: '⬡', LineString: '╱', Point: '●' };

function displayName(feature, index) {
    if (feature.properties?.name) return feature.properties.name;
    return `${feature.geometry?.type ?? 'Feature'} ${index + 1}`;
}

function FeatureList({ features, selectedFeatureId, onSelect, onDelete }) {
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
                        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {displayName(feature, index)}
                        </span>
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
