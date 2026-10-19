import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, Panel, applyNodeChanges, useReactFlow } from '@xyflow/react';
import { Button } from 'primereact/button';
import { Dropdown } from 'primereact/dropdown';
import { InputText } from 'primereact/inputtext';
import { ConfirmDialog, confirmDialog } from 'primereact/confirmdialog';
import { loadDaemons, subscribeDaemons } from './daemonRoster.js';
import { createCatalogLoader, sameVehicle, vehicleKey, vehicleLabel, vehicleOptions } from './flowCatalog.js';
import {
    addEdge, addEngine, addProducer, availableStreams, canConnect, emptyFlow, fileBaseName,
    parseFlowJson, removeEdge, removeNode, serializeFlow, setVehicle, toGabrielToml, updateEdge, updateNode, validateFlow,
} from './flowModel.js';
import {
    ERROR_COLOR, FLOW_DRAG_TYPE, WARNING_COLOR,
    applyFlowEdgeChanges, applyFlowNodeChanges, connectionKind, legendEntries, mergeNodes, toReactFlow,
} from './flowView.js';
import ProducerNode from './ProducerNode.jsx';
import EngineNode from './EngineNode.jsx';
import CallbackEdge from './CallbackEdge.jsx';
import FlowPalette from './FlowPalette.jsx';
import FlowPanel from './FlowPanel.jsx';
import CanvasContextMenu from './CanvasContextMenu.jsx';
import { flowCanvasThemeVars } from './canvasTheme.js';
import '@xyflow/react/dist/style.css';

const nodeTypes = { producer: ProducerNode, engine: EngineNode };
const edgeTypes = { callback: CallbackEdge };
const DRAFT_STORAGE_KEY = 'steeleagle-flow-draft';
const NO_ISSUES = { errors: [], warnings: [] };

// The draft survives tab switches and reloads; it's a convenience, not
// storage -- the exported file is the saved flow.
function loadDraft() {
    try {
        const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
        return raw ? parseFlowJson(raw) : emptyFlow();
    } catch {
        return emptyFlow();
    }
}

function saveDraft(flow) {
    try {
        localStorage.setItem(DRAFT_STORAGE_KEY, serializeFlow(flow));
    } catch {
        // storage full or blocked; the flow still lives in page state
    }
}

function download(filename, text, type) {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

function FlowBuilderInner({ theme, toast, active = true }) {
    const { screenToFlowPosition, fitView } = useReactFlow();
    const [importCount, setImportCount] = useState(0);
    const [flow, setFlow] = useState(loadDraft);
    const [selection, setSelection] = useState(null);
    const [contextMenu, setContextMenu] = useState(null); // {x, y, nodeId} | {x, y, edgeId}
    const [daemons, setDaemons] = useState(loadDaemons);
    const [catalog, setCatalog] = useState(null);
    const [loadingCatalog, setLoadingCatalog] = useState(false);
    const [rfNodes, setRfNodes] = useState([]);
    const fileInputRef = useRef(null);

    const notify = useCallback((severity, summary, detail) => {
        toast?.current?.show({ severity, summary, detail });
    }, [toast]);

    useEffect(() => saveDraft(flow), [flow]);
    useEffect(() => subscribeDaemons(setDaemons), []);

    const loader = useMemo(() => createCatalogLoader((c) => { setCatalog(c); setLoadingCatalog(false); }), []);
    const refreshCatalog = useCallback(() => {
        setLoadingCatalog(true);
        loader(daemons);
    }, [loader, daemons]);
    useEffect(() => { refreshCatalog(); }, [refreshCatalog]);
    // Refresh when the tab/page becomes visible again (initial mount is covered above).
    const wasActive = useRef(active);
    useEffect(() => {
        if (active && !wasActive.current) refreshCatalog();
        wasActive.current = active;
    }, [active, refreshCatalog]);
    // Re-fit after an import, once the new nodes have been rendered and measured.
    useEffect(() => {
        if (!importCount) return undefined;
        const raf = requestAnimationFrame(() => fitView({ maxZoom: 1 }));
        return () => cancelAnimationFrame(raf);
    }, [importCount, fitView]);

    const validation = useMemo(() => (catalog ? validateFlow(flow, catalog) : NO_ISSUES), [flow, catalog]);
    const onChangeStream = useCallback((id, stream) => setFlow((f) => updateNode(f, id, { stream })), []);
    const view = useMemo(
        () => toReactFlow(flow, catalog, validation, selection, { onChangeStream }),
        [flow, catalog, validation, selection, onChangeStream],
    );
    useEffect(() => { setRfNodes((prev) => mergeNodes(prev, view.nodes)); }, [view.nodes]);
    const legend = useMemo(() => legendEntries(flow, catalog), [flow, catalog]);

    // --- canvas events ---

    const onNodesChange = useCallback((changes) => {
        setRfNodes((ns) => applyNodeChanges(changes, ns));
        setFlow((f) => applyFlowNodeChanges(f, changes));
        if (changes.some((c) => c.type === 'remove')) setSelection(null);
    }, []);

    const onEdgesChange = useCallback((changes) => {
        setFlow((f) => applyFlowEdgeChanges(f, changes));
        if (changes.some((c) => c.type === 'remove')) setSelection(null);
    }, []);

    const isValidConnection = useCallback((conn) => {
        if (!catalog) return false;
        const kind = connectionKind(conn.sourceHandle);
        if (kind === 'output' && conn.targetHandle === 'cb-in') return false;
        return canConnect(flow, catalog, conn.source, conn.target, kind) === null;
    }, [flow, catalog]);

    const onConnect = useCallback((conn) => {
        try {
            setFlow(addEdge(flow, catalog, conn.source, conn.target, connectionKind(conn.sourceHandle)));
        } catch (e) {
            notify('warn', 'Not connected', e.message);
        }
    }, [flow, catalog, notify]);

    // Say why a drop onto a node was refused; isValidConnection only colors
    // the handle.
    const onConnectEnd = useCallback((_event, state) => {
        if (!catalog || state.isValid || !state.fromNode || !state.toNode) return;
        const kind = connectionKind(state.fromHandle?.id);
        const [source, target] = state.fromHandle?.type === 'target'
            ? [state.toNode.id, state.fromNode.id]
            : [state.fromNode.id, state.toNode.id];
        const reason = canConnect(flow, catalog, source, target, kind)
            ?? (kind === 'output' ? 'output edges must end at an engine' : null);
        if (reason) notify('warn', 'Not connected', reason);
    }, [flow, catalog, notify]);

    const onDragOver = useCallback((event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    const onDrop = useCallback((event) => {
        event.preventDefault();
        const raw = event.dataTransfer.getData(FLOW_DRAG_TYPE);
        if (!raw || !catalog) return;
        const item = JSON.parse(raw);
        const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
        try {
            if (item.kind === 'vehicle') {
                const [stream] = availableStreams(flow, catalog);
                if (!stream) throw new Error(`Every stream of ${flow.vehicle.name} is already on the canvas`);
                setFlow(addProducer(flow, stream, position));
            } else {
                setFlow(addEngine(flow, item.daemon, item.engine, position));
            }
        } catch (e) {
            notify('warn', 'Not added', e.message);
        }
    }, [flow, catalog, screenToFlowPosition, notify]);

    // --- toolbar ---

    const options = useMemo(() => vehicleOptions(catalog ?? [], flow.vehicle), [catalog, flow.vehicle]);

    function onPickVehicle(key) {
        const vehicle = options.find((o) => vehicleKey(o) === key);
        if (!vehicle || sameVehicle(vehicle, flow.vehicle)) return;
        const producers = flow.nodes.filter((n) => n.kind === 'producer').length;
        if (!producers) {
            setFlow((f) => setVehicle(f, vehicle));
            return;
        }
        confirmDialog({
            group: 'flow',
            header: 'Change vehicle',
            message: `Switch to ${vehicleLabel(vehicle, options)}? This removes the ${producers} producer node(s) for ${flow.vehicle.name} and their edges.`,
            icon: 'pi pi-exclamation-triangle',
            accept: () => { setFlow((f) => setVehicle(f, vehicle)); setSelection(null); },
        });
    }

    function onNew() {
        confirmDialog({
            group: 'flow',
            header: 'New flow',
            message: 'Discard the current flow? Export it first if you want to keep it.',
            icon: 'pi pi-exclamation-triangle',
            accept: () => { setFlow(emptyFlow()); setSelection(null); },
        });
    }

    async function onImportFile(event) {
        const file = event.target.files?.[0];
        event.target.value = '';
        if (!file) return;
        try {
            setFlow(parseFlowJson(await file.text()));
            setSelection(null);
            setImportCount((n) => n + 1);
            notify('success', 'Flow imported', file.name);
        } catch (e) {
            notify('error', 'Import failed', e.message);
        }
    }

    function onExportToml() {
        try {
            download(`${fileBaseName(flow)}.toml`, toGabrielToml(flow, catalog), 'application/toml');
        } catch (e) {
            notify('error', 'Export failed', e.message);
        }
    }

    function deleteItem(item) {
        if (item?.nodeId) setFlow((f) => removeNode(f, item.nodeId));
        if (item?.edgeId) setFlow((f) => removeEdge(f, item.edgeId));
        // Removing a node also removes its edges, so a selected edge may be gone too.
        setSelection(null);
    }

    const contextMenuItems = contextMenu?.nodeId
        ? [
            { label: '✏ Edit node', onClick: () => setSelection({ nodeId: contextMenu.nodeId }) },
            { label: '🗑 Delete node', danger: true, onClick: () => deleteItem(contextMenu) },
        ]
        : [
            { label: '✏ Edit edge', onClick: () => setSelection({ edgeId: contextMenu?.edgeId }) },
            { label: '🗑 Delete edge', danger: true, onClick: () => deleteItem(contextMenu) },
        ];

    const issues = [
        ...validation.errors.map((i) => ({ ...i, color: ERROR_COLOR, icon: 'pi-times-circle' })),
        ...validation.warnings.map((i) => ({ ...i, color: WARNING_COLOR, icon: 'pi-exclamation-triangle' })),
    ];

    return (
        <div className="flex flex-column" style={{ height: 'calc(100vh - 180px)', ...flowCanvasThemeVars(theme) }}>
            <ConfirmDialog group="flow" />
            <input ref={fileInputRef} type="file" accept=".json,application/json" style={{ display: 'none' }} onChange={onImportFile} />
            <div className="flex gap-2 align-items-center p-2 flex-wrap" style={{ borderBottom: '1px solid #2a3a4a', flexShrink: 0 }}>
                <InputText value={flow.name} onChange={(e) => setFlow((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Flow name" className="p-inputtext-sm" style={{ width: 180 }} />
                <Dropdown
                    value={flow.vehicle ? vehicleKey(flow.vehicle) : null}
                    options={options.map((o) => ({ label: vehicleLabel(o, options), value: vehicleKey(o) }))}
                    onChange={(e) => onPickVehicle(e.value)}
                    placeholder={catalog ? 'Select vehicle' : 'Loading vehicles…'}
                    className="p-inputtext-sm"
                    style={{ width: 240 }}
                />
                <Button label="New" icon="pi pi-file" size="small" outlined onClick={onNew} />
                <Button label="Import JSON" icon="pi pi-file-import" size="small" outlined onClick={() => fileInputRef.current?.click()} />
                <Button label="Export JSON" icon="pi pi-file-export" size="small" outlined
                    onClick={() => download(`${fileBaseName(flow)}.flow.json`, serializeFlow(flow), 'application/json')} />
                <Button label="Export TOML" icon="pi pi-download" size="small" outlined
                    disabled={!catalog || validation.errors.length > 0}
                    tooltip={validation.errors.length ? 'Fix the errors below first' : undefined}
                    tooltipOptions={{ showOnDisabled: true, position: 'bottom' }}
                    onClick={onExportToml} />
            </div>
            <div className="flex" style={{ flex: 1, minHeight: 0 }}>
                <FlowPalette flow={flow} catalog={catalog} loading={loadingCatalog} onRefresh={refreshCatalog} />
                <div style={{ flex: 1, position: 'relative' }} onClick={() => setContextMenu(null)}>
                    <ReactFlow
                        // Its own id: React Flow names the background pattern and edge
                        // markers after it, and the FSM canvas (always mounted, often
                        // hidden) keeps the default '1' -- sharing it made url(#…)
                        // resolve to the hidden canvas's defs and draw nothing.
                        id="flow-builder"
                        colorMode={theme}
                        nodes={rfNodes}
                        edges={view.edges}
                        nodeTypes={nodeTypes}
                        edgeTypes={edgeTypes}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        isValidConnection={isValidConnection}
                        onConnect={onConnect}
                        onConnectEnd={onConnectEnd}
                        // Clicking a producer's stream dropdown shouldn't open the panel.
                        onNodeClick={(e, n) => { if (!e.target.closest('select')) setSelection({ nodeId: n.id }); }}
                        onEdgeClick={(_e, ed) => setSelection({ edgeId: ed.id })}
                        onPaneClick={() => setSelection(null)}
                        onNodeContextMenu={(e, n) => { e.preventDefault(); setContextMenu({ x: e.clientX, y: e.clientY, nodeId: n.id }); }}
                        onEdgeContextMenu={(e, ed) => { e.preventDefault(); setContextMenu({ x: e.clientX, y: e.clientY, edgeId: ed.id }); }}
                        onPaneContextMenu={() => setContextMenu(null)}
                        onDragOver={onDragOver}
                        onDrop={onDrop}
                        fitView
                        fitViewOptions={{ maxZoom: 1 }}
                        deleteKeyCode={active ? 'Backspace' : null}
                    >
                        <Controls />
                        <MiniMap />
                        {legend.length > 0 && (
                            <Panel position="top-right">
                                <div style={{
                                    background: 'var(--node-bg)', border: '1px solid var(--palette-border)', borderRadius: 4,
                                    padding: '6px 10px', fontSize: 11, color: 'var(--node-chip-text)', maxWidth: 320, textAlign: 'left',
                                }}>
                                    {legend.map((entry) => (
                                        <div key={entry.symbol} className="flex gap-2">
                                            <span style={{ color: 'var(--menu-accent)' }}>{entry.symbol}</span>
                                            <span>{entry.text}</span>
                                        </div>
                                    ))}
                                </div>
                            </Panel>
                        )}
                        <Background variant="lines" gap={24} color="var(--flow-grid)" bgColor="var(--flow-canvas-bg)" />
                    </ReactFlow>
                    <CanvasContextMenu position={contextMenu} items={contextMenuItems} onClose={() => setContextMenu(null)} />
                </div>
                <FlowPanel flow={flow} catalog={catalog} selection={selection}
                    onUpdateNode={(id, patch) => setFlow((f) => updateNode(f, id, patch))}
                    onUpdateEdge={(id, patch) => setFlow((f) => updateEdge(f, id, patch))}
                    onDelete={() => deleteItem(selection)}
                    onHide={() => setSelection(null)} />
            </div>
            {issues.length > 0 && (
                <div style={{ maxHeight: 120, overflowY: 'auto', borderTop: '1px solid #2a3a4a', flexShrink: 0 }} className="p-2">
                    {issues.map((issue, i) => (
                        <div key={i} className="flex align-items-center gap-2 text-sm"
                            style={{ cursor: issue.nodeId || issue.edgeId ? 'pointer' : 'default', color: issue.color }}
                            onClick={() => {
                                if (issue.nodeId) setSelection({ nodeId: issue.nodeId });
                                else if (issue.edgeId) setSelection({ edgeId: issue.edgeId });
                            }}>
                            <i className={`pi ${issue.icon}`} />
                            <span>{issue.message}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// Plan page tab for authoring a Gabriel dataflow -- see
// docs/superpowers/specs/2026-10-16-gcs-flow-builder-design.md.
function FlowBuilder(props) {
    return (
        <ReactFlowProvider>
            <FlowBuilderInner {...props} />
        </ReactFlowProvider>
    );
}

export default FlowBuilder;
