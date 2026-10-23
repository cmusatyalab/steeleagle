import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Dialog } from 'primereact/dialog';
import { Button } from 'primereact/button';
import { Dropdown } from 'primereact/dropdown';
import { InputNumber } from 'primereact/inputnumber';
import { InputText } from 'primereact/inputtext';
import { InputTextarea } from 'primereact/inputtextarea';
import { Message } from 'primereact/message';
import { SelectButton } from 'primereact/selectbutton';
import { TabPanel, TabView } from 'primereact/tabview';
import { confirmDialog } from 'primereact/confirmdialog';
import InstanceEditor from './InstanceEditor.jsx';
import { daemonRequest, describeFailure, query } from './daemonApi.js';
import {
    CATEGORIES,
    CATEGORY_LABELS,
    SETTINGS,
    duplicateInstance,
    formToState,
    hasErrors,
    newInstance,
    stateToForm,
} from './configForm.js';

const MODES = [{ label: 'Form', value: 'form' }, { label: 'Raw TOML', value: 'raw' }];
const BOOLEAN_OPTIONS = [{ label: 'Not set', value: null }, { label: 'Yes', value: true }, { label: 'No', value: false }];
const NO_ERRORS = { settings: {}, instances: {} };

// Edits a daemon's whole config and applies it with Configure, which
// replaces the config and restarts the daemon and every service it runs.
// The Form and Raw TOML views convert through /api/daemons/config/convert;
// the form is merged into the raw text it came from (`baseRaw`), so
// comments and anything the form doesn't show survive. Saves carry the
// config_hash read at load, so a concurrent change is a conflict, not an
// overwrite. `focus` ({ category, name }) opens on that service's tab with
// its card expanded.
function ConfigureDialog({ daemon, focus, onHide, onDone }) {
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState(null);
    const [notice, setNotice] = useState(null);
    const [configHash, setConfigHash] = useState(null);
    const [mode, setMode] = useState('form');
    const [state, setState] = useState(null);
    const [raw, setRaw] = useState('');
    const [baseRaw, setBaseRaw] = useState('');
    const [expanded, setExpanded] = useState(() => new Set());
    const [tab, setTab] = useState(0);
    const tabsRef = useRef(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const [conflict, setConflict] = useState(false);
    const [showErrors, setShowErrors] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        setLoadError(null);
        setNotice(null);
        setError(null);
        setConflict(false);
        setShowErrors(false);
        const res = await daemonRequest('GET', `/api/daemons/config?${query({ address: daemon.address })}`);
        if (res.body?.raw_toml == null) {
            setLoadError(describeFailure(res) ?? 'Could not load the config');
            setLoading(false);
            return;
        }
        setConfigHash(res.body.config_hash);
        setRaw(res.body.raw_toml);
        setBaseRaw(res.body.raw_toml);
        let open = new Set();
        if (res.body.form) {
            const loaded = formToState(res.body.form);
            setState(loaded);
            setMode('form');
            const target = focus && loaded.instances[focus.category]?.find((i) => i.name === focus.name);
            if (target) {
                open = new Set([target.key]);
                setTab(CATEGORIES.indexOf(focus.category) + 1);
            }
        } else {
            // A config the form can't represent opens in Raw TOML for repair.
            setState(null);
            setMode('raw');
            setNotice(res.body.error);
        }
        setExpanded(open);
        setLoading(false);
    }, [daemon.address, focus]);

    // The tab strip scrolls, and doesn't follow a tab chosen in code (opening
    // on a focused service's category), so bring the active tab into view.
    useEffect(() => {
        tabsRef.current?.querySelector('.p-tabview-nav li.p-highlight')
            ?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }, [tab, mode, loading]);

    // Loading the config from the daemon is the effect's whole job; the
    // setState calls inside load() are the intended sync, not a cascade.
    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        load();
    }, [load]);

    const { form, errors } = state ? stateToForm(state) : { form: null, errors: NO_ERRORS };
    const shownErrors = showErrors ? errors : NO_ERRORS;

    const setSetting = (key, value) => setState((s) => ({ ...s, settings: { ...s.settings, [key]: value } }));
    const updateInstance = (category, key, patch) => setState((s) => ({
        ...s,
        instances: { ...s.instances, [category]: s.instances[category].map((i) => (i.key === key ? { ...i, ...patch } : i)) },
    }));
    const insertInstance = (category, inst, afterKey) => {
        setState((s) => {
            const list = [...s.instances[category]];
            const at = afterKey ? list.findIndex((i) => i.key === afterKey) + 1 : list.length;
            list.splice(at, 0, inst);
            return { ...s, instances: { ...s.instances, [category]: list } };
        });
        setExpanded((e) => new Set(e).add(inst.key));
    };
    const removeInstance = (category, key) => setState((s) => ({
        ...s,
        instances: { ...s.instances, [category]: s.instances[category].filter((i) => i.key !== key) },
    }));
    const toggle = (key) => setExpanded((e) => {
        const next = new Set(e);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        return next;
    });

    const switchMode = async (next) => {
        if (!next || next === mode) return;
        setError(null);
        if (next === 'raw') {
            if (hasErrors(errors)) {
                setShowErrors(true);
                setError('Fix the highlighted fields first.');
                return;
            }
            const res = await daemonRequest('POST', '/api/daemons/config/convert', { to: 'raw', form, base_toml: baseRaw });
            const failure = describeFailure(res);
            if (failure) {
                setError(failure);
                return;
            }
            setRaw(res.body.raw_toml);
        } else {
            const res = await daemonRequest('POST', '/api/daemons/config/convert', { to: 'form', raw_toml: raw });
            const failure = describeFailure(res);
            if (failure) {
                setError(failure);
                return;
            }
            setState(formToState(res.body.form));
            setBaseRaw(raw);
            setExpanded(new Set());
            setNotice(null);
        }
        setMode(next);
    };

    const apply = async (payload) => {
        setBusy(true);
        const res = await daemonRequest('PUT', '/api/daemons/config', { address: daemon.address, config_hash: configHash, ...payload });
        setBusy(false);
        if (res.body?.conflict) {
            setConflict(true);
            return;
        }
        const failure = describeFailure(res);
        if (failure) {
            setError(failure);
            return;
        }
        onDone();
    };

    const confirmApply = () => {
        setError(null);
        let payload;
        if (mode === 'raw') {
            payload = { raw_toml: raw };
        } else {
            if (hasErrors(errors)) {
                setShowErrors(true);
                setError('Fix the highlighted fields first.');
                return;
            }
            payload = { form };
        }
        confirmDialog({
            header: 'Restart Daemon?',
            icon: 'pi pi-exclamation-triangle',
            message: (
                <div className="flex flex-column gap-2" style={{ maxWidth: '32rem' }}>
                    <span>Applying this configuration restarts the daemon on <b>{daemon.name}</b>. Every service it runs will stop and restart, including its vehicles.</span>
                    <span className="font-semibold">Do not apply while any of its vehicles is flying or running a mission.</span>
                </div>
            ),
            acceptLabel: 'Apply and Restart',
            rejectLabel: 'Cancel',
            acceptClassName: 'p-button-danger',
            accept: () => apply(payload),
        });
    };

    const ready = !loading && !loadError;
    const tabErrorCount = (category) => state.instances[category].filter((i) => shownErrors.instances[i.key]).length;

    const settingField = ({ key, label, type }) => {
        const value = state.settings[key];
        const err = shownErrors.settings[key];
        let input;
        if (type === 'text') {
            input = <InputText value={value ?? ''} onChange={(e) => setSetting(key, e.target.value)} disabled={busy} placeholder="not set" />;
        } else if (type === 'port') {
            input = (
                <InputNumber value={value} onValueChange={(e) => setSetting(key, e.value ?? null)} useGrouping={false} min={1} max={65535} disabled={busy} invalid={!!err} placeholder="not set" />
            );
        } else {
            input = <Dropdown value={value} options={BOOLEAN_OPTIONS} onChange={(e) => setSetting(key, e.value)} disabled={busy} />;
        }
        return (
            <div key={key} className="flex flex-column gap-1" style={{ width: '14rem' }}>
                <label className="text-sm">{label}</label>
                {input}
                {err && <small className="p-error">{err}</small>}
            </div>
        );
    };

    const categoryPanel = (category) => {
        const list = state.instances[category];
        const count = tabErrorCount(category);
        return (
            <TabPanel key={category} header={`${CATEGORY_LABELS[category]} (${list.length})${count ? ' ⚠' : ''}`}>
                <div className="flex flex-column gap-2">
                    {list.length === 0 && <div className="text-color-secondary text-sm">None configured.</div>}
                    {list.map((inst) => (
                        <InstanceEditor
                            key={inst.key}
                            inst={inst}
                            errors={shownErrors.instances[inst.key]}
                            expanded={expanded.has(inst.key)}
                            onToggle={() => toggle(inst.key)}
                            onChange={(patch) => updateInstance(category, inst.key, patch)}
                            onRemove={() => removeInstance(category, inst.key)}
                            onDuplicate={() => insertInstance(category, duplicateInstance(inst), inst.key)}
                            disabled={busy}
                        />
                    ))}
                    <div>
                        <Button label={`Add ${category}`} icon="pi pi-plus" size="small" text onClick={() => insertInstance(category, newInstance(category))} disabled={busy} />
                    </div>
                </div>
            </TabPanel>
        );
    };

    const footer = (
        <div className="flex justify-content-between align-items-center gap-2">
            <span className="text-sm text-color-secondary">{busy ? 'Applying; the daemon is restarting...' : ''}</span>
            <div className="flex gap-2">
                <Button label="Cancel" text size="small" onClick={onHide} disabled={busy} />
                <Button label="Apply" icon={busy ? 'pi pi-spin pi-spinner' : 'pi pi-check'} severity="danger" size="small" onClick={confirmApply} disabled={busy || !ready || conflict} />
            </div>
        </div>
    );

    return (
        <Dialog
            header={`Configure ${daemon.name}`}
            visible
            onHide={() => { if (!busy) onHide(); }}
            closable={!busy}
            style={{ width: '60rem', maxWidth: '95vw' }}
            contentStyle={{ minHeight: '28rem' }}
            footer={footer}
        >
            {loading && <div className="text-color-secondary">Loading config...</div>}
            {loadError && <Message severity="error" text={loadError} className="w-full" />}
            {ready && (
                <div className="flex flex-column gap-3">
                    {conflict && (
                        <div className="flex align-items-center gap-2 p-2 border-round" style={{ backgroundColor: 'var(--yellow-100)', color: 'var(--yellow-900)' }}>
                            <i className="pi pi-exclamation-triangle" />
                            <span className="flex-1 text-sm">The config changed on the daemon since you opened this. Reload to see the current version (your edits will be discarded).</span>
                            <Button label="Reload" size="small" onClick={load} />
                        </div>
                    )}
                    {notice && <Message severity="warn" text={notice} className="w-full" />}
                    <SelectButton value={mode} options={MODES} onChange={(e) => switchMode(e.value)} disabled={busy} allowEmpty={false} />
                    {mode === 'form' && state ? (
                        <div ref={tabsRef}>
                        <TabView scrollable activeIndex={tab} onTabChange={(e) => setTab(e.index)}>
                            <TabPanel header={`Daemon${Object.keys(shownErrors.settings).length ? ' ⚠' : ''}`}>
                                <div className="flex flex-column gap-3">
                                    <small className="text-color-secondary">Daemon-wide settings only take effect the first time a daemon is configured.</small>
                                    <div className="flex flex-wrap gap-3">{SETTINGS.map(settingField)}</div>
                                </div>
                            </TabPanel>
                            {CATEGORIES.map(categoryPanel)}
                        </TabView>
                        </div>
                    ) : (
                        <InputTextarea
                            value={raw}
                            onChange={(e) => setRaw(e.target.value)}
                            rows={22}
                            disabled={busy}
                            className="w-full"
                            placeholder="Empty config (see cmd/eagled/defaults/new_config.toml)"
                            style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}
                        />
                    )}
                    {error && <small className="p-error" style={{ whiteSpace: 'pre-wrap' }}>{error}</small>}
                </div>
            )}
        </Dialog>
    );
}

export default ConfigureDialog;
