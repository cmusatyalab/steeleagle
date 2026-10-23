import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath } from '@xyflow/react';
import { CALLBACK_COLOR, ERROR_COLOR } from './flowView.js';

// A callback: an engine signalling an event to another node. Dashed and
// colored apart from output edges, labeled with the event name. Callbacks
// between the same two nodes are shifted apart (data.shift): along the
// source's bottom edge and, inversely, the target's left edge, so their
// paths nest instead of crossing, with their labels stacked.
function CallbackEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, markerEnd, data, selected }) {
    const shift = data?.shift ?? 0;
    // The bend depth varies too, so the runs under the source don't overlap;
    // its sign keeps the nesting when the target is to the left.
    const [path, labelX, labelY] = getSmoothStepPath({
        sourceX: sourceX + shift, sourceY, sourcePosition, targetX, targetY: targetY - shift, targetPosition,
        offset: 20 + (targetX < sourceX ? shift : -shift),
    });
    const color = data?.errors?.length ? ERROR_COLOR : CALLBACK_COLOR;
    return (
        <>
            <BaseEdge id={id} path={path} markerEnd={markerEnd} style={{ stroke: color, strokeDasharray: '6 4', strokeWidth: selected ? 2.5 : 1.5 }} />
            <EdgeLabelRenderer>
                <div
                    className="nodrag nopan"
                    style={{
                        position: 'absolute',
                        transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY + shift * 2}px)`,
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
