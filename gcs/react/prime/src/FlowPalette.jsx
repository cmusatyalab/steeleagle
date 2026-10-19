import { Button } from 'primereact/button';
import { engineLocation, vehicleLabel, vehicleOptions } from './flowCatalog.js';
import { availableStreams, isEnginePlaced } from './flowModel.js';
import { FLOW_DRAG_TYPE, paletteTitle } from './flowView.js';

const sectionHeader = {
    fontSize: 12, color: 'var(--palette-header)', textTransform: 'uppercase', letterSpacing: 1,
    padding: '6px 10px', borderBottom: '1px solid var(--palette-border)', textAlign: 'center',
};

function Tag({ children, color, title }) {
    return <span title={title} style={{ fontSize: 8, padding: '1px 4px', borderRadius: 3, background: color, color: '#000', marginLeft: 'auto' }}>{children}</span>;
}

function Item({ payload, disabled, title, children }) {
    return (
        <div
            draggable={!disabled}
            onDragStart={(e) => {
                e.dataTransfer.setData(FLOW_DRAG_TYPE, JSON.stringify(payload));
                e.dataTransfer.effectAllowed = 'move';
            }}
            title={title}
            style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px', fontSize: 13,
                cursor: disabled ? 'not-allowed' : 'grab', opacity: disabled ? 0.4 : 1,
                borderBottom: '1px solid var(--palette-item-div)', color: 'var(--palette-item-text)',
            }}
        >
            {children}
        </div>
    );
}

// What can go on the canvas: the flow's vehicle (dropped as a producer for
// its next unplaced stream) and every engine on a reachable daemon, grouped
// by daemon. Items already placed are disabled. Unreachable daemons are left
// out (their nodes still show as unresolved on the canvas).
function FlowPalette({ flow, catalog, loading, onRefresh }) {
    const free = catalog ? availableStreams(flow, catalog) : [];
    const reachable = catalog?.filter((d) => d.reachable);
    return (
        <div style={{ width: 180, background: 'var(--palette-bg)', height: '100%', overflowY: 'auto', borderRight: '1px solid var(--palette-border)' }}>
            <div style={{ ...sectionHeader, position: 'relative' }}>
                <span style={{ lineHeight: '32px' }}>Producer</span>
                <Button icon="pi pi-refresh" text rounded size="small" loading={loading}
                    style={{ position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)' }}
                    onClick={onRefresh} tooltip="Refresh catalog" tooltipOptions={{ position: 'bottom' }} />
            </div>
            {!flow.vehicle ? (
                <div className="p-2 text-sm text-color-secondary">Select a vehicle in the toolbar.</div>
            ) : (
                <Item payload={{ kind: 'vehicle' }} disabled={free.length === 0}
                    title={free.length ? `Drop to add a producer (${free.join(', ')})` : 'Every stream is already on the canvas'}>
                    <i className="pi pi-send" style={{ fontSize: 11 }} />
                    <span>{vehicleLabel(flow.vehicle, vehicleOptions(catalog ?? [], flow.vehicle))}</span>
                </Item>
            )}

            <div style={{ ...sectionHeader, marginTop: 8 }}>Engines</div>
            {catalog === null && <div className="p-2 text-sm text-color-secondary">Loading catalog…</div>}
            {catalog?.length === 0 && <div className="p-2 text-sm text-color-secondary">No daemons in the roster (add them on the Orchestrate page).</div>}
            {catalog?.length > 0 && reachable.length === 0 && <div className="p-2 text-sm text-color-secondary">No reachable daemons.</div>}
            {reachable?.map((daemon) => (
                <div key={daemon.address}>
                    <div className="px-2 pt-2 pb-1" style={{ fontSize: 11, color: 'var(--palette-header)' }} title={daemon.address}>
                        {daemon.name}
                    </div>
                    {daemon.engines.length === 0 && <div className="px-2 pb-2 text-xs text-color-secondary">No engines</div>}
                    {daemon.engines.map((engine) => {
                        const placed = isEnginePlaced(flow, daemon.address, engine.name);
                        const location = engineLocation(flow, daemon.address);
                        return (
                            <Item key={engine.name} disabled={placed}
                                payload={{ kind: 'engine', daemon: { name: daemon.name, address: daemon.address }, engine: engine.name }}
                                title={placed ? 'Already on the canvas' : paletteTitle(engine)}>
                                <i className="pi pi-microchip" style={{ fontSize: 11 }} />
                                <span>{engine.name}</span>
                                {engine.category && <span style={{ fontSize: 9, opacity: 0.7 }}>{engine.category}</span>}
                                {!engine.typed && <Tag color="#e8c87a" title={engine.problem ?? undefined}>untyped</Tag>}
                                {flow.vehicle && <Tag color={location === 'local' ? '#a3e8a0' : '#7ecfff'}>{location}</Tag>}
                            </Item>
                        );
                    })}
                </div>
            ))}
        </div>
    );
}

export default FlowPalette;
