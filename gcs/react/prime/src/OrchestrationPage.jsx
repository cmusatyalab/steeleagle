import { useState, useEffect, useMemo, useCallback } from 'react';
import { Button } from 'primereact/button';
import { InputText } from 'primereact/inputtext';
import { Dialog } from 'primereact/dialog';
import { TabView, TabPanel } from 'primereact/tabview';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { ConfirmDialog, confirmDialog } from 'primereact/confirmdialog';
import { getApiUrl } from './urls.js';
import { postToApi } from './apiUtils.js';
import LogViewer from './LogViewer.jsx';
import React from 'react';

// Persisted independently of whether a daemon is actually reachable -- the
// roster of daemons you've told the GCS about is useful on its own (e.g.
// "server1:9090 is configured but currently unreachable"), so it isn't
// tied to live connectivity state the way vehicle status is.
const DAEMONS_STORAGE_KEY = 'steeleagle-daemons';

// Admin status, not live telemetry (contrast App.jsx's 500ms vehicle
// poll, which drives map markers) -- 5s keeps the roster's connectivity
// dots reasonably fresh without hammering every daemon in the roster on
// every tick.
const POLL_INTERVAL_MS = 5000;

function loadDaemons() {
    try {
        const raw = localStorage.getItem(DAEMONS_STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

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

// Mirrors eagle CLI's real subcommands 1:1 (cmd/eagle/main.go) so this
// preview accurately reflects the eventual command surface rather than
// inventing placeholder names. None of these are wired to a daemon yet --
// every click just surfaces a toast.
const DAEMON_COMMANDS = [
    { label: 'Configure', icon: 'pi pi-upload' },
    { label: 'Install Plugin', icon: 'pi pi-plus-circle' },
    { label: 'List Plugins', icon: 'pi pi-list' },
    { label: 'Restart Daemon', icon: 'pi pi-refresh' },
    { label: 'Reset Config', icon: 'pi pi-exclamation-triangle', danger: true },
];

// Daemon-wide config (as opposed to per-vehicle state, which lives on the
// Vehicles tab) -- field set, order, and conditionals mirror eagle CLI's
// own `status` output (cmd/eagle/main.go printStatus) so this is a direct
// GUI reflection of the same source of truth, not a reinvented one.
function DaemonConfigPanel({ status }) {
    if (status === undefined) {
        return <div className="text-color-secondary p-2">Checking daemon status...</div>;
    }
    if (!status.reachable) {
        return <div className="text-color-secondary p-2">Daemon is unreachable.</div>;
    }
    // Platform describes the running binary, not the applied config, so it's
    // reported (and shown) even before the daemon's first Configure. A daemon
    // built before it was added reports neither, so the row is just omitted.
    const rows = [];
    if (status.os || status.arch) rows.push(['Platform', `${status.os}/${status.arch}`]);
    const cfg = status.config;
    if (status.configured && cfg) {
        rows.push(
            ['Daemon', cfg.daemon_name],
            ['Port Base', cfg.port_base],
            ['Plugin Dir', cfg.plugin_dir],
            ['Swarm Controller', cfg.swarm_controller_address],
        );
        if (cfg.gabriel_server_endpoint) rows.push(['Gabriel', cfg.gabriel_server_endpoint]);
        rows.push(['VPN', `${cfg.vpn} (vehicles: ${cfg.vehicle_vpn})`]);
        if (cfg.vpn) rows.push(['Tailscale Auth Key Env', `$${cfg.tailscale_authkey_env}`]);
    }
    return (
        <div className="p-2">
            {rows.map(([label, value]) => (
                <div key={label} className="flex gap-2 text-sm py-1" style={{ borderBottom: '1px solid var(--surface-border)' }}>
                    <span className="text-color-secondary" style={{ width: '12rem', flexShrink: 0 }}>{label}</span>
                    <span style={{ fontFamily: 'monospace' }}>{value}</span>
                </div>
            ))}
            {!status.configured && <div className="text-color-secondary pt-2">Daemon is not configured yet.</div>}
        </div>
    );
}

function OrchestrationPage({ toast }) {
    const [daemons, setDaemons] = useState(loadDaemons);
    const [selectedDaemonId, setSelectedDaemonId] = useState(null);
    const [newName, setNewName] = useState('');
    const [newAddress, setNewAddress] = useState('');
    const [addDialogVisible, setAddDialogVisible] = useState(false);

    useEffect(() => {
        localStorage.setItem(DAEMONS_STORAGE_KEY, JSON.stringify(daemons));
    }, [daemons]);

    const [daemonStatus, setDaemonStatus] = useState({});

    const pollOneStatus = useCallback(async (address) => {
        try {
            const response = await fetch(getApiUrl(`/api/daemons/status?address=${encodeURIComponent(address)}`));
            if (!response.ok) return { reachable: false, vehicles: [], configured: false, config: null, os: '', arch: '' };
            const result = await response.json();
            return {
                reachable: result.reachable,
                vehicles: result.vehicles ?? [],
                configured: result.configured ?? false,
                config: result.config ?? null,
                os: result.os ?? '',
                arch: result.arch ?? '',
            };
        } catch {
            return { reachable: false, vehicles: [], configured: false, config: null, os: '', arch: '' };
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

    const selectedDaemon = useMemo(() => daemons.find((d) => d.id === selectedDaemonId) ?? null, [daemons, selectedDaemonId]);

    // Installed-plugins listing is persistent (unlike the toast-based
    // pass/fail commands) since it's a dataset worth browsing, not a
    // one-shot outcome. Keyed by daemon id (like daemonStatus above) so
    // switching daemons naturally shows that daemon's own last result
    // instead of a stale one, with no separate reset-on-switch effect.
    const [pluginsResults, setPluginsResults] = useState({});

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

    const notWiredUp = useCallback((label) => {
        toast.current.show({ severity: 'info', summary: 'Not Wired Up', detail: `"${label}" isn't connected to a daemon yet.` });
    }, [toast]);

    const refreshDaemonStatus = useCallback(async (daemonId, address) => {
        const status = await pollOneStatus(address);
        setDaemonStatus((prev) => ({ ...prev, [daemonId]: status }));
    }, [pollOneStatus]);

    const onStopVehicles = useCallback(async (address, names) => {
        const result = await postToApi('/api/daemons/stop-vehicles', { address, names }, toast, 'Stop Vehicle Error');
        if (result === null) return;
        if (!result.reachable) {
            toast.current.show({ severity: 'error', summary: 'Stop Vehicle', detail: result.error ?? 'Daemon unreachable' });
            return;
        }
        const failed = (result.results ?? []).filter((r) => !r.ok);
        if (failed.length > 0) {
            toast.current.show({ severity: 'error', summary: 'Stop Vehicle', detail: failed.map((r) => `${r.name}: ${r.error || 'failed'}`).join('; ') });
            return;
        }
        toast.current.show({ severity: 'success', summary: 'Stop Vehicle', detail: `Sent to ${names.join(', ')}` });
    }, [toast]);

    const onRestartVehicles = useCallback(async (address, names) => {
        const result = await postToApi('/api/daemons/restart-vehicles', { address, names }, toast, 'Restart Vehicle Error');
        if (result === null) return;
        if (!result.reachable) {
            toast.current.show({ severity: 'error', summary: 'Restart Vehicle', detail: result.error ?? 'Daemon unreachable' });
            return;
        }
        const failed = (result.results ?? []).filter((r) => !r.ok);
        if (failed.length > 0) {
            toast.current.show({ severity: 'error', summary: 'Restart Vehicle', detail: failed.map((r) => `${r.name}: ${r.error || 'failed'}`).join('; ') });
            return;
        }
        toast.current.show({ severity: 'success', summary: 'Restart Vehicle', detail: `Sent to ${names.join(', ')}` });
    }, [toast]);

    const onForgetVehicles = useCallback(async (daemonId, address, names) => {
        const result = await postToApi('/api/daemons/forget-vehicles', { address, names }, toast, 'Forget Vehicle Error');
        if (result === null) return;
        if (!result.reachable) {
            toast.current.show({ severity: 'error', summary: 'Forget Vehicle', detail: result.error ?? 'Daemon unreachable' });
            return;
        }
        const failed = (result.results ?? []).filter((r) => !r.ok);
        if (failed.length > 0) {
            toast.current.show({ severity: 'error', summary: 'Forget Vehicle', detail: failed.map((r) => `${r.name}: ${r.error || 'failed'}`).join('; ') });
        } else {
            toast.current.show({ severity: 'success', summary: 'Forget Vehicle', detail: `Forgot ${names.join(', ')}` });
        }
        refreshDaemonStatus(daemonId, address);
    }, [toast, refreshDaemonStatus]);

    const confirmForgetVehicle = useCallback((address, name) => {
        confirmDialog({
            message: `Permanently forget "${name}" on this daemon? This cannot be undone.`,
            header: 'Forget Vehicle',
            icon: 'pi pi-exclamation-triangle',
            acceptClassName: 'p-button-danger',
            accept: () => onForgetVehicles(selectedDaemon.id, address, [name]),
        });
    }, [onForgetVehicles, selectedDaemon]);

    const onListPlugins = useCallback(async (daemonId, address) => {
        setPluginsResults((prev) => ({ ...prev, [daemonId]: { status: 'loading' } }));
        let response = null;
        try {
            response = await fetch(getApiUrl(`/api/daemons/plugins?address=${encodeURIComponent(address)}`));
        } catch (err) {
            setPluginsResults((prev) => ({ ...prev, [daemonId]: null }));
            toast.current.show({ severity: 'error', summary: 'List Plugins', detail: `request failed: ${err.message}` });
            return;
        }
        let result = null;
        try {
            result = await response.json();
        } catch {
            setPluginsResults((prev) => ({ ...prev, [daemonId]: null }));
            toast.current.show({ severity: 'error', summary: 'List Plugins', detail: `server returned a non-JSON response (status ${response.status})` });
            return;
        }
        if (!result.reachable) {
            setPluginsResults((prev) => ({ ...prev, [daemonId]: null }));
            toast.current.show({ severity: 'error', summary: 'List Plugins', detail: result.error ?? 'Daemon unreachable' });
            return;
        }
        setPluginsResults((prev) => ({ ...prev, [daemonId]: { status: 'loaded', plugins: result.plugins } }));
    }, [toast]);

    const onRestartDaemon = useCallback(async (daemon) => {
        const result = await postToApi('/api/daemons/restart-daemon', { address: daemon.address }, toast, 'Restart Daemon Error');
        if (result === null) return;
        toast.current.show(
            result.reachable
                ? { severity: 'success', summary: 'Restart Daemon', detail: `Restart sent to ${daemon.name}` }
                : { severity: 'error', summary: 'Restart Daemon', detail: result.error ?? 'Daemon unreachable' }
        );
    }, [toast]);

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
        if (label === 'Configure' || label === 'Install Plugin') {
            notWiredUp(label);
            return;
        }
        if (label === 'List Plugins') {
            onListPlugins(daemon.id, daemon.address);
            return;
        }
        if (label === 'Restart Daemon') {
            confirmDialog({
                message: `Restart the eagled process on "${daemon.name}"? Vehicle processes it supervises will be interrupted.`,
                header: 'Restart Daemon',
                icon: 'pi pi-exclamation-triangle',
                acceptClassName: 'p-button-danger',
                accept: () => onRestartDaemon(daemon),
            });
            return;
        }
        if (label === 'Reset Config') {
            confirmDialog({
                message: `Permanently wipe all configuration and vehicles on "${daemon.name}"? This cannot be undone.`,
                header: 'Reset Config',
                icon: 'pi pi-exclamation-triangle',
                acceptClassName: 'p-button-danger',
                accept: () => onResetConfig(daemon),
            });
        }
    }, [notWiredUp, onListPlugins, onRestartDaemon, onResetConfig]);

    return (
        <div className="p-2 flex gap-2" style={{ minHeight: '70vh' }}>
            <ConfirmDialog />
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
                        {daemons.length === 0 ? 'Add a daemon to get started.' : 'Select a daemon on the left to view its vehicles, issue commands, or view logs.'}
                    </div>
                ) : (
                    <>
                        <div className="px-1 pb-2">
                            <span className="font-bold text-lg">{selectedDaemon.name}</span>
                            <span className="text-color-secondary ml-2">{selectedDaemon.address}</span>
                        </div>
                        <TabView>
                            <TabPanel header="Config">
                                <DaemonConfigPanel status={daemonStatus[selectedDaemon.id]} />
                            </TabPanel>
                            <TabPanel header="Vehicles">
                                <DataTable
                                    value={daemonStatus[selectedDaemon.id]?.vehicles ?? []}
                                    emptyMessage={
                                        daemonStatus[selectedDaemon.id] === undefined ? 'Checking daemon status...'
                                            : daemonStatus[selectedDaemon.id].reachable === false ? 'Daemon is unreachable.'
                                            : 'No vehicles configured on this daemon.'
                                    }
                                    size="small"
                                >
                                    <Column field="name" header="Name" sortable />
                                    <Column field="driver" header="Driver" sortable />
                                    <Column field="running" header="Running" body={(v) => (v.running ? 'Yes' : 'No')} sortable />
                                    <Column field="port" header="Port" />
                                    <Column
                                        header="Actions"
                                        body={(v) => (
                                            <div className="flex gap-1">
                                                <Button
                                                    icon="pi pi-stop-circle"
                                                    size="small"
                                                    text
                                                    rounded
                                                    tooltip="Stop"
                                                    tooltipOptions={{ position: 'top' }}
                                                    aria-label={`Stop ${v.name}`}
                                                    onClick={() => onStopVehicles(selectedDaemon.address, [v.name])}
                                                />
                                                <Button
                                                    icon="pi pi-refresh"
                                                    size="small"
                                                    text
                                                    rounded
                                                    tooltip="Restart"
                                                    tooltipOptions={{ position: 'top' }}
                                                    aria-label={`Restart ${v.name}`}
                                                    onClick={() => onRestartVehicles(selectedDaemon.address, [v.name])}
                                                />
                                                <Button
                                                    icon="pi pi-trash"
                                                    size="small"
                                                    text
                                                    rounded
                                                    severity="danger"
                                                    tooltip="Forget"
                                                    tooltipOptions={{ position: 'top' }}
                                                    aria-label={`Forget ${v.name}`}
                                                    onClick={() => confirmForgetVehicle(selectedDaemon.address, v.name)}
                                                />
                                            </div>
                                        )}
                                    />
                                </DataTable>
                            </TabPanel>
                            <TabPanel header="Commands">
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
                                {pluginsResults[selectedDaemon.id] && (
                                    <div className="px-2 pb-2">
                                        <div className="font-bold text-sm mb-1">Installed Plugins</div>
                                        {pluginsResults[selectedDaemon.id].status === 'loading' ? (
                                            <div className="text-color-secondary text-sm">Loading installed plugins...</div>
                                        ) : pluginsResults[selectedDaemon.id].plugins.length === 0 ? (
                                            <div className="text-color-secondary text-sm">No plugins installed.</div>
                                        ) : (
                                            <DataTable value={pluginsResults[selectedDaemon.id].plugins} size="small">
                                                <Column field="name" header="Name" sortable />
                                                <Column field="category" header="Category" body={(p) => p.category.toLowerCase()} sortable />
                                                <Column field="ref" header="Ref" />
                                            </DataTable>
                                        )}
                                    </div>
                                )}
                            </TabPanel>
                            <TabPanel header="Logs">
                                <LogViewer key={selectedDaemon.id} daemon={selectedDaemon} />
                            </TabPanel>
                        </TabView>
                    </>
                )}
            </div>
        </div>
    );
}

export default React.memo(OrchestrationPage);
