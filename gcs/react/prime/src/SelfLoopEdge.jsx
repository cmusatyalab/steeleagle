import { BaseEdge, EdgeLabelRenderer, useReactFlow } from '@xyflow/react';

function SelfLoopEdge({ id, source, sourceX, sourceY, targetX, targetY, label, style }) {
    const { getNode } = useReactFlow();
    const node = getNode(source);
    const nodeWidth = node?.measured?.width ?? 120;
    // Extend far enough right to clear the node edge with breathing room
    const offset = nodeWidth / 2 + 50;

    // D-shaped cubic bezier going to the right of the node.
    // sourceX === targetX (same node center); sourceY > targetY (bottom vs top handle).
    const path = [
        `M ${sourceX},${sourceY}`,
        `C ${sourceX + offset},${sourceY}`,
        `  ${targetX + offset},${targetY}`,
        `  ${targetX},${targetY}`,
    ].join(' ');

    // Place the label at the rightmost point of the curve, vertically centred
    const labelX = sourceX + offset + 16;
    const labelY = (sourceY + targetY) / 2;

    return (
        <>
            <BaseEdge id={id} path={path} style={style} />
            {label && (
                <EdgeLabelRenderer>
                    <div
                        style={{
                            position: 'absolute',
                            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
                            pointerEvents: 'all',
                            fontSize: 10,
                            color: style?.stroke,
                            background: '#131d27',
                            padding: '1px 5px',
                            borderRadius: 3,
                        }}
                        className="nodrag nopan"
                    >
                        {label}
                    </div>
                </EdgeLabelRenderer>
            )}
        </>
    );
}

export default SelfLoopEdge;
