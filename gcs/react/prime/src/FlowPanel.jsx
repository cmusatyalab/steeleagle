import { Button } from 'primereact/button';
import { Sidebar } from 'primereact/sidebar';
import { Dropdown } from 'primereact/dropdown';
import { InputNumber } from 'primereact/inputnumber';
import { InputText } from 'primereact/inputtext';
import { resolveNode, shortType } from './flowCatalog.js';
import { forwardedTypes, nodeById, nodeLabel } from './flowModel.js';

function Row({ label, children }) {
    return (
        <div>
            <label style={{ fontSize: 13, color: 'var(--text-color-secondary)', display: 'block', marginBottom: 4 }}>{label}</label>
            {children}
        </div>
    );
}

// A message type by its short name, with the full path on hover.
function TypeName({ type }) {
    return <span title={type ?? undefined}>{shortType(type)}</span>;
}

// Why catalog data is missing or partial (no plugin file, dropped entries).
function ProblemRow({ problem }) {
    return problem ? <Row label="Problem"><span className="text-sm" style={{ color: '#e8c87a' }}>{problem}</span></Row> : null;
}

const typeList = (types) => (types?.length
    ? types.map((t, i) => <span key={t}>{i > 0 && ', '}<TypeName type={t} /></span>)
    : '—');

// Properties of the selected node or edge, in a right-hand Sidebar like the
// Mission Builder's TaskNodePanel/EdgePanel. Everything editable is a flow
// document field; everything else (types, events, location) is read from
// the catalog.
function FlowPanel({ flow, catalog, selection, onUpdateNode, onUpdateEdge, onDelete, onHide }) {
    const node = selection?.nodeId ? nodeById(flow, selection.nodeId) : null;
    const edge = selection?.edgeId ? flow.edges.find((e) => e.id === selection.edgeId) : null;
    const resolution = (n) => (catalog && n ? resolveNode(flow, catalog, n) : null);

    let body;
    let header;
    if (node?.kind === 'producer') {
        const r = resolution(node);
        header = 'Producer';
        body = (
            <>
                <Row label="Stream"><b>{nodeLabel(flow, node)}</b></Row>
                <Row label="Type"><TypeName type={r?.output} /></Row>
                {r?.stream?.kind === 'camera' && (
                    <Row label="Camera">
                        <div className="text-sm">
                            {r.stream.description && <div>{r.stream.description}</div>}
                            {r.stream.hres && <div>{r.stream.hres}×{r.stream.vres}{r.stream.fps ? ` @ ${r.stream.fps} fps` : ''}</div>}
                            <div>Primary: {r.stream.primary ? 'yes' : 'no'}</div>
                        </div>
                    </Row>
                )}
                <ProblemRow problem={r?.problem} />
                <Row label="Tokens">
                    <InputNumber value={node.tokens} min={1} showButtons size={4} className="w-full"
                        onValueChange={(e) => onUpdateNode(node.id, { tokens: e.value ?? 1 })} />
                </Row>
            </>
        );
    } else if (node?.kind === 'engine') {
        const r = resolution(node);
        header = 'Engine';
        body = (
            <>
                <Row label="Name"><b>{node.engine}</b></Row>
                <Row label="Daemon">{node.daemon.name} <span className="text-xs text-color-secondary">({node.daemon.address})</span></Row>
                <Row label="Location">{r?.location ?? '—'}</Row>
                <Row label="Category">{r?.category ?? '—'}</Row>
                <ProblemRow problem={r?.problem} />
                <Row label="Accepts">{typeList(r?.accepts)}</Row>
                <Row label="Forwards">{typeList(catalog ? forwardedTypes(flow, catalog, node.id) : [])}</Row>
                <Row label="Events">
                    {r?.events?.length
                        ? r.events.map((ev) => (
                            <div key={ev} className="text-sm">
                                {ev}{r.eventTypes[ev] && <> (<TypeName type={r.eventTypes[ev]} />)</>}
                            </div>
                        ))
                        : '—'}
                </Row>
            </>
        );
    } else if (edge) {
        const source = nodeById(flow, edge.source);
        const target = nodeById(flow, edge.target);
        header = edge.kind === 'callback' ? 'Event' : 'Output edge';
        body = (
            <>
                <div style={{ fontSize: 12, color: '#aaa' }}>
                    <span style={{ color: '#7ecfff' }}>{nodeLabel(flow, source)}</span>
                    <span> → </span>
                    <span style={{ color: '#7ecfff' }}>{nodeLabel(flow, target)}</span>
                </div>
                {edge.kind === 'output' ? (
                    <Row label="Timeout">
                        <InputText value={edge.timeout} placeholder="1s" className="w-full"
                            onChange={(e) => onUpdateEdge(edge.id, { timeout: e.target.value.trim() })} />
                    </Row>
                ) : (
                    <Row label="Event">
                        <Dropdown value={edge.event} className="w-full"
                            options={[...new Set([edge.event, ...(resolution(source)?.events ?? [])])]}
                            onChange={(e) => onUpdateEdge(edge.id, { event: e.value })} />
                    </Row>
                )}
            </>
        );
    }

    return (
        <Sidebar
            visible={!!body}
            position="right"
            onHide={onHide}
            style={{ width: 320 }}
            header={<span style={{ fontWeight: 'bold' }}>{header}</span>}
        >
            <div className="flex flex-column gap-3 p-2">
                {body}
                <hr style={{ borderColor: '#2a3a4a', margin: '4px 0' }} />
                <Button
                    label={edge ? 'Delete edge' : 'Delete node'}
                    icon="pi pi-trash"
                    severity="danger"
                    outlined
                    size="small"
                    onClick={onDelete}
                />
            </div>
        </Sidebar>
    );
}

export default FlowPanel;
