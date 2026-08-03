import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
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
import SelfLoopEdge from './SelfLoopEdge.jsx';
import TaskNodePanel from './TaskNodePanel.jsx';
import EdgePanel from './EdgePanel.jsx';
import FsmPalette from './FsmPalette.jsx';
import ConnectModal from './ConnectModal.jsx';
import { getApiUrl } from './App.jsx';
import { runValidation } from './validation.js';
import ChatPage from './chat/ChatPage.jsx';

const nodeTypes = { taskNode: TaskNode };
const edgeTypes = { selfLoop: SelfLoopEdge };

let _nodeIdCounter = 1;
function nextNodeId() { return `node-${_nodeIdCounter++}`; }

// BFS layout: place nodes in grid columns by distance from start
function bfsLayout(nodeIds, startId, edges) {
    const adj = {};
    nodeIds.forEach(id => { adj[id] = []; });
    edges.forEach(e => {
        if (e.source !== e.target && adj[e.source]) adj[e.source].push(e.target);
    });

    const visited = new Set();
    const levels = {};
    const queue = startId ? [startId] : nodeIds.slice(0, 1);
    let level = 0;
    queue.forEach(id => { visited.add(id); levels[id] = 0; });

    while (queue.length) {
        const next = [];
        queue.forEach(id => {
            (adj[id] || []).forEach(t => {
                if (!visited.has(t)) { visited.add(t); levels[t] = level + 1; next.push(t); }
            });
        });
        queue.length = 0;
        queue.push(...next);
        if (next.length) level++;
    }
    // any unreachable nodes get appended after
    nodeIds.forEach(id => { if (!(id in levels)) levels[id] = level + 1; });

    const colCounts = {};
    const positions = {};
    nodeIds.forEach(id => {
        const col = levels[id] ?? 0;
        const row = colCounts[col] ?? 0;
        colCounts[col] = row + 1;
        positions[id] = { x: col * 260, y: row * 130 };
    });
    return positions;
}

// Generate a DSL string from canvas state
function generateDsl(nodes, edges, eventInstances, startNodeId, schema) {
    const dataEntries = [];
    const usedDataIds = new Set();

    function dataId(instanceId, paramName) {
        let id = `${instanceId}_${paramName}`;
        let n = 2;
        while (usedDataIds.has(id)) id = `${instanceId}_${paramName}_${n++}`;
        usedDataIds.add(id);
        return id;
    }

    function serializeVal(val, fieldSchema) {
        if (val === undefined || val === null) return null;
        if (typeof val === 'object' && !Array.isArray(val) && fieldSchema?.nested_fields?.length) {
            const typeName = fieldSchema.object_type || 'Object';
            const did = dataId(fieldSchema._ownerInstanceId || 'item', fieldSchema.name);
            const attrParts = Object.entries(val)
                .filter(([, v]) => v !== undefined && v !== null && v !== '')
                .map(([k, v]) => `${k} = ${v}`);
            dataEntries.push(`    ${typeName} ${did}(${attrParts.join(', ')})`);
            return did;
        }
        if (typeof val === 'boolean') return val ? 'true' : 'false';
        if (val === '') return null;
        return String(val);
    }

    function buildAttrStr(params, fields, instanceId) {
        const parts = [];
        for (const [k, v] of Object.entries(params || {})) {
            const fs = fields?.find(f => f.name === k);
            const fsWithOwner = fs ? { ...fs, _ownerInstanceId: instanceId } : null;
            const sv = serializeVal(v, fsWithOwner);
            if (sv !== null) parts.push(`${k} = ${sv}`);
        }
        return parts.length ? `(${parts.join(', ')})` : '';
    }

    const actionLines = nodes.map(n => {
        const fields = schema.actions[n.data.type_name]?.fields ?? [];
        return `    ${n.data.type_name} ${n.data.instance_id}${buildAttrStr(n.data.params, fields, n.data.instance_id)}`;
    });

    const eventLines = (eventInstances || []).map(ev => {
        const fields = schema.events[ev.type_name]?.fields ?? [];
        return `    ${ev.type_name} ${ev.instance_id}${buildAttrStr(ev.params, fields, ev.instance_id)}`;
    });

    const nodeById = Object.fromEntries(nodes.map(n => [n.id, n]));
    const startNode = nodes.find(n => n.id === startNodeId);
    const startInstId = startNode?.data.instance_id ?? '';

    const duringBlocks = nodes.map(n => {
        const nodeEdges = edges.filter(e => e.source === n.id);
        if (!nodeEdges.length) return null;
        const transLines = nodeEdges.map(e => {
            const evId = e.data?.eventId ?? 'done';
            const target = nodeById[e.target]?.data.instance_id ?? e.target;
            return `        ${evId} -> ${target}`;
        });
        return `    During ${n.data.instance_id}:\n${transLines.join('\n')}`;
    }).filter(Boolean);

    const parts = [];
    if (dataEntries.length) parts.push(`Data:\n${dataEntries.join('\n')}`);
    parts.push(`Actions:\n${actionLines.join('\n')}`);
    if (eventLines.length) parts.push(`Events:\n${eventLines.join('\n')}`);
    const missionContent = [`    Start ${startInstId}`, ...duringBlocks].join('\n');
    parts.push(`Mission:\n${missionContent}`);

    return parts.join('\n\n');
}

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
                     setPanelEdgeId, pushSnapshot, toast, theme }) {
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
        pushSnapshot();
        const isSelfLoop = connection.source === connection.target;
        setEdges(es => addEdge({
            ...connection,
            type: isSelfLoop ? 'selfLoop' : 'smoothstep',
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

        pushSnapshot();
        setNodes(ns => [...ns, newNode]);
        if (isFirst) setStartNodeId(id);
    }, [nodes, schema, namedAreas, screenToFlowPosition, pushSnapshot]);

    // Right-click context menu on a node
    const onNodeContextMenu = useCallback((event, node) => {
        event.preventDefault();
        setContextMenu({ x: event.clientX, y: event.clientY, nodeId: node.id });
    }, []);

    // Right-click context menu on an edge
    const onEdgeContextMenu = useCallback((event, edge) => {
        event.preventDefault();
        setContextMenu({ x: event.clientX, y: event.clientY, edgeId: edge.id });
    }, []);

    function setAsStart(nodeId) {
        pushSnapshot();
        setStartNodeId(nodeId);
        setNodes(ns => ns.map(n => ({ ...n, data: { ...n.data, isStart: n.id === nodeId } })));
        setContextMenu(null);
    }

    function deleteNode(nodeId) {
        pushSnapshot();
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
                colorMode={theme}
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onEdgeClick={onEdgeClick}
                onDragOver={onDragOver}
                onDrop={onDrop}
                onNodeContextMenu={onNodeContextMenu}
                onEdgeContextMenu={onEdgeContextMenu}
                fitView
            >
                <Controls />
                <MiniMap />
                <Background variant="dots" gap={12} size={1} />
            </ReactFlow>

            {/* Context menu — shared by nodes and edges */}
            {contextMenu && (
                <div
                    style={{
                        position: 'fixed', left: contextMenu.x, top: contextMenu.y,
                        background: '#1e2a38', border: '1px solid #4a7a9b', borderRadius: 6,
                        zIndex: 1000, minWidth: 160, boxShadow: '0 4px 12px #00000088',
                    }}
                    onClick={e => e.stopPropagation()}
                >
                    {contextMenu.nodeId ? (
                        <>
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
                                🗑 Delete node
                            </div>
                        </>
                    ) : (
                        <>
                            <div
                                style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 12 }}
                                onMouseEnter={e => e.currentTarget.style.background = '#2a3a50'}
                                onMouseLeave={e => e.currentTarget.style.background = ''}
                                onClick={() => { setPanelEdgeId(contextMenu.edgeId); setContextMenu(null); }}
                            >
                                ✏ Edit transition
                            </div>
                            <div
                                style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 12, color: '#e88080' }}
                                onMouseEnter={e => e.currentTarget.style.background = '#2a3a50'}
                                onMouseLeave={e => e.currentTarget.style.background = ''}
                                onClick={() => { pushSnapshot(); setEdges(es => es.filter(e => e.id !== contextMenu.edgeId)); setContextMenu(null); }}
                            >
                                🗑 Delete transition
                            </div>
                        </>
                    )}
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

function PlanPage({ vehicles, squadList, theme }) {
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
    const [loadingDsl, setLoadingDsl] = useState(false);
    const fileInputRef = useRef(null);
    const toast = useRef(null);
    const [validationIssues, setValidationIssues] = useState({});
    const [activeTab, setActiveTab] = useState(0);

    // Undo / redo history
    const pastRef = useRef([]);
    const futureRef = useRef([]);
    const schemaRef = useRef(schema);
    const [canUndo, setCanUndo] = useState(false);
    const [canRedo, setCanRedo] = useState(false);
    useEffect(() => { schemaRef.current = schema; }, [schema]);

    useEffect(() => {
        const timer = setTimeout(() => {
            const { issues } = runValidation(nodes, schema, startNodeId);
            setValidationIssues(issues);
        }, 500);
        return () => clearTimeout(timer);
    }, [nodes, startNodeId, schema]);

    function snapshotCurrent() {
        return {
            nodes: nodes.map(n => ({
                id: n.id,
                type: n.type,
                position: n.position,
                data: {
                    type_name: n.data.type_name,
                    instance_id: n.data.instance_id,
                    params: n.data.params,
                    isStart: n.data.isStart,
                },
            })),
            edges,
            eventInstances,
            startNodeId,
        };
    }

    function applySnapshot(snap) {
        setNodes(snap.nodes.map(n => ({
            ...n,
            data: {
                ...n.data,
                schema: schemaRef.current.actions[n.data.type_name],
                onOpenPanel: () => setPanelNodeId(n.id),
            },
        })));
        setEdges(snap.edges);
        setEventInstances(snap.eventInstances);
        setStartNodeId(snap.startNodeId);
    }

    function pushSnapshot() {
        const snap = snapshotCurrent();
        pastRef.current = [...pastRef.current.slice(-49), snap];
        futureRef.current = [];
        setCanUndo(true);
        setCanRedo(false);
    }

    function undo() {
        if (!pastRef.current.length) return;
        const snap = pastRef.current[pastRef.current.length - 1];
        futureRef.current = [snapshotCurrent(), ...futureRef.current.slice(0, 49)];
        pastRef.current = pastRef.current.slice(0, -1);
        applySnapshot(snap);
        setCanUndo(pastRef.current.length > 0);
        setCanRedo(true);
    }

    function redo() {
        if (!futureRef.current.length) return;
        const snap = futureRef.current[0];
        pastRef.current = [...pastRef.current.slice(-49), snapshotCurrent()];
        futureRef.current = futureRef.current.slice(1);
        applySnapshot(snap);
        setCanUndo(true);
        setCanRedo(futureRef.current.length > 0);
    }

    // Stable keyboard handler via refs so it doesn't re-register on every render
    const undoRef = useRef(undo);
    const redoRef = useRef(redo);
    useEffect(() => { undoRef.current = undo; });
    useEffect(() => { redoRef.current = redo; });
    useEffect(() => {
        function onKeyDown(e) {
            if (!(e.ctrlKey || e.metaKey)) return;
            if (e.key === 'z' && !e.shiftKey) { e.preventDefault(); undoRef.current(); }
            if (e.key === 'y' || (e.key === 'z' && e.shiftKey)) { e.preventDefault(); redoRef.current(); }
        }
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, []);

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
                let detail = `Server error ${resp.status}`;
                try { const err = await resp.json(); detail = err.detail ?? detail; } catch (_) { detail = await resp.text().catch(() => detail); }
                toast.current.show({ severity: 'error', summary: 'Deploy failed', detail });
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
        pushSnapshot();
        setNodes(ns => ns.map(n => n.id === nodeId ? { ...n, data: { ...n.data, params } } : n));
    }

    function updateNodeId(nodeId, newId) {
        pushSnapshot();
        setNodes(ns => ns.map(n => n.id === nodeId ? { ...n, data: { ...n.data, instance_id: newId } } : n));
    }

    function updateEventParams(instanceId, params) {
        pushSnapshot();
        setEventInstances(evs => evs.map(ev => ev.instance_id === instanceId ? { ...ev, params } : ev));
    }

    function deleteEdge(edgeId) {
        pushSnapshot();
        setEdges(es => es.filter(e => e.id !== edgeId));
    }

    function deleteNodeById(nodeId) {
        pushSnapshot();
        setNodes(ns => ns.filter(n => n.id !== nodeId));
        setEdges(es => es.filter(e => e.source !== nodeId && e.target !== nodeId));
        if (startNodeId === nodeId) setStartNodeId(null);
        setPanelNodeId(null);
    }

    function handleNewMission() {
        if (nodes.length === 0 && edges.length === 0) return;
        if (!window.confirm('Start a new mission? The current canvas will be cleared.')) return;
        pushSnapshot();
        setNodes([]);
        setEdges([]);
        setEventInstances([]);
        setStartNodeId(null);
        setCompiledMission(null);
    }

    function loadFromParsed(parsed) {
        pushSnapshot();
        const evMap = Object.fromEntries(parsed.events.map(ev => [ev.instance_id, ev]));

        // Use instance_id as the React Flow node id for simplicity
        const rfNodes = parsed.nodes.map(n => ({
            id: n.instance_id,
            type: 'taskNode',
            position: { x: 0, y: 0 },
            data: {
                type_name: n.type_name,
                instance_id: n.instance_id,
                params: n.params,
                isStart: n.instance_id === parsed.start_id,
                schema: schema.actions[n.type_name],
                onOpenPanel: () => setPanelNodeId(n.instance_id),
            },
        }));

        const rfEdges = parsed.edges.map(e => {
            const isSelfLoop = e.source === e.target;
            const evId = e.event_id;
            const isDone = evId === 'done';
            return {
                id: `e-${e.source}-${evId}-${e.target}`,
                source: e.source,
                target: e.target,
                type: isSelfLoop ? 'selfLoop' : 'smoothstep',
                data: { eventId: evId },
                label: evId,
                animated: !isDone,
                style: { stroke: isDone ? '#a3e8a0' : '#c47aff' },
                labelStyle: { fill: isDone ? '#a3e8a0' : '#c47aff', fontSize: 10 },
            };
        });

        const nodeIds = rfNodes.map(n => n.id);
        const positions = bfsLayout(nodeIds, parsed.start_id, parsed.edges);
        rfNodes.forEach(n => { n.position = positions[n.id] || { x: 0, y: 0 }; });

        setNodes(rfNodes);
        setEdges(rfEdges);
        setEventInstances(parsed.events);
        setStartNodeId(parsed.start_id ?? (rfNodes[0]?.id ?? null));
        setCompiledMission(null);
    }

    async function handleLoadDsl(file) {
        if (!file) return;
        setLoadingDsl(true);
        try {
            const text = await file.text();
            const resp = await fetch(getApiUrl('/api/parse_dsl'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dsl: text }),
            });
            if (!resp.ok) {
                const err = await resp.json();
                toast.current.show({ severity: 'error', summary: 'DSL parse error', detail: err.detail });
                return;
            }
            const parsed = await resp.json();
            loadFromParsed(parsed);
            toast.current.show({ severity: 'success', summary: 'DSL loaded', detail: `${parsed.nodes.length} actions, ${parsed.events.length} events` });
        } catch (e) {
            toast.current.show({ severity: 'error', summary: 'Load failed', detail: e.message });
        } finally {
            setLoadingDsl(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    }

    function handleExportDsl() {
        const dsl = generateDsl(nodes, edges, eventInstances, startNodeId, schema);
        const blob = new Blob([dsl + '\n'], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'mission.dsl';
        a.click();
        URL.revokeObjectURL(url);
    }

    // Apply an assistant-produced artifact from the Chat tab. For a mission
    // draft targeting the FSM builder we reuse the same loader as "Load DSL",
    // then switch to the FSM Builder tab so the result is visible immediately.
    // This is entirely frontend today; no backend/MCP call is involved yet.
    function handleApplyArtifact(target, artifact) {
        if (target !== 'fsm-builder' || !artifact?.payload) {
            toast.current?.show({
                severity: 'info',
                summary: 'Nothing to apply',
                detail: 'This message has no FSM draft attached.',
            });
            return;
        }
        const p = artifact.payload;
        loadFromParsed({
            nodes: (p.nodes ?? []).map(n => ({
                instance_id: n.instance_id,
                type_name: n.type_name,
                params: n.params ?? {},
            })),
            events: p.events ?? [],
            edges: p.edges ?? [],
            start_id: p.start_id ?? (p.nodes?.[0]?.instance_id ?? null),
        });
        setActiveTab(0);
        toast.current?.show({
            severity: 'success',
            summary: 'Applied to FSM Builder',
            detail: `Loaded ${(p.nodes ?? []).length} actions into the canvas.`,
        });
    }

    const liveDsl = nodes.length > 0 ? generateDsl(nodes, edges, eventInstances, startNodeId, schema) : '# Add nodes to see DSL preview';

    const nodesWithWarnings = useMemo(
        () => nodes.map(n => ({
            ...n,
            data: { ...n.data, _warnings: validationIssues[n.id] ?? [] },
        })),
        [nodes, validationIssues]
    );

    const totalWarnings = useMemo(
        () => Object.values(validationIssues).reduce((s, arr) => s + arr.length, 0),
        [validationIssues]
    );

    return (
        <>
            <Toast ref={toast} />
            <TabView activeIndex={activeTab} onTabChange={(e) => setActiveTab(e.index)} renderActiveOnly={false}>
                <TabPanel header="FSM Builder" leftIcon="pi pi-share-alt mr-2" headerClassName="mr-2">
                    <div className="flex flex-column" style={{ height: 'calc(100vh - 180px)' }}>
                        {/* Hidden file input — outside toolbar div */}
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".dsl,.txt"
                            style={{ display: 'none' }}
                            onChange={e => handleLoadDsl(e.target.files[0])}
                        />

                        {/* Toolbar — now at top with borderBottom */}
                        <div className="flex gap-2 align-items-center p-2" style={{ borderBottom: '1px solid #2a3a4a', flexShrink: 0 }}>
                            <Button
                                icon="pi pi-undo"
                                size="small"
                                outlined
                                disabled={!canUndo}
                                onClick={undo}
                                tooltip="Undo (Ctrl+Z)"
                                tooltipOptions={{ position: 'top' }}
                            />
                            <Button
                                icon="pi pi-refresh"
                                size="small"
                                outlined
                                disabled={!canRedo}
                                onClick={redo}
                                tooltip="Redo (Ctrl+Shift+Z)"
                                tooltipOptions={{ position: 'top' }}
                            />
                            <Button
                                label="New"
                                icon="pi pi-file"
                                size="small"
                                outlined
                                disabled={nodes.length === 0 && edges.length === 0}
                                onClick={handleNewMission}
                                tooltip="Clear canvas and start a new mission"
                                tooltipOptions={{ position: 'top' }}
                            />
                            <Button
                                label="Load DSL"
                                icon="pi pi-folder-open"
                                size="small"
                                outlined
                                loading={loadingDsl}
                                onClick={() => fileInputRef.current?.click()}
                            />
                            <Button
                                label="Export DSL"
                                icon="pi pi-file-export"
                                size="small"
                                outlined
                                disabled={nodes.length === 0}
                                onClick={handleExportDsl}
                            />
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
                        </div>

                        {/* Canvas — middle */}
                        <div className="flex flex-1" style={{
                            overflow: 'hidden',
                            '--node-bg':            theme === 'light' ? '#ffffff'  : '#1e3040',
                            '--node-text':          theme === 'light' ? '#111827'  : '#ffffff',
                            '--node-id-color':      theme === 'light' ? '#1d4ed8'  : '#7ecfff',
                            '--node-chip-bg':       theme === 'light' ? '#f1f5f9'  : '#0d1820',
                            '--node-chip-text':     theme === 'light' ? '#475569'  : '#aaaaaa',
                            '--palette-bg':         theme === 'light' ? '#f8fafc'  : '#1a2530',
                            '--palette-border':     theme === 'light' ? '#e2e8f0'  : '#2a3a4a',
                            '--palette-header':     theme === 'light' ? '#1d4ed8'  : '#7ecfff',
                            '--palette-item-text':  theme === 'light' ? '#1e293b'  : '#ffffff',
                            '--palette-item-div':   theme === 'light' ? '#e2e8f0'  : '#1e2a38',
                            '--palette-item-hover': theme === 'light' ? '#dbeafe'  : '#1e3040',
                        }}>
                            <FsmPalette onSchemaLoaded={setSchema} />
                            <ReactFlowProvider>
                                <FsmCanvas
                                    nodes={nodesWithWarnings} edges={edges}
                                    setNodes={setNodes} setEdges={setEdges}
                                    eventInstances={eventInstances} setEventInstances={setEventInstances}
                                    startNodeId={startNodeId} setStartNodeId={setStartNodeId}
                                    schema={schema} features={features}
                                    panelNode={panelNode} setPanelNode={setPanelNodeId}
                                    setPanelEdgeId={setPanelEdgeId}
                                    pushSnapshot={pushSnapshot}
                                    toast={toast}
                                    theme={theme}
                                />
                            </ReactFlowProvider>
                        </div>

                        {/* Status bar — separate div at bottom with borderTop */}
                        <div className="flex align-items-center px-2 py-1" style={{ borderTop: '1px solid #2a3a4a', flexShrink: 0 }}>
                            <span className="text-sm ml-auto" style={{ color: '#888' }}>
                                {nodes.length} actions · {eventInstances.length} events
                                {startNode
                                    ? ` · start: ${startNode.data.instance_id}`
                                    : <span style={{ color: '#e8c87a' }}> · ⚠ no start set</span>}
                                {totalWarnings > 0 && (
                                    <span style={{ color: '#e8c87a' }}> · ⚠ {totalWarnings} warning{totalWarnings !== 1 ? 's' : ''}</span>
                                )}
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
                        onDelete={deleteNodeById}
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

                <TabPanel header="Map" leftIcon="pi pi-map mr-2" headerClassName="mr-2">
                    <div style={{ height: 'calc(100vh - 180px)' }}>
                        <MapDraw features={features} setFeatures={setFeatures} />
                    </div>
                </TabPanel>

                <TabPanel header="DSL Preview" leftIcon="pi pi-code mr-2" headerClassName="mr-2">
                    <div className="flex flex-column" style={{ height: 'calc(100vh - 180px)' }}>
                        <div className="flex gap-2 align-items-center p-2" style={{ borderBottom: '1px solid #2a3a4a', flexShrink: 0 }}>
                            <Button
                                label="Export DSL"
                                icon="pi pi-file-export"
                                size="small"
                                outlined
                                disabled={nodes.length === 0}
                                onClick={handleExportDsl}
                            />
                            {compiledMission && (
                                <Button
                                    label="Download .json"
                                    icon="pi pi-download"
                                    size="small"
                                    outlined
                                    onClick={handleDownload}
                                />
                            )}
                        </div>
                        <InputTextarea
                            style={{ flex: 1, width: '100%', fontFamily: 'monospace', fontSize: 12, resize: 'none' }}
                            readOnly
                            value={liveDsl}
                        />
                    </div>
                </TabPanel>

                <TabPanel header="Chat" leftIcon="pi pi-comments mr-2" headerClassName="mr-2">
                    <ChatPage onApplyArtifact={handleApplyArtifact} />
                </TabPanel>
            </TabView>
        </>
    );
}

export default PlanPage;
