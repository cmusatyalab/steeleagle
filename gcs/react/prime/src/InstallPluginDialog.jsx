import React, { useState, useMemo } from 'react';
import { Dialog } from 'primereact/dialog';
import { InputText } from 'primereact/inputtext';
import { Dropdown } from 'primereact/dropdown';
import { Button } from 'primereact/button';
import { getApiUrl } from './urls.js';
import { PLUGIN_CATEGORIES, emptyInstallForm, validateInstallForm, installRequestBody } from './pluginForm.js';

// Red asterisk after a required field's label; the one optional field
// (subpath) just goes unmarked.
function RequiredMark() {
    return <span className="p-error ml-1" aria-hidden="true">*</span>;
}

// Installing runs the plugin's own install.sh on the daemon, which can take
// minutes (eagled bounds it at 5). So the request just stays open: the form
// locks and can't be dismissed while it runs, and a failure is shown inline
// (with install.sh's own output) rather than in a toast that disappears.
//
// Mount this only while it's open (the parent does) so every open starts
// from a blank form and no stale failure.
function InstallPluginDialog({ daemon, onHide, onInstalled }) {
    const [form, setForm] = useState(emptyInstallForm);
    const [busy, setBusy] = useState(false);
    const [failure, setFailure] = useState(null); // { message, detail? }

    const errors = useMemo(() => validateInstallForm(form), [form]);
    const valid = Object.keys(errors).length === 0;
    const set = (field) => (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }));

    const submit = async () => {
        if (!valid || busy) return;
        setBusy(true);
        setFailure(null);
        try {
            const response = await fetch(getApiUrl('/api/daemons/install-plugin'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(installRequestBody(daemon.address, form)),
            });
            let result;
            try {
                result = await response.json();
            } catch {
                setFailure({ message: `Server returned a non-JSON response (status ${response.status}).` });
                return;
            }
            if (!response.ok) {
                setFailure({ message: `Request rejected (HTTP ${response.status}).`, detail: JSON.stringify(result.detail ?? result, null, 2) });
            } else if (!result.reachable) {
                setFailure({ message: `${daemon.name} is unreachable.`, detail: result.error });
            } else if (!result.ok) {
                setFailure({ message: 'Install failed.', detail: result.error });
            } else {
                onInstalled(form.name.trim());
                return;
            }
        } catch (err) {
            setFailure({ message: `Request failed: ${err.message}` });
        } finally {
            setBusy(false);
        }
    };

    const field = (label, key, placeholder, required = true) => (
        <div className="flex flex-column gap-1">
            <label className="text-sm">{label}{required && <RequiredMark />}</label>
            <InputText
                value={form[key]}
                onChange={set(key)}
                onKeyDown={(e) => { if (e.key === 'Enter') submit(); }}
                placeholder={placeholder}
                disabled={busy}
                className="w-full"
                invalid={!!form[key] && !!errors[key]}
            />
            {form[key] && errors[key] && <small className="p-error">{errors[key]}</small>}
        </div>
    );

    return (
        <Dialog
            header={`Install Plugin on ${daemon.name}`}
            visible
            onHide={() => { if (!busy) onHide(); }}
            closable={!busy}
            closeOnEscape={!busy}
            style={{ width: '32rem' }}
            footer={(
                <div className="flex justify-content-end gap-2">
                    <Button label="Cancel" text size="small" onClick={onHide} disabled={busy} />
                    <Button
                        label={busy ? 'Installing...' : 'Install'}
                        icon={busy ? 'pi pi-spin pi-spinner' : 'pi pi-download'}
                        size="small"
                        onClick={submit}
                        disabled={!valid || busy}
                    />
                </div>
            )}
        >
            <div className="flex flex-column gap-3">
                {field('Name', 'name', 'e.g. parrot_anafi')}
                {field('Repository URL', 'repo', 'https://github.com/org/plugins.git')}
                {field('Ref (commit SHA, branch, or tag)', 'ref', 'e.g. main')}
                {field('Subpath', 'subpath', 'folder containing install.sh; blank = repo root', false)}
                <div className="flex flex-column gap-1">
                    <label className="text-sm">Category<RequiredMark /></label>
                    <Dropdown
                        value={form.category}
                        options={PLUGIN_CATEGORIES}
                        onChange={(e) => setForm((prev) => ({ ...prev, category: e.value }))}
                        placeholder="Select a category"
                        disabled={busy}
                        className="w-full"
                    />
                </div>
                {busy && <div className="text-color-secondary text-sm">Fetching and running install.sh on the daemon. This can take a few minutes.</div>}
                {failure && (
                    <div className="flex flex-column gap-1">
                        <span className="p-error font-bold text-sm">{failure.message}</span>
                        {failure.detail && (
                            <pre
                                className="text-xs m-0 p-2 border-round"
                                style={{ maxHeight: '14rem', overflow: 'auto', whiteSpace: 'pre-wrap', backgroundColor: 'var(--surface-ground)' }}
                            >
                                {failure.detail}
                            </pre>
                        )}
                    </div>
                )}
            </div>
        </Dialog>
    );
}

export default InstallPluginDialog;
