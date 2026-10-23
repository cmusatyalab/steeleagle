import { Handle, Position } from '@xyflow/react';
import { NodeShell } from './FlowNodeParts.jsx';
import { CALLBACK_COLOR } from './flowView.js';

const LOCATION_COLORS = { local: '#a3e8a0', remote: '#7ecfff' };

// An engine service on some daemon. The bottom handle starts callbacks; it
// stays mounted (invisible and unconnectable) when the engine declares no
// events, so an existing callback edge never loses its anchor.
function EngineNode({ data, selected }) {
    const { node, resolution } = data;
    const location = resolution?.location;
    const hasEvents = (resolution?.events?.length ?? 0) > 0;
    return (
        <NodeShell kind="Engine" label={node.engine} data={data} selected={selected}>
            <Handle type="target" id="in" position={Position.Left} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--node-chip-text)', marginTop: 2 }}>
                <span>{node.daemon.name}</span>
                {location && (
                    <span style={{ fontSize: 8, padding: '1px 4px', borderRadius: 3, background: LOCATION_COLORS[location], color: '#000' }}>
                        {location}
                    </span>
                )}
                {resolution?.category && (
                    <span style={{ fontSize: 8, padding: '1px 4px', borderRadius: 3, border: '1px solid var(--node-chip-text)' }}>
                        {resolution.category}
                    </span>
                )}
            </div>
            <Handle type="source" id="out" position={Position.Right} />
            <Handle
                type="source"
                id="cb"
                position={Position.Bottom}
                isConnectable={hasEvents}
                title={hasEvents ? `callback: ${resolution.events.join(', ')}` : undefined}
                style={{ background: CALLBACK_COLOR, opacity: hasEvents ? 1 : 0 }}
            />
        </NodeShell>
    );
}

export default EngineNode;
