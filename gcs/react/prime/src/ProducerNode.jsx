import { Handle, Position } from '@xyflow/react';
import { NodeShell } from './FlowNodeParts.jsx';
import { CALLBACK_COLOR } from './flowView.js';

// One stream of the flow's vehicle. The left handle only takes callbacks
// (output edges never end at a producer); the right handle feeds engines.
// Primary cameras are starred, and disabled while another producer streams
// one (flowModel.streamChoices).
function ProducerNode({ data, selected }) {
    const { node, label, streamChoices, onChangeStream } = data;
    return (
        <NodeShell kind="Producer" label={label} data={data} selected={selected}>
            <Handle type="target" id="cb-in" position={Position.Left} style={{ background: CALLBACK_COLOR }} />
            <select
                className="nodrag"
                value={node.stream}
                onChange={(e) => onChangeStream?.(e.target.value)}
                style={{ fontSize: 11, marginTop: 4, width: '100%' }}
            >
                {streamChoices.map((c) => (
                    <option key={c.name} value={c.name} disabled={c.disabled} title={c.reason ?? undefined}>
                        {c.primary ? `${c.name} ★` : c.name}
                    </option>
                ))}
            </select>
            {node.tokens !== 1 && (
                <div style={{ fontSize: 9, color: 'var(--node-chip-text)', marginTop: 2 }}>tokens: {node.tokens}</div>
            )}
            <Handle type="source" id="out" position={Position.Right} />
        </NodeShell>
    );
}

export default ProducerNode;
