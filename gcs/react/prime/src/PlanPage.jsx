import { useRef, useEffect, useState, useCallback } from 'react'
import { Editor } from 'primereact/editor';
import { Splitter, SplitterPanel } from 'primereact/splitter';
import { ReactFlow, applyNodeChanges, applyEdgeChanges, addEdge, Controls, MiniMap, Background } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import MapDraw from './MapDraw.jsx';
import { InputTextarea } from "primereact/inputtextarea";

const initialNodes = [
    { id: 'n1', position: { x: 0, y: 0 }, data: { label: 'Patrol' } },
    { id: 'n2', position: { x: 0, y: 100 }, data: { label: 'Track' } },
];
const initialEdges = [{ id: 'n1-n2', source: 'n1', target: 'n2' }];

function PlanPage() {
    const [editorContent, setEditorContent] = useState('');
    const [nodes, setNodes] = useState(initialNodes);
    const [edges, setEdges] = useState(initialEdges);
    const [features, setFeatures] = useState(JSON.stringify({"type":"FeatureCollection","features":[]}));
    const [dsl, setDsl] = useState("");

    const onNodesChange = useCallback(
        (changes) => setNodes((nodesSnapshot) => applyNodeChanges(changes, nodesSnapshot)),
        [],
    );
    const onEdgesChange = useCallback(
        (changes) => setEdges((edgesSnapshot) => applyEdgeChanges(changes, edgesSnapshot)),
        [],
    );
    const onConnect = useCallback(
        (params) => setEdges((edgesSnapshot) => addEdge(params, edgesSnapshot)),
        [],
    );
    return (
        <>
            <Splitter className="h-30rem flex align-items-center justify-content-center">
                <SplitterPanel style={{ height: '100%' }} className="flex align-items-center justify-content-center m-2" size={50} minSize={50}>
                    <MapDraw features={features} setFeatures={setFeatures} />
                </SplitterPanel>
                <SplitterPanel style={{ height: '100%' }} className="flex flex-column align-items-center justify-content-center m-2 gap-2" size={50} minSize={50}>
                    <ReactFlow
                        colorMode="dark"
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        fitView
                    >
                        <Controls />
                        <MiniMap />
                        <Background variant="dots" gap={12} size={1} />
                    </ReactFlow>
                </SplitterPanel>
            </Splitter>
            <Splitter className="h-10rem flex align-items-center justify-content-center">
                <SplitterPanel className="flex align-items-center justify-content-center m-2" size={50} minSize={50}>
                    <InputTextarea className="h-auto w-full" value={features} onChange={(e) => setFeatures(e.target.value)} rows={5} cols={30} />
                </SplitterPanel>
                <SplitterPanel className="flex align-items-center justify-content-center m-2" size={50} minSize={50}>
                    <InputTextarea className="h-auto w-full" value={dsl} rows={5} cols={30} />
                </SplitterPanel>
            </Splitter>
        </>
    );

}

export default PlanPage;
