import { useCallback } from 'react';
import { Handle, Position } from '@xyflow/react';

const TYPE_ICONS = {
    TakeOff: '🛫', Land: '🛬', ReturnToHome: '🏠',
    Patrol: '🗺', Track: '🎯', Wait: '⏱',
    Hold: '✋', ElevateToAltitude: '⬆', PrePatrolSequence: '🔄',
    SetGimbalPose: '📷', SetGlobalPosition: '📍', SetRelativePosition: '↗',
    SetHeading: '🧭', SetVelocity: '💨', PrecisionLand: '🎯',
    AvoidTask: '🚧',
};

function TaskNode({ data }) {
    const { type_name, instance_id, params, isStart, _hasError, _warnings, schema, onOpenPanel } = data;

    const icon = TYPE_ICONS[type_name] || '⚙';
    const fields = schema?.fields ?? [];

    const handleClick = useCallback(() => {
        onOpenPanel();
    }, [onOpenPanel]);

    const summaryFields = fields.filter(f => f.required || params[f.name] !== undefined).slice(0, 2);

    function summarise(f) {
        const v = params[f.name] ?? f.default;
        if (v === null || v === undefined) return '—';
        if (typeof v === 'object') return v.area ?? JSON.stringify(v);
        return String(v);
    }

    // Border priority: compile error > pre-compile warning > start state > default
    const borderColor = _hasError        ? '#ff4444'
                      : _warnings?.length ? '#e8c87a'
                      : isStart           ? '#a3e8a0'
                      :                    '#4a7a9b';

    return (
        <div
            onClick={handleClick}
            style={{
                background: '#1e3040',
                border: `2px solid ${borderColor}`,
                borderRadius: 8,
                padding: '8px 12px',
                minWidth: 120,
                cursor: 'pointer',
                userSelect: 'none',
            }}
        >
            <Handle type="target" position={Position.Top} />
            <Handle type="source" position={Position.Bottom} />

            {/* Header row: icon · type name · START chip · warning badge */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: summaryFields.length ? 4 : 0 }}>
                <span style={{ fontSize: 16 }}>{icon}</span>
                <span style={{ fontWeight: 'bold', color: isStart ? '#a3e8a0' : '#fff', fontSize: 12 }}>
                    {type_name}
                </span>
                {isStart && (
                    <span style={{
                        fontSize: 8, background: '#a3e8a0', color: '#000',
                        padding: '1px 4px', borderRadius: 3,
                        marginLeft: _warnings?.length ? 4 : 'auto',
                    }}>
                        START
                    </span>
                )}
                {_warnings?.length > 0 && (
                    <span
                        title={_warnings.join('\n')}
                        style={{
                            fontSize: 8, background: '#e8c87a', color: '#000',
                            padding: '1px 4px', borderRadius: 3, marginLeft: 'auto',
                        }}
                    >
                        ⚠ {_warnings.length}
                    </span>
                )}
            </div>

            {/* Instance ID */}
            <div style={{ fontSize: 9, color: '#7ecfff', marginBottom: summaryFields.length ? 4 : 0 }}>
                {instance_id}
            </div>

            {/* Param summary chips */}
            {summaryFields.map(f => (
                <div key={f.name} style={{ fontSize: 9, background: '#0d1820', padding: '2px 5px', borderRadius: 3, marginBottom: 2, color: '#aaa' }}>
                    {f.name}: {summarise(f)}
                </div>
            ))}
        </div>
    );
}

export default TaskNode;
