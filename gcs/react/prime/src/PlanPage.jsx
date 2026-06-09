import { useState, useCallback, useRef, useEffect } from 'react';
import { TabView, TabPanel } from 'primereact/tabview';
import { Button } from 'primereact/button';
import { Toast } from 'primereact/toast';
import { InputTextarea } from 'primereact/inputtextarea';
import {
    ReactFlow, Background, Controls, MiniMap,
    applyNodeChanges, applyEdgeChanges, addEdge,
    useReactFlow, ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import tokml from 'tokml';
import MapDraw from './MapDraw.jsx';
import TaskNode from './TaskNode.jsx';
import TaskNodePanel from './TaskNodePanel.jsx';
import EdgePanel from './EdgePanel.jsx';
import FsmPalette from './FsmPalette.jsx';
import ConnectModal from './ConnectModal.jsx';
import { getApiUrl } from './App.jsx';

const nodeTypes = { taskNode: TaskNode };

let _nodeIdCounter = 1;
function nextNodeId() { return `node-${_nodeIdCounter++}`; }

// Extract named areas from GeoJSON features string
function getNamedAreas(featuresStr) {
    try {
        const fc = typeof featuresStr === 'string' ? JSON.parse(featuresStr) : featuresStr;
        return (fc.features || [])
            .map(f => f.properties?.name)
            .filter(Boolean);
    } catch { return []; }
}

function FsmCanvas({ nodes, edges, setNodes, setEdges, eventInstances, setEventInstances,
                     startNodeId, setStartNodeId, schema, features, panelNode, setPanelNode,
                     setPanelEdgeId, toast }) {
    const { screenToFlowPosition } = useReactFlow();
    const [connectModal, setConnectModal] = useState({ visible: false, connection: null });
    const [contextMenu, setContextMenu] = useState(null);
    const namedAreas = getNamedAreas(features);

    const onNodesChange = useCallback((changes) => setNodes(ns => applyNodeChanges(changes, ns)), []);
    const onEdgesChange = useCallback((changes) => setEdges(es => applyEdgeChanges(changes, es)), []);

    // Called when a connection is drawn between two handles (including self-loops)
    const onConnect = useCallback((connection) => {
        setConnectModal({ visible: true, connection });
    }, []);

    const onEdgeClick = useCallback((event, edge) => {
        setPanelEdgeId(edge.id);
    }, [setPanelEdgeId]);

    function confirmConnect(connection, eventId) {
        setEdges(es => addEdge({
            ...connection,
            data: { eventId },
            label: eventId,
            animated: eventId !== 'done',
            style: { stroke: eventId === 'done' ? '#a3e8a0' : '#c47aff' },
            labelStyle: { fill: eventId === 'done' ? '#a3e8a0' : '#c47aff', fontSize: 10 },
        }, es));
    }

    // Drag from palette onto canvas
    const onDragOver = useCallback((event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    const onDrop = useCallback((event) => {
        event.preventDefault();
        const typeName = event.dataTransfer.getData('application/reactflow/typeName');
        if (!typeName) return;

        const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
        const id = nextNodeId();
        const isFirst = nodes.length === 0;

        // Build defaults from schema
        const fields = schema.actions[typeName]?.fields ?? [];
        const defaultParams = Object.fromEntries(
            fields.filter(f => 'default' in f).map(f => [f.name, f.default])
        );

        const base = typeName.replace(/([A-Z])/g, '_$1').toLowerCase().replace(/^_/, '');
        const count = nodes.filter(n => n.data.type_name === typeName).length;
        const instanceId = `${base}_${count + 1}`;

        const newNode = {
            id,
            type: 'taskNode',
            position,
            data: {
                type_name: typeName,
                instance_id: instanceId,
                params: defaultParams,
                isStart: isFirst,
                schema: schema.actions[typeName],
                namedAreas,
                onUpdate: (params) => setNodes(ns => ns.map(n => n.id === id ? { ...n, data: { ...n.data, params } } : n)),
                onUpdateId: (newId) => setNodes(ns => ns.map(n => n.id === id ? { ...n, data: { ...n.data, instance_id: newId } } : n)),
                onOpenPanel: () => setPanelNode(id),
            },
        };

        setNodes(ns => [...ns, newNode]);
        if (isFirst) setStartNodeId(id);
    }, [nodes, schema, namedAreas, screenToFlowPosition]);

    // Right-click context menu on a node
    const onNodeContextMenu = useCallback((event, node) => {
        event.preventDefault();
        setContextMenu({ x: event.clientX, y: event.clientY, nodeId: node.id });
    }, []);

    function setAsStart(nodeId) {
        setStartNodeId(nodeId);
        setNodes(ns => ns.map(n => ({ ...n, data: { ...n.data, isStart: n.id === nodeId } })));
        setContextMenu(null);
    }

    function deleteNode(nodeId) {
        setNodes(ns => ns.filter(n => n.id !== nodeId));
        setEdges(es => es.filter(e => e.source !== nodeId && e.target !== nodeId));
        if (startNodeId === nodeId) setStartNodeId(null);
        setContextMenu(null);
    }

    // Sync namedAreas into all node data when features change
    useEffect(() => {
        setNodes(ns => ns.map(n => ({ ...n, data: { ...n.data, namedAreas } })));
    }, [features]);

    return (
        <div style={{ flex: 1, position: 'relative' }} onClick={() => setContextMenu(null)}>
            <ReactFlow
                colorMode="dark"
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onEdgeClick={onEdgeClick}
                onDragOver={onDragOver}
                onDrop={onDrop}
                onNodeContextMenu={onNodeContextMenu}
                fitView
            >
                <Controls />
                <MiniMap />
                <Background variant="dots" gap={12} size={1} />
            </ReactFlow>

            {/* Context menu */}
            {contextMenu && (
                <div
                    style={{
                        position: 'fixed', left: contextMenu.x, top: contextMenu.y,
                        background: '#1e2a38', border: '1px solid #4a7a9b', borderRadius: 6,
                        zIndex: 1000, minWidth: 160, boxShadow: '0 4px 12px #00000088',
                    }}
                    onClick={e => e.stopPropagation()}
                >
                    <div
                        style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 12 }}
                        onMouseEnter={e => e.currentTarget.style.background = '#2a3a50'}
                        onMouseLeave={e => e.currentTarget.style.background = ''}
                        onClick={() => setAsStart(contextMenu.nodeId)}
                    >
                        ▶ Set as Start State
                    </div>
                    <div
                        style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 12, color: '#e88080' }}
                        onMouseEnter={e => e.currentTarget.style.background = '#2a3a50'}
                        onMouseLeave={e => e.currentTarget.style.background = ''}
                        onClick={() => deleteNode(contextMenu.nodeId)}
                    >
                        🗑 Delete
                    </div>
                </div>
            )}

            <ConnectModal
                visible={connectModal.visible}
                onHide={() => setConnectModal({ visible: false, connection: null })}
                connection={connectModal.connection}
                eventInstances={eventInstances}
                schema={schema}
                onConfirm={confirmConnect}
                onAddEvent={(ev) => setEventInstances(evs => [...evs, ev])}
            />
        </div>
    );
}

function PlanPage({ vehicles, squadList }) {
    const [nodes, setNodes] = useState([]);
    const [edges, setEdges] = useState([]);
    const [eventInstances, setEventInstances] = useState([]);
    const [startNodeId, setStartNodeId] = useState(null);
    const [schema, setSchema] = useState({ actions: {}, events: {} });
    const [compiledMission, setCompiledMission] = useState(null);
    const [features, setFeatures] = useState(JSON.stringify({ type: 'FeatureCollection', features: [] }));
    const [panelNodeId, setPanelNodeId] = useState(null);
    const panelNode = panelNodeId ? nodes.find(n => n.id === panelNodeId) : null;
    const [panelEdgeId, setPanelEdgeId] = useState(null);
    const panelEdge = panelEdgeId ? edges.find(e => e.id === panelEdgeId) : null;
    const panelEventInstance = panelEdge ? eventInstances.find(ev => ev.instance_id === panelEdge.data?.eventId) : null;
    const panelEdgeSourceLabel = panelEdge ? (nodes.find(n => n.id === panelEdge.source)?.data.instance_id ?? panelEdge.source) : '';
    const panelEdgeTargetLabel = panelEdge ? (nodes.find(n => n.id === panelEdge.target)?.data.instance_id ?? panelEdge.target) : '';
    const [compiling, setCompiling] = useState(false);
    const [deploying, setDeploying] = useState(false);
    const toast = useRef(null);

    const startNode = nodes.find(n => n.id === startNodeId);

    async function handleCompile() {
        if (!startNodeId) {
            toast.current.show({ severity: 'warn', summary: 'No start state', detail: 'Right-click a node and set it as the start state.' });
            return;
        }
        setCompiling(true);
        try {
            const body = {
                nodes: nodes.map(n => ({
                    instance_id: n.data.instance_id,
                    type_name: n.data.type_name,
                    params: n.data.params,
                })),
                events: eventInstances,
                edges: edges.map(e => ({
                    source: nodes.find(n => n.id === e.source)?.data.instance_id,
                    event_id: e.data?.eventId ?? 'done',
                    target: nodes.find(n => n.id === e.target)?.data.instance_id,
                })),
                start_id: startNode?.data.instance_id,
            };
            const resp = await fetch(getApiUrl('/api/compile'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const result = await resp.json();
            if (result.errors) {
                toast.current.show({ severity: 'error', summary: 'Compile error', detail: result.errors[0]?.message });
                // Highlight error nodes
                const errorIds = new Set(result.errors.map(e => e.node_id));
                setNodes(ns => ns.map(n => ({
                    ...n,
                    data: { ...n.data, _hasError: errorIds.has(n.data.instance_id) },
                })));
            } else {
                setCompiledMission(result.mission);
                setNodes(ns => ns.map(n => ({ ...n, data: { ...n.data, _hasError: false } })));
                toast.current.show({ severity: 'success', summary: 'Compiled', detail: 'mission.json ready.' });
            }
        } catch (e) {
            toast.current.show({ severity: 'error', summary: 'Compile failed', detail: e.message });
        } finally {
            setCompiling(false);
        }
    }

    function handleDownload() {
        if (!compiledMission) return;
        const blob = new Blob([JSON.stringify(compiledMission, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'mission.json';
        a.click();
        URL.revokeObjectURL(url);
    }

    async function handleDeploy() {
        if (!compiledMission) {
            toast.current.show({ severity: 'warn', summary: 'Not compiled', detail: 'Compile the mission first.' });
            return;
        }
        if (!squadList || squadList.length === 0) {
            toast.current.show({ severity: 'warn', summary: 'No vehicles', detail: 'Select at least one vehicle in the Control panel first.' });
            return;
        }
        setDeploying(true);
        try {
            const utf8ToB64 = (str) => btoa(unescape(encodeURIComponent(str)));
            const featObj = typeof features === 'string' ? JSON.parse(features) : features;
            const kmlString = tokml(featObj);
            const kml = utf8ToB64(kmlString);
            const dsl = utf8ToB64(JSON.stringify(compiledMission));
            const resp = await fetch(getApiUrl('/api/upload'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ kml, dsl, vehicles: squadList }),
            });
            if (!resp.ok) {
                const err = await resp.json();
                toast.current.show({ severity: 'error', summary: 'Deploy failed', detail: err.detail });
            } else {
                toast.current.show({ severity: 'success', summary: 'Deployed', detail: `Mission sent to ${squadList.join(', ')}.` });
            }
        } catch (e) {
            toast.current.show({ severity: 'error', summary: 'Deploy failed', detail: e.message });
        } finally {
            setDeploying(false);
        }
    }

    function updateNodeParams(nodeId, params) {
        setNodes(ns => ns.map(n => n.id === nodeId ? { ...n, data: { ...n.data, params } } : n));
    }

    function updateNodeId(nodeId, newId) {
        setNodes(ns => ns.map(n => n.id === nodeId ? { ...n, data: { ...n.data, instance_id: newId } } : n));
    }

    function updateEventParams(instanceId, params) {
        setEventInstances(evs => evs.map(ev => ev.instance_id === instanceId ? { ...ev, params } : ev));
    }

    function deleteEdge(edgeId) {
        setEdges(es => es.filter(e => e.id !== edgeId));
    }

    return (
        <>
            <Toast ref={toast} />
            <TabView>
                <TabPanel header="FSM Builder" leftIcon="pi pi-share-alt mr-2">
                    <div className="flex flex-column" style={{ height: 'calc(100vh - 180px)' }}>
                        <div className="flex flex-1" style={{ overflow: 'hidden' }}>
                            <FsmPalette onSchemaLoaded={setSchema} />
                            <ReactFlowProvider>
                                <FsmCanvas
                                    nodes={nodes} edges={edges}
                                    setNodes={setNodes} setEdges={setEdges}
                                    eventInstances={eventInstances} setEventInstances={setEventInstances}
                                    startNodeId={startNodeId} setStartNodeId={setStartNodeId}
                                    schema={schema} features={features}
                                    panelNode={panelNode} setPanelNode={setPanelNodeId}
                                    setPanelEdgeId={setPanelEdgeId}
                                    toast={toast}
                                />
                            </ReactFlowProvider>
                        </div>

                        {/* Toolbar */}
                        <div className="flex gap-2 align-items-center p-2" style={{ borderTop: '1px solid #2a3a4a', flexShrink: 0 }}>
                            <Button
                                label="Compile"
                                icon="pi pi-cog"
                                size="small"
                                loading={compiling}
                                onClick={handleCompile}
                            />
                            <Button
                                label="Download .json"
                                icon="pi pi-download"
                                size="small"
                                outlined
                                disabled={!compiledMission}
                                onClick={handleDownload}
                            />
                            <Button
                                label={`Deploy → ${squadList?.length ? squadList.join(', ') : 'no vehicles'}`}
                                icon="pi pi-send"
                                size="small"
                                severity="success"
                                disabled={!compiledMission}
                                loading={deploying}
                                onClick={handleDeploy}
                            />
                            <span className="text-sm text-color-secondary ml-auto">
                                {nodes.length} actions · {eventInstances.length} events
                                {startNode
                                    ? ` · start: ${startNode.data.instance_id}`
                                    : ' · ⚠ no start set'}
                            </span>
                        </div>
                    </div>

                    <TaskNodePanel
                        visible={!!panelNode}
                        onHide={() => setPanelNodeId(null)}
                        node={panelNode}
                        schema={panelNode ? schema.actions[panelNode.data.type_name] : null}
                        namedAreas={getNamedAreas(features)}
                        onUpdate={updateNodeParams}
                        onUpdateId={updateNodeId}
                    />

                    <EdgePanel
                        visible={!!panelEdge}
                        onHide={() => setPanelEdgeId(null)}
                        edge={panelEdge}
                        eventInstance={panelEventInstance}
                        eventSchema={panelEventInstance ? schema.events[panelEventInstance.type_name] : null}
                        sourceLabel={panelEdgeSourceLabel}
                        targetLabel={panelEdgeTargetLabel}
                        onUpdateEvent={updateEventParams}
                        onDeleteEdge={deleteEdge}
                    />
                </TabPanel>

                <TabPanel header="Map" leftIcon="pi pi-map mr-2">
                    <div style={{ height: 'calc(100vh - 180px)' }}>
                        <MapDraw features={features} setFeatures={setFeatures} />
                    </div>
                </TabPanel>

                <TabPanel header="JSON Output" leftIcon="pi pi-code mr-2">
                    <InputTextarea
                        style={{ width: '100%', height: 'calc(100vh - 200px)', fontFamily: 'monospace', fontSize: 12 }}
                        readOnly
                        value={compiledMission ? JSON.stringify(compiledMission, null, 2) : '// compile a mission to see output'}
                    />
                </TabPanel>
            </TabView>
        </>
    );
}

export default PlanPage;
