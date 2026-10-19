import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath } from '@xyflow/react';
import { CALLBACK_COLOR, ERROR_COLOR } from './flowView.js';

// A callback: an engine signalling an event to another node. Dashed and
// colored apart from output edges, labeled with the event name.
function CallbackEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, markerEnd, data, selected }) {
    const [path, labelX, labelY] = getSmoothStepPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
    const color = data?.errors?.length ? ERROR_COLOR : CALLBACK_COLOR;
    return (
        <>
            <BaseEdge id={id} path={path} markerEnd={markerEnd} style={{ stroke: color, strokeDasharray: '6 4', strokeWidth: selected ? 2.5 : 1.5 }} />
            <EdgeLabelRenderer>
                <div
                    className="nodrag nopan"
                    style={{
                        position: 'absolute',
                        transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
                        fontSize: 10,
                        padding: '1px 5px',
                        borderRadius: 3,
                        background: 'var(--node-bg)',
                        color,
                        border: `1px solid ${color}`,
                        pointerEvents: 'all',
                    }}
                >
                    {data?.edge.event}
                </div>
            </EdgeLabelRenderer>
        </>
    );
}

export default CallbackEdge;
