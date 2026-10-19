import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { Button } from 'primereact/button';
import { SelectButton } from 'primereact/selectbutton';
import { Tag } from 'primereact/tag';
import { Message } from 'primereact/message';
import { confirmDialog } from 'primereact/confirmdialog';
import ServiceConfigPanel from './ServiceConfigPanel.jsx';
import { daemonRequest, describeFailure, query } from './daemonApi.js';
import { CATEGORIES, CATEGORY_LABELS } from './configForm.js';
import { formatUptime, hasRunState, logSourcesFor, runStatus, sourceIcon, sourceLabel } from './pluginView.js';

// Same cadence as OrchestrationPage's daemon status poll.
const POLL_INTERVAL_MS = 5000;
const FILTERS = [{ label: 'All', value: 'all' }, ...CATEGORIES.map((c) => ({ label: CATEGORY_LABELS[c], value: c }))];

// The Services tab: every service in one daemon's config (vehicles,
// engines, monitors, extras), with each one's run state and uptime from the
// daemon's ListServices (both columns hidden for a daemon that can't report
// them). The only per-service action is a restart (plus a jump to its logs),
// offered only where the daemon allows it (vehicles, engines, monitors; the
// rest restart through Configure). Expanding a row shows the
// service's config entry read-only; changes go through the Configure
// command.
// Mounted only while its tab is active, so it polls only while visible.
function PluginsTab({ daemon, toast, onShowLogs, onEditConfig }) {
    const [state, setState] = useState({ loaded: false, reachable: true, instances: [], error: null });
    const [filter, setFilter] = useState('all');
    // Keyed by row key, so expanded rows stay open across polls.
    const [expandedRows, setExpandedRows] = useState({});

    const refresh = useCallback(async () => {
        const res = await daemonRequest('GET', `/api/daemons/plugins?${query({ address: daemon.address })}`);
        if (res.body?.reachable === false) {
            setState({ loaded: true, reachable: false, instances: [], error: res.body.error ?? 'Daemon unreachable' });
            return;
        }
        const instances = (res.body?.instances ?? []).map((i) => ({ ...i, key: `${i.category}/${i.name}` }));
        setState({ loaded: true, reachable: true, instances, error: describeFailure(res) });
    }, [daemon.address]);

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        refresh();
        const intervalId = setInterval(refresh, POLL_INTERVAL_MS);
        return () => clearInterval(intervalId);
    }, [refresh]);

    // Not wrapped in useCallback: the React Compiler can't preserve a [toast]
    // dependency for toast.current, and it memoizes these itself.
    const restart = async (inst) => {
        const res = await daemonRequest('POST', '/api/daemons/plugins/restart', {
            address: daemon.address,
            instances: [{ name: inst.name, category: inst.category }],
        });
        const failure = describeFailure(res);
        toast.current.show(failure
            ? { severity: 'error', summary: `Restart ${inst.name}`, detail: failure }
            : { severity: 'success', summary: `Restart ${inst.name}`, detail: 'Restart sent' });
    };

    const confirmRestart = (inst) => confirmDialog({
        message: inst.category === 'vehicle'
            ? `Restart "${inst.name}"? Do not restart a vehicle while it is flying or running a mission.`
            : `Restart "${inst.name}"?`,
        header: 'Restart Service',
        icon: 'pi pi-refresh',
        acceptLabel: 'Restart',
        accept: () => restart(inst),
    });

    const visible = useMemo(
        () => (filter === 'all' ? state.instances : state.instances.filter((i) => i.category === filter)),
        [state.instances, filter]
    );

    const showRunState = hasRunState(state.instances);

    const statusCell = (inst) => {
        const status = runStatus(inst);
        return status ? <Tag value={status.label} severity={status.severity} /> : '—';
    };

    const sourceCell = (inst) => (
        <span className="flex align-items-center gap-2" title={sourceLabel(inst.source)} style={{ maxWidth: '32rem' }}>
            <i className={sourceIcon(inst.source)} />
            <span className="text-sm white-space-nowrap overflow-hidden text-overflow-ellipsis">
                {inst.source ? sourceLabel(inst.source) : inst.plugin_id || '—'}
            </span>
        </span>
    );

    return (
        <div>
            <div className="flex align-items-center justify-content-between gap-2 mb-2 flex-wrap">
                <SelectButton value={filter} options={FILTERS} onChange={(e) => e.value && setFilter(e.value)} allowEmpty={false} />
            </div>
            {state.reachable && state.error && <Message severity="warn" text={state.error} className="w-full mb-2" />}
            <DataTable
                value={visible}
                emptyMessage={!state.loaded ? 'Loading services...' : !state.reachable ? `Daemon is unreachable. ${state.error ?? ''}` : 'No services configured on this daemon. Add them with Configure.'}
                size="small"
                dataKey="key"
                expandedRows={expandedRows}
                onRowToggle={(e) => setExpandedRows(e.data)}
                rowExpansionTemplate={(inst) => <ServiceConfigPanel inst={inst} onEdit={() => onEditConfig(inst)} />}
            >
                <Column expander style={{ width: '3rem' }} />
                <Column field="name" header="Name" sortable />
                <Column field="category" header="Category" sortable body={(i) => <Tag value={i.category} severity="info" />} />
                {showRunState && <Column field="running" header="Status" sortable body={statusCell} />}
                {showRunState && <Column field="uptime_s" header="Uptime" sortable body={(i) => formatUptime(i.uptime_s)} />}
                <Column header="Source" body={sourceCell} />
                <Column
                    header=""
                    style={{ width: '6rem' }}
                    body={(inst) => (
                        <div className="flex gap-1">
                            <Button icon="pi pi-align-left" size="small" text rounded tooltip={`${inst.name} logs`} tooltipOptions={{ position: 'top' }} aria-label={`${inst.name} logs`} onClick={() => onShowLogs(logSourcesFor(inst))} />
                            {inst.restartable && (
                                <Button icon="pi pi-refresh" size="small" text rounded tooltip={`Restart ${inst.name}`} tooltipOptions={{ position: 'top' }} aria-label={`Restart ${inst.name}`} onClick={() => confirmRestart(inst)} />
                            )}
                        </div>
                    )}
                />
            </DataTable>
        </div>
    );
}

export default PluginsTab;
