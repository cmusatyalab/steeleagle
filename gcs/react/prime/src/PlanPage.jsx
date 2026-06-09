import { useState, useCallback } from 'react'
import { TabView, TabPanel } from 'primereact/tabview';
import { Background, Controls, MiniMap, ReactFlow,
         applyNodeChanges, applyEdgeChanges } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import MapDraw from './MapDraw.jsx';
import { InputTextarea } from 'primereact/inputtextarea';

function PlanPage({ vehicles, squadList }) {
    const [nodes, setNodes] = useState([]);
    const [edges, setEdges] = useState([]);
    const [eventInstances, setEventInstances] = useState([]);
    const [startNodeId, setStartNodeId] = useState(null);
    const [schema, setSchema] = useState({ actions: {}, events: {} });
    const [compiledMission, setCompiledMission] = useState(null);
    const [features, setFeatures] = useState(JSON.stringify({ type: 'FeatureCollection', features: [] }));

    const onNodesChange = useCallback(
        (changes) => setNodes((ns) => applyNodeChanges(changes, ns)), []);
    const onEdgesChange = useCallback(
        (changes) => setEdges((es) => applyEdgeChanges(changes, es)), []);

    return (
        <TabView className="h-full">
            <TabPanel header="FSM Builder" leftIcon="pi pi-share-alt mr-2">
                <div className="flex" style={{ height: 'calc(100vh - 180px)' }}>
                    {/* Palette placeholder — filled in Task 7 */}
                    <div style={{ width: 180, background: '#1e2a38', flexShrink: 0 }}>
                        <p className="p-2 text-sm text-color-secondary">Palette loading...</p>
                    </div>
                    {/* Canvas */}
                    <div className="flex-1" style={{ position: 'relative' }}>
                        <ReactFlow
                            colorMode="dark"
                            nodes={nodes}
                            edges={edges}
                            onNodesChange={onNodesChange}
                            onEdgesChange={onEdgesChange}
                            fitView
                        >
                            <Controls />
                            <MiniMap />
                            <Background variant="dots" gap={12} size={1} />
                        </ReactFlow>
                    </div>
                </div>
                {/* Toolbar placeholder — filled in Task 10 */}
                <div className="flex gap-2 p-2" style={{ borderTop: '1px solid #2a3a4a' }}>
                    <span className="text-sm text-color-secondary">
                        {nodes.length} actions · {eventInstances.length} events
                        {startNodeId ? ` · start: ${nodes.find(n => n.id === startNodeId)?.data?.instance_id ?? startNodeId}` : ' · ⚠ no start set'}
                    </span>
                </div>
            </TabPanel>

            <TabPanel header="Map" leftIcon="pi pi-map mr-2">
                <div style={{ height: 'calc(100vh - 180px)' }}>
                    <MapDraw features={features} setFeatures={setFeatures} />
                </div>
            </TabPanel>

            <TabPanel header="JSON Output" leftIcon="pi pi-code mr-2">
                <InputTextarea
                    className="w-full h-full"
                    style={{ height: 'calc(100vh - 200px)', fontFamily: 'monospace', fontSize: 12 }}
                    readOnly
                    value={compiledMission ? JSON.stringify(compiledMission, null, 2) : '// compile a mission to see output'}
                />
            </TabPanel>
        </TabView>
    );
}

export default PlanPage;
