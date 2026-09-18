import { useState, useEffect, useMemo, useCallback } from 'react';
import { Button } from 'primereact/button';
import { InputText } from 'primereact/inputtext';
import { TabView, TabPanel } from 'primereact/tabview';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { VirtualScroller } from 'primereact/virtualscroller';
import { Tag } from 'primereact/tag';
import React from 'react';

// Persisted independently of whether a daemon is actually reachable -- the
// roster of daemons you've told the GCS about is useful on its own (e.g.
// "server1:9090 is configured but currently unreachable"), so it isn't
// tied to live connectivity state the way vehicle status is.
const DAEMONS_STORAGE_KEY = 'steeleagle-daemons';

function loadDaemons() {
    try {
        const raw = localStorage.getItem(DAEMONS_STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

// Mirrors eagle CLI's real subcommands 1:1 (cmd/eagle/main.go) so this
// preview accurately reflects the eventual command surface rather than
// inventing placeholder names. None of these are wired to a daemon yet --
// every click just surfaces a toast.
const DAEMON_COMMANDS = [
    { label: 'Configure', icon: 'pi pi-upload' },
    { label: 'Install Plugin', icon: 'pi pi-plus-circle' },
    { label: 'List Plugins', icon: 'pi pi-list' },
    { label: 'Status', icon: 'pi pi-info-circle' },
    { label: 'Restart Daemon', icon: 'pi pi-refresh' },
    { label: 'Reset Config', icon: 'pi pi-exclamation-triangle', danger: true },
];

// Act on a specific vehicle rather than the daemon as a whole, so they stay
// disabled until the Vehicles tab has real data to pick a target from.
const VEHICLE_COMMANDS = [
    { label: 'Stop', icon: 'pi pi-stop-circle' },
    { label: 'Restart', icon: 'pi pi-refresh' },
    { label: 'Forget', icon: 'pi pi-trash', danger: true },
];

const LOG_LEVEL_SEVERITY = {
    trace: 'secondary',
    debug: 'secondary',
    info: 'info',
    warn: 'warning',
    error: 'danger',
    fatal: 'danger',
    panic: 'danger',
};

// Placeholder content for the log viewer -- there's no streaming/log RPC on
// DaemonService yet (see eagled.proto), so this just demonstrates the
// intended per-line shape (timestamp, zerolog level, message) that real
// entries would eventually have. Once wired, this becomes application
// state that appends incoming lines (capped at a few thousand per daemon
// so a long-running session doesn't grow unbounded) rather than a
// hardcoded single entry.
const PLACEHOLDER_LOG_ITEMS = [
    { timestamp: new Date(), level: 'info', message: 'Log streaming isn\'t wired up yet -- this is a placeholder for how entries will look.' },
];

function logItemTemplate(item) {
    return (
        <div className="flex align-items-start gap-2 px-2 py-1 text-xs" style={{ fontFamily: 'monospace' }}>
            <span className="text-color-secondary" style={{ flexShrink: 0 }}>{item.timestamp.toLocaleTimeString()}</span>
            <Tag severity={LOG_LEVEL_SEVERITY[item.level] ?? 'secondary'} value={item.level} style={{ flexShrink: 0, minWidth: '3.5rem', textAlign: 'center' }} />
            <span>{item.message}</span>
        </div>
    );
}

function OrchestrationPage({ toast }) {
    const [daemons, setDaemons] = useState(loadDaemons);
    const [selectedDaemonId, setSelectedDaemonId] = useState(null);
    const [newName, setNewName] = useState('');
    const [newAddress, setNewAddress] = useState('');

    useEffect(() => {
        localStorage.setItem(DAEMONS_STORAGE_KEY, JSON.stringify(daemons));
    }, [daemons]);

    const selectedDaemon = useMemo(() => daemons.find((d) => d.id === selectedDaemonId) ?? null, [daemons, selectedDaemonId]);

    const onAddDaemon = useCallback(() => {
        const name = newName.trim();
        const address = newAddress.trim();
        if (!name || !address) return;
        const id = crypto.randomUUID();
        setDaemons((prev) => [...prev, { id, name, address }]);
        setNewName('');
        setNewAddress('');
        setSelectedDaemonId(id);
    }, [newName, newAddress]);

    const onRemoveDaemon = useCallback((id) => {
        setDaemons((prev) => prev.filter((d) => d.id !== id));
        setSelectedDaemonId((prev) => (prev === id ? null : prev));
    }, []);

    const notWiredUp = useCallback((label) => {
        toast.current.show({ severity: 'info', summary: 'Not Wired Up', detail: `"${label}" isn't connected to a daemon yet.` });
    }, [toast]);

    return (
        <div className="p-2 flex gap-2" style={{ minHeight: '70vh' }}>
            <div className="flex flex-column gap-2" style={{ width: 280, flexShrink: 0 }}>
                <div className="border-round p-2" style={{ backgroundColor: 'var(--surface-card)', border: '1px solid var(--surface-border)' }}>
                    <div className="font-bold mb-2 px-1">Daemons</div>
                    {daemons.length === 0 && (
                        <div className="text-color-secondary text-sm px-1 pb-2">No daemons added yet.</div>
                    )}
                    {daemons.map((d) => (
                        <div
                            key={d.id}
                            onClick={() => setSelectedDaemonId(d.id)}
                            className="flex align-items-center gap-2 p-2 border-round cursor-pointer mb-1"
                            style={{
                                backgroundColor: d.id === selectedDaemonId ? 'var(--surface-hover)' : undefined,
                                borderLeft: d.id === selectedDaemonId ? '3px solid var(--primary-color)' : '3px solid transparent',
                            }}
                        >
                            <span
                                title="Connectivity not checked yet -- not wired up"
                                style={{ width: '10px', height: '10px', borderRadius: '50%', border: '2px solid var(--gray-500)', flexShrink: 0 }}
                            />
                            <div className="flex-1" style={{ minWidth: 0 }}>
                                <div className="text-sm font-semibold white-space-nowrap overflow-hidden text-overflow-ellipsis">{d.name}</div>
                                <div className="text-xs text-color-secondary white-space-nowrap overflow-hidden text-overflow-ellipsis">{d.address}</div>
                            </div>
                            <Button
                                icon="pi pi-trash"
                                size="small"
                                text
                                rounded
                                severity="danger"
                                aria-label={`Remove ${d.name}`}
                                onClick={(e) => { e.stopPropagation(); onRemoveDaemon(d.id); }}
                            />
                        </div>
                    ))}
                </div>
                <div className="border-round p-2 flex flex-column gap-2" style={{ backgroundColor: 'var(--surface-card)', border: '1px solid var(--surface-border)' }}>
                    <div className="font-bold px-1">Add Daemon</div>
                    <InputText placeholder="Name" value={newName} onChange={(e) => setNewName(e.target.value)} className="w-full" />
                    <InputText placeholder="host:port" value={newAddress} onChange={(e) => setNewAddress(e.target.value)} className="w-full" />
                    <Button label="Add" icon="pi pi-plus" size="small" disabled={!newName.trim() || !newAddress.trim()} onClick={onAddDaemon} />
                </div>
            </div>

            <div className="flex-1 border-round p-2" style={{ backgroundColor: 'var(--surface-card)', border: '1px solid var(--surface-border)', minWidth: 0 }}>
                {!selectedDaemon ? (
                    <div className="text-color-secondary flex align-items-center justify-content-center h-full">
                        {daemons.length === 0 ? 'Add a daemon to get started.' : 'Select a daemon on the left to view its vehicles, issue commands, or view logs.'}
                    </div>
                ) : (
                    <>
                        <div className="px-1 pb-2">
                            <span className="font-bold text-lg">{selectedDaemon.name}</span>
                            <span className="text-color-secondary ml-2">{selectedDaemon.address}</span>
                        </div>
                        <TabView>
                            <TabPanel header="Vehicles">
                                <DataTable value={[]} emptyMessage="No vehicle status available yet -- this daemon isn't wired up." size="small">
                                    <Column field="name" header="Name" />
                                    <Column field="driver" header="Driver" />
                                    <Column field="running" header="Running" />
                                    <Column field="port" header="Port" />
                                </DataTable>
                            </TabPanel>
                            <TabPanel header="Commands">
                                <div className="flex flex-column gap-3 p-2">
                                    <div>
                                        <div className="text-color-secondary text-sm mb-2">Daemon</div>
                                        <div className="flex flex-wrap gap-2">
                                            {DAEMON_COMMANDS.map((cmd) => (
                                                <Button
                                                    key={cmd.label}
                                                    label={cmd.label}
                                                    icon={cmd.icon}
                                                    size="small"
                                                    outlined
                                                    severity={cmd.danger ? 'danger' : undefined}
                                                    onClick={() => notWiredUp(cmd.label)}
                                                />
                                            ))}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-color-secondary text-sm mb-2">Vehicle</div>
                                        <div className="flex flex-wrap gap-2">
                                            {VEHICLE_COMMANDS.map((cmd) => (
                                                <Button
                                                    key={cmd.label}
                                                    label={cmd.label}
                                                    icon={cmd.icon}
                                                    size="small"
                                                    outlined
                                                    severity={cmd.danger ? 'danger' : undefined}
                                                    disabled
                                                    tooltip="No vehicles available yet"
                                                    tooltipOptions={{ position: 'bottom' }}
                                                />
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </TabPanel>
                            <TabPanel header="Logs">
                                {/* VirtualScroller only initializes once its OWN element already
                                    has a nonzero rendered height (its isVisible() check runs before
                                    the scrollHeight prop's imperative resize ever gets a chance to
                                    apply) -- a sized wrapper alone doesn't help, since a bare div
                                    doesn't auto-fill its parent's height. Giving the component
                                    itself `style={{ height: '100%' }}` (a real, immediate CSS
                                    height, not JS-applied) is what breaks that chicken-and-egg. */}
                                <div style={{ height: '24rem' }}>
                                    <VirtualScroller
                                        items={PLACEHOLDER_LOG_ITEMS}
                                        itemSize={28}
                                        scrollHeight="24rem"
                                        appendOnly
                                        itemTemplate={logItemTemplate}
                                        style={{ height: '100%' }}
                                    />
                                </div>
                            </TabPanel>
                        </TabView>
                    </>
                )}
            </div>
        </div>
    );
}

export default React.memo(OrchestrationPage);
