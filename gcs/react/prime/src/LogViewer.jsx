import React, { useState, useEffect, useReducer, useMemo, useRef, useCallback } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { MultiSelect } from 'primereact/multiselect';
import { Button } from 'primereact/button';
import { Tag } from 'primereact/tag';
import { getApiUrl } from './urls.js';
import { LEVELS, initialLogState, toRow, advanceCursors, appendRows, filterRows } from './logState.js';

const INITIAL_TAIL = 200;
const FLUSH_INTERVAL_MS = 100;
const SOURCES_POLL_MS = 10000;
const MAX_BACKOFF_MS = 10000;
const ROW_HEIGHT = 28;

const LOG_LEVEL_SEVERITY = {
    trace: 'secondary',
    debug: 'secondary',
    info: 'info',
    warn: 'warning',
    error: 'danger',
    fatal: 'danger',
    panic: 'danger',
};

function rowsReducer(state, action) {
    return action.type === 'rows' ? appendRows(state, action.rows) : state;
}

function sleep(ms, signal) {
    return new Promise((resolve) => {
        const onAbort = () => { clearTimeout(t); resolve(); };
        const t = setTimeout(() => { signal.removeEventListener('abort', onAbort); resolve(); }, ms);
        signal.addEventListener('abort', onAbort, { once: true });
    });
}

function logRowTemplate(row) {
    if (row.dropped > 0) {
        return (
            <div className="flex align-items-center px-2 text-xs text-color-secondary" style={{ height: ROW_HEIGHT, fontStyle: 'italic', opacity: 0.7 }}>
                {`${row.source}: ${row.text}`}
            </div>
        );
    }
    return (
        <div className="flex align-items-center gap-2 px-2 text-xs" style={{ height: ROW_HEIGHT, fontFamily: 'monospace', whiteSpace: 'pre' }}>
            <span className="text-color-secondary" style={{ flexShrink: 0 }}>{row.time.toLocaleTimeString()}</span>
            <span className="text-color-secondary" style={{ flexShrink: 0, minWidth: '9rem' }}>{row.source}</span>
            {row.level
                ? <Tag severity={LOG_LEVEL_SEVERITY[row.level] ?? 'secondary'} value={row.level} style={{ flexShrink: 0, minWidth: '3.5rem', textAlign: 'center' }} />
                : <span style={{ flexShrink: 0, minWidth: '3.5rem' }} />}
            <span>{row.text}</span>
        </div>
    );
}

// Owns one stream: connect, buffer, reconnect with per-source cursors, render.
function LogStream({ address, sources, levels }) {
    const [state, dispatch] = useReducer(rowsReducer, undefined, initialLogState);
    const [status, setStatus] = useState('connecting');
    const [lastError, setLastError] = useState(null);
    const [follow, setFollow] = useState(true);
    const containerRef = useRef(null);

    useEffect(() => {
        const ctrl = new AbortController();
        let cursors = {};
        let buffer = [];
        // Rows are batched so a busy daemon costs ~10 renders/s, not one per line.
        const flush = setInterval(() => {
            if (buffer.length === 0) return;
            const rows = buffer;
            buffer = [];
            dispatch({ type: 'rows', rows });
        }, FLUSH_INTERVAL_MS);

        const run = async () => {
            let backoff = 500;
            while (!ctrl.signal.aborted) {
                let serverError = null;
                try {
                    // tail applies to sources with no cursor; the server lets a
                    // cursor override it, so reconnects resume without repeats.
                    await fetchEventSource(getApiUrl('/api/daemons/logs/stream'), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ address, sources, tail: INITIAL_TAIL, follow: true, after_seq: cursors }),
                        signal: ctrl.signal,
                        openWhenHidden: true, // reopening on tab-visible would resend a stale body
                        async onopen(res) {
                            if (!res.ok) throw new Error(`HTTP ${res.status}`);
                            backoff = 500;
                            setLastError(null);
                            setStatus('live');
                        },
                        onmessage(ev) {
                            if (ev.event === 'record') {
                                const row = toRow(JSON.parse(ev.data));
                                cursors = advanceCursors(cursors, row);
                                buffer.push(row);
                            } else if (ev.event === 'error') {
                                serverError = JSON.parse(ev.data).error;
                            }
                        },
                        onclose() { throw new Error('stream closed'); },
                        onerror(err) { throw err; },
                    });
                } catch (err) {
                    if (ctrl.signal.aborted) return;
                    setLastError(serverError ?? err.message);
                }
                if (ctrl.signal.aborted) return;
                setStatus('retrying');
                await sleep(backoff, ctrl.signal);
                backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
            }
        };
        run();

        return () => { ctrl.abort(); clearInterval(flush); };
    }, [address, sources]);

    const rows = useMemo(() => filterRows(state.records, levels), [state.records, levels]);

    useEffect(() => {
        if (follow) {
            const el = containerRef.current;
            if (el) el.scrollTop = el.scrollHeight;
        }
    }, [rows, follow]);

    const onScroll = useCallback((e) => {
        const el = e.target;
        setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < ROW_HEIGHT);
    }, []);

    return (
        <div>
            <div className="flex align-items-center justify-content-between text-xs pb-1 px-1">
                <span>
                    {status === 'live' && <span style={{ color: 'var(--green-500)' }}>Live</span>}
                    {status === 'connecting' && <span className="text-color-secondary">Connecting...</span>}
                    {status === 'retrying' && <Tag severity="warning" value="Disconnected, retrying..." />}
                    {status === 'retrying' && lastError && <span className="text-color-secondary ml-2">{lastError}</span>}
                </span>
                <span className="text-color-secondary">{rows.length} lines</span>
            </div>
            {/* Plain scrollable div, not PrimeReact's VirtualScroller: real
                browser testing found VirtualScroller collapses to rendering a
                single row (and does not self-recover) when scrollToIndex()
                targets the very last index of a list that's simultaneously
                still being appended to -- exactly what the follow effect above
                does on every batch. rows is capped at 5,000 (logState.js), so
                rendering all of them directly is cheap enough to not need
                virtualization. */}
            <div style={{ position: 'relative', height: '24rem' }}>
                <div ref={containerRef} onScroll={onScroll} style={{ height: '100%', overflowY: 'auto' }}>
                    {rows.map((row) => <div key={row.key}>{logRowTemplate(row)}</div>)}
                </div>
                {!follow && (
                    <Button
                        label="Jump to latest"
                        icon="pi pi-arrow-down"
                        size="small"
                        style={{ position: 'absolute', right: 16, bottom: 12 }}
                        onClick={() => setFollow(true)}
                    />
                )}
            </div>
        </div>
    );
}

function LogViewer({ daemon }) {
    const [available, setAvailable] = useState([]);
    const [selectedSources, setSelectedSources] = useState([]);
    const [levels, setLevels] = useState([]);

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            try {
                const res = await fetch(getApiUrl(`/api/daemons/log-sources?address=${encodeURIComponent(daemon.address)}`));
                const body = await res.json();
                if (!cancelled && body.reachable) setAvailable(body.sources);
            } catch {
                // LogStream's banner already reports connectivity.
            }
        };
        load();
        const id = setInterval(load, SOURCES_POLL_MS);
        return () => { cancelled = true; clearInterval(id); };
    }, [daemon.address]);

    const sourceOptions = useMemo(
        () => available.map((s) => ({ label: s.running ? s.name : `${s.name} (stopped)`, value: s.name })),
        [available]
    );

    return (
        <div>
            <div className="flex flex-wrap align-items-center gap-2 pb-2">
                <MultiSelect
                    value={selectedSources}
                    options={sourceOptions}
                    onChange={(e) => setSelectedSources(e.value)}
                    placeholder="All sources"
                    maxSelectedLabels={2}
                    className="w-16rem"
                />
                <MultiSelect
                    value={levels}
                    options={LEVELS}
                    onChange={(e) => setLevels(e.value)}
                    placeholder="All levels"
                    maxSelectedLabels={2}
                    className="w-12rem"
                />
            </div>
            <LogStream key={selectedSources.join('\n')} address={daemon.address} sources={selectedSources} levels={levels} />
        </div>
    );
}

export default React.memo(LogViewer);
