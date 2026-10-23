import { useState, useEffect, useMemo, useCallback } from 'react';
import { Button } from 'primereact/button';
import { InputText } from 'primereact/inputtext';
import { Dialog } from 'primereact/dialog';
import { TabView, TabPanel } from 'primereact/tabview';
import { ConfirmDialog, confirmDialog } from 'primereact/confirmdialog';
import { getApiUrl } from './urls.js';
import { postToApi } from './apiUtils.js';
import LogViewer from './LogViewer.jsx';
import PluginsTab from './PluginsTab.jsx';
import ConfigureDialog from './ConfigureDialog.jsx';
import { loadDaemons, saveDaemons } from './daemonRoster.js';
import React from 'react';

// Admin status, not live telemetry (contrast App.jsx's 500ms vehicle
// poll, which drives map markers) -- 5s keeps the roster's connectivity
// dots reasonably fresh without hammering every daemon in the roster on
// every tick.
const POLL_INTERVAL_MS = 5000;

// The discoverable set (daemons tagged tag:steeleagle-daemon on the
// tailnet, per /api/daemons/discovered) changes far less often than
// reachability does -- a new daemon joining the tailnet, not a vehicle
// starting/stopping -- so this polls much slower than POLL_INTERVAL_MS.
const DISCOVERY_POLL_MS = 15000;

// crypto.randomUUID() is spec-gated to secure contexts (HTTPS or
// localhost), so it throws on GCS instances reached over plain HTTP on
// the LAN. crypto.getRandomValues() has no such restriction, so build
// a v4 UUID from it when randomUUID isn't available.
function generateId() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
        const bytes = crypto.getRandomValues(new Uint8Array(16));
        bytes[6] = (bytes[6] & 0x0f) | 0x40;
        bytes[8] = (bytes[8] & 0x3f) | 0x80;
        const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0'));
        return `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10, 16).join('')}`;
    }
    return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

// Daemon-wide commands, shown on the Info tab. Configure edits the daemon's
// whole config (eagled replaces it whole and restarts); the Services tab
// lists what it runs.
const LOGS_TAB = 2;

const DAEMON_COMMANDS = [
    { label: 'Configure', icon: 'pi pi-cog' },
    { label: 'Reset Config', icon: 'pi pi-exclamation-triangle', danger: true },
];

// Read-only daemon-wide settings: the top-level keys of the daemon's
// config.toml. They are edited with the Configure command.
const SETTING_ROWS = [
    ['hostname', 'Hostname'],
    ['vehicle_port_base', 'Vehicle Port Base'],
    ['gabriel_port', 'Gabriel Port'],
    ['swarm_controller_port', 'Swarm Controller Port'],
    ['headless', 'Headless'],
    ['auto_run', 'Auto-run'],
    ['auto_install', 'Auto-install'],
];

function DaemonInfoPanel({ status }) {
    if (status === undefined) {
        return <div className="text-color-secondary p-2">Checking daemon status...</div>;
    }
    if (!status.reachable) {
        return <div className="text-color-secondary p-2">Daemon is unreachable.</div>;
    }
    if (!status.ok) {
        return <div className="text-color-secondary p-2">{status.error}</div>;
    }
    if (!status.configured) {
        return <div className="text-color-secondary p-2">Daemon is not configured yet.</div>;
    }
    const rows = SETTING_ROWS
        .filter(([key]) => status.settings[key] !== undefined)
        .map(([key, label]) => [label, String(status.settings[key])]);
    return (
        <div className="p-2">
            {rows.map(([label, value]) => (
                <div key={label} className="flex gap-2 text-sm py-1" style={{ borderBottom: '1px solid var(--surface-border)' }}>
                    <span className="text-color-secondary" style={{ width: '12rem', flexShrink: 0 }}>{label}</span>
                    <span style={{ fontFamily: 'monospace' }}>{value}</span>
                </div>
            ))}
        </div>
    );
}

function OrchestrationPage({ toast }) {
    const [daemons, setDaemons] = useState(loadDaemons);
    const [selectedDaemonId, setSelectedDaemonId] = useState(null);
    const [newName, setNewName] = useState('');
    const [newAddress, setNewAddress] = useState('');
    const [addDialogVisible, setAddDialogVisible] = useState(false);
    const [configureDialogVisible, setConfigureDialogVisible] = useState(false);
    // The service the Configure dialog opens on ({ category, name }), or null.
    const [configureFocus, setConfigureFocus] = useState(null);
    const [activeTab, setActiveTab] = useState(0);
    // The Services tab's logs button: the sources to preselect, and a counter
    // that remounts LogViewer so the preselection applies each time.
    const [logFilter, setLogFilter] = useState({ daemonId: null, sources: [], seq: 0 });

    useEffect(() => {
        saveDaemons(daemons);
    }, [daemons]);

    const [daemonStatus, setDaemonStatus] = useState({});

    const pollOneStatus = useCallback(async (address) => {
        const unreachable = { reachable: false, ok: false, configured: false, settings: {}, error: null };
        try {
            const response = await fetch(getApiUrl(`/api/daemons/status?address=${encodeURIComponent(address)}`));
            if (!response.ok) return unreachable;
            const result = await response.json();
            return {
                reachable: result.reachable,
                ok: result.ok ?? false,
                configured: result.configured ?? false,
                settings: result.settings ?? {},
                error: result.error ?? null,
            };
        } catch {
            return unreachable;
        }
    }, []);

    // Polls every daemon in the roster (not just the selected one), so
    // every row's status dot stays current even for daemons you're not
    // currently looking at. Deliberately doesn't toast on failure -- an
    // unreachable daemon is a normal 200 response with reachable:false
    // (handled inside pollOneStatus), and a background poll that toasts
    // on every failed tick would be spammy, unlike an explicit
    // user-triggered action (postToApi's toast-on-failure is right there).
    useEffect(() => {
        let cancelled = false;
        const poll = async () => {
            const entries = await Promise.all(
                daemons.map(async (d) => [d.id, await pollOneStatus(d.address)])
            );
            if (!cancelled) {
                setDaemonStatus((prev) => ({ ...prev, ...Object.fromEntries(entries) }));
            }
        };
        poll();
        const intervalId = setInterval(poll, POLL_INTERVAL_MS);
        return () => { cancelled = true; clearInterval(intervalId); };
    }, [daemons, pollOneStatus]);

    // Daemons the GCS backend can see tagged tag:steeleagle-daemon on the
    // tailnet (best-effort -- an empty list here just means this GCS host
    // isn't tailnet-joined or nothing's currently tagged, not an error).
    const [discoveredDaemons, setDiscoveredDaemons] = useState([]);

    useEffect(() => {
        let cancelled = false;
        const poll = async () => {
            try {
                const response = await fetch(getApiUrl('/api/daemons/discovered'));
                const result = await response.json();
                if (!cancelled) setDiscoveredDaemons(result.daemons ?? []);
            } catch {
                // Leave the previous discovered list in place on a transient failure.
            }
        };
        poll();
        const intervalId = setInterval(poll, DISCOVERY_POLL_MS);
        return () => { cancelled = true; clearInterval(intervalId); };
    }, []);

    // Discovered entries already in the roster (added manually, or
    // promoted earlier) aren't offered again.
    const newlyDiscoveredDaemons = useMemo(
        () => discoveredDaemons.filter((disc) => !daemons.some((d) => d.address === disc.address)),
        [discoveredDaemons, daemons]
    );

    const onAddDiscoveredDaemon = useCallback((disc) => {
        const id = generateId();
        setDaemons((prev) => [...prev, { id, name: disc.name, address: disc.address }]);
        setSelectedDaemonId(id);
    }, []);

    const selectedDaemon = useMemo(() => daemons.find((d) => d.id === selectedDaemonId) ?? null, [daemons, selectedDaemonId]);

    const onAddDaemon = useCallback(() => {
        const name = newName.trim();
        const address = newAddress.trim();
        if (!name || !address) return;
        const id = generateId();
        setDaemons((prev) => [...prev, { id, name, address }]);
        setNewName('');
        setNewAddress('');
        setSelectedDaemonId(id);
        setAddDialogVisible(false);
    }, [newName, newAddress]);

    const onRemoveDaemon = useCallback((id) => {
        setDaemons((prev) => prev.filter((d) => d.id !== id));
        setSelectedDaemonId((prev) => (prev === id ? null : prev));
    }, []);

    const refreshDaemonStatus = useCallback(async (daemonId, address) => {
        const status = await pollOneStatus(address);
        setDaemonStatus((prev) => ({ ...prev, [daemonId]: status }));
    }, [pollOneStatus]);

    const onResetConfig = useCallback(async (daemon) => {
        const result = await postToApi('/api/daemons/reset-config', { address: daemon.address }, toast, 'Reset Config Error');
        if (result === null) return;
        toast.current.show(
            result.reachable
                ? { severity: 'success', summary: 'Reset Config', detail: `Config reset on ${daemon.name}` }
                : { severity: 'error', summary: 'Reset Config', detail: result.error ?? 'Daemon unreachable' }
        );
        if (result.reachable) refreshDaemonStatus(daemon.id, daemon.address);
    }, [toast, refreshDaemonStatus]);

    const onDaemonCommand = useCallback((label, daemon) => {
        if (label === 'Configure') {
            setConfigureFocus(null);
            setConfigureDialogVisible(true);
            return;
        }
        if (label === 'Reset Config') {
            confirmDialog({
                message: `Permanently wipe all configuration and services on "${daemon.name}"? This cannot be undone.`,
                header: 'Reset Config',
                icon: 'pi pi-exclamation-triangle',
                acceptClassName: 'p-button-danger',
                accept: () => onResetConfig(daemon),
            });
        }
    }, [onResetConfig]);

    return (
        <div className="p-2 flex gap-2" style={{ minHeight: '70vh' }}>
            <ConfirmDialog />
            {configureDialogVisible && selectedDaemon && (
                <ConfigureDialog
                    daemon={selectedDaemon}
                    focus={configureFocus}
                    onHide={() => setConfigureDialogVisible(false)}
                    onDone={() => {
                        setConfigureDialogVisible(false);
                        toast.current.show({ severity: 'success', summary: 'Configure', detail: `Config applied to ${selectedDaemon.name}; the daemon is restarting` });
                        refreshDaemonStatus(selectedDaemon.id, selectedDaemon.address);
                    }}
                />
            )}
            <div className="flex flex-column gap-2" style={{ width: 280, flexShrink: 0 }}>
                <div className="border-round p-2" style={{ backgroundColor: 'var(--surface-card)', border: '1px solid var(--surface-border)' }}>
                    <div className="flex align-items-center justify-content-between mb-2 px-1">
                        <span className="font-bold">Daemons</span>
                        <Button
                            icon="pi pi-plus"
                            size="small"
                            text
                            rounded
                            aria-label="Add Daemon"
                            tooltip="Add Daemon"
                            tooltipOptions={{ position: 'top' }}
                            onClick={() => setAddDialogVisible(true)}
                        />
                    </div>
                    {daemons.length === 0 && (
                        <div className="text-color-secondary text-sm px-1 pb-2">No daemons added yet.</div>
                    )}
                    <div style={{ maxHeight: '50vh', overflowY: 'auto' }}>
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
                                title={
                                    !daemonStatus[d.id] ? 'Checking...'
                                        : daemonStatus[d.id].reachable ? 'Reachable' : 'Unreachable'
                                }
                                style={{
                                    width: '10px', height: '10px', borderRadius: '50%', flexShrink: 0,
                                    backgroundColor: !daemonStatus[d.id] ? 'transparent'
                                        : daemonStatus[d.id].reachable ? 'var(--green-500)' : 'var(--red-500)',
                                    border: `2px solid ${!daemonStatus[d.id] ? 'var(--gray-500)' : daemonStatus[d.id].reachable ? 'var(--green-500)' : 'var(--red-500)'}`,
                                }}
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
                </div>
                {newlyDiscoveredDaemons.length > 0 && (
                    <div className="border-round p-2" style={{ backgroundColor: 'var(--surface-card)', border: '1px solid var(--surface-border)' }}>
                        <div className="font-bold mb-2 px-1">Discovered on Tailnet</div>
                        <div style={{ maxHeight: '30vh', overflowY: 'auto' }}>
                        {newlyDiscoveredDaemons.map((disc) => (
                            <div key={disc.address} className="flex align-items-center gap-2 p-2 border-round mb-1">
                                <span
                                    title={disc.online ? 'Online' : 'Offline'}
                                    style={{
                                        width: '10px', height: '10px', borderRadius: '50%', flexShrink: 0,
                                        backgroundColor: disc.online ? 'var(--green-500)' : 'transparent',
                                        border: `2px solid ${disc.online ? 'var(--green-500)' : 'var(--gray-500)'}`,
                                    }}
                                />
                                <div className="flex-1" style={{ minWidth: 0 }}>
                                    <div className="text-sm font-semibold white-space-nowrap overflow-hidden text-overflow-ellipsis">{disc.name}</div>
                                    <div className="text-xs text-color-secondary white-space-nowrap overflow-hidden text-overflow-ellipsis">{disc.address}</div>
                                </div>
                                <Button
                                    icon="pi pi-plus"
                                    size="small"
                                    text
                                    rounded
                                    aria-label={`Add ${disc.name}`}
                                    tooltip="Add to roster"
                                    tooltipOptions={{ position: 'top' }}
                                    onClick={() => onAddDiscoveredDaemon(disc)}
                                />
                            </div>
                        ))}
                        </div>
                    </div>
                )}
            </div>

            <Dialog
                header="Add Daemon"
                visible={addDialogVisible}
                onHide={() => setAddDialogVisible(false)}
                style={{ width: '24rem' }}
            >
                <div className="flex flex-column gap-2">
                    <InputText placeholder="Name" value={newName} onChange={(e) => setNewName(e.target.value)} className="w-full" autoFocus />
                    <InputText
                        placeholder="host:port"
                        value={newAddress}
                        onChange={(e) => setNewAddress(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter' && newName.trim() && newAddress.trim()) onAddDaemon(); }}
                        className="w-full"
                    />
                    <Button label="Add" icon="pi pi-plus" size="small" disabled={!newName.trim() || !newAddress.trim()} onClick={onAddDaemon} />
                </div>
            </Dialog>

            <div className="flex-1 border-round p-2" style={{ backgroundColor: 'var(--surface-card)', border: '1px solid var(--surface-border)', minWidth: 0 }}>
                {!selectedDaemon ? (
                    <div className="text-color-secondary flex align-items-center justify-content-center h-full">
                        {daemons.length === 0 ? 'Add a daemon to get started.' : 'Select a daemon on the left to view its services, issue commands, or view logs.'}
                    </div>
                ) : (
                    <>
                        <div className="px-1 pb-2">
                            <span className="font-bold text-lg">{selectedDaemon.name}</span>
                            <span className="text-color-secondary ml-2">{selectedDaemon.address}</span>
                        </div>
                        <TabView activeIndex={activeTab} onTabChange={(e) => setActiveTab(e.index)}>
                            <TabPanel header="Info">
                                <div className="flex flex-wrap gap-2 p-2">
                                    {DAEMON_COMMANDS.map((cmd) => (
                                        <Button
                                            key={cmd.label}
                                            label={cmd.label}
                                            icon={cmd.icon}
                                            size="small"
                                            outlined
                                            severity={cmd.danger ? 'danger' : undefined}
                                            onClick={() => onDaemonCommand(cmd.label, selectedDaemon)}
                                        />
                                    ))}
                                </div>
                                <DaemonInfoPanel status={daemonStatus[selectedDaemon.id]} />
                            </TabPanel>
                            <TabPanel header="Services">
                                <PluginsTab
                                    key={selectedDaemon.id}
                                    daemon={selectedDaemon}
                                    toast={toast}
                                    onEditConfig={(inst) => {
                                        setConfigureFocus({ category: inst.category, name: inst.name });
                                        setConfigureDialogVisible(true);
                                    }}
                                    onShowLogs={(sources) => {
                                        setLogFilter((f) => ({ daemonId: selectedDaemon.id, sources, seq: f.seq + 1 }));
                                        setActiveTab(LOGS_TAB);
                                    }}
                                />
                            </TabPanel>
                            <TabPanel header="Logs">
                                <LogViewer key={`${selectedDaemon.id}-${logFilter.seq}`} daemon={selectedDaemon} initialSources={logFilter.daemonId === selectedDaemon.id ? logFilter.sources : []} />
                            </TabPanel>
                        </TabView>
                    </>
                )}
            </div>
        </div>
    );
}

export default React.memo(OrchestrationPage);
