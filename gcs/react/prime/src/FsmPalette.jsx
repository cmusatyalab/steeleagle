import { useEffect, useState } from 'react';
import { getApiUrl } from './App.jsx';

const TYPE_ICONS = {
    TakeOff: '🛫', Land: '🛬', ReturnToHome: '🏠',
    Patrol: '🗺', Track: '🎯', Wait: '⏱',
    Hold: '✋', ElevateToAltitude: '⬆', PrePatrolSequence: '🔄',
    SetGimbalPose: '📷', SetGlobalPosition: '📍', SetRelativePosition: '↗',
    SetHeading: '🧭', SetVelocity: '💨', PrecisionLand: '🎯',
    AvoidTask: '🚧',
};

function FsmPalette({ onSchemaLoaded }) {
    const [schema, setSchema] = useState({ actions: {}, events: {} });
    const [actionsOpen, setActionsOpen] = useState(true);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetch(getApiUrl('/api/schema'))
            .then(r => r.json())
            .then(data => {
                setSchema(data);
                onSchemaLoaded(data);
                setLoading(false);
            })
            .catch(e => { setError(e.message); setLoading(false); });
    }, []);

    function onDragStart(event, typeName) {
        event.dataTransfer.setData('application/reactflow/typeName', typeName);
        event.dataTransfer.effectAllowed = 'move';
    }

    if (loading) return <div className="p-2 text-sm text-color-secondary">Loading schema…</div>;
    if (error) return <div className="p-2 text-sm" style={{ color: '#e88' }}>Schema error: {error}</div>;

    return (
        <div style={{ width: 180, background: 'var(--palette-bg)', height: '100%', overflowY: 'auto', borderRight: '1px solid var(--palette-border)' }}>
            <div
                className="flex align-items-center gap-2 p-2"
                style={{ cursor: 'pointer', borderBottom: '1px solid var(--palette-border)', userSelect: 'none' }}
                onClick={() => setActionsOpen(o => !o)}
            >
                <i className={`pi pi-${actionsOpen ? 'chevron-down' : 'chevron-right'}`} style={{ fontSize: 10 }} />
                <span style={{ fontSize: 12, color: 'var(--palette-header)', textTransform: 'uppercase', letterSpacing: 1 }}>Actions</span>
            </div>
            {actionsOpen && Object.keys(schema.actions).map(typeName => (
                <div
                    key={typeName}
                    draggable
                    onDragStart={e => onDragStart(e, typeName)}
                    title={schema.actions[typeName].description}
                    style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '5px 10px', cursor: 'grab', fontSize: 13,
                        borderBottom: '1px solid var(--palette-item-div)',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--palette-item-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = ''}
                >
                    <span>{TYPE_ICONS[typeName] || '⚙'}</span>
                    <span style={{ color: 'var(--palette-item-text)' }}>{typeName}</span>
                </div>
            ))}
        </div>
    );
}

export default FsmPalette;
