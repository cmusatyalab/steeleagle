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
    const [eventsOpen, setEventsOpen] = useState(true);
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
        <div style={{ width: 180, background: '#1a2530', height: '100%', overflowY: 'auto', borderRight: '1px solid #2a3a4a' }}>
            {/* Actions section */}
            <div
                className="flex align-items-center gap-2 p-2"
                style={{ cursor: 'pointer', borderBottom: '1px solid #2a3a4a', userSelect: 'none' }}
                onClick={() => setActionsOpen(o => !o)}
            >
                <i className={`pi pi-${actionsOpen ? 'chevron-down' : 'chevron-right'}`} style={{ fontSize: 10 }} />
                <span style={{ fontSize: 11, color: '#7ecfff', textTransform: 'uppercase', letterSpacing: 1 }}>Actions</span>
            </div>
            {actionsOpen && Object.keys(schema.actions).map(typeName => (
                <div
                    key={typeName}
                    draggable
                    onDragStart={e => onDragStart(e, typeName)}
                    title={schema.actions[typeName].description}
                    style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '5px 10px', cursor: 'grab', fontSize: 11,
                        borderBottom: '1px solid #1e2a38',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = '#1e3040'}
                    onMouseLeave={e => e.currentTarget.style.background = ''}
                >
                    <span>{TYPE_ICONS[typeName] || '⚙'}</span>
                    <span style={{ color: '#fff' }}>{typeName}</span>
                </div>
            ))}

            {/* Events section (reference only) */}
            <div
                className="flex align-items-center gap-2 p-2"
                style={{ cursor: 'pointer', borderBottom: '1px solid #2a3a4a', userSelect: 'none', marginTop: 8 }}
                onClick={() => setEventsOpen(o => !o)}
            >
                <i className={`pi pi-${eventsOpen ? 'chevron-down' : 'chevron-right'}`} style={{ fontSize: 10 }} />
                <span style={{ fontSize: 11, color: '#c47aff', textTransform: 'uppercase', letterSpacing: 1 }}>Events</span>
            </div>
            {eventsOpen && Object.keys(schema.events).map(typeName => (
                <div
                    key={typeName}
                    title={schema.events[typeName].description}
                    style={{
                        padding: '4px 10px', fontSize: 11,
                        borderBottom: '1px solid #1e2a38', color: '#c47aff',
                    }}
                >
                    {typeName}
                </div>
            ))}
        </div>
    );
}

export default FsmPalette;
